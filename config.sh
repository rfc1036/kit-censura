#!/bin/bash
#
# Kit Configuration File
##############################

# Lists to be processed
# Currently available options are: manuale aams tabacchi agcom cncpo consob
LISTS="manuale aams tabacchi agcom cncpo"

# CNCPO URL
URL_cncpo='https://212.14.145.50/'

# Local File for CNCPO
FILE_cncpo='tmp/blacklist.csv'

# Local File for AGCOM
# To be manyally updated from https://www.agcom.it/provvedimenti-a-tutela-del-diritto-d-autore
FILE_agcom='lista.agcom'

# Skip SHA256 Checks 
SKIP_SHA256_CKSUM=false

# Local file for Consob list
# To be manully updated from https://www.consob.it/web/area-pubblica/oscuramenti
# -- Not mandatory until explicit request from Consob --
FILE_consob='lista.consob'

# Local file for Manuale
FILE_manuale='lista.manuale'

# curl options
CERTS_cncpo='--cert cncpo.pem --key cncpo.key --cacert cncpo-ca.pem'

# curl options for cncpo
CURL_OPTS_cncpo="$CERTS_cncpo"

# curl options for aams
CURL_OPTS_aams=''

# path of the file on each remote target DNS server
CONFFILE='/etc/bind/censura/named.conf'

# list of target DNS servers
SERVERS='root@ns1.example.net root@ns3.example.net root@ns5.example.net root@ns6.example.net'

# do not waste too much time trying to connect to unresponsive remote servers
RSYNC_OPTIONS='--timeout=30 -rt'

# the local file
CONF='lists/named.conf'

# the directory on the name servers containing the zone files
CONFDIR='/etc/bind/censura'

############ Blackholing

# Lists to be applied for blackholing
ROUTES_LISTS='cncpo'

# Blackhole Nexthop
BLACKHOLE_NEXTHOP='192.168.254.254'


############ Logging

# Set true to enable logging to file
LOGGING_ENABLE=true

# Logfile path
LOGFILE='/var/log/kit-censura.log'


########### Alerting 

# Set true to enable alerting 
ALERT_ENABLE=true
# insert NOC email to enable alerting
NOC_EMAIL=''
# sender address
FROM_EMAIL='cncpo@connesi.it'
