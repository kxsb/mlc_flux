from contextlib import nullcontext
from datetime import date
import json

import pytest

from server import backfill_transactions as backfill


def test_build_year_windows_defaults_to_newest_first():
    windows = backfill.build_year_windows(
        "2019-04-17",
        "2026-06-14",
    )

    assert windows[0] == backfill.BackfillWindow(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 6, 14),
    )
    assert windows[-1] == backfill.BackfillWindow(
        date_from=date(2019, 4, 17),
        date_to=date(2019, 12, 31),
    )
    assert len(windows) == 8


def test_plan_only_has_no_runtime_side_effects(monkeypatch, capsys):
    monkeypatch.setattr(
        backfill,
        "execute_backfill",
        lambda windows: (_ for _ in ()).throw(
            AssertionError("execute_backfill must not run")
        ),
    )

    assert backfill.main([
        "--date-from",
        "2025-01-01",
        "--date-to",
        "2026-06-14",
    ]) == 0

    report = json.loads(capsys.readouterr().out)

    assert report["executed"] is False
    assert report["input001_shadow_updated"] is False
    assert report["windows"] == [
        {
            "date_from": "2026-01-01",
            "date_to": "2026-06-14",
        },
        {
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
        },
    ]


def test_backfill_window_updates_legacy_without_touching_shadow(monkeypatch):
    raw = [{"id": "late-1"}]
    safe = [{"id": "late-1", "safe": True}]
    calls = {}

    class FakeApp:
        def app_context(self):
            return nullcontext()

    monkeypatch.setattr(backfill, "create_app", lambda: FakeApp())
    monkeypatch.setattr(backfill, "init_db", lambda: calls.setdefault("init", 0))

    def fake_get_transactions(**kwargs):
        calls["fetch"] = kwargs
        return raw

    monkeypatch.setattr(backfill, "get_transactions", fake_get_transactions)
    monkeypatch.setattr(
        backfill,
        "anonymize_transactions",
        lambda rows: safe,
    )

    def fake_insert(rows):
        calls["insert"] = rows
        return {
            "upserted": 1,
            "inserted_new": 1,
            "existing": 0,
        }

    monkeypatch.setattr(
        backfill,
        "_insert_transactions_for_sync",
        fake_insert,
    )

    result = backfill.backfill_window(
        backfill.BackfillWindow(
            date_from=date(2025, 1, 1),
            date_to=date(2025, 12, 31),
        )
    )

    assert calls["fetch"] == {
        "date_from": "2025-01-01",
        "date_to": "2025-12-31",
    }
    assert calls["insert"] is safe
    assert result["fetched"] == 1
    assert result["inserted_new"] == 1

    # Le module de backfill n'importe ni n'appelle materialize_cyclos_shadow.
    assert not hasattr(backfill, "materialize_cyclos_shadow")


def test_execute_backfill_stops_on_first_failure_and_records_error(monkeypatch):
    windows = [
        backfill.BackfillWindow(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 6, 14),
        ),
        backfill.BackfillWindow(
            date_from=date(2025, 1, 1),
            date_to=date(2025, 12, 31),
        ),
        backfill.BackfillWindow(
            date_from=date(2024, 1, 1),
            date_to=date(2024, 12, 31),
        ),
    ]

    monkeypatch.setattr(
        backfill,
        "create_pre_backfill_backups",
        lambda: {"legacy": "/tmp/backup.db"},
    )

    seen = []

    def fake_window(window):
        seen.append(window.date_from.year)
        if window.date_from.year == 2025:
            raise RuntimeError("simulated failure")
        return {
            **window.as_dict(),
            "fetched": 10,
            "upserted": 10,
            "inserted_new": 2,
            "existing": 8,
        }

    monkeypatch.setattr(backfill, "backfill_window", fake_window)

    states = []
    monkeypatch.setattr(
        backfill,
        "_save_backfill_state",
        lambda status, message: states.append((status, message)),
    )

    with pytest.raises(RuntimeError, match="simulated failure"):
        backfill.execute_backfill(windows)

    assert seen == [2026, 2025]
    assert states
    assert states[-1][0] == "error"
    assert "1 fenêtre(s) réussie(s)" in states[-1][1]


def test_execute_backfill_aggregates_results_and_preserves_shadow(monkeypatch):
    windows = [
        backfill.BackfillWindow(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 6, 14),
        ),
        backfill.BackfillWindow(
            date_from=date(2025, 1, 1),
            date_to=date(2025, 12, 31),
        ),
    ]

    monkeypatch.setattr(
        backfill,
        "create_pre_backfill_backups",
        lambda: {
            "legacy": "/tmp/legacy.db",
            "input001": "/tmp/input001.db",
        },
    )

    results = {
        2026: {
            "fetched": 100,
            "upserted": 100,
            "inserted_new": 3,
            "existing": 97,
        },
        2025: {
            "fetched": 200,
            "upserted": 200,
            "inserted_new": 5,
            "existing": 195,
        },
    }

    def fake_window(window):
        return {
            **window.as_dict(),
            **results[window.date_from.year],
        }

    monkeypatch.setattr(backfill, "backfill_window", fake_window)

    states = []
    monkeypatch.setattr(
        backfill,
        "_save_backfill_state",
        lambda status, message: states.append((status, message)),
    )

    report = backfill.execute_backfill(windows)

    assert report["executed"] is True
    assert report["input001_shadow_updated"] is False
    assert report["totals"] == {
        "fetched": 300,
        "upserted": 300,
        "inserted_new": 8,
        "existing": 292,
    }
    assert states[-1][0] == "success"
    assert "8 nouvelle(s)" in states[-1][1]
