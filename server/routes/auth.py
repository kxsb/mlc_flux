from __future__ import annotations

from urllib.parse import urlparse

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from server.control_db import (
    authenticate_user,
    get_user_by_id,
    list_user_mlc_access,
    record_auth_event,
)


auth_bp = Blueprint("auth", __name__)


def _safe_next_url(value: str | None) -> str:
    if not value:
        return "/"

    parsed = urlparse(value)

    if parsed.scheme or parsed.netloc:
        return "/"

    if not value.startswith("/"):
        return "/"

    if value.startswith("//"):
        return "/"

    return value


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    user = get_user_by_id(int(user_id))
    if user is None or not user.get("is_active"):
        session.clear()
        return None

    return user


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template(
            "login.html",
            next_url=_safe_next_url(request.args.get("next")),
            error=None,
        )

    email = request.form.get("email") or ""
    password = request.form.get("password") or ""
    next_url = _safe_next_url(request.form.get("next"))

    user = authenticate_user(
        email=email,
        password=password,
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
        user_agent=request.headers.get("User-Agent"),
    )

    if user is None:
        return render_template(
            "login.html",
            next_url=next_url,
            error="Identifiants invalides.",
        ), 401

    session.clear()
    session["user_id"] = user["id"]
    session["user_email"] = user["email"]
    session["user_display_name"] = user["display_name"]
    session["global_role"] = user["global_role"]

    return redirect(next_url or "/")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    user_id = session.get("user_id")
    email = session.get("user_email")

    if user_id:
        record_auth_event(
            event_type="logout",
            user_id=int(user_id),
            email=email,
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
            user_agent=request.headers.get("User-Agent"),
        )

    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/api/me", methods=["GET"])
def api_me():
    user = current_user()

    if user is None:
        return jsonify({
            "authenticated": False,
            "user": None,
            "mlc_access": [],
        })

    return jsonify({
        "authenticated": True,
        "user": user,
        "mlc_access": list_user_mlc_access(user["id"]),
    })
