import yaml
import os
import imaplib
import email
import re

################ Reading Configuration File ###############
def read_yaml(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

################ Checking Download Folder ###############
def check_folder(path):
    if not os.path.exists(path):
        os.mkdir(path)
        print('\n[OS:] CREATE FOLDER : {} \n'.format(path))
    else:
        print('\n[OS:] FOLDER EXISTS : {} \n'.format(path))


################ IMAP SSL Establish Connection ###############
def connect(imap_config):
    try:
        print('Connect imap host ...')
        imap = imaplib.IMAP4_SSL(host=imap_config['HOST'], port=imap_config['PORT'])   
        resp_code, response = imap.login(imap_config['USERNAME'], imap_config['PASSWORD'])
        print('   [IMAPLIB:] CONNECTION OBJECT : {}'.format(imap))
        print('Operation successfull. \n')
        return imap
    
    except Exception as e:
        print("ErrorType : {}, Error : {} \n".format(type(e).__name__, e))
        resp_code, response = None, None

################ IMAP SSL Disconnect ###############
def disconnect(imap):
    try:
        
        print('\nDisconnect imap host ...')
        resp_code, response = imap.close()
        print('   [IMAPLIB:] RESPONSE CODE     : {}'.format(resp_code))
        print('   [IMAPLIB:] RESPONSE          : {}'.format(response))
        resp_code, response = imap.logout()
        print('   [IMAPLIB:] RESPONSE CODE     : {}'.format(resp_code))
        print('   [IMAPLIB:] RESPONSE          : {}'.format(response))
        print('Operation successfull. \n')

    except Exception as e:
        print("ErrorType : {}, Error : {} \n".format(type(e).__name__, e))
        resp_code, response = None, None


################ Move email processed ###############
def move_email(imap, mail_ids):
    try:

        mailbox = config['IMAP']['MAILBOX_ARCHIVE']
        print('Move mail to Mailbox {} ...'.format(mailbox))
        print('Email ids : {}'.format(mail_ids))
    
        resp_code, response = imap.copy(mail_ids, mailbox)
        print('   [IMAPLIB:] RESPONSE CODE     : {}'.format(resp_code))
        print('   [IMAPLIB:] RESPONSE          : {}'.format(response))
        
        resp_code, response = imap.store(mail_ids, '+FLAGS', '\\Deleted')
        print('   [IMAPLIB:] RESPONSE CODE     : {}'.format(resp_code))
        print('   [IMAPLIB:] RESPONSE          : {}'.format(response))
        
        resp_code, response = imap.expunge()
        print('   [IMAPLIB:] RESPONSE CODE     : {}'.format(resp_code))
        print('   [IMAPLIB:] RESPONSE          : {}'.format(response))

        print('... operation completed \n')

    except Exception as e:
        print("ErrorType : {}, Error : {} \n".format(type(e).__name__, e))
        resp_code, response = None, None


################ Download Attachment ###############
def download(imap, email_from_list, path, file_name_crypt ):
    try:
        for email_from in email_from_list:
            print('   [IMAPLIB:] READ MAIL FROM {}'.format(email_from))
            resp_code, data = imap.search(None,'FROM "{email}"'.format(email=email_from))
            print('   [IMAPLIB:] RESPONSE CODE     : {}'.format(resp_code))
            print('   [IMAPLIB:] RESPONSE          : {}'.format(data))

            for msgId in data[0].split():
                print('   [IMAPLIB:] Mail ids : {}'.format(msgId.decode()))
                resp_code, messageParts = imap.fetch(msgId, '(RFC822)')
                print('   [IMAPLIB:] RESPONSE CODE     : {}'.format(resp_code))
                emailBody = messageParts[0][1]
                raw_email_string = emailBody.decode('utf-8')
                mail = email.message_from_string(raw_email_string)

                for part in mail.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    fileName = part.get_filename()

                    if fileName and re.search(r'^Allegato B Elenco URL \d+_\d{4}_\d{2}_\d{2}.*\.txt$', fileName):
                        print("   [IMAPLIB:] BLACKLIST RETRIEVED IN DOWNLOAD: {name}".format(name=fileName))
                        filePath = os.path.join(path, file_name_crypt)
                        try:
                            with open(filePath, 'wb') as fp:
                                fp.write(part.get_payload(decode=True))
                            move_email(imap, msgId.decode())
                        except Exception as e:
                            print("ErrorType : {}, Error : {} \n".format(type(e).__name__, e))
                    else:
                        print('   [IMAPLIB:] NO BLACKLIST ATTACHED: {name}'.format(name=fileName))
    except Exception as e:
        print("ErrorType : {}, Error : {} \n".format(type(e).__name__, e))
        resp_code, response = None, None
        

############### Set configuration files ###############
config = read_yaml("./settings.yaml")
path = config['FOLDER']['DOWNLOAD_DIR']
imap_config = config['IMAP']
attachment_config = config['ATTACHMENT']
folder_config = config['FOLDER']

############## Start scrypt #################
check_folder(path)

# IMAP connection
imap = connect(imap_config)
imap.select()

# Normalizza EMAIL_FROM in lista
email_from_list = [e.strip() for e in attachment_config['EMAIL_FROM'].split(",")]

# Download blacklist and disconnect IMAP
download(
    imap, 
    email_from_list,
    path, 
    attachment_config['FILE_NAME_CRYPT']
)
disconnect(imap)



############## The end #################
