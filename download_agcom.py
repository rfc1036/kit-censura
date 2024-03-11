#!/usr/bin/env python3

import requests, optparse, ssl
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Set default SSL context to use TLS 1.2
ssl_context = ssl.create_default_context()
ssl_context.set_ciphers('DEFAULT:@SECLEVEL=1')
ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

def main():
    global options
# Definisco le tre variabili sotto e le inizializzo con valori a caso
# Questo perchè se in tutta la pagina non trovo un provvedimento
# allora determina,lastDetermina e allegatoB restano non inizializzate e mandano
# in errore lo script

    global delibera
    global lastDelibera
    global allegatoB


    delibera = ""
    lastDelibera = "https://www.agcom.it/provvedimenti-a-tutela-del-diritto-d-autore"
    allegatoB = "https://www.example.com"


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
    lastDelibera = None
    while((curpage<10) and (lastDelibera is None)):        
        url = "https://www.agcom.it/provvedimenti-a-tutela-del-diritto-d-autore?p_p_id=listapersconform_WAR_agcomlistsportlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1&p_p_col_count=1&_listapersconform_WAR_agcomlistsportlet_numpagris=50&_listapersconform_WAR_agcomlistsportlet_curpagris={}".format(curpage)
        page = requests.get(url, verify=False)
        soup = BeautifulSoup(page.content, "html.parser")
        for div in soup.findAll('div', attrs={'class':'risultato'}):
            if lastDelibera: break
            for p in div.findAll('p'):
                if ((p.text.lower().find("provvedimento")==-1) and (p.text.lower().find("ordine")==-1)):continue
                    #determina = div.find(lambda tag:(tag.name=="a" and (tag.text.lower().find("determina")!=-1) or (tag.text.lower().find("delibera")!=-1)))
                delibera = div.find(lambda tag:(tag.name=="a" and tag.text.lower().find("delibera")!=-1))
                if delibera:
                    lastDelibera = "https://www.agcom.it"+delibera["href"]
                    #### Check Allegato ######
                    page = requests.get(lastDelibera, verify=False)
                    soup = BeautifulSoup(page.content, "html.parser")
                    # Controllo se ho trovato un Allegato B vedendo se la variabile inizializzata è stata modificata
                    # Solo se allegatoB è stato trovato, allora lo elaboro
                    for allegato in soup.find_all("a"):
                        if not "Allegato B" in allegato.text:continue
                        allegatoB = allegato["href"]
                        break
                    if not "www.example.com" in allegatoB:
                        response = requests.get(allegatoB, verify=False)
                        with open(options.out_file,'wb') as f:
                            f.write(response.content)
                    else:
                        lastDelibera = None
                    break
        curpage = curpage + 1
    if lastDelibera is None:
        return(False)

if __name__ == '__main__':
    main()
