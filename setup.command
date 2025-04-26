#!/bin/sh

cd `dirname $0`

if [ ! -d venv ]; then
  echo Initialising database
  createdb track-db
  psql track-db -c "\i ./db-init.sql"

  echo Creating Python virtual environment
  python -m venv venv

  echo Installing dependencies
  pip install -r requirements.txt
fi

exit 0