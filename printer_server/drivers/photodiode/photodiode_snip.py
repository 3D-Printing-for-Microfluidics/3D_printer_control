from printer_server.extensions import socketio
from printer_server.hardware_configuration import driver_handles


photodiode = driver_handles.photodiode

@socketio.on("get_photodiode_power", namespace="/manual")
def get_photodiode_power(message):
    

    wavelength = int(message["wavelength"])
    
    # in phododiode.py set w, get p, emit p

# Set variable power and double check this works
    #end of stuff
    socketio.emit("send_photodiode_power", power, namespace="/manual", broadcast=True)