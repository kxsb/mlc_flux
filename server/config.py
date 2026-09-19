import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8001"))
    FLASK_ENV = os.getenv("FLASK_ENV", "development")

    SECRET_KEY = os.getenv("MLCFLUX_SECRET_KEY", os.getenv("SECRET_KEY", ""))

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME_SECONDS = int(
        os.getenv("PERMANENT_SESSION_LIFETIME_SECONDS", "28800")
    )

    # Routes HTTP de synchronisation désactivées tant qu'aucun token
    # d'administration n'est explicitement configuré.
    SYNC_API_TOKEN = os.getenv("SYNC_API_TOKEN", "")

    ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "")
