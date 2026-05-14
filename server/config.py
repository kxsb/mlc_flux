import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8001"))
    FLASK_ENV = os.getenv("FLASK_ENV", "development")

    CYCLOS_BASE_URL = os.getenv("CYCLOS_BASE_URL", "")
    CYCLOS_USERNAME = os.getenv("CYCLOS_USERNAME", "")
    CYCLOS_PASSWORD = os.getenv("CYCLOS_PASSWORD", "")

    # Routes HTTP de synchronisation désactivées tant qu'aucun token
    # d'administration n'est explicitement configuré.
    SYNC_API_TOKEN = os.getenv("SYNC_API_TOKEN", "")
