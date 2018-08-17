#!/bin/sh

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/../.. && pwd )"
. $PROJECT_ROOT/env/bin/activate
export FLASK_APP=$PROJECT_ROOT/printer_server/autoapp.py
export DISPLAY=:0.0
date >> $PROJECT_ROOT/error_report.txt 
python $FLASK_APP >> $PROJECT_ROOT/error.txt &
# python -u $FLASK_APP > >(tee -a error_report.txt) 2> >(tee -a error_report.txt >&2) & 
# python -u $FLASK_APP |& tee -a error_report.txt

