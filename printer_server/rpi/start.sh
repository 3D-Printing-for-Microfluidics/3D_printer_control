#!/bin/sh

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/../.. && pwd )"
. $PROJECT_ROOT/env/bin/activate
export FLASK_APP=$PROJECT_ROOT/printer_server/autoapp.py
date >> $PROJECT_ROOT/error.txt 
python $FLASK_APP >> $PROJECT_ROOT/error.txt &

