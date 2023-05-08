#!/bin/bash

source config.sh
source curl_errors.sh

# be verbose when stdout is a tty
if [ ! -t 0 ]; then
  CURL_OPTS_aams="$CURL_OPTS_aams --silent --show-error"
fi

download_aams() {
  local output=$1
  local disable_alert=$2

  local FILE_aams0='tmp/landing_page.html'
  local FILE_aams1='tmp/elenco_siti_inibiti.txt'
  local FILE_aams2='tmp/elenco_siti_inibiti.sha-256'

if [ "x$disable_alert" != "x" ]  ; then
	NOC_EMAIL=""
fi

  curl --fail --location --remote-time $CURL_OPTS_aams \
    --output $FILE_aams0.tmp $URL_aams
  CURL_RETURN=$?
  if [ $CURL_RETURN != 0 ] ; then
        SUBJECT="Error while fetching Censura lists"
        TXT="Curl on $(hostname -f) have returned $CURL_RETURN:\n\n${curl_errors[$CURL_RETURN]}\n\n when trying to get $URL_aams."
        if [ $ALERT_ENABLE == true ] && [ "x$NOC_EMAIL" != 'x' ] ; then
                echo -e "Subject: $SUBJECT\nFrom:$FROM_EMAIL\n$TXT" | sendmail $NOC_EMAIL
        fi
        echo "Warning: $TXT" >&2
  else
        test $LOGGING_ENABLE == true && echo "$(date '+%d/%m/%y %H:%m:%S') - Successfully downloaded file $URL_aams" >> $LOGFILE
  fi
  mv $FILE_aams0.tmp $FILE_aams0

  ELENCO=$(cat $FILE_aams0 | grep txt | grep -i Elenco | cut -d\" -f2) 
  CONTROLLO=$(cat $FILE_aams0 | grep txt | grep -i Controllo | cut -d\" -f2)
  BASE=$(echo $URL_aams | cut -d\/ -f-3)
  URL_aams1="$BASE$ELENCO"
  URL_aams2="$BASE$CONTROLLO"

  curl --fail --location --remote-time $CURL_OPTS_aams \
    --output $FILE_aams1.tmp $URL_aams1
  CURL_RETURN=$?
  if [ $CURL_RETURN != 0 ] ; then
        SUBJECT="Error while fetching Censura lists"
        TXT="Curl on $(hostname -f) have returned $CURL_RETURN:\n\n${curl_errors[$CURL_RETURN]}\n\n when trying to get $URL_aams1."
	if [ $ALERT_ENABLE == true ] && [ "x$NOC_EMAIL" != 'x' ] ; then
        	echo -e "Subject: $SUBJECT\nFrom:$FROM_EMAIL\n$TXT" | sendmail $NOC_EMAIL
	fi
	echo "Warning: $TXT" >&2
  else	
	test $LOGGING_ENABLE == true && echo "$(date '+%d/%m/%y %H:%m:%S') - Successfully downloaded file $URL_aams1" >> $LOGFILE	
  fi
  mv $FILE_aams1.tmp $FILE_aams1

  curl --fail --location --remote-time $CURL_OPTS_aams \
    --output $FILE_aams2.tmp $URL_aams2
  CURL_RETURN=$?
  if [ $CURL_RETURN != 0 ] ; then
        SUBJECT="Error while fetching Censura lists"
        TXT="Curl on $(hostname -f) have returned $CURL_RETURN:\n\n${curl_errors[$CURL_RETURN]}\n\n when trying to get $URL_aams2."
 	if [ $ALERT_ENABLE == true ] && [ "x$NOC_EMAIL" != 'x' ] ; then
        	echo -e "Subject: $SUBJECT\nFrom:$FROM_EMAIL\n$TXT" | sendmail $NOC_EMAIL
	fi
	echo "Warning: $TXT" >&2
  else
	test $LOGGING_ENABLE == true && echo "$(date '+%d/%m/%y %H:%m:%S') - Successfully downloaded file $URL_aams2" >> $LOGFILE

  fi
  mv $FILE_aams2.tmp $FILE_aams2


  if [ $SKIP_SHA256_CKSUM != true ] && ! echo "$(cat $FILE_aams2) $FILE_aams1" | sha256sum --check --status ; then
    TXT="Invalid SHA-256 checksum for $FILE_aams1!"
    SUBJECT="Error while fetching AAMS lists"
    test $LOGGING_ENABLE == true && echo "$(date '+%d/%m/%y %H:%m:%S') - Invalid SHA-256 checksum for $output!" >> $LOGFILE
    echo "Invalid SHA-256 checksum for $FILE_aams1!" >&2
    if [ $ALERT_ENABLE == true ] && [ "x$NOC_EMAIL" != 'x' ] ; then 
    	echo -e "Subject: $SUBJECT\nFrom:$FROM_EMAIL\n$TXT" | sendmail $NOC_EMAIL
    fi 
    exit 1
  fi

test $LOGGING_ENABLE == true && echo "$(date '+%d/%m/%y %H:%m:%S') - Parsing Started for file $output" >> $LOGFILE
./parse_aams $FILE_aams1 $output 2>&1 | tee -a $LOGFILE
if [ $? == 0 ] ; then
	test $LOGGING_ENABLE == true && echo "$(date '+%d/%m/%y %H:%m:%S') - Parsing Ended for file $output" >> $LOGFILE
else
	test $LOGGING_ENABLE == true && echo "$(date '+%d/%m/%y %H:%m:%S') - Error while Parsing $FILE_aams1" >> $LOGFILE
fi
}

