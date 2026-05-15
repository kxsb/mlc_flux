from flask import Flask
from server.config import Config
from server.routes.health import health_bp
from server.routes.transactions import transactions_bp
from server.routes.stored_transactions import stored_transactions_bp
from server.routes.sync import sync_bp
from server.routes.legacy_api import legacy_api_bp
from server.routes.status import status_bp
from server.database import init_db

def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)

    # Garantit que le schéma SQLite existe avant l'exposition des routes.
    # Idempotent : CREATE TABLE IF NOT EXISTS ne modifie pas une base déjà initialisée.
    init_db()

    app.register_blueprint(health_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(stored_transactions_bp)
    app.register_blueprint(sync_bp)
    app.register_blueprint(legacy_api_bp)
    app.register_blueprint(status_bp)

    return app
