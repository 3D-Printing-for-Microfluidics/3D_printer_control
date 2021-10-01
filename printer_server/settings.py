# -*- coding: utf-8 -*-
"""Application configuration."""
import os
import socket


class Config(object):
    """Base configuration."""

    SECRET_KEY = os.environ.get("PRINTER_SERVER_SECRET", "secret-key")  # TODO: Change me
    APP_DIR = os.path.abspath(os.path.dirname(__file__))  # This directory
    PROJECT_ROOT = os.path.abspath(os.path.join(APP_DIR, os.pardir))
    UPLOAD_FOLDER = os.path.abspath(os.path.join(PROJECT_ROOT, "upload"))
    PRINT_SERVER_FOLDER = os.path.abspath(os.path.join(PROJECT_ROOT, "printer_server"))
    DEBUG_TB_ENABLED = False  # Disable Debug toolbar
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    DB_NAME = "3d_printer_database.db"
    DB_PATH = os.path.join(PROJECT_ROOT, DB_NAME)
    SQLALCHEMY_DATABASE_URI = "sqlite:///{0}".format(DB_PATH)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    HOSTNAME = socket.gethostname()


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
