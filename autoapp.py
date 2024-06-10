"""Create an application instance."""
from flask.helpers import get_debug_flag
from printer_server.app import create_app
from printer_server.settings import DevConfig, ProdConfig

CONFIG = DevConfig if get_debug_flag() else ProdConfig

app, soketio = create_app(CONFIG)

if __name__ == "__main__":
    soketio.run(app, host="0.0.0.0", port=5000)
