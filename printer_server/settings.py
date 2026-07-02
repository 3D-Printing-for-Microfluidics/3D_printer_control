"""Application configuration."""
import os
import socket
import hashlib
from dotenv import load_dotenv


load_dotenv()

class Config:
    """Base configuration."""

    PROFILE_CODE = False
    LOG_THREADING = False
    ADMIN_PWD = os.getenv("PRINTER_SERVER_ADMIN_PASSWORD", "admin")
    hash_object = hashlib.sha256(ADMIN_PWD.encode('utf-8'))
    SECRET_KEY = hash_object.hexdigest()

    APP_DIR = os.path.abspath(os.path.dirname(__file__))  # This directory
    PROJECT_ROOT = os.path.abspath(os.path.join(APP_DIR, os.pardir))
    UPLOAD_FOLDER = os.path.abspath(os.path.join(PROJECT_ROOT, "upload"))
    PROFILES_FOLDER = os.path.abspath(os.path.join(PROJECT_ROOT, "profiles"))
    PRINT_SERVER_FOLDER = os.path.abspath(os.path.join(PROJECT_ROOT, "printer_server"))

    DEBUG_TB_ENABLED = False  # Disable Debug toolbar
    DEBUG_TB_INTERCEPT_REDIRECTS = False

    DB_NAME = "3d_printer_database.db"
    DB_PATH = os.path.join(PROJECT_ROOT, DB_NAME)
    SQLALCHEMY_DATABASE_URI = "sqlite:///{0}".format(DB_PATH)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    HOSTNAME = socket.gethostname()

    OPEN_ACCESS = os.getenv("PRINTER_SERVER_OPEN_ACCESS", "false").lower() == "true"
    OPEN_REGISTRATION = os.getenv("PRINTER_SERVER_OPEN_REGISTRATION", "false").lower() == "true"
    SESSION_EXPIRATION_MINUTES = int(os.getenv("PRINTER_SERVER_SESSION_EXPIRATION_MINUTES", "60"))
    LOGIN_EXPIRATION_MINUTES = int(os.getenv("PRINTER_SERVER_LOGIN_EXPIRATION_MINUTES", "10"))
    SMTP_SERVER = os.getenv("PRINTER_SERVER_SMTP_SERVER", "localhost")
    SMTP_PORT = int(os.getenv("PRINTER_SERVER_SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("PRINTER_SERVER_SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("PRINTER_SERVER_SMTP_PASSWORD", "")

    NEW_USER_PRINT_PERMISSION = os.getenv("PRINTER_SERVER_NEW_USER_PRINT_PERMISSION", "true").lower() == "true"
    NEW_USER_CALIBRATION_PERMISSION = os.getenv("PRINTER_SERVER_NEW_USER_CALIBRATION_PERMISSION", "false").lower() == "true"
    NEW_USER_ADVANCED_PERMISSION = os.getenv("PRINTER_SERVER_NEW_USER_ADVANCED_PERMISSION", "false").lower() == "true"
    NEW_USER_ADMIN_PERMISSION = os.getenv("PRINTER_SERVER_NEW_USER_ADMIN_PERMISSION", "false").lower() == "true"

class ProdConfig(Config):
    """Production configuration."""

    ENV = "prod"
    DEBUG = False
    DEBUG_TB_ENABLED = False  # Disable Debug toolbar


class DevConfig(Config):
    """Development configuration."""

    ENV = "dev"
    DEBUG = True
    DEBUG_TB_ENABLED = True
    CACHE_TYPE = "simple"  # Can be "memcached", "redis", etc.


class TestConfig(Config):
    """Test configuration."""

    TESTING = True
    DEBUG = True
    DB_PATH = os.path.join(Config.PROJECT_ROOT, "test.db")
    SQLALCHEMY_DATABASE_URI = "sqlite:///{0}".format(DB_PATH)
    BCRYPT_LOG_ROUNDS = (
        4  # For faster tests; needs at least 4 to avoid "ValueError: Invalid rounds"
    )
    WTF_CSRF_ENABLED = False  # Allows form testing
