#!/usr/bin/env python3

import requests, optparse, sys
from urllib3.exceptions import InsecureRequestWarning
from bs4 import BeautifulSoup
from random import randint
from time import sleep
import ua_generator

# Funzione di Attesa Randomica per evitare di essere identificati come bot di Scraping
def waitRand():
    waitms = randint(100,2000)/1000
    sleep(waitms)

def main():
    global options

    # Variabili
    global provvedimento
    global lastProvvedimento
    global allegatoB

    # Aggiunte Variabili per Evitare di essere identificati come bot di Scraping
    global referer
    global user_agent

    provvedimento = ""
    lastProvvedimento = "https://www.agcom.it/provvedimenti-a-tutela-del-diritto-d-autore"
    allegatoB = "https://www.example.com"
    referer = lastProvvedimento

    # Imposto User Agent Randomico
    user_agent = ua_generator.generate(device='desktop', platform=('windows', 'macos', 'linux'), browser=('chrome', 'edge', 'firefox', 'safari')).text

    # Elaborazione argomenti della linea di comando
    usage = "usage: %prog [options] arg"
    parser = optparse.OptionParser(usage)
    parser.add_option("-o", "--output", dest="out_file", help="File di output generato")

    (options, args) = parser.parse_args()
    if len(args) == 1:
        parser.error("Numero di argomenti non corretto")
    if (options.out_file is None):
        parser.error("Numero di argomenti non corretto")

    # Disabilita i warning relativi alla mancata verifica dei certificati
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    curpage=1
    lastProvvedimento = None
    while((curpage<10) and (lastProvvedimento is None)):
        url = "https://www.agcom.it/provvedimenti-a-tutela-del-diritto-d-autore?p_p_id=listapersconform_WAR_agcomlistsportlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1&p_p_col_count=1&_listapersconform_WAR_agcomlistsportlet_numpagris=10&_listapersconform_WAR_agcomlistsportlet_curpagris={}".format(curpage)
        if(curpage > 1): waitRand()
        s = requests.Session()
        s.headers.update({'referer': referer, 'user-agent': user_agent })
        page = s.get(url, verify=False)
        referer = url
        soup = BeautifulSoup(page.content, "html.parser")
        for div in soup.findAll('div', attrs={'class':'risultato'}):
            if lastProvvedimento: break
            for p in div.findAll('p'):
                if ((p.text.lower().find("provvedimento")==-1) and (p.text.lower().find("ordine")==-1)): continue
                provvedimento = None
                for a in div.findAll('a'):
                    if (a.text.lower().find("delibera")!=-1 or a.text.lower().find("determina")!=-1):
                        provvedimento = a
                        break
                if provvedimento:
                    lastProvvedimento = "https://www.agcom.it"+provvedimento["href"]
                    #### Check Allegato ######
                    waitRand()
                    s = requests.Session()
                    s.headers.update({'referer': referer, 'user-agent': user_agent })
                    page = s.get(lastProvvedimento, allow_redirects=True, verify=False)
                    soup = BeautifulSoup(page.content, "html.parser")
                    # Controllo se ho trovato un Allegato B vedendo se la variabile inizializzata è stata modificata
                    # Solo se allegatoB è stato trovato, allora lo elaboro
                    for allegato in soup.find_all("a"):
                        if not "Allegato B" in allegato.text:continue
                        allegatoB = allegato["href"]
                        break
                    if not "www.example.com" in allegatoB:
                        waitRand()
                        s = requests.Session()
                        s.headers.update({'referer': referer, 'user-agent': user_agent })
                        response = s.get(allegatoB, allow_redirects=True, verify=False)
                        with open(options.out_file,'wb') as f:
                            f.write(response.content)
                    else:
                        lastProvvedimento = None
                    break
        curpage = curpage + 1
    if lastProvvedimento is None:
        return(False)

if __name__ == '__main__':
    main()
