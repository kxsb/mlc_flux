"""REL001 unit tests: intact modules, mocked I/O boundaries, temporary SQLite.

Do not import server.__init__: its eager Flask imports require Unix fcntl, and
creating the app initializes runtime databases. Mocks below also prevent these
unit tests from reaching providers, mappings, environment files or real data.
"""
from contextlib import closing, nullcontext
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def load_subject(monkeypatch):
    def load(relative_path, dependencies):
        for name in ("server", "server.services"):
            package = ModuleType(name)
            package.__path__ = []
            monkeypatch.setitem(sys.modules, name, package)
        for name, exports in dependencies.items():
            module = ModuleType(name)
            module.__dict__.update(exports)
            monkeypatch.setitem(sys.modules, name, module)
        spec = importlib.util.spec_from_file_location(
            "rel001_subject", ROOT / relative_path,
        )
        subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(subject)
        return subject
    return load


@pytest.fixture
def orchestrator(load_subject, monkeypatch, tmp_path):
    subject = load_subject("server/sync_mlc_instance.py", {
        "server.mlc_context": {"normalize_mlc_id": Mock()},
        "server.mlc_profiles": {
            "load_mlc_profiles": lambda: [SimpleNamespace(id="graine")],
        },
    })
    monkeypatch.setattr(subject, "configure_instance", Mock())
    monkeypatch.setattr(subject, "sync_transactions_service", Mock(return_value={"inserted": 1}))
    monkeypatch.setattr(subject, "rebuild_semantics", Mock(return_value={"classified": 1}))
    child = Mock(return_value=SimpleNamespace(returncode=0, stdout="done", stderr=""))
    monkeypatch.setattr(subject.subprocess, "run", child)
    steps = []
    original_step_result = subject.step_result

    def record_step(*args, **kwargs):
        step = original_step_result(*args, **kwargs)
        steps.append(step)
        return step

    monkeypatch.setattr(subject, "step_result", record_step)
    report_path = tmp_path / "report.json"
    argv = [
        "--mlc", "graine", "--date-from", "2026-01-01", "--date-to", "2026-01-02",
        "--env-file", str(tmp_path / "unused.env"), "--json-out", str(report_path),
    ]
    return subject, child, steps, report_path, argv


def test_subprocess_success_is_reported_ok(orchestrator, capsys):
    subject, child, steps, report_path, argv = orchestrator
    assert subject.main(argv) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report == json.loads(report_path.read_text(encoding="utf-8"))
    children = [step for step in steps if (step.get("payload") or {}).get("module")]
    assert children and len(children) == child.call_count
    assert all(step["status"] == "ok" for step in children)
    assert all(step["payload"]["returncode"] == 0 for step in children)


def test_subprocess_failure_stops_without_continue(orchestrator, capsys):
    subject, child, steps, report_path, argv = orchestrator
    child.return_value = SimpleNamespace(returncode=7, stdout="", stderr="failure")
    with pytest.raises(RuntimeError, match="returncode=7"):
        subject.main(argv)
    assert child.call_count == 1
    assert steps[-1]["step"] == "professional_chain_fate_summary"
    assert steps[-1]["status"] == "error"
    assert steps[-1]["payload"]["returncode"] == 7
    assert steps[-1]["payload"]["ok"] is False
    # Existing fail-fast contract: raise immediately, no final report emitted.
    assert not report_path.exists()
    assert capsys.readouterr().out == ""


def test_subprocess_failure_continues_but_final_report_fails(orchestrator, capsys):
    subject, child, steps, report_path, argv = orchestrator
    def completed(*args, **kwargs):
        if child.call_count == 1:
            return SimpleNamespace(returncode=7, stdout="", stderr="contact person@example.test")
        return SimpleNamespace(returncode=0, stdout="done", stderr="")
    child.side_effect = completed
    assert subject.main([*argv, "--continue-on-error"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert report == json.loads(report_path.read_text(encoding="utf-8"))
    failed = next(step for step in steps if step["step"] == "professional_chain_fate_summary")
    assert failed["status"] == "error"
    assert failed["payload"]["returncode"] == 7
    assert "person@example.test" not in failed["payload"]["stderr"]
    assert "[email masqué]" in failed["payload"]["stderr"]
    assert next(step for step in steps if step["step"] == "actor_user_links")["status"] == "ok"
    assert steps[-1]["step"] == "integrity_quick"
    assert steps[-1]["status"] == "ok"
    assert child.call_count > 1


@pytest.mark.parametrize("payload", [{"ok": False, "returncode": 0}, {"ok": True, "returncode": 7}])
def test_explicit_failure_signal_is_not_ignored(orchestrator, monkeypatch, payload):
    subject, _, steps, _, argv = orchestrator
    monkeypatch.setattr(subject, "run_subprocess_module", Mock(return_value=payload))
    with pytest.raises(RuntimeError):
        subject.main(argv)
    assert steps[-1]["status"] == "error"


def row(number="new", **overrides):
    return {
        "transaction_number": number, "cyclos_id": f"cyclos-{number}",
        "date": "2026-01-01", "group_label": "payment", "from_label": "U_test",
        "to_label": "P0001", "amount": "12.50", "type_label": "payment",
        "from_family": "U", "to_family": "P", **overrides,
    }


@pytest.fixture
def transaction_sync(load_subject, tmp_path, monkeypatch):
    db_path = tmp_path / "transactions.sqlite"
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.executescript("""
            CREATE TABLE transactions (
                transaction_number TEXT PRIMARY KEY, cyclos_id TEXT,
                date TEXT NOT NULL, group_label TEXT, from_label TEXT,
                to_label TEXT, amount REAL, type_label TEXT
            );
            CREATE UNIQUE INDEX idx_transactions_cyclos_id_unique
                ON transactions (cyclos_id)
                WHERE cyclos_id IS NOT NULL AND TRIM(cyclos_id) <> '';
            CREATE TABLE untouched (marker TEXT);
            INSERT INTO untouched VALUES ('preserve');
            INSERT INTO transactions (transaction_number, cyclos_id, date, amount)
                VALUES ('old-1', 'cyclos-old-1', '2025-01-01', 3),
                       ('old-2', 'cyclos-old-2', '2025-01-02', 4);
        """)
    connections = []
    def connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        connections.append(conn)
        return conn
    init_db = Mock()
    get_connection = Mock(side_effect=connect)
    fetch = Mock(return_value=[row()])
    subject = load_subject("server/services/cyclos_transaction_sync.py", {
        "server.database": {"init_db": init_db, "get_connection": get_connection},
        "server.services.cyclos_client": {"get_transactions": fetch},
        "server.services.cyclos_actor_classifier": {
            "classify_cyclos_transaction": Mock(side_effect=AssertionError("Real classification must not run")),
        },
    })
    monkeypatch.setattr(subject, "classify_transaction_for_storage", lambda tx, **kwargs: tx)
    yield SimpleNamespace(subject=subject, path=db_path, fetch=fetch,
                          init_db=init_db, get_connection=get_connection)
    for conn in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn.execute("SELECT 1")
    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT marker FROM untouched").fetchall() == [("preserve",)]


def stored(state):
    with closing(sqlite3.connect(state.path)) as conn:
        return conn.execute("SELECT * FROM transactions ORDER BY transaction_number").fetchall()


def test_reset_false_preserves_existing_transactions(transaction_sync):
    state = transaction_sync
    before = stored(state)
    report = state.subject.sync_cyclos_transactions(mlc_id="graine", reset=False)
    assert [r for r in stored(state) if r[0].startswith("old-")] == before
    assert len(stored(state)) == 3
    assert report["deleted"] == 0
    assert report["inserted"] == 1
    # Replaying the same lot updates rather than duplicates it.
    replay = state.subject.sync_cyclos_transactions(mlc_id="graine", reset=False)
    assert replay["inserted"] == 0 and replay["updated"] == 1
    assert len(stored(state)) == 3


def test_reset_replaces_transactions_and_reports_deleted(transaction_sync):
    state = transaction_sync
    report = state.subject.sync_cyclos_transactions(mlc_id="graine", reset=True, write=True)
    assert [r[0] for r in stored(state)] == ["new"]
    assert stored(state)[0][6] == 12.5
    assert report["deleted"] == 2
    assert report["inserted"] == 1 and report["updated"] == 0
    assert report["reset"] is True and report["write"] is True


def test_reset_with_write_false_never_opens_storage(transaction_sync):
    state = transaction_sync
    before = stored(state)
    report = state.subject.sync_cyclos_transactions(mlc_id="graine", reset=True, write=False)
    assert stored(state) == before
    assert report["deleted"] == report["inserted"] == report["updated"] == 0
    assert report["write"] is False
    state.init_db.assert_not_called()
    state.get_connection.assert_not_called()


@pytest.mark.parametrize("unknown_field", ["from_family", "to_family"])
def test_rejected_batch_never_resets_storage(transaction_sync, unknown_field):
    state = transaction_sync
    before = stored(state)
    state.fetch.return_value = [row(), row("unknown", **{unknown_field: "X"})]
    report = state.subject.sync_cyclos_transactions(mlc_id="graine", reset=True, write=True)
    assert stored(state) == before
    assert report["unknown_count"] == 1 and report["error"]
    assert report["write"] is False and report["deleted"] == 0
    state.init_db.assert_not_called()
    state.get_connection.assert_not_called()


def test_reset_rolls_back_delete_and_partial_insert_on_sql_error(transaction_sync):
    state = transaction_sync
    before = stored(state)
    state.fetch.return_value = [row(), row("invalid", date=None)]
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
        state.subject.sync_cyclos_transactions(mlc_id="graine", reset=True, write=True)
    assert stored(state) == before


def test_fetch_failure_never_resets_storage(transaction_sync):
    state = transaction_sync
    before = stored(state)
    state.fetch.side_effect = RuntimeError("Simulated fetch failure")
    with pytest.raises(RuntimeError, match="fetch failure"):
        state.subject.sync_cyclos_transactions(mlc_id="graine", reset=True, write=True)
    assert stored(state) == before
    state.init_db.assert_not_called()
    state.get_connection.assert_not_called()


def test_explicit_reset_with_empty_validated_batch_clears_transactions(transaction_sync):
    state = transaction_sync
    state.fetch.return_value = []
    report = state.subject.sync_cyclos_transactions(mlc_id="graine", reset=True, write=True)
    assert stored(state) == []
    assert report["deleted"] == 2 and report["inserted"] == 0


@pytest.fixture
def db_builder(load_subject, monkeypatch):
    sync = Mock(return_value={"inserted": 1})
    app_context = Mock(side_effect=nullcontext)
    dependencies = {
        "app": {"app": SimpleNamespace(app_context=app_context)},
        "server.database": {
            "get_db_path": Mock(return_value=Path("unused.sqlite")),
            "init_db": Mock(), "init_professional_enrichment_db": Mock(),
        },
        "server.services.cyclos_transaction_sync": {"sync_cyclos_transactions": sync},
        "server.services.cyclos_professional_profile_enrichment": {
            "fetch_professional_profile_enrichment_sample": Mock(),
            "sync_professional_profile_enrichment_sample": Mock(),
        },
        "server.services.professional_ref_mapping": {
            "count_professional_mappings": Mock(return_value=0),
        },
    }
    subject = load_subject("server/build_mlc_db.py", dependencies)
    boundaries = [app_context]
    boundaries.extend(
        mock for exports in dependencies.values() for mock in exports.values()
        if isinstance(mock, Mock)
    )
    for name, result in (
        ("_load_env_file", None), ("_db_counts", {}),
        ("_flow_summary", []), ("_smoke_tests", {}),
    ):
        mock = Mock(return_value=result)
        monkeypatch.setattr(subject, name, mock)
        boundaries.append(mock)
    monkeypatch.setattr(subject, "os", SimpleNamespace(environ={}))
    return subject, sync, boundaries


@pytest.mark.parametrize("limit_args", [
    [], ["--limit", "100"], ["--limit", "0"], ["--limit", "1"],
    ["--limit", "100", "--dry-run"],
])
def test_build_reset_rejects_numeric_limit_before_io(db_builder, capsys, limit_args):
    subject, _, boundaries = db_builder
    with pytest.raises(SystemExit) as error:
        subject.main(["--mlc", "graine", "--reset-transactions", *limit_args])
    assert error.value.code == 2
    assert "--limit none" in capsys.readouterr().err
    assert subject.os.environ == {}
    for boundary in boundaries:
        boundary.assert_not_called()


def test_build_reset_rejects_empty_limit_before_io(db_builder):
    subject, _, boundaries = db_builder
    with pytest.raises(SystemExit) as error:
        subject.main(["--mlc", "graine", "--reset-transactions", "--limit", ""])
    assert error.value.code == 2
    assert subject.os.environ == {}
    for boundary in boundaries:
        boundary.assert_not_called()


@pytest.mark.parametrize("date_args", [
    [], ["--date-from", "2026-01-01"], ["--date-to", "2026-01-31"],
])
def test_build_reset_requires_both_dates_before_io(db_builder, capsys, date_args):
    subject, _, boundaries = db_builder
    with pytest.raises(SystemExit) as error:
        subject.main([
            "--mlc", "graine", "--reset-transactions", "--limit", "none", *date_args,
        ])
    assert error.value.code == 2
    message = capsys.readouterr().err
    assert "--date-from" in message and "--date-to" in message
    assert subject.os.environ == {}
    for boundary in boundaries:
        boundary.assert_not_called()


@pytest.mark.parametrize("args, expected_limit, expected_reset, expected_dates", [
    (["--reset-transactions", "--limit", "none",
      "--date-from", "2026-01-01", "--date-to", "2026-01-31"],
     None, True, ("2026-01-01", "2026-01-31")),
    (["--limit", "100"], 100, False, (None, None)),
    ([], 100, False, (None, None)),
])
def test_build_allowed_limits_reach_mocked_sync(
    db_builder, capsys, args, expected_limit, expected_reset, expected_dates,
):
    subject, sync, _ = db_builder
    assert subject.main(["--mlc", "graine", "--skip-smoke", *args]) == 0
    sync.assert_called_once_with(
        mlc_id="graine", days=7, date_from=expected_dates[0], date_to=expected_dates[1],
        limit=expected_limit, reset=expected_reset, write=True,
    )
    report = json.loads(capsys.readouterr().out)
    assert report["parameters"]["limit"] == expected_limit
    assert report["parameters"]["reset_transactions"] is expected_reset
    assert report["parameters"]["date_from"] == expected_dates[0]
    assert report["parameters"]["date_to"] == expected_dates[1]
