#!/bin/sh

# Set project root 
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/../.. && pwd )"

# Activate virtual environment 
. $PROJECT_ROOT/env/bin/activate

# Set required FLASK_APP environment variable 
export FLASK_APP=$PROJECT_ROOT/printer_server/autoapp.py

# Set display to the local display (light engine or local Xsession)
export DISPLAY=:0.0

# Run flask app 
python $FLASK_APP
