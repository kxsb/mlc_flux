from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from server.control_db import list_user_mlc_access
from server.mlc_profiles import get_mlc_profile, list_public_mlc_profiles
from server.routes.auth import current_user


mlc_instances_bp = Blueprint("mlc_instances", __name__)


def _visible_profiles_for_user(user):
    profiles = list_public_mlc_profiles()
    access_items = list_user_mlc_access(user["id"])
    access_by_mlc = {
        item["mlc_id"]: item["role"]
        for item in access_items
    }

    visible_profiles = []

    for profile in profiles:
        role = access_by_mlc.get(profile["id"])

        if user.get("global_role") != "admin" and not role:
            continue

        item = dict(profile)
        item["access_role"] = role or "admin"
        visible_profiles.append(item)

    return visible_profiles


def _user_can_access_mlc(user, mlc_id: str) -> tuple[bool, str | None]:
    if user.get("global_role") == "admin":
        try:
            get_mlc_profile(mlc_id)
        except KeyError:
            return False, None

        access_by_mlc = {
            item["mlc_id"]: item["role"]
            for item in list_user_mlc_access(user["id"])
        }
        return True, access_by_mlc.get(mlc_id, "admin")

    for item in list_user_mlc_access(user["id"]):
        if item["mlc_id"] == mlc_id:
            return True, item["role"]

    return False, None


@mlc_instances_bp.route("/api/mlc-instances", methods=["GET"])
def mlc_instances():
    user = current_user()

    if user is None:
        return jsonify({
            "authenticated": False,
            "error": "Authentification requise.",
            "instances": []
        }), 401

    return jsonify({
        "instances": _visible_profiles_for_user(user),
        "active_mlc_id": session.get("active_mlc_id"),
        "active_mlc_role": session.get("active_mlc_role"),
    })


@mlc_instances_bp.route("/api/current-mlc", methods=["GET"])
def current_mlc():
    user = current_user()

    if user is None:
        return jsonify({
            "authenticated": False,
            "active_mlc": None,
        }), 401

    active_mlc_id = session.get("active_mlc_id")
    active_mlc_role = session.get("active_mlc_role")

    if not active_mlc_id:
        return jsonify({
            "authenticated": True,
            "active_mlc": None,
        })

    allowed, role = _user_can_access_mlc(user, active_mlc_id)
    if not allowed:
        session.pop("active_mlc_id", None)
        session.pop("active_mlc_role", None)
        return jsonify({
            "authenticated": True,
            "active_mlc": None,
        })

    profile = get_mlc_profile(active_mlc_id).public_dict()
    profile["access_role"] = active_mlc_role or role

    return jsonify({
        "authenticated": True,
        "active_mlc": profile,
    })


@mlc_instances_bp.route("/api/select-mlc", methods=["POST"])
def select_mlc():
    user = current_user()

    if user is None:
        return jsonify({
            "authenticated": False,
            "error": "Authentification requise.",
        }), 401

    payload = request.get_json(silent=True) or {}
    mlc_id = str(payload.get("mlc_id") or "").strip()

    if not mlc_id:
        return jsonify({
            "error": "mlc_id manquant.",
        }), 400

    allowed, role = _user_can_access_mlc(user, mlc_id)
    if not allowed:
        return jsonify({
            "error": "Accès refusé à cette monnaie locale.",
        }), 403

    profile = get_mlc_profile(mlc_id).public_dict()
    profile["access_role"] = role

    session["active_mlc_id"] = mlc_id
    session["active_mlc_role"] = role

    return jsonify({
        "ok": True,
        "active_mlc": profile,
    })
