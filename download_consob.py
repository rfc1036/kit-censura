#!/usr/bin/env python3

import requests, optparse, re
from urlextract import URLExtract
from tldextract import extract
from collections import OrderedDict
from bs4 import BeautifulSoup

def main():
    global options

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
    urls = []
    url = "https://www.consob.it/web/area-pubblica/oscuramenti?p_p_id=com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_m9PTOY4SM1GU&_com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_m9PTOY4SM1GU_cur={}".format(curpage)
    page = requests.get(url,verify=False)
    soup = BeautifulSoup(page.content, "html.parser")
    for span in soup.findAll('span', attrs={'class':'lfr-icon-menu-text'}):
        pag=span.getText()
        totpages=int(re.search(r"[0-9]{1,2}$",pag).group(0))
    while(curpage<=totpages):
        url = "https://www.consob.it/web/area-pubblica/oscuramenti?p_p_id=com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_m9PTOY4SM1GU&_com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_m9PTOY4SM1GU_cur={}".format(curpage)
        page = requests.get(url,verify=False)
        soup = BeautifulSoup(page.content, "html.parser")
        for div in soup.findAll('div', attrs={'class':'divContent'}):
            for p in div.findAll(string=re.compile("Di seguito.*siti|riguardano i siti")):
                block = p.find_next().getText()
                extractor = URLExtract()
                for url in extractor.find_urls(block):
                    tsd, td, tsu = extract(url)
                    if tsd != "":
                        url=tsd + '.' + td + '.' + tsu
                    else:
                        url=td + '.' + tsu
                    urls.append(url)
        curpage = curpage + 1
    #print("\n".join(urls))

    with open(options.out_file,'wb') as f:
        f.write("\n".join(urls).encode())
    
if __name__ == '__main__':
    main()
