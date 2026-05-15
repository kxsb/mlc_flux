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

    # Accès externe à Odoo via JSON-RPC.
    # ODOO_JSONRPC_URL peut être fourni explicitement ; sinon il est
    # déduit de ODOO_BASE_URL.
    ODOO_BASE_URL = os.getenv("ODOO_BASE_URL", "").rstrip("/")
    ODOO_JSONRPC_URL = os.getenv(
        "ODOO_JSONRPC_URL",
        f"{ODOO_BASE_URL}/jsonrpc" if ODOO_BASE_URL else "",
    )
    ODOO_DB = os.getenv("ODOO_DB", "")
    ODOO_LOGIN = os.getenv("ODOO_LOGIN", "")
    ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "")

    # Routes HTTP de synchronisation désactivées tant qu'aucun token
    # d'administration n'est explicitement configuré.
    SYNC_API_TOKEN = os.getenv("SYNC_API_TOKEN", "")
