from __future__ import annotations

from flask import jsonify, redirect, request, url_for

from server.routes.auth import current_user


PUBLIC_PATHS = {
    "/",
    "/login",
    "/logout",
    "/api/health",
    "/api/me",
    "/api/mlc-instances",
    "/api/current-mlc",
    "/api/mlc/current",
    "/api/select-mlc",
    "/api/account-requests",
    "/favicon.ico",
    "/robots.txt",
}

PUBLIC_PREFIXES = (
    "/static/",
)

PUBLIC_ENDPOINTS = {
    "static",
    "mlc_select",
    "auth.login",
    "auth.logout",
    "auth.api_me",
    "mlc_instances.mlc_instances",
    "mlc_instances.current_mlc",
    "mlc_instances.select_mlc",
    "account_requests.create_account_request",
}


def _is_public_request_path(path: str) -> bool:
    if request.method == "OPTIONS":
        return True

    if path in PUBLIC_PATHS:
        return True

    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def _is_public_endpoint() -> bool:
    endpoint = request.endpoint
    return bool(endpoint and endpoint in PUBLIC_ENDPOINTS)


def _wants_json_response(path: str) -> bool:
    if path.startswith("/api/"):
        return True

    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept


def install_auth_guard(app):
    @app.before_request
    def require_authenticated_user():
        path = request.path or "/"

        # AUTH_FLOW005_PUBLIC_SELECTOR
        # Le sélecteur de MLC et les routes nécessaires à son affichage
        # sont visibles avant connexion. Les données métier restent protégées.
        if _is_public_request_path(path) or _is_public_endpoint():
            return None

        user = current_user()
        if user is not None:
            return None

        if _wants_json_response(path):
            return jsonify({
                "authenticated": False,
                "error": "Authentification requise."
            }), 401

        next_url = request.full_path if request.query_string else path
        if next_url.endswith("?"):
            next_url = next_url[:-1]

        return redirect(url_for("auth.login", next=next_url))
