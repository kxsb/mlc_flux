from app import app
from server.routes.current_mlc import current_mlc


def test_route_count_characterization():
    # Baseline Neutral après suppression du portail multi-instance.
    assert len(list(app.url_map.iter_rules())) == 76


def test_root_requires_authentication():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_successful_login_creates_session_without_mlc_selection(monkeypatch):
    from flask import session
    from server.routes import auth

    user = {
        "id": 42,
        "email": "standalone@example.test",
        "display_name": "Standalone",
        "global_role": "user",
    }
    monkeypatch.setitem(app.config, "SECRET_KEY", "test-only-session-key")
    monkeypatch.setattr(auth, "authenticate_user", lambda **kwargs: user)
    monkeypatch.setattr(auth, "_auth_load_user_by_id", lambda user_id: user)

    with app.test_request_context("/login", method="POST", data={
        "email": user["email"], "password": "test-only-password",
    }):
        session["pending_mlc_id"] = "graine"
        session["active_mlc_id"] = "graine"
        session["active_mlc_role"] = "manager"
        response = auth.login()

        assert response.status_code == 302
        assert response.headers["Location"] == "/"
        assert session["user_id"] == user["id"]
        assert session["user_email"] == user["email"]
        assert session["global_role"] == "user"
        assert not any("mlc" in key for key in session)
        assert auth.current_user() == user


def test_failed_login_does_not_create_session(monkeypatch):
    from flask import session
    from server.routes import auth

    monkeypatch.setitem(app.config, "SECRET_KEY", "test-only-session-key")
    monkeypatch.setattr(auth, "authenticate_user", lambda **kwargs: None)

    with app.test_request_context("/login", method="POST", data={
        "email": "standalone@example.test", "password": "invalid",
    }):
        _, status = auth.login()

        assert status == 401
        assert "user_id" not in session


def test_version_api_is_public():
    client = app.test_client()

    response = client.get("/api/version")

    assert response.status_code == 200


def test_multi_instance_selector_routes_are_removed():
    routes = {
        str(rule)
        for rule in app.url_map.iter_rules()
    }

    assert "/api/mlc-instances" not in routes
    assert "/api/select-mlc" not in routes
    assert "/api/current-mlc" in routes


def test_current_mlc_api_requires_authentication():
    client = app.test_client()

    response = client.get("/api/current-mlc")

    assert response.status_code == 401

    payload = response.get_json()
    assert payload["authenticated"] is False


def test_current_mlc_uses_server_configuration(
    monkeypatch,
):
    monkeypatch.setenv(
        "MLCFLUX_DEFAULT_MLC_ID",
        "gonette",
    )

    with app.test_request_context(
        "/api/current-mlc"
    ):
        response = current_mlc()

    payload = response.get_json()

    assert payload["mlc_id"] == "gonette"
    assert payload["current_mlc_id"] == "gonette"
    assert payload["active_mlc_id"] == "gonette"
    assert payload["active_mlc"]["id"] == "gonette"


def test_health_v2_currently_requires_authentication():
    """
    Comportement déjà caractérisé avant SINGLE001.

    /api/v2/health existe mais n'est toujours pas dans
    les chemins publics de l'auth guard.
    """
    client = app.test_client()

    response = client.get("/api/v2/health")

    assert response.status_code == 401

    payload = response.get_json()
    assert payload["authenticated"] is False


def test_active_mlc_is_always_server_configured(
    monkeypatch,
):
    from server.mlc_context import get_active_mlc_id

    monkeypatch.setenv(
        "MLCFLUX_DEFAULT_MLC_ID",
        "gonette",
    )

    assert (
        get_active_mlc_id(
            fallback_to_default=False
        )
        == "gonette"
    )


def test_monetary_indicators_query_cannot_switch_mlc(
    monkeypatch,
):
    import app as app_module

    monkeypatch.setenv(
        "MLCFLUX_DEFAULT_MLC_ID",
        "gonette",
    )

    monkeypatch.setattr(
        app_module,
        "get_adaptive_monetary_indicators",
        lambda mlc_id: {
            "mlc_id": mlc_id,
        },
    )

    with app.test_request_context(
        "/api/monetary-indicators?mlc=graine"
    ):
        response = (
            app_module.api_monetary_indicators()
        )

    assert response.get_json()["mlc_id"] == "gonette"


def test_payment_basin_request_cannot_switch_mlc(
    monkeypatch,
):
    from flask import session
    from server.services.professional_payment_basin_map import (
        _payment_basin_active_mlc_id,
    )

    monkeypatch.setenv(
        "MLCFLUX_DEFAULT_MLC_ID",
        "gonette",
    )
    monkeypatch.setenv(
        "MLCFLUX_ACTIVE_MLC_ID",
        "graine",
    )

    with app.test_request_context(
        "/?mlc=graine",
        headers={
            "X-MLC-Id": "graine",
            "X-MLCFlux-MLC-Id": "graine",
        },
    ):
        session["active_mlc_id"] = "graine"
        session["pending_mlc_id"] = "graine"

        assert (
            _payment_basin_active_mlc_id()
            == "gonette"
        )


def test_user_to_professional_map_cannot_switch_mlc(
    monkeypatch,
):
    from server.routes.user_to_professional_map import (
        _resolve_mlc_id,
    )

    monkeypatch.setenv(
        "MLCFLUX_DEFAULT_MLC_ID",
        "gonette",
    )

    with app.test_request_context(
        "/api/user-to-professional-map"
        "?mlc=graine"
        "&mlc_id=graine"
        "&instance=graine"
    ):
        assert _resolve_mlc_id() == "gonette"



def test_ticket_routes_are_removed():
    routes = {
        str(rule)
        for rule in app.url_map.iter_rules()
    }

    assert not any(
        route.startswith("/api/tickets")
        for route in routes
    )
