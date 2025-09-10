#!/bin/bash -x 

chmod +x download_*.py

echo Creating new empty files:

for lista in manuale consob agcom aams tabacchi pscaiip; do
	touch lista.$lista
	touch lista.$lista-ip
done


echo Creating dirs
mkdir tmp lists gpg


