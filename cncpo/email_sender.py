#! /usr/bin/python

import yaml
import sys
import os
import re
from smtplib import SMTP_SSL as SMTP	
	
from email.mime.text import MIMEText

# READ DATA FROM STDIN
content = sys.stdin.readlines();
# typical values for text_subtype are plain, html, xml
text_subtype = 'plain'

def read_yaml(file_path):
	with open(file_path, "r") as f:
		return yaml.safe_load(f)

############### Set configuration files ###############
conf = read_yaml("./settings.yaml")
config = conf['REPLY']

#try:
msg = MIMEText('\n'.join(content), text_subtype)
msg['Subject']= config['REPLY_SUBJECT']
msg['From']   = config['REPLY_SENDER'] 
msg['To'] = config['REPLY_DESTINATION'] + ',' + config['REPLY_CC']
dest = [ config['REPLY_DESTINATION'] ,  config['REPLY_CC'] ]

conn = SMTP(config['SMTP_SERVER'])
conn.set_debuglevel(False)
conn.ehlo()
conn.login(config['REPLY_USERNAME'], config['REPLY_PASSWORD'])
try:
	conn.sendmail(config['REPLY_SENDER'], dest , msg.as_string())
finally:
	conn.quit()
sys.exit(0)

#except:
#	sys.exit( "mail failed; %s" % "CUSTOM_ERROR" )
