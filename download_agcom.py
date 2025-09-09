#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ---------------------------
# Written by IA
# ---------------------------
import sys
import re
import os
import argparse
import html
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser

LISTING_URL = "https://www.agcom.it/provvedimenti-a-tutela-del-diritto-d-autore"
UA = "Mozilla/5.0 (Python urllib; AGCOM Allegato B fetcher)"

# ---------------------------
# HTTP helpers
# ---------------------------
def http_get(url, timeout=25, binary=False):
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        if binary:
            return data, resp.headers.get_content_type(), resp.headers
        charset = resp.headers.get_content_charset() or "utf-8"
        return data.decode(charset, errors="replace"), resp.headers.get_content_type(), resp.headers

def is_same_domain(url, domain="agcom.it"):
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.endswith(domain)
    except Exception:
        return False

def content_disposition_filename(headers):
    cd = headers.get("Content-Disposition") or headers.get("content-disposition")
    if not cd:
        return None
    # filename*, RFC 5987
    m = re.search(r'filename\*\s*=\s*(?:UTF-8\'\')?([^;]+)', cd, flags=re.I)
    if m:
        return unquote_pct(m.group(1)).strip('"\' ')
    # filename=
    m = re.search(r'filename\s*=\s*"([^"]+)"', cd, flags=re.I)
    if m:
        return m.group(1)
    m = re.search(r'filename\s*=\s*([^;]+)', cd, flags=re.I)
    if m:
        return m.group(1).strip('"\' ')
    return None

def unquote_pct(s):
    try:
        from urllib.parse import unquote
        return unquote(s)
    except Exception:
        return s

# ---------------------------
# HTML parsing
# ---------------------------
class AnchorCollector(HTMLParser):
    """Raccoglie (href, text) in ordine di apparizione."""
    def __init__(self):
        super().__init__()
        self.links = []  # list[(href, text)]
        self._in_a = False
        self._href = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._in_a = True
            self._href = None
            for k, v in attrs:
                if k.lower() == "href" and v:
                    self._href = v.strip()
                    break

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._in_a:
            text = html.unescape("".join(self._buf)).strip()
            if self._href:
                self.links.append((self._href, text))
            self._in_a = False
            self._href = None
            self._buf = []

    def handle_data(self, data):
        if self._in_a and data:
            self._buf.append(data)

def parse_anchors(base_url, html_text):
    p = AnchorCollector()
    p.feed(html_text)
    out = []
    seen = set()
    for href, text in p.links:
        if not href or href.startswith("#"):
            continue
        absu = urljoin(base_url, href)
        key = (absu, text.strip())
        if key not in seen:
            out.append((absu, text.strip()))
            seen.add(key)
    return out

# ---------------------------
# Heuristics
# ---------------------------
FILE_EXTS = (".pdf", ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".csv", ".zip", ".7z", ".txt")

def looks_like_file_url(u: str) -> bool:
    path = urlparse(u).path.lower()
    return any(path.endswith(ext) for ext in FILE_EXTS)

def is_txt_url(u: str) -> bool:
    path = urlparse(u).path.lower()
    if path.endswith(".txt"):
        return True
    # a volte c'è un "download?..." con parametro che contiene .txt
    q = parse_qs(urlparse(u).query)
    for vals in q.values():
        for v in vals:
            if ".txt" in v.lower():
                return True
    return False

def text_has_allegato_b(txt: str) -> bool:
    t = (txt or "").lower()
    return "allegato b" in t

def find_download_links(page_url, html_text):
    """Restituisce TUTTI i link plausibili di download nella pagina (assoluti)."""
    cands = []
    for absu, txt in parse_anchors(page_url, html_text):
        low = (txt or "").lower()
        if looks_like_file_url(absu) or "download" in low or "scarica" in low or "allegato" in low:
            cands.append(absu)
    return cands

# ---------------------------
# Trovare l'ultimo Allegato B
# ---------------------------
def resolve_allegato_b_urls(post_url, timeout, verbose=False):
    """Ritorna (lista_txt, lista_altri_formati) per l’“Allegato B” nel post."""
    html_text, ctype, _ = http_get(post_url, timeout=timeout, binary=False)
    if verbose:
        print(f"[INFO] Apertura post: {post_url} (Content-Type: {ctype})", file=sys.stderr)

    txt_candidates = []
    any_candidates = []

    # 1) Link <a> con testo 'Allegato B'
    for absu, txt in parse_anchors(post_url, html_text):
        if not is_same_domain(absu, "agcom.it"):
            continue
        if not text_has_allegato_b(txt):
            continue

        if looks_like_file_url(absu):
            (txt_candidates if is_txt_url(absu) else any_candidates).append(absu)
            continue

        # Pagina intermedia → cerca link di download
        try:
            inner_html, inner_type, _ = http_get(absu, timeout=timeout, binary=False)
        except Exception as e:
            if verbose:
                print(f"[WARN] Impossibile aprire pagina allegato: {absu} ({e})", file=sys.stderr)
            continue

        links = find_download_links(absu, inner_html)
        for u in links:
            if is_txt_url(u):
                txt_candidates.append(u)
            else:
                any_candidates.append(u)

    # 2) Fallback
    if not txt_candidates and not any_candidates:
        for absu, txt in parse_anchors(post_url, html_text):
            if not is_same_domain(absu, "agcom.it"):
                continue
            if "download?" in absu.lower() or looks_like_file_url(absu):
                if "allegato" in (txt or "").lower() or "b" == (txt or "").strip().lower():
                    (txt_candidates if is_txt_url(absu) else any_candidates).append(absu)

    return dedupe(txt_candidates), dedupe(any_candidates)

def dedupe(seq):
    out, seen = [], set()
    for x in seq:
        if x not in seen:
            out.append(x); seen.add(x)
    return out

def pick_latest_post_with_allegato_b(listing_url, timeout, verbose=False, max_candidates=60):
    """Scandisce i link dell’elenco; restituisce il primo post che ha Allegato B."""
    listing_html, ctype, _ = http_get(listing_url, timeout=timeout, binary=False)
    if verbose:
        print(f"[INFO] Apertura listing: {listing_url} (Content-Type: {ctype})", file=sys.stderr)

    anchors = parse_anchors(listing_url, listing_html)

    checked = 0
    seen_pages = set()
    for absu, txt in anchors:
        if checked >= max_candidates:
            break
        if not absu.lower().startswith("http"):
            continue
        if not is_same_domain(absu, "agcom.it"):
            continue
        if absu in seen_pages:
            continue
        seen_pages.add(absu)

        path = urlparse(absu).path.lower()
        if any(path.endswith(ext) for ext in (".jpg",".png",".gif",".svg",".css",".js")):
            continue

        checked += 1
        if verbose:
            print(f"[INFO] Controllo post candidato {checked}: {absu}", file=sys.stderr)

        try:
            txt_c, any_c = resolve_allegato_b_urls(absu, timeout=timeout, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"[WARN] Errore su {absu}: {e}", file=sys.stderr)
            continue

        if txt_c or any_c:
            return absu, txt_c, any_c

    return None, [], []

# ---------------------------
# Post-processing del TXT
# ---------------------------
# Righe di versione tipo: "0000311_2024.06.06" o con "-" al posto di "_"
VERSION_LINE_RE = re.compile(r"^\s*\d{5,}[_-]\d{4}\.\d{2}\.\d{2}\s*$")

def bytes_to_text_normalized(data, headers):
    """
    Decodifica i bytes in testo, rimuove BOM, normalizza le EOL a Unix (LF).
    """
    charset = None
    try:
        charset = headers.get_content_charset()
    except Exception:
        pass

    if charset:
        try:
            text = data.decode(charset, errors="replace")
        except Exception:
            text = data.decode("utf-8", errors="replace")
    else:
        # utf-8-sig rimuove eventuale BOM
        try:
            text = data.decode("utf-8-sig")
        except Exception:
            text = data.decode("utf-8", errors="replace")

    # Normalizza EOL: CRLF/CR -> LF (toglie i ^M)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Rimuovi BOM residuo
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    return text

def clean_sort_dedupe_domains(text):
    """
    - Rimuove QUALSIASI riga che corrisponde al pattern versione
      (es. 0000311_2024.06.06), ovunque si trovi nel file
    - Normalizza: strip, minuscolo, toglie eventuale punto finale
    - Deduplica e ordina
    - Ritorna testo con LF finale
    """
    lines = text.split("\n")

    cleaned = []
    seen = set()
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        # scarta la riga di versione ovunque sia
        if VERSION_LINE_RE.match(s):
            continue

        s = s.lower()
        # opzionale: togli punto finale residuo
        if s.endswith("."):
            s = s[:-1]
        # ignora eventuali commenti
        if s.startswith("#"):
            continue

        if s not in seen:
            seen.add(s)
            cleaned.append(s)

    cleaned.sort()
    return "\n".join(cleaned) + ("\n" if cleaned else "")

# ---------------------------
# Download helper
# ---------------------------
def guess_filename(file_url, headers=None, default="Allegato_B.txt"):
    if headers:
        fn = content_disposition_filename(headers)
        if fn:
            return fn
    path = urlparse(file_url).path
    base = os.path.basename(path)
    return base or default

def ensure_txt_name(name):
    return name if name.lower().endswith(".txt") else (os.path.splitext(name)[0] + ".txt")

def save_text_to_path(text: str, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

def download(file_url, timeout=25, verbose=False):
    data, ctype, headers = http_get(file_url, timeout=timeout, binary=True)
    if verbose:
        clen = headers.get("Content-Length") or len(data)
        print(f"[INFO] Download: {file_url} ({ctype}, {clen} bytes)", file=sys.stderr)
    return data, ctype, headers

# ---------------------------
# CLI
# ---------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Scarica l'ultimo 'Allegato B' (TXT), pulisce e stampa/salva l'elenco (LF, ordinato, no duplicati)."
    )
    ap.add_argument("--start", default=LISTING_URL, help="URL della pagina elenco (default: %(default)s)")
    ap.add_argument("-o", "--output", default=None,
                    help="Percorso di output (file o cartella). Se omesso, stampa su stdout.")
    ap.add_argument("--timeout", type=int, default=25, help="Timeout HTTP in secondi (default: %(default)s)")
    ap.add_argument("--max-candidates", type=int, default=60, help="Numero massimo di link-candidati da esplorare (default: %(default)s)")
    ap.add_argument("--require-txt", dest="require_txt", action="store_true",
                    help="Fallisce se non trova un Allegato B in formato .txt")
    ap.add_argument("-v", "--verbose", action="store_true", help="Log dettagliati su stderr")
    args = ap.parse_args()

    # 1) Trova il post più recente con Allegato B
    post_url, txt_candidates, any_candidates = pick_latest_post_with_allegato_b(
        args.start, timeout=args.timeout, verbose=args.verbose, max_candidates=args.max_candidates
    )
    if not post_url:
        print("ERRORE: non sono riuscito a individuare un post con 'Allegato B'.", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"[OK] Post trovato: {post_url}", file=sys.stderr)
        if txt_candidates:
            print(f"[INFO] Candidati TXT trovati: {len(txt_candidates)}", file=sys.stderr)
        if any_candidates:
            print(f"[INFO] Altri candidati: {len(any_candidates)}", file=sys.stderr)

    # 2) Scegli URL finale (preferisci TXT)
    if args.require_txt and not txt_candidates:
        print("ERRORE: nessun Allegato B in formato TXT trovato.", file=sys.stderr)
        sys.exit(2)
    candidates_order = txt_candidates + any_candidates
    if not candidates_order:
        print("ERRORE: nessun link per 'Allegato B' trovato nel post.", file=sys.stderr)
        sys.exit(3)
    chosen_url = candidates_order[0]

    # 3) Scarica bytes
    try:
        data, ctype, headers = download(chosen_url, timeout=args.timeout, verbose=args.verbose)
    except Exception as e:
        print(f"ERRORE durante il download: {e}", file=sys.stderr)
        sys.exit(4)

    # 4) Decodifica/normalizza testo e pulisci elenco
    text = bytes_to_text_normalized(data, headers)
    result = clean_sort_dedupe_domains(text)

    # 5) Output: stdout (se -o omesso) oppure salva su file
    if args.output is None:
        # stampa contenuto del file risultante
        sys.stdout.write(result)
    else:
        out_arg = Path(args.output)
        if out_arg.exists() and out_arg.is_dir():
            fname = ensure_txt_name(guess_filename(chosen_url, headers=headers, default="Allegato_B.txt"))
            dest = out_arg / fname
        else:
            if str(out_arg).endswith(os.sep) or (out_arg.suffix == "" and not out_arg.exists()):
                out_arg.mkdir(parents=True, exist_ok=True)
                fname = ensure_txt_name(guess_filename(chosen_url, headers=headers, default="Allegato_B.txt"))
                dest = out_arg / fname
            else:
                dest = out_arg
                # forza .txt se il path è senza estensione
                if dest.suffix == "":
                    dest = dest.with_suffix(".txt")

        try:
            save_text_to_path(result, dest)
            if args.verbose:
                print(f"[OK] Salvato: {dest}", file=sys.stderr)
        except Exception as e:
            print(f"ERRORE nel salvataggio su {dest}: {e}", file=sys.stderr)
            sys.exit(5)

if __name__ == "__main__":
    main()
