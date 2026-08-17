#!/usr/bin/env python3
"""
Scarica e normalizza la lista dei siti abusivi dall'IVASS.

Il sito pubblica un indice paginato di comunicati stampa; ogni voce è un PDF
che contiene i domini da bloccare come hyperlink e/o testo. Lo script:
  1. Recupera tutte le pagine dell'indice
  2. Raccoglie i link ai PDF dei provvedimenti (pattern ivcs*.pdf)
  3. Per ciascun PDF estrae domini via testo (pypdf + URLExtract)
     e via annotazioni ipertestuali
  4. Filtra i domini interni IVASS e normalizza con tldextract
  5. Scrive un dominio per riga nel file di output
"""

import io
import optparse
import re
import sys

import pypdf
import requests
from bs4 import BeautifulSoup
from tldextract import extract as tldext
from urlextract import URLExtract
from urllib3.exceptions import InsecureRequestWarning


HTTP_RE = re.compile(r'https?://([^\s\'"<>),;]+)', re.IGNORECASE)


def _build_tld_re():
    import tldextract.tldextract as _tld

    snap = _tld.TLDExtract()
    snap.update()
    tlds = sorted(snap.tlds, key=len, reverse=True)

    tld_pattern = '|'.join(
        re.escape(t)
        for t in tlds
        if '.' not in t
    )

    return re.compile(
        r'\b[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?'
        r'(?:\.[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?)*'
        r'\.(' + tld_pattern + r')\b',
        re.IGNORECASE
    )


DOMAIN_RE = _build_tld_re()

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

BASE_URL = "https://www.ivass.it"
INDEX_URL = BASE_URL + "/cyber/siti-abusivi/index.html"

# Timeout HTTP: (connect timeout, read timeout)
HTTP_TIMEOUT = (10, 30)

# Domini da escludere sempre (IVASS stesso, enti istituzionali, social media)
EXCLUDE_DOMAINS = {
    # Istituzionali
    "ivass.it",
    "governo.it",
    "giustizia.it",
    "example.com",
    "bancaditalia.it",
    "consob.it",
    "agcm.it",
    "agcom.it",
    "mef.gov.it",

    # Social media presenti nei footer/contatti dei PDF IVASS
    "facebook.com",
    "fb.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "threads.net",
    "whatsapp.com",
    "telegram.org",
    "t.me",
}


def get_all_pdf_urls():
    """Itera le pagine dell'indice e restituisce tutti gli URL dei PDF provvedimenti."""

    pdf_urls = []
    seen = set()
    page_num = 1

    while True:
        url = f"{INDEX_URL}?page={page_num}" if page_num > 1 else INDEX_URL

        try:
            resp = requests.get(
                url,
                verify=False,
                timeout=HTTP_TIMEOUT
            )
            resp.raise_for_status()

        except Exception as e:
            print(
                f"Warning: impossibile recuperare pagina {page_num}: {e}",
                file=sys.stderr
            )
            break

        soup = BeautifulSoup(resp.content, "html.parser")
        found_on_page = 0

        for a in soup.find_all("a", href=re.compile(r"\.pdf", re.I)):
            href = a["href"].strip()

            if href.startswith("/"):
                href = BASE_URL + href

            # Considera solo i comunicati IVASS (pattern ivcs*.pdf)
            if "ivcs" not in href.lower():
                continue

            if href not in seen:
                seen.add(href)
                pdf_urls.append(href)
                found_on_page += 1

        if found_on_page == 0:
            break

        # Passa alla pagina successiva se esiste il link
        if not soup.find(
            "a",
            href=re.compile(rf"[?&]page={page_num + 1}")
        ):
            break

        page_num += 1

    return pdf_urls


def is_valid_hostname(hostname):
    """
    Valida sintatticamente un hostname DNS.

    Regole principali:
      - lunghezza massima complessiva: 253 caratteri
      - ogni label: 1..63 caratteri
      - solo lettere, numeri e trattino
      - una label non può iniziare o terminare con '-'

    Esempio scartato:
      -parlare-prima-operatore.it
    """

    if not hostname:
        return False

    hostname = hostname.strip().lower().rstrip(".")

    if len(hostname) > 253:
        return False

    labels = hostname.split(".")

    if len(labels) < 2:
        return False

    label_re = re.compile(
        r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
        re.IGNORECASE
    )

    for label in labels:
        if not label or len(label) > 63:
            return False

        if not label_re.fullmatch(label):
            return False

    return True


def normalize_domain(raw_url):
    """
    Ricava il dominio registrato da un URL/dominio grezzo.
    Restituisce None se non è un dominio valido o va escluso.

    Compatibile con le versioni recenti di tldextract, nelle quali
    extract() restituisce un ExtractResult non iterabile.
    """

    result = tldext(raw_url)

    tsd = result.subdomain
    td = result.domain
    tsu = result.suffix

    if not td or not tsu:
        return None

    full = f"{tsd}.{td}.{tsu}" if tsd else f"{td}.{tsu}"
    full = full.lower().strip(".")

    base = f"{td}.{tsu}".lower().strip(".")

    # tldextract può estrarre componenti anche da hostname
    # sintatticamente invalidi. La validazione va fatta esplicitamente.
    if not is_valid_hostname(full):
        return None

    if base in EXCLUDE_DOMAINS or full in EXCLUDE_DOMAINS:
        return None

    # Scarta indirizzi IP, localhost e token generici
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", full):
        return None

    return full


def extract_domains_from_pdf(pdf_bytes, pdf_url=None):
    """Estrae domini da un PDF tramite testo e annotazioni ipertestuali."""

    extractor = URLExtract()
    domains = set()

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

        for page in reader.pages:

            # 1. Testo visibile
            text = page.extract_text() or ""
            candidates = set()

            for match in HTTP_RE.finditer(text):
                candidates.add(match.group(1))

            for url in extractor.find_urls(text):
                candidates.add(url)

            for match in DOMAIN_RE.finditer(text):
                candidates.add(match.group(0))

            for raw in candidates:
                d = normalize_domain(raw)

                if d:
                    domains.add(d)

            # 2. Annotazioni hyperlink (URI embedded nel PDF)
            if "/Annots" in page:
                for annot_ref in page["/Annots"]:
                    try:
                        annot = annot_ref.get_object()

                        if annot.get("/Subtype") == "/Link":
                            action = annot.get("/A")

                            if action and action.get("/S") == "/URI":
                                uri = str(action["/URI"])
                                d = normalize_domain(uri)

                                if d:
                                    domains.add(d)

                    except Exception:
                        # Una annotazione malformata non deve invalidare
                        # l'intero PDF.
                        pass

    except Exception as e:
        if pdf_url:
            print(
                f"Warning: errore nel parsing del PDF {pdf_url}: {e}",
                file=sys.stderr
            )
        else:
            print(
                f"Warning: errore nel parsing del PDF: {e}",
                file=sys.stderr
            )

    return domains


def main():
    usage = "usage: %prog -o <output_file>"

    parser = optparse.OptionParser(usage)

    parser.add_option(
        "-o",
        "--output",
        dest="out_file",
        help="File di output (un dominio per riga)"
    )

    (options, args) = parser.parse_args()

    if options.out_file is None:
        parser.error("Specificare il file di output con -o")

    all_domains = set()

    pdf_urls = get_all_pdf_urls()

    print(
        f"Trovati {len(pdf_urls)} PDF da processare",
        file=sys.stderr
    )

    total = len(pdf_urls)

    for index, pdf_url in enumerate(pdf_urls, start=1):

        print(
            f"[{index}/{total}] {pdf_url}",
            file=sys.stderr
        )

        try:
            resp = requests.get(
                pdf_url,
                verify=False,
                timeout=HTTP_TIMEOUT
            )

            resp.raise_for_status()

            domains = extract_domains_from_pdf(
                resp.content,
                pdf_url=pdf_url
            )

            all_domains.update(domains)

        except requests.exceptions.Timeout as e:
            print(
                f"Warning: timeout durante il download di {pdf_url}: {e}",
                file=sys.stderr
            )

        except requests.exceptions.RequestException as e:
            print(
                f"Warning: errore HTTP durante il download di {pdf_url}: {e}",
                file=sys.stderr
            )

        except Exception as e:
            print(
                f"Warning: impossibile processare {pdf_url}: {e}",
                file=sys.stderr
            )

    print(
        f"Domini totali estratti: {len(all_domains)}",
        file=sys.stderr
    )

    with open(options.out_file, "wb") as f:
        f.write(
            ("\n".join(sorted(all_domains)) + "\n").encode()
        )


if __name__ == "__main__":
    main()
