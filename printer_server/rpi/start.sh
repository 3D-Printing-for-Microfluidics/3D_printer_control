#!/bin/sh

# Set project root 
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/../.. && pwd )"
# Actuvate virtual environment 
. $PROJECT_ROOT/env/bin/activate
# Set required FLASK_APP environment variable 
export FLASK_APP=$PROJECT_ROOT/printer_server/autoapp.py
# Set display to the local display (light engine or local Xsession)
export DISPLAY=:0.0
# Save timestamp to error log 
date >> $PROJECT_ROOT/error_report.txt 
# Redirect output to error log 
python $FLASK_APP >> $PROJECT_ROOT/error.txt &

# Some experimental stuff for better error reporting and logging 
# python -u $FLASK_APP > >(tee -a error_report.txt) 2> >(tee -a error_report.txt >&2) & 
# python -u $FLASK_APP |& tee -a error_report.txt

