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
