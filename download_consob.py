#!/usr/bin/env python3

import urllib3
import requests, optparse, re
from urlextract import URLExtract
from tldextract import extract
from collections import OrderedDict
from bs4 import BeautifulSoup
from bs4.element import Tag
from bs4.element import NavigableString
from random import randint
from time import sleep
import ua_generator

# Funzione di Attesa Randomica per evitare di essere identificati come bot di Scraping
def waitRand():
    waitms = randint(500,2000)/1000
    sleep(waitms)

def main():
    global options

    # Imposta le variabili per il WAF
    referer = "https://www.consob.it/web/area-pubblica/occhio-alle-truffe"
    user_agent = ua_generator.generate(device='desktop', platform=('windows', 'macos', 'linux'), browser=('chrome', 'edge', 'firefox', 'safari')).text
    accept_language = "it-IT,it;"
    accept = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    cookies = None

    # Sopprime i warning relativi a richieste HTTPS non sicure
    urllib3.disable_warnings()

    # Elaborazione argomenti della linea di comando
    usage = "usage: %prog [options] arg"
    parser = optparse.OptionParser(usage)
    parser.add_option("-o", "--output", dest="out_file", help="File di output generato")

    (options, args) = parser.parse_args()
    if len(args) == 1:
        parser.error("Numero di argomenti non corretto")
    if (options.out_file is None):
        parser.error("Numero di argomenti non corretto")

    curpage=1
    totpages=0
    urls = []
    while(curpage<=totpages or totpages==0):
        url = "https://www.consob.it/web/area-pubblica/oscuramenti?p_p_id=com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_m9PTOY4SM1GU&_com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_m9PTOY4SM1GU_cur={}".format(curpage)
        if(curpage > 1): waitRand()
        s = requests.Session()
        s.headers.update({'Referer': referer, 'User-Agent': user_agent, 'Accept-Language': accept_language, 'Accept': accept, 'Upgrade-Insecure-Requests': '1' })
        page = s.get(url, cookies=cookies, verify=False)
        cookies = page.cookies
        referer = url
        if((str(page.content)).find("you are a bot")!=-1):
            print("WAF detected BOT, sorry!")
            return(False)
        soup = BeautifulSoup(page.content, "html.parser")
        # Recupera il numero di pagine totali se non recuperato ancora
        if(totpages==0):
            for span in soup.findAll('span', attrs={'class':'lfr-icon-menu-text'}):
                pag=span.get_text()
                totpages=int(re.search(r"[0-9]{1,2}$",pag).group(0))
                # Esce se non ha trovato il numero di pagine
                if(totpages==0):
                    print("Non posso determinare il numero di pagine della lista")
                    return(False)
        # Ricerca il contenuto
        for div in soup.find_all('div', attrs={'class':'divContent'}):
            for comunicato in div.find_all('h4'):
                block = comunicato.find_next('div')
                if(not block):
                   continue
                content = str(block.get_text().encode("ascii", "ignore"))
                extractor = URLExtract()
                for url in extractor.find_urls(content):
                    ext = extract(url)
                    if ext.domain == "consob" and ext.suffix == "it": continue
                    if ext.domain == "europa" and ext.suffix == "eu": continue
                    url = (ext.subdomain+"."+ext.domain+"."+ext.suffix) if ext.subdomain != "" else (ext.domain+"."+ext.suffix)
                    urls.append(url)
        curpage = curpage + 1

    # Scrive la lista
    with open(options.out_file,'wb') as f:
        f.write("\n".join(urls).encode())

if __name__ == '__main__':
    main()

