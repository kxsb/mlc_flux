from __future__ import annotations

import argparse
import html
import re
import sqlite3
import sys
import time
from pathlib import Path

# ECON_UI005A_SCRIPT_PATH_BOOTSTRAP — permet aussi `python server/sync_naf_activity_labels.py`.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from datetime import datetime, UTC
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from server.database import get_db_path


INSEE_SUBCLASS_URL = "https://www.insee.fr/fr/metadonnees/nafr2/sousClasse/{code_lower}"
USER_AGENT = "MLCFlux/1.0 (+https://mlcflux.org; naf-label-enrichment)"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _normalize_naf_code(value: str | None) -> str:
    return str(value or "").strip().upper().replace(" ", "")


def _insee_code_path(code: str) -> str:
    return _normalize_naf_code(code).lower()


def _clean_label(value: str | None) -> str:
    cleaned = html.unescape(str(value or ""))
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" \t\r\n:-–—")


def _parse_label(code: str, page: str) -> str:
    escaped_code = re.escape(code)

    patterns = [
        rf"Sous-classe\s+{escaped_code}\s*:\s*([^<\n\r]+)",
        rf"Sous-classe\s+{escaped_code.lower()}\s*:\s*([^<\n\r]+)",
        rf"<h1[^>]*>\s*Sous-classe\s+{escaped_code}\s*:\s*(.*?)</h1>",
        rf"<title[^>]*>\s*nafr2-{escaped_code.replace('.', r'\.')}\s*-\s*(.*?)\s*</title>",
    ]

    for pattern in patterns:
        match = re.search(pattern, page, flags=re.IGNORECASE | re.DOTALL)
        if match:
            label = _clean_label(match.group(1))
            if label:
                # Retire d'éventuels suffixes de titre web.
                label = re.sub(r"\s*\|\s*Insee\s*$", "", label).strip()
                return label

    # Fallback plus large : cherche le titre principal indépendamment du code.
    match = re.search(
        r"<h1[^>]*>\s*Sous-classe\s+[0-9]{2}\.[0-9]{2}[A-Z]\s*:\s*(.*?)</h1>",
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        label = _clean_label(match.group(1))
        if label:
            return label

    return ""


def fetch_insee_label(code: str, *, timeout: int = 20) -> dict:
    normalized = _normalize_naf_code(code)
    url = INSEE_SUBCLASS_URL.format(code_lower=_insee_code_path(normalized))

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            page = raw.decode(charset, errors="replace")
    except HTTPError as exc:
        return {
            "code": normalized,
            "label": "",
            "status": f"http_{exc.code}",
            "source_url": url,
        }
    except URLError as exc:
        return {
            "code": normalized,
            "label": "",
            "status": f"url_error:{exc.reason}",
            "source_url": url,
        }
    except Exception as exc:
        return {
            "code": normalized,
            "label": "",
            "status": f"error:{type(exc).__name__}:{exc}",
            "source_url": url,
        }

    label = _parse_label(normalized, page)

    return {
        "code": normalized,
        "label": label,
        "status": "ok" if label else "parse_failed",
        "source_url": url,
    }


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS naf_activity_labels (
            naf_code TEXT PRIMARY KEY,
            naf_label TEXT NOT NULL,
            source_provider TEXT NOT NULL,
            source_url TEXT,
            status TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_naf_activity_labels_status
        ON naf_activity_labels(status)
        """
    )


def load_codes(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT UPPER(REPLACE(TRIM(naf_code), ' ', '')) AS naf_code
        FROM professional_economic_registry
        WHERE naf_code IS NOT NULL
          AND TRIM(naf_code) <> ''
        ORDER BY naf_code
        """
    ).fetchall()

    return [
        _normalize_naf_code(row["naf_code"])
        for row in rows
        if _normalize_naf_code(row["naf_code"])
    ]


def save_result(conn: sqlite3.Connection, result: dict) -> None:
    now = _now()

    conn.execute(
        """
        INSERT INTO naf_activity_labels (
            naf_code,
            naf_label,
            source_provider,
            source_url,
            status,
            fetched_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(naf_code) DO UPDATE SET
            naf_label = excluded.naf_label,
            source_provider = excluded.source_provider,
            source_url = excluded.source_url,
            status = excluded.status,
            updated_at = excluded.updated_at
        """,
        (
            result["code"],
            result.get("label") or "",
            "insee_nafr2_sousclasse_page",
            result.get("source_url"),
            result.get("status") or "unknown",
            now,
            now,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.08)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        ensure_table(conn)
        codes = load_codes(conn)
        if args.limit is not None:
            codes = codes[: args.limit]

        print(f"DB: {db_path}")
        print(f"codes_to_fetch: {len(codes)}")
        print(f"apply: {args.apply}")

        ok = 0
        failed = 0

        for index, code in enumerate(codes, start=1):
            result = fetch_insee_label(code)
            label = result.get("label") or ""
            status = result.get("status") or "unknown"

            print(f"{index:03d}/{len(codes):03d} {code} | {status} | {label}")

            if args.apply:
                save_result(conn, result)

            if label:
                ok += 1
            else:
                failed += 1

            if args.sleep and index < len(codes):
                time.sleep(args.sleep)

        if args.apply:
            conn.commit()

        print()
        print(f"ok: {ok}")
        print(f"failed: {failed}")

        if failed:
            print("WARN: certains libellés n'ont pas été résolus.", file=sys.stderr)

        return 0 if ok else 1

    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
