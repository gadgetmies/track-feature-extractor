#!/bin/sh

cd `dirname $0`

./setup.command

while [ -z ${folder} ]; do
  read -p "Enter folder to analyse: " folder
done

echo Starting analysis on ${folder}...

python main.py -m multi -r true ${folder}

echo Analysis done. You can now start prompting the database using the \"prompt.command\" script.

exit 0