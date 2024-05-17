#!/bin/bash -x 

echo Downloading external tools

# use local copy
#wget "https://github.com/mphilosopher/censura/raw/master/src/download_agcom.py" -O download_agcom.py
#chmod +x download_agcom.py
#
#wget "https://github.com/mphilosopher/censura/raw/master/src/download_consob.py" -O download_consob.py
#chmod +x download_consob.py

echo Creating new empty files:

touch lista.manuale
touch lista.manuale-ip


echo Creating dirs
mkdir tmp lists gpg


