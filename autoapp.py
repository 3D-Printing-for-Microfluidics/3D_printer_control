"""Create an application instance."""
from printer_server.extensions import socketio
from printer_server.app import app

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
