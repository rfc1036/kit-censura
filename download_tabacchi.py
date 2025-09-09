#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

LISTING_URL = "https://www.adm.gov.it/portale/siti-inibiti-tabacchi"
UA = "Mozilla/5.0 (Python urllib; ADM elenco_siti_inibiti_tabacchi.txt fetcher)"

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

def is_same_domain(url, domain="adm.gov.it"):
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
FILE_EXTS = (".txt", ".pdf", ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".csv", ".zip", ".7z")

def looks_like_file_url(u: str) -> bool:
    path = urlparse(u).path.lower()
    return any(path.endswith(ext) for ext in FILE_EXTS)

def is_txt_url(u: str) -> bool:
    path = urlparse(u).path.lower()
    if path.endswith(".txt"):
        return True
    q = parse_qs(urlparse(u).query)
    for vals in q.values():
        for v in vals:
            if ".txt" in v.lower():
                return True
    return False

# ---------------------------
# Individua direttamente elenco_siti_inibiti_tabacchi.txt
# ---------------------------
TARGET_SUBSTR = "elenco_siti_inibiti_tabacchi.txt"

def find_txt_url_on_page(listing_url, timeout=25, verbose=False):
    """
    Strategia robusta:
      1) cerca tra gli <a href=...> un URL che contenga 'elenco_siti_inibiti_tabacchi.txt'
      2) se non trovato, scansiona l'HTML grezzo per path/URL che contengono quella stringa
    Ritorna l'URL assoluto o None.
    """
    html_text, ctype, _ = http_get(listing_url, timeout=timeout, binary=False)
    if verbose:
        print(f"[INFO] Apertura pagina: {listing_url} (Content-Type: {ctype})", file=sys.stderr)

    # (1) anchor href
    for absu, txt in parse_anchors(listing_url, html_text):
        if TARGET_SUBSTR in absu.lower():
            return absu

    # (2) scan HTML grezzo – prova a ricostruire un URL plausibile
    patterns = [
        r'(?P<u>https?://[^\s"\'<>]*elenco_siti_inibiti_tabacchi\.txt(?:\?[^\s"\'<>]*)?)',
        r'(?P<u>/[^\s"\'<>]*elenco_siti_inibiti_tabacchi\.txt(?:\?[^\s"\'<>]*)?)',
        r'(?P<u>[A-Za-z0-9_\-./]*elenco_siti_inibiti_tabacchi\.txt(?:\?[^\s"\'<>]*)?)',
    ]
    for pat in patterns:
        m = re.search(pat, html_text, flags=re.I)
        if m:
            cand = m.group("u")
            return urljoin(listing_url, cand)

    return None

# ---------------------------
# Post-processing del TXT
# ---------------------------
# Righe "versione" tipo: "0000311_2024.06.06" o con "-" al posto di "_"
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
    - Normalizza: strip, minuscolo; toglie schema/percorsi; toglie '.' finale
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
        if VERSION_LINE_RE.match(s):
            continue

        s = s.lower()
        # togli "http(s)://"
        if s.startswith(("http://", "https://")):
            s = s.split("://", 1)[1]
        # tronca a prima "/" (solo dominio)
        s = s.split("/", 1)[0]
        # togli eventuale '.' finale
        if s.endswith("."):
            s = s[:-1]
        # ignora commenti
        if s.startswith("#"):
            continue

        if s and s not in seen:
            seen.add(s)
            cleaned.append(s)

    cleaned.sort()
    return "\n".join(cleaned) + ("\n" if cleaned else "")

# ---------------------------
# Download helper
# ---------------------------
def guess_filename(file_url, headers=None, default="elenco_siti_inibiti_tabacchi.txt"):
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
        description="Scarica 'elenco_siti_inibiti_tabacchi.txt' (ADM), pulisce e stampa/salva l'elenco (LF, ordinato, no duplicati)."
    )
    ap.add_argument("--start", default=LISTING_URL, help="URL della pagina (default: %(default)s)")
    ap.add_argument("-o", "--output", default=None,
                    help="Percorso di output (file o cartella). Se omesso, stampa su stdout.")
    ap.add_argument("--timeout", type=int, default=25, help="Timeout HTTP in secondi (default: %(default)s)")
    ap.add_argument("--require-txt", dest="require_txt", action="store_true",
        help="Fallisce se l'URL non è un .txt")
    ap.add_argument("-v", "--verbose", action="store_true", help="Log dettagliati su stderr")
    args = ap.parse_args()

    # 1) Individua direttamente l'URL al TXT
    txt_url = find_txt_url_on_page(args.start, timeout=args.timeout, verbose=args.verbose)
    if not txt_url:
        print("ERRORE: impossibile trovare 'elenco_siti_inibiti_tabacchi.txt' sulla pagina.", file=sys.stderr)
        sys.exit(1)

    if args.require_txt and not is_txt_url(txt_url):
        print("ERRORE: trovato un link ma non sembra .txt (usa --require-txt).", file=sys.stderr)
        sys.exit(2)

    if args.verbose:
        print(f"[OK] URL TXT: {txt_url}", file=sys.stderr)

    # 2) Scarica
    try:
        data, ctype, headers = download(txt_url, timeout=args.timeout, verbose=args.verbose)
    except Exception as e:
        print(f"ERRORE durante il download: {e}", file=sys.stderr)
        sys.exit(3)

    # 3) Normalizza e pulisci
    text = bytes_to_text_normalized(data, headers)
    result = clean_sort_dedupe_domains(text)

    # 4) Output: stdout o file
    if args.output is None:
        sys.stdout.write(result)
    else:
        out_arg = Path(args.output)
        if out_arg.exists() and out_arg.is_dir():
            fname = ensure_txt_name(guess_filename(txt_url, headers=headers, default="elenco_siti_inibiti_tabacchi.txt"))
            dest = out_arg / fname
        else:
            if str(out_arg).endswith(os.sep) or (out_arg.suffix == "" and not out_arg.exists()):
                out_arg.mkdir(parents=True, exist_ok=True)
                fname = ensure_txt_name(guess_filename(txt_url, headers=headers, default="elenco_siti_inibiti_tabacchi.txt"))
                dest = out_arg / fname
            else:
                dest = out_arg
                if dest.suffix == "":
                    dest = dest.with_suffix(".txt")

        try:
            save_text_to_path(result, dest)
            if args.verbose:
                print(f"[OK] Salvato: {dest}", file=sys.stderr)
        except Exception as e:
            print(f"ERRORE nel salvataggio su {dest}: {e}", file=sys.stderr)
            sys.exit(4)

if __name__ == "__main__":
    main()

