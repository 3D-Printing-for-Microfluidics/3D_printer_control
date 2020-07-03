#!/bin/sh

# Set project root
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. && pwd )"

# Activate virtual environment
. $PROJECT_ROOT/env/bin/activate

# Open printer server folder
cd $PROJECT_ROOT/printer_server

# Remove old database if it exists
[ -e migrations ] && echo "Moving old migrations to migrations.bak" && mv migrations migrations.bak
[ -e dev.db ] && echo "Moving old db to dev.db.bak" && mv dev.db dev.db.bak

# # Set flask app pointer
export FLASK_APP=autoapp.py

# Create new database
flask db init
flask db migrate
flask db upgrade

# Go back to original folder
cd $PROJECT_ROOT
