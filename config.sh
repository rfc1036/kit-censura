#!/bin/bash
#
# Kit Configuration File
##############################

# Lists to be processed
# Currently available options are:
# manuale - For manually added FQDN or IPv4
# aams - For AAMS Lists
# tabacchi - For ADM Lists (Tobacco and Gambling)
# agcom - For AGCOM Lists (Copyright infringment)
# cncpo - For CNCPO Lists (anti-pedophilia)
# consob - For CONSOB Lists (Trading) - Not Mandatory and BROKEN right now since they have implemented anti-bot protection.
# pscaiip - For Privacy Shield FQDN or IPv4 created by exteral tool provided by AIIP (Associazione Italiana Internet Provider)
LISTS="manuale aams tabacchi agcom consob cncpo pscaiip"

# Lists to be downloaded/updated
# You might use all lists here. To be used to keep old
# lists active but you don't want to download or update 
# new records
UPDATE_LISTS=$LISTS


########### Alerting 

# Set true to enable alerting 
ALERT_ENABLE=true
# insert NOC email to enable alerting
NOC_EMAIL=''
#NOC_EMAIL=''
# sender address
FROM_EMAIL='cncpo@connesi.it'

##################### CNCPO ########################
# CNCPO PEC IMAP SERVER
CNCPO_IMAP_SERVER='mail.pecprovider.it'

# CNCPO PEC USERNAME
CNCPO_IMAP_USER='changeme@pecprovider.it'

# CNCPO PEC PASSWORD
CNCPO_IMAP_PSWD='Shhh Dont tell anyone'

# CNCPO ARCHIVE IMAP FOLDER
CNCPO_IMAP_ARCHIVE_FOLDER='Archive'

# CNCPO SENDER 
CNCPO_MAIL_FROM='dipps012.B3L4@pecps.interno.it'

# CNCPO ATTACHMENT FILE NAME
CNCPO_FILENAME='blacklist.csv.gpg'

# CNCPO ENCRYPTED FILENAME
CNCPO_FILE_NAME_CRYPT='blacklist.crypted'

# CNCPO DECRYPTED FILENAME
CNCPO_FILE_NAME_DECRYPT='blacklist.decrypted'

# CNCPO GPG PATH
CNCPO_GPG_PATH='/usr/bin/gpg'

# CNCPO WORKING DIR
CNCPO_WORKING_DIR='cncpo'

# CNCPO DOWNLOAD DIR
CNCPO_DOWNLOAD_DIR='download'

# CNCPO SETTING TEMPLATE FILE (DO NOT CHANGE)
CNCPO_SETTINGS_TMPL='settings.yaml.template'

# IMPORT PRIVATE KEY AUTOMATICALLY AT EACH RUN?
GPG_IMPORT_KEY=true

# GPG PRIVATE KEYFILE TO BE IMPORTED
GPG_PRIVATE_KEY="gpg/private.gpg"

# GPG KEYFILE PASSWORD
GPG_KEY_PASSWORD='Shhh Dont tell anyone'

# GPG Import Args
GPG_IMPORT_ARGS="--batch --pinentry-mode loopback --passphrase $GPG_KEY_PASSWORD"

# Local File for CNCPO
FILE_cncpo='tmp/blacklist.csv'

# GPG Decrypt Args
GPG_DECRYPT_ARGS="--batch --pinentry-mode loopback --passphrase $GPG_KEY_PASSWORD"

# SEND Automatic Reply?
CNCPO_REPLY_ENABLED=true

# Reply message Subject 
CNCPO_REPLY_SUBJECT="Messaggio di avvenuta ricezione lista filtraggi CNCPO"

# Reply message Sender
CNCPO_REPLY_SENDER=$CNCPO_IMAP_USER

# Reply message Recipient
CNCPO_REPLY_DESTINATION=$CNCPO_MAIL_FROM

# Put NOC In Copy of Reply message
CNCPO_REPLY_CC=$NOC_EMAIL

# SNMP Server
CNCPO_SMTP_SERVER=$CNCPO_IMAP_SERVER

# SNMP Authentication User
CNCPO_REPLY_USERNAME=$CNCPO_IMAP_USER

# SNMP Authentication PASSWORD
CNCPO_REPLY_PASSWORD=$CNCPO_IMAP_PSWD

# Reply Message Template.
# Underscore variables (_LISTAID_ , _LISTADATE_ and _DATE_) will be replaced automatically
CNCPO_REPLY_TEMPLATE="Buongiorno,
con la presente si segnala che in data _DATE_ e' avvenuta ricezione e applicazione della lista dei siti da inibire per il CNCPO avente progressivo _LISTAID_ e identificativo _LISTADATE_.
Il messaggio e' stato generato automaticamente, pertanto vi preghiamo di segnalare qualsiasi eventuale problema o incorrettezza del presente riscontro.

Cordiali Saluti.
Acme S.p.A.
"

##################### AGCOM DDA ########################
# Local File for AGCOM DDAs
FILE_agcom='lista.agcom'

# What method for dowloading the AGCOM list? Valid options are "pec", "manual" or "website"
##
# - 'pec' for downloading the "Allegato B" from PEC (see configuration below)
# - 'manual' for manually handle the "lista.agcom" file
# - 'website' for download directly from AGCOM website (Beware that AGCOM website publish the DDAs one year behind)
#
AGCOM_METHOD='pec'

### PEC Method Configuration parameters

# WORKING DIR
AGCOM_WORKING_DIR='agcom-dda'

# DOWNLOAD DIR INSIDE AGCOM_WORKING_DIR
AGCOM_DOWNLOAD_DIR='download'

# DOWNLOAD FILE INSIDE AGCOM_WORKING_DIR
AGCOM_FILE_NAME="blacklist-agcom-dda.txt"

#TODO: CHECK IF NEEDED
AGCOM_BLACKLIST_DIR='blacklist'

# TEMPLATE FOR CONFIG FILE
AGCOM_SETTINGS_TMPL='settings.yaml.template'

# AGCOM PEC IMAP SERVER
AGCOM_IMAP_SERVER='mail.pecprovider.it'

# AGCOM PEC USERNAME
AGCOM_IMAP_USER='mailbox@mail.pecprovider.it'

# AGCOM PEC PASSWORD
AGCOM_IMAP_PSWD='Dont tell anyone'

# AGCOM IMAP FOLDER FOR ARCHIVE PROCESSED MESSAGES
AGCOM_IMAP_ARCHIVE_FOLDER='Archive-DDA'

# AGCOM PEC SENDER
# You can allow multiple sender separated by comma
AGCOM_MAIL_FROM='agcom@cert.agcom.it'

# SEND Automatic Reply?
AGCOM_REPLY_ENABLED=true

# Reply Helper for AGCOM (in AGCOM_WORKING_DIR)
AGCOM_EMAIL_SENDER='email_sender.py'

# Reply message Subject 
AGCOM_REPLY_SUBJECT="Messaggio di avvenuta ricezione DDA AGCOM"

# Reply message Sender 
AGCOM_REPLY_SENDER=$AGCOM_IMAP_USER

# Reply message Recipient
AGCOM_REPLY_DESTINATION=$AGCOM_MAIL_FROM

# Destination is PEC?
AGCOM_REPLY_IS_PEC=true

# Put Someone In Copy
AGCOM_REPLY_CC=$NOC_EMAIL

# SNMP Server
AGCOM_SMTP_SERVER=$AGCOM_IMAP_SERVER

# SNMP Authentication User
AGCOM_REPLY_USERNAME=$AGCOM_IMAP_USER

# SNMP Authentication PASSWORD
AGCOM_REPLY_PASSWORD=$AGCOM_IMAP_PSWD

# Message Template.
# Underscore variables (_LISTAID_ , _LISTADATE_ and _DATE_) will be replaced automatically
AGCOM_REPLY_TEMPLATE="Buongiorno,
con la presente si segnala che in data _DATE_ e' avvenuta ricezione e applicazione della lista dei siti da inibire.

Cordiali Saluti.
SnakeOil S.p.A.
"



##################### MANUALE ########################
# Local file for Manuale
FILE_manuale='lista.manuale'


##################### PSCAIIP ########################
# Local file for Piracy Shield Client by AAIP
PATH_pscaiip='/opt/piracy-shield-agent-main/'

# List name
FILE_pscaiip='lista.pscaiip'

# File Paths
PATH_pscaiip_fqdn='/opt/piracy-shield-agent-main/src/storage/app/fqdn/last.txt'
PATH_pscaiip_ipv4='/opt/piracy-shield-agent-main/src/storage/app/ipv4/last.txt'
PATH_pscaiip_ipv6='/opt/piracy-shield-agent-main/src/storage/app/ipv6/last.txt'

# Since the Piracy Shield's server are often overloaded
# there is a random sleep option
PSCAIIP_RANDOM_SLEEP=true

# Maximum sleep time in seconds (default 30)
PSCAIIP_MAXWAIT=30

# Send Email on PSC ERROR?
ALERT_PSCAIIP_ENABLE=true

##################### CONSOB ########################
# Local file for Consob list
FILE_consob='lista.consob'

##################### AAMS ########################
# Local file for Aams list
FILE_consob='lista.aams'

##################### TABACCHI ########################
FILE_tabacchi='lista.tabacchi'

##################### DNS SECTION ########################
# path of the file on each remote target DNS server

CONFFILE='/etc/bind/censura/named.conf'

# list of target DNS servers
SERVERS='root@ns1.example.net root@ns3.example.net root@ns5.example.net root@ns6.example.net'

# do not waste too much time trying to connect to unresponsive remote servers
RSYNC_OPTIONS='--timeout=30 -rt'

# the local file
CONF='lists/named.conf'

# local full ip list
CONF_IP='lists/ip-fullist'

# the directory on the name servers containing the zone files
CONFDIR='/etc/bind/censura'

############ External Tools

# Download Helper for agcom
AGCOM_DOWNLOAD_HELPER='download_agcom.py'

# Download Helper for consob
CONSOB_DOWNLOAD_HELPER='download_consob.py'

# Download Helper for aams
AAMS_DOWNLOAD_HELPER='download_aams.py'

# Download Helper for tabacchi
TABACCHI_DOWNLOAD_HELPER='download_tabacchi.py'

# Download Helper for CNCPO (in CNCPO_WORKING_DIR)
CNCPO_DOWNLOAD_HELPER='download_attachment.py'

# Reply Helper for CNCPO (in CNCPO_WORKING_DIR)
CNCPO_EMAIL_SENDER='email_sender.py'

############ Blackholing

# Lists to be applied for blackholing
ROUTES_LISTS='cncpo'

# Blackhole Nexthop
BLACKHOLE_NEXTHOP='192.168.254.254'

# Aggregate route?
AGGREGATE_PREFIX=true

# Aggregated prefix list path
AGGREGATE_LIST_FILE='lists/cidr-fullist'

# Tool for cidr summarization
AGGREGATION_TOOL='supernets.py'

# Maximum CIDR length (default 25)
AGGREGATION_MAXLEN=25

############ Logging

# Set true to enable logging to file
LOGGING_ENABLE=true

# Logfile path
LOGFILE='/var/log/kit-censura.log'


