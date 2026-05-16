from __future__ import annotations

import fcntl
import json
import time
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import requests
from flask import current_app

from server.database import get_connection
from server.services.cyclos_actor_user_links import load_actor_user_links
from server.services.cyclos_client import create_session_token


ACCOUNT_TYPE = "compteparticulier"
INTERVAL_UNIT = "days"
INTERVAL_COUNT = 1

# BAL-HIST002B :
# 59 jours inclusifs demandés -> 60 points renvoyés par Cyclos.
WINDOW_INCLUSIVE_DAYS = 59
WINDOW_DATE_TO_OFFSET_DAYS = WINDOW_INCLUSIVE_DAYS - 1

SOURCE = "cyclos_balances_history_daily"
LOCK_DIR = Path(__file__).resolve().parents[1] / "data" / "locks"
LOCK_PATH = LOCK_DIR / "cyclos_individual_daily_balances.lock"


class DailyBalanceBackfillAlreadyRunning(RuntimeError):
    pass


def _utc_now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds")


def _short_error(message, max_len=800):
    text = str(message or "")
    return text[:max_len]


def _parse_day(value):
    return date.fromisoformat(str(value)[:10])


def _iso(day):
    return day.isoformat()


def _balance_float(value):
    if value in (None, ""):
        return 0.0
    return float(str(value).replace(",", "."))


def _db():
    conn = get_connection()
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


@contextmanager
def individual_balance_backfill_lock():
    LOCK_DIR.mkdir(parents=True, exist_ok=True)

    with LOCK_PATH.open("w") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DailyBalanceBackfillAlreadyRunning(
                "Une synchronisation des soldes quotidiens particuliers est déjà en cours."
            ) from exc

        lock_file.write(f"pid_lock_acquired_at={_utc_now_iso()}\n")
        lock_file.flush()

        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def load_balance_subjects(limit_users=None):
    payload = load_actor_user_links()
    links = payload.get("links") or {}

    subjects = []

    for record in links.values():
        pseudonym = str(record.get("pseudonym") or "").strip()
        user_id = str(record.get("user_id") or "").strip()

        if not pseudonym or not user_id:
            continue

        subjects.append({
            "pseudonym": pseudonym,
            "user_id": user_id,
        })

    subjects.sort(key=lambda item: item["pseudonym"])

    if limit_users is not None:
        subjects = subjects[:limit_users]

    return subjects


def build_windows(date_from, date_to, max_windows=None):
    start = _parse_day(date_from)
    end = _parse_day(date_to)

    windows = []
    cursor = start

    while cursor <= end:
        requested_to = min(
            cursor + timedelta(days=WINDOW_DATE_TO_OFFSET_DAYS),
            end,
        )

        windows.append({
            "window_date_from": _iso(cursor),
            "window_date_to": _iso(requested_to),
        })

        # Continuité BAL-HIST002B :
        # la fenêtre retourne un point supplémentaire à date_to + 1.
        # La suivante repart donc de date_to + 1, ce qui crée
        # une jonction exactement identique côté valeurs retournées.
        cursor = requested_to + timedelta(days=1)

        if max_windows is not None and len(windows) >= max_windows:
            break

    return windows


def fetch_daily_balance_window(
    *,
    base_url,
    session_token,
    user_id,
    window_date_from,
    window_date_to,
    max_attempts=3,
    request_pause_seconds=0.0,
):
    path = (
        f"/{quote(str(user_id), safe='')}/accounts/"
        f"{ACCOUNT_TYPE}/balances-history"
    )

    params = [
        ("datePeriod", window_date_from),
        ("datePeriod", window_date_to),
        ("intervalUnit", INTERVAL_UNIT),
        ("intervalCount", str(INTERVAL_COUNT)),
    ]

    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                f"{base_url}{path}",
                headers={
                    "Session-Token": session_token,
                    "Accept": "application/json",
                },
                params=params,
                timeout=90,
            )

            if response.status_code == 200:
                payload = response.json()
                balances = payload.get("balances") or []
                interval = payload.get("interval") or {}

                if interval.get("field") != "days" or interval.get("amount") not in (1, "1"):
                    raise RuntimeError(
                        f"Intervalle inattendu : {interval!r}"
                    )

                if request_pause_seconds:
                    time.sleep(request_pause_seconds)

                return {
                    "status": "ok",
                    "attempts": attempt,
                    "balances": balances,
                    "interval": interval,
                }

            if response.status_code in (429, 500, 502, 503, 504):
                last_error = (
                    f"HTTP {response.status_code} sur balances-history "
                    f"{window_date_from}→{window_date_to}"
                )
                time.sleep(min(2 ** attempt, 20))
                continue

            body = response.text.strip()
            raise RuntimeError(
                f"HTTP {response.status_code} sur balances-history "
                f"{window_date_from}→{window_date_to}: {body[:400]}"
            )

        except Exception as exc:
            last_error = str(exc)

            if attempt < max_attempts:
                time.sleep(min(2 ** attempt, 20))
                continue

    return {
        "status": "error",
        "attempts": max_attempts,
        "error": _short_error(last_error),
        "balances": [],
    }


def window_already_success(pseudonym, window_date_from, window_date_to):
    conn = _db()
    cur = conn.cursor()

    row = cur.execute("""
        SELECT status
        FROM cyclos_individual_daily_balance_windows
        WHERE pseudonym = ?
          AND window_date_from = ?
          AND window_date_to = ?
        LIMIT 1
    """, (
        pseudonym,
        window_date_from,
        window_date_to,
    )).fetchone()

    conn.close()

    return bool(row and row[0] == "success")


def mark_window_running(pseudonym, window_date_from, window_date_to):
    conn = _db()
    cur = conn.cursor()
    now = _utc_now_iso()

    cur.execute("""
        INSERT INTO cyclos_individual_daily_balance_windows (
            pseudonym,
            window_date_from,
            window_date_to,
            status,
            attempts,
            last_run_at
        ) VALUES (?, ?, ?, 'running', 0, ?)
        ON CONFLICT(pseudonym, window_date_from, window_date_to) DO UPDATE SET
            status='running',
            last_run_at=excluded.last_run_at
    """, (
        pseudonym,
        window_date_from,
        window_date_to,
        now,
    ))

    conn.commit()
    conn.close()


def store_window_success(
    *,
    pseudonym,
    window_date_from,
    window_date_to,
    balances,
    attempts,
):
    conn = _db()
    cur = conn.cursor()
    fetched_at = _utc_now_iso()

    try:
        cur.execute("BEGIN")

        points_stored = 0

        for point in balances:
            balance_date_raw = point.get("date")
            amount_raw = point.get("amount")

            if not balance_date_raw:
                continue

            balance_date = str(balance_date_raw)[:10]
            balance = _balance_float(amount_raw)

            cur.execute("""
                INSERT INTO cyclos_individual_daily_balances (
                    pseudonym,
                    balance_date,
                    balance,
                    fetched_at,
                    source
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(pseudonym, balance_date) DO UPDATE SET
                    balance=excluded.balance,
                    fetched_at=excluded.fetched_at,
                    source=excluded.source
            """, (
                pseudonym,
                balance_date,
                balance,
                fetched_at,
                SOURCE,
            ))
            points_stored += 1

        cur.execute("""
            INSERT INTO cyclos_individual_daily_balance_windows (
                pseudonym,
                window_date_from,
                window_date_to,
                status,
                points_received,
                points_stored,
                attempts,
                last_error,
                last_run_at,
                fetched_at
            ) VALUES (?, ?, ?, 'success', ?, ?, ?, NULL, ?, ?)
            ON CONFLICT(pseudonym, window_date_from, window_date_to) DO UPDATE SET
                status='success',
                points_received=excluded.points_received,
                points_stored=excluded.points_stored,
                attempts=excluded.attempts,
                last_error=NULL,
                last_run_at=excluded.last_run_at,
                fetched_at=excluded.fetched_at
        """, (
            pseudonym,
            window_date_from,
            window_date_to,
            len(balances),
            points_stored,
            attempts,
            fetched_at,
            fetched_at,
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "points_received": len(balances),
        "points_stored": points_stored,
    }


def store_window_error(
    *,
    pseudonym,
    window_date_from,
    window_date_to,
    attempts,
    error,
):
    conn = _db()
    cur = conn.cursor()
    now = _utc_now_iso()

    cur.execute("""
        INSERT INTO cyclos_individual_daily_balance_windows (
            pseudonym,
            window_date_from,
            window_date_to,
            status,
            points_received,
            points_stored,
            attempts,
            last_error,
            last_run_at,
            fetched_at
        ) VALUES (?, ?, ?, 'error', 0, 0, ?, ?, ?, NULL)
        ON CONFLICT(pseudonym, window_date_from, window_date_to) DO UPDATE SET
            status='error',
            points_received=0,
            points_stored=0,
            attempts=excluded.attempts,
            last_error=excluded.last_error,
            last_run_at=excluded.last_run_at
    """, (
        pseudonym,
        window_date_from,
        window_date_to,
        attempts,
        _short_error(error),
        now,
    ))

    conn.commit()
    conn.close()


def run_daily_balance_backfill(
    *,
    date_from,
    date_to,
    limit_users=None,
    max_windows_per_user=None,
    request_pause_seconds=0.0,
    progress_callback=None,
):
    subjects = load_balance_subjects(limit_users=limit_users)
    windows = build_windows(
        date_from=date_from,
        date_to=date_to,
        max_windows=max_windows_per_user,
    )

    base_url = current_app.config["CYCLOS_BASE_URL"].rstrip("/")
    session_token = create_session_token()

    total_candidate_windows = len(subjects) * len(windows)

    result = {
        "subjects_total": len(subjects),
        "windows_per_subject": len(windows),
        "candidate_windows_total": total_candidate_windows,
        "windows_success": 0,
        "windows_error": 0,
        "windows_skipped_success": 0,
        "points_received": 0,
        "points_stored": 0,
    }

    for subject_index, subject in enumerate(subjects, start=1):
        pseudonym = subject["pseudonym"]
        user_id = subject["user_id"]

        if progress_callback:
            progress_callback({
                "stage": "subject_start",
                "subject_index": subject_index,
                "subjects_total": len(subjects),
                "pseudonym": pseudonym,
            })

        for window_index, window in enumerate(windows, start=1):
            window_from = window["window_date_from"]
            window_to = window["window_date_to"]

            if window_already_success(pseudonym, window_from, window_to):
                result["windows_skipped_success"] += 1

                if progress_callback:
                    progress_callback({
                        "stage": "window_skipped",
                        "subject_index": subject_index,
                        "subjects_total": len(subjects),
                        "window_index": window_index,
                        "windows_per_subject": len(windows),
                        "pseudonym": pseudonym,
                        "window_date_from": window_from,
                        "window_date_to": window_to,
                    })
                continue

            mark_window_running(pseudonym, window_from, window_to)

            fetch_result = fetch_daily_balance_window(
                base_url=base_url,
                session_token=session_token,
                user_id=user_id,
                window_date_from=window_from,
                window_date_to=window_to,
                request_pause_seconds=request_pause_seconds,
            )

            if fetch_result["status"] == "ok":
                storage = store_window_success(
                    pseudonym=pseudonym,
                    window_date_from=window_from,
                    window_date_to=window_to,
                    balances=fetch_result["balances"],
                    attempts=fetch_result["attempts"],
                )

                result["windows_success"] += 1
                result["points_received"] += storage["points_received"]
                result["points_stored"] += storage["points_stored"]

                if progress_callback:
                    progress_callback({
                        "stage": "window_success",
                        "subject_index": subject_index,
                        "subjects_total": len(subjects),
                        "window_index": window_index,
                        "windows_per_subject": len(windows),
                        "pseudonym": pseudonym,
                        "window_date_from": window_from,
                        "window_date_to": window_to,
                        "points_received": storage["points_received"],
                        "points_stored": storage["points_stored"],
                        "global_windows_success": result["windows_success"],
                        "global_windows_error": result["windows_error"],
                        "global_windows_skipped": result["windows_skipped_success"],
                    })
            else:
                store_window_error(
                    pseudonym=pseudonym,
                    window_date_from=window_from,
                    window_date_to=window_to,
                    attempts=fetch_result.get("attempts") or 0,
                    error=fetch_result.get("error"),
                )

                result["windows_error"] += 1

                if progress_callback:
                    progress_callback({
                        "stage": "window_error",
                        "subject_index": subject_index,
                        "subjects_total": len(subjects),
                        "window_index": window_index,
                        "windows_per_subject": len(windows),
                        "pseudonym": pseudonym,
                        "window_date_from": window_from,
                        "window_date_to": window_to,
                        "error": fetch_result.get("error"),
                        "global_windows_success": result["windows_success"],
                        "global_windows_error": result["windows_error"],
                        "global_windows_skipped": result["windows_skipped_success"],
                    })

    return result
