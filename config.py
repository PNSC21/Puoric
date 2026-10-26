import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or os.urandom(32)
    ADMIN_SIGNUP_KEY = os.getenv("ADMIN_SIGNUP_KEY")
    UPI_PAYEE_ID = os.getenv("UPI_PAYEE_ID", "").strip()
    UPI_PAYEE_NAME = os.getenv("UPI_PAYEE_NAME", "Puoric").strip()
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