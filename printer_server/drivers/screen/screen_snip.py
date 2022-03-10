from email import message
import os
from printer_server.settings import Config
from printer_server.extensions import socketio
from flask import request, Blueprint, render_template

from PIL import Image

def handleUpload(request):
    if "file" in request.files:  # Check if the post request has the file part
        file = request.files["file"]  # Get the file
        light_engine = request.form["light_engine"]
        # Specify location of uploaded image and give default name
        imagePath = os.path.join(Config.UPLOAD_FOLDER, "calibration_images", f"{light_engine}.png")
        if file.filename != "" and file:  # File part of request actually has a file
            try:
                with Image.open(file) as img:  # Open file as PIL object
                    # Check imagePath format and mode
                    if img.format == "PNG" and img.mode == "L":
                        # Seek to the beginning of file (fixes bug in Werkzeug file I\O)
                        file.stream.seek(0)
                        file.save(imagePath)  # save it to the server
                        socketio.emit(
                            "calibration_image_uploaded",
                            light_engine,
                            namespace="/manual",
                            broadcast=True,
                        )
                        return ""
            except (OSError, FileNotFoundError):  # File has big issues
                pass
    socketio.emit("calibration_image_bad", light_engine, namespace="/manual", broadcast=True)
    return ""
