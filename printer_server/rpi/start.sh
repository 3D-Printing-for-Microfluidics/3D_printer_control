#!/bin/sh

ROOT="/home/pi/Developer/Python/3D_printer_control"
. $ROOT/env/bin/activate
export FLASK_APP=$ROOT/printer_server/autoapp.py
export FLASK_DEBUG=1
flask run --host=0.0.0.0 --port=5000 &