import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///" + os.path.join(basedir, "instance", "ecommerce_v2.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "zerocryptolife@gmail.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or (f"SmartMarket <{MAIL_USERNAME}>" if MAIL_USERNAME else None)

  
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID","")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET","")
    ADMIN_NAME = os.environ.get("ADMIN_NAME", "System Administrator")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "amizerow@gmail.com")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(basedir, "app", "static", "uploads")
    PRODUCTS_PER_PAGE = 12
