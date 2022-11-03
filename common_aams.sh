CURL_OPTS_aams=''
# insert NOC email to enable alerting
NOC_EMAIL=''
FROM_EMAIL='alerting@connesi.it'

source curl_errors.sh

# be verbose when stdout is a tty
if [ ! -t 0 ]; then
  CURL_OPTS_aams="$CURL_OPTS_aams --silent --show-error"
fi

download_aams() {
  local output=$1

  local FILE_aams1='tmp/elenco_siti_inibiti.txt'
  local FILE_aams2='tmp/elenco_siti_inibiti.sha-256'

  curl --fail --location --remote-time $CURL_OPTS_aams \
    --output $FILE_aams1.tmp $URL_aams1
  CURL_RETURN=$?
  if [ $CURL_RETURN != 0 ] ; then
        SUBJECT="Error while fetching Censura lists"
        TXT="Curl on $(hostname -f) have returned $CURL_RETURN:\n\n${curl_errors[$CURL_RETURN]}\n\n when trying to get $URL_aams1."
	if [ "x$NOC_EMAIL" != 'x' ] ; then
        	echo -e "Subject: $SUBJECT\nFrom:$FROM_EMAIL\n$TXT" | sendmail $NOC_EMAIL
	fi
	echo "Warning: $TXT" >&2

  fi
  mv $FILE_aams1.tmp $FILE_aams1

  curl --fail --location --remote-time $CURL_OPTS_aams \
    --output $FILE_aams2.tmp $URL_aams2
  CURL_RETURN=$?
  if [ $CURL_RETURN != 0 ] ; then
        SUBJECT="Error while fetching Censura lists"
        TXT="Curl on $(hostname -f) have returned $CURL_RETURN:\n\n${curl_errors[$CURL_RETURN]}\n\n when trying to get $URL_aams2."
 	if [ "x$NOC_EMAIL" != 'x' ] ; then
        	echo -e "Subject: $SUBJECT\nFrom:$FROM_EMAIL\n$TXT" | sendmail $NOC_EMAIL
	fi
	echo "Warning: $TXT" >&2

  fi
  mv $FILE_aams2.tmp $FILE_aams2

  if ! echo "$(cat $FILE_aams2) $FILE_aams1" | sha256sum --check --status; then
    TXT="Invalid SHA-256 checksum for $FILE_aams1!"
    SUBJECT="Error while fetching AAMS lists"
    echo "Invalid SHA-256 checksum for $FILE_aams1!" >&2
    if [ "x$NOC_EMAIL" != 'x' ] ; then 
    	echo -e "Subject: $SUBJECT\nFrom:$FROM_EMAIL\n$TXT" | sendmail $NOC_EMAIL
    fi 
    exit 1
  fi

  ./parse_aams $FILE_aams1 $output
}

