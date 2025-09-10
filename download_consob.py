#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
import time
import argparse
import html
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse
from urllib.error import URLError, HTTPError

START_URL_DEFAULT = "https://www.consob.it/web/area-pubblica/oscuramenti"

# -----------------------------
# HTTP fetch (stdlib)
# -----------------------------
def fetch(url, timeout=20, retries=2, ua=None):
    last = None
    for _ in range(retries + 1):
        try:
            req = Request(url, headers={
                "User-Agent": ua or "Mozilla/5.0 (Python urllib; Consob Oscuramenti scraper)"
            })
            with urlopen(req, timeout=timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        except Exception as e:
            last = e
            time.sleep(0.6)
    raise last

# -----------------------------
# HTML parser minimale
# -----------------------------
class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []   # (href, text)
        self.texts = []   # blocchi di testo
        self._a_href = None
        self._a_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = None
            for k, v in attrs:
                if k.lower() == "href" and v:
                    href = v.strip()
                    break
            self._a_href = href

    def handle_endtag(self, tag):
        if tag.lower() == "a":
            txt = "".join(self._a_text).strip()
            if self._a_href:
                self.links.append((self._a_href, txt))
            self._a_href = None
            self._a_text = []

    def handle_data(self, data):
        if not data:
            return
        s = data.strip()
        if not s:
            return
        s = html.unescape(s)
        self.texts.append(s)
        if self._a_href is not None:
            self._a_text.append(s)

# -----------------------------
# Regex / util
# -----------------------------
# URL completi o domini "in chiaro" (es. example.com)
URL_OR_DOMAIN = re.compile(
    r"\bhttps?://[^\s<>()\"']+|\b[a-z0-9.-]+\.[a-z]{2,}\b",
    re.IGNORECASE
)

# Frasi che introducono l’elenco di oscuramenti
TRIGGER = re.compile(
    r"(ha\s+(?:ordinato|disposto)\s+l[’']oscuramento|l[’']oscuramento\s+dell[’']accesso)",
    re.IGNORECASE
)

def normalize_abs(base_url, href):
    if not href or href.startswith("#"):
        return None
    return urljoin(base_url, href)

def extract_domain_from_url(u: str):
    """Restituisce solo il dominio (netloc) da URL completi o stringhe tipo 'example.com'."""
    if not u:
        return None
    s = u.strip().strip(").,;:!?]'\"")
    if not s:
        return None

    if s.lower().startswith(("http://", "https://")):
        p = urlparse(s)
        host = p.netloc
    else:
        # forza uno schema per il parse
        p = urlparse("http://" + s)
        host = p.netloc

    host = host.strip().lower()
    host = host.split(":")[0]            # rimuove eventuale porta
    if host.startswith("www."):
        host = host[4:]                  # normalizza www.
    if not host or "." not in host:
        return None
    return host

def is_consob_domain(domain: str):
    return domain.endswith("consob.it")

def looks_like_next(text):
    t = (text or "").strip().lower()
    return any(k in t for k in ("successiva", "pagina successiva", "avanti", "next", "›", "»"))

def find_next_link(base_url, html_text):
    # rel="next"
    m = re.search(r'<a[^>]+rel=["\']?next["\']?[^>]*href=["\']([^"\']+)["\']', html_text, re.I)
    if m:
        return urljoin(base_url, m.group(1))

    # fallback: ancora con testo
    p = LinkCollector()
    p.feed(html_text)
    for href, txt in p.links:
        if looks_like_next(txt):
            u = normalize_abs(base_url, href)
            if u:
                return u

    # euristica Liferay: parametro _cur=
    cands = []
    for href, _ in p.links:
        if href and "_cur=" in href:
            cands.append(urljoin(base_url, href))
    if cands:
        best, best_n = None, -1
        for u in cands:
            mm = re.search(r"[?&]_.*?_cur=(\d+)", u)
            if mm:
                n = int(mm.group(1))
                if n > best_n:
                    best, best_n = u, n
        if best:
            return best
    return None

def extract_article_links(listing_url, html_text):
    """Da una pagina indice ricava link ai comunicati (pagine consob, no PDF)."""
    p = LinkCollector()
    p.feed(html_text)
    urls = set()
    for href, _ in p.links:
        u = normalize_abs(listing_url, href)
        if not u:
            continue
        if ".pdf" in u.lower():
            continue
        if u.lower().startswith("http"):
            if "consob.it" in urlparse(u).netloc.lower():
                urls.add(u)
    return sorted(urls)

# -----------------------------
# Estrazione "strict" solo oscuramenti
# -----------------------------
def _extract_from_lists_near_triggers(html_text):
    domains = set()
    for m in re.finditer(r"<(ul|ol)[^>]*>(.*?)</\1>", html_text, flags=re.I | re.S):
        start = m.start()
        pre = html_text[max(0, start-800):start]
        if not TRIGGER.search(pre):
            continue
        block = m.group(2)
        for mm in URL_OR_DOMAIN.finditer(block):
            dom = extract_domain_from_url(mm.group(0))
            if dom and not is_consob_domain(dom):
                domains.add(dom)
    return domains

def _extract_from_trigger_paragraphs(html_text):
    domains = set()
    for m in TRIGGER.finditer(html_text):
        seg = html_text[m.end(): m.end()+1500]
        for mm in URL_OR_DOMAIN.finditer(seg):
            dom = extract_domain_from_url(mm.group(0))
            if dom and not is_consob_domain(dom):
                domains.add(dom)
    return domains

def _extract_from_li_heuristic(html_text):
    domains = set()
    for m in re.finditer(r"<li[^>]*>(.*?)</li>", html_text, flags=re.I | re.S):
        pre = html_text[max(0, m.start()-600):m.start()].lower()
        if "oscurament" not in pre:
            continue
        li_html = m.group(1)
        for mm in URL_OR_DOMAIN.finditer(li_html):
            dom = extract_domain_from_url(mm.group(0))
            if dom and not is_consob_domain(dom):
                domains.add(dom)
    return domains

def extract_blocked_domains_only(article_url, html_text):
    """Estrae SOLO i domini effettivamente 'oscurati' dal comunicato."""
    compact = re.sub(r"\s+", " ", html_text)
    d1 = _extract_from_lists_near_triggers(compact)
    if d1:
        return d1
    d2 = _extract_from_trigger_paragraphs(compact)
    if d2:
        return d2
    return _extract_from_li_heuristic(compact)

# -----------------------------
# Post-process: elimina i sottodomini se c'è anche il dominio base
# -----------------------------
def filter_subdomains(domains):
    """
    Mantiene solo i domini che NON sono sottodomini di un altro dominio presente.
    Esempio: se ci sono 'pippo.pluto.it' e 'pluto.it' → resta solo 'pluto.it'.
    Se c’è solo 'pippo.pluto.it' → resta quello.
    """
    s = set(domains)
    keep = set()
    for d in s:
        is_sub = any((d != e and d.endswith("." + e)) for e in s)
        if not is_sub:
            keep.add(d)
    return keep

# -----------------------------
# Crawler principale
# -----------------------------
def crawl(start_url, delay=0.6, max_pages=0, timeout=20, verbose=False):
    seen_listing = set()
    seen_article = set()
    global_domains = set()

    queue = [start_url]
    pages_done = 0

    while queue:
        listing_url = queue.pop(0)
        if listing_url in seen_listing:
            continue
        seen_listing.add(listing_url)

        try:
            html_text = fetch(listing_url, timeout=timeout)
        except Exception as e:
            if verbose:
                print(f"[WARN] listing fallita {listing_url}: {e}", file=sys.stderr)
            continue

        pages_done += 1
        if verbose:
            print(f"[INFO] Listing {pages_done}: {listing_url}", file=sys.stderr)

        # link ai comunicati
        article_links = extract_article_links(listing_url, html_text)
        article_links = [u for u in article_links if "/web/" in urlparse(u).path]

        for aurl in article_links:
            if aurl in seen_article:
                continue
            seen_article.add(aurl)
            try:
                page = fetch(aurl, timeout=timeout)
            except Exception as e:
                if verbose:
                    print(f"[WARN] articolo fallito {aurl}: {e}", file=sys.stderr)
                continue

            domains = extract_blocked_domains_only(aurl, page)
            if verbose:
                print(f"[INFO] {aurl} → {len(domains)} domini (oscuramenti)", file=sys.stderr)

            for d in domains:
                global_domains.add(d)

            time.sleep(delay)

        next_url = find_next_link(listing_url, html_text)
        if next_url and next_url not in seen_listing:
            queue.append(next_url)
            if verbose:
                print(f"[INFO] Prossima pagina: {next_url}", file=sys.stderr)

        if max_pages and pages_done >= max_pages:
            break

        time.sleep(delay)

    return global_domains

# -----------------------------
# CLI
# -----------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Estrai SOLO i domini dei siti oscurati dalla pagina CONSOB 'Oscuramenti' (uno per riga) e rimuovi i sottodomini se è presente il dominio base."
    )
    ap.add_argument("--start", default=START_URL_DEFAULT,
                    help="URL di partenza (default: %(default)s)")
    ap.add_argument("--delay", type=float, default=0.6,
                    help="Pausa tra richieste (s) (default: %(default)s)")
    ap.add_argument("--max-pages", type=int, default=0,
                    help="Limita il numero di pagine archivio (0 = tutte)")
    ap.add_argument("--timeout", type=int, default=20,
                    help="Timeout HTTP (s) (default: %(default)s)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="Log di avanzamento su stderr")
    ap.add_argument("-o", "--output", default="-",
                    help="File di output (default: stdout)")

    args = ap.parse_args()

    # 1) raccogli tutti i domini (strict)
    all_domains = crawl(args.start, delay=args.delay, max_pages=args.max_pages,
                        timeout=args.timeout, verbose=args.verbose)

    # 2) rimuovi sottodomini se esiste il dominio base
    collapsed = filter_subdomains(all_domains)

    # 3) scrivi output (uno per riga)
    if args.output == "-":
        out = sys.stdout
        need_close = False
    else:
        out = open(args.output, "w", encoding="utf-8", newline="\n")
        need_close = True

    try:
        for d in sorted(collapsed):
            print(d, file=out)
    finally:
        if need_close:
            out.close()

if __name__ == "__main__":
    main()

