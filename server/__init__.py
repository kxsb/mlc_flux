from server.auth_guards import install_auth_guard
from server.security_middleware import install_security_middleware
from datetime import timedelta
from server.control_db import init_control_db
from server.routes.auth import auth_bp
from flask import Flask, request
from server.config import Config
from server.routes.health import health_bp
from server.routes.transactions import transactions_bp
from server.routes.sync import sync_bp
from server.routes.legacy_api import legacy_api_bp
from server.routes.status import status_bp
from server.routes.info_content import info_content_bp
from server.routes.admin_integrity import admin_integrity_bp
from server.routes.admin_accounts import admin_accounts_bp
from server.routes.account_requests import account_requests_bp
from server.routes.tickets import tickets_bp
from server.routes.monetary_indicators import monetary_indicators_bp
from server.routes.individual_balances import individual_balances_bp
from server.routes.user_postal_clusters import user_postal_clusters_bp
from server.routes.professional_detail_dynamics import professional_detail_dynamics_bp
from server.routes.professional_reuse_prospects import professional_reuse_prospects_bp
from server.routes.professional_payment_basin_map import professional_payment_basin_map_bp
from server.routes.user_to_professional_map import user_to_professional_map_bp
from server.routes.professional_activity import professional_activity_bp
from server.routes.professional_economic_registry import professional_economic_registry_bp
from server.routes.current_mlc import current_mlc_bp
from server.database import init_db, init_professional_enrichment_db

def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)
    app.permanent_session_lifetime = timedelta(
        seconds=app.config.get("PERMANENT_SESSION_LIFETIME_SECONDS", 28800)
    )

    # Garantit que le schéma SQLite existe avant l'exposition des routes.
    # Idempotent : CREATE TABLE IF NOT EXISTS ne modifie pas une base déjà initialisée.
    init_db()
    init_professional_enrichment_db()
    init_control_db()

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(sync_bp)
    app.register_blueprint(legacy_api_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(info_content_bp)
    app.register_blueprint(admin_integrity_bp)
    app.register_blueprint(admin_accounts_bp)
    app.register_blueprint(account_requests_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(monetary_indicators_bp)
    app.register_blueprint(individual_balances_bp)
    app.register_blueprint(user_postal_clusters_bp)
    app.register_blueprint(professional_detail_dynamics_bp)
    app.register_blueprint(professional_reuse_prospects_bp)
    app.register_blueprint(professional_payment_basin_map_bp)
    app.register_blueprint(user_to_professional_map_bp)
    app.register_blueprint(professional_activity_bp)
    app.register_blueprint(professional_economic_registry_bp)
    app.register_blueprint(current_mlc_bp)

    install_security_middleware(app)
    install_auth_guard(app)

    return app
