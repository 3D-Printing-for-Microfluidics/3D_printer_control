#!/bin/sh

# This script should be run from inside the main 3D_printer_control directory

# Set project root
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. && pwd )"

# Activate virtual environment
. $PROJECT_ROOT/env/bin/activate

# Open printer server folder
# cd $PROJECT_ROOT/printer_server
# cd $PROJECT_ROOT

# # Set flask app pointer
export FLASK_APP=autoapp.py

# Create new database
flask db migrate
flask db upgrade
flask seed-db

# Go back to original folder
# cd $PROJECT_ROOT
