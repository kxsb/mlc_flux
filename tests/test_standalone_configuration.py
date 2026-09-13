import pytest

from server.mlc_context import get_default_mlc_id


def test_default_mlc_requires_explicit_configuration(monkeypatch):
    monkeypatch.delenv("MLCFLUX_DEFAULT_MLC_ID", raising=False)

    with pytest.raises(
        RuntimeError,
        match="MLCFLUX_DEFAULT_MLC_ID",
    ):
        get_default_mlc_id()


def test_default_mlc_rejects_unknown_profile(monkeypatch):
    monkeypatch.setenv(
        "MLCFLUX_DEFAULT_MLC_ID",
        "unknown-mlc",
    )

    with pytest.raises(
        RuntimeError,
        match="aucun profil MLC valide",
    ):
        get_default_mlc_id()


def test_default_mlc_accepts_declared_profile(monkeypatch):
    monkeypatch.setenv(
        "MLCFLUX_DEFAULT_MLC_ID",
        "gonette",
    )

    assert get_default_mlc_id() == "gonette"
