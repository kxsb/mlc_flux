from server.runtime_config import get_cyclos_config


CYCLOS_ENV_NAMES = (
    "CYCLOS_BASE_URL",
    "CYCLOS_USERNAME",
    "CYCLOS_PASSWORD",
    "MLC_GONETTE_CYCLOS_BASE_URL",
    "MLC_GONETTE_CYCLOS_USERNAME",
    "MLC_GONETTE_CYCLOS_PASSWORD",
)


def _clear_cyclos_env(monkeypatch):
    for name in CYCLOS_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_cyclos_config_can_be_empty(monkeypatch):
    _clear_cyclos_env(monkeypatch)

    config = get_cyclos_config("gonette")

    assert config.mlc_id == "gonette"
    assert config.base_url == ""
    assert config.username == ""
    assert config.password == ""
    assert config.is_complete is False


def test_cyclos_config_uses_generic_standalone_env(
    monkeypatch,
):
    _clear_cyclos_env(monkeypatch)

    monkeypatch.setenv(
        "CYCLOS_BASE_URL",
        "https://cyclos.example.test/",
    )
    monkeypatch.setenv(
        "CYCLOS_USERNAME",
        "generic-user",
    )
    monkeypatch.setenv(
        "CYCLOS_PASSWORD",
        "generic-password",
    )

    config = get_cyclos_config("gonette")

    assert (
        config.base_url
        == "https://cyclos.example.test"
    )
    assert config.username == "generic-user"
    assert config.password == "generic-password"
    assert config.is_complete is True


def test_mlc_specific_cyclos_env_has_priority(
    monkeypatch,
):
    _clear_cyclos_env(monkeypatch)

    monkeypatch.setenv(
        "CYCLOS_BASE_URL",
        "https://generic.example.test",
    )
    monkeypatch.setenv(
        "CYCLOS_USERNAME",
        "generic-user",
    )
    monkeypatch.setenv(
        "CYCLOS_PASSWORD",
        "generic-password",
    )

    monkeypatch.setenv(
        "MLC_GONETTE_CYCLOS_BASE_URL",
        "https://specific.example.test",
    )
    monkeypatch.setenv(
        "MLC_GONETTE_CYCLOS_USERNAME",
        "specific-user",
    )
    monkeypatch.setenv(
        "MLC_GONETTE_CYCLOS_PASSWORD",
        "specific-password",
    )

    config = get_cyclos_config("gonette")

    assert (
        config.base_url
        == "https://specific.example.test"
    )
    assert config.username == "specific-user"
    assert config.password == "specific-password"
