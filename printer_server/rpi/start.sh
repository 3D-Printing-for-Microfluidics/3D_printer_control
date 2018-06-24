#!/bin/sh

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/../.. && pwd )"
. $PROJECT_ROOT/env/bin/activate
export FLASK_APP=$PROJECT_ROOT/printer_server/autoapp.py
export FLASK_DEBUG=1
flask run --host=0.0.0.0 --port=5000 &