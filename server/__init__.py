from flask import Flask
from server.config import Config
from server.routes.health import health_bp
from server.routes.transactions import transactions_bp
from server.routes.sync import sync_bp
from server.routes.legacy_api import legacy_api_bp
from server.routes.status import status_bp
from server.routes.info_content import info_content_bp
from server.routes.admin_integrity import admin_integrity_bp
from server.routes.tickets import tickets_bp
from server.routes.monetary_indicators import monetary_indicators_bp
from server.routes.individual_balances import individual_balances_bp
from server.routes.user_postal_clusters import user_postal_clusters_bp
from server.routes.professional_detail_dynamics import professional_detail_dynamics_bp
from server.routes.professional_reuse_prospects import professional_reuse_prospects_bp
from server.routes.professional_payment_basin_map import professional_payment_basin_map_bp
from server.routes.professional_activity import professional_activity_bp
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
    app.register_blueprint(sync_bp)
    app.register_blueprint(legacy_api_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(info_content_bp)
    app.register_blueprint(admin_integrity_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(monetary_indicators_bp)
    app.register_blueprint(individual_balances_bp)
    app.register_blueprint(user_postal_clusters_bp)
    app.register_blueprint(professional_detail_dynamics_bp)
    app.register_blueprint(professional_reuse_prospects_bp)
    app.register_blueprint(professional_payment_basin_map_bp)
    app.register_blueprint(professional_activity_bp)

    return app
