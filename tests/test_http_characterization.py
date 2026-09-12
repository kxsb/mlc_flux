from app import app


def test_route_count_characterization():
    # Baseline mlcflux_multi au début du chantier Neutral.
    # Ce test est volontairement de caractérisation.
    assert len(list(app.url_map.iter_rules())) == 84


def test_public_selector_is_available():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200


def test_version_api_is_public():
    client = app.test_client()

    response = client.get("/api/version")

    assert response.status_code == 200


def test_mlc_instances_api_is_public():
    client = app.test_client()

    response = client.get("/api/mlc-instances")

    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload, dict)

    instances = payload.get("instances")
    assert isinstance(instances, list)

    instance_ids = {
        str(instance.get("id"))
        for instance in instances
        if isinstance(instance, dict)
    }

    assert {"gonette", "graine"} <= instance_ids


def test_health_v2_currently_requires_authentication():
    """
    Caractérisation du comportement initial.

    /api/v2/health existe mais n'est actuellement pas dans
    les chemins publics de l'auth guard.
    """
    client = app.test_client()

    response = client.get("/api/v2/health")

    assert response.status_code == 401

    payload = response.get_json()
    assert payload["authenticated"] is False
