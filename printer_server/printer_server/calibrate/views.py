# -*- coding: utf-8 -*-
"""Control view."""
from flask import Blueprint, render_template

from printer_server.hardware import printer3d
from printer_server.threads import calibrationThreads
from printer_server.extensions import socketio

# Create bluprint 
blueprint = Blueprint('calibrate', __name__, url_prefix='/', static_folder='../static')

# Decorator to handle navigation to calibration page 
@blueprint.route('/calibrate')
def index():
    return render_template('calibrate.html')

# If hardware isn't initialized, initialize it 
@socketio.on('initialize', namespace='/calibrate')
def initialize():
    if printer3d.state is 'uninitialized':
        calibrationThreads.initialize()
    else: 
        socketio.emit('initialized', namespace='/calibrate', broadcast=True)
        
@socketio.on('solus_go_to_top', namespace='/calibrate')
def solus_go_to_top():
    calibrationThreads.goToZmax()

@socketio.on('solus_go_to_bottom', namespace='/calibrate')
def solus_go_to_bottom():
    calibrationThreads.goToZmin()

@socketio.on('calibration_motor', namespace='/calibrate')
def calibration_motor_move(message):
    calibrationThreads.calibration_motor_move(message["axis"],message["steps"])
