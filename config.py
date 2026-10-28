import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or os.urandom(32)
    ADMIN_SIGNUP_KEY = os.getenv("ADMIN_SIGNUP_KEY")
    UPI_PAYEE_ID = os.getenv("UPI_PAYEE_ID", "").strip()
    UPI_PAYEE_NAME = os.getenv("UPI_PAYEE_NAME", "Puoric").strip()
    STORE_EMAIL = os.getenv("STORE_EMAIL", "").strip()
    STORE_PHONE = os.getenv("STORE_PHONE", "").strip()
    STORE_WHATSAPP_NUMBER = os.getenv("STORE_WHATSAPP_NUMBER", "").strip()
    STORE_ADDRESS = os.getenv("STORE_ADDRESS", "").strip()
    STORE_INSTAGRAM_URL = os.getenv("STORE_INSTAGRAM_URL", "").strip()
    STORE_FACEBOOK_URL = os.getenv("STORE_FACEBOOK_URL", "").strip()
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'puoric.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "").lower() in {
        "1", "true", "yes"
    }
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in {"1", "true", "yes"}