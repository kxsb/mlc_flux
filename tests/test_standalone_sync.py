import pytest

from server import sync_payment_basin_postal_areas as postal_sync
from server.sync_mlc_instance import build_parser


@pytest.mark.parametrize("mlc_id", ["gonette", "graine"])
def test_postal_sync_defaults_to_only_the_configured_mlc(monkeypatch, capsys, mlc_id):
    import json

    monkeypatch.setenv("MLCFLUX_DEFAULT_MLC_ID", mlc_id)
    calls = []

    def build(mlc_id, **kwargs):
        calls.append((mlc_id, kwargs))
        return {"postal_code_count_requested": 2, "area_count": 2, "failure_count": 0}

    monkeypatch.setattr(postal_sync, "build_postal_areas_for_instance", build)
    postal_sync.main(["--dry-run", "--limit", "2"])

    assert calls == [(mlc_id, {"sleep_seconds": 0.12, "limit": 2, "dry_run": True})]
    report = json.loads(capsys.readouterr().out)
    assert len(report) == 1
    assert report[0]["mlc_id"] == mlc_id
    assert report[0]["areas"] == 2


@pytest.mark.parametrize("mlc_id", ["gonette", "graine"])
def test_sync_parser_keeps_supported_profiles_and_period(mlc_id):
    args = build_parser().parse_args(["--mlc", mlc_id, "--days", "3", "--plan-only"])
    assert args.mlc == mlc_id
    assert args.days == 3
    assert args.plan_only is True


def test_sync_parser_rejects_unknown_profile():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--mlc", "missing-profile"])


def test_postal_sync_requires_an_explicit_installation(monkeypatch):
    monkeypatch.delenv("MLCFLUX_DEFAULT_MLC_ID", raising=False)
    with pytest.raises(SystemExit) as exc:
        postal_sync.main(["--dry-run"])
    assert exc.value.code == 2
