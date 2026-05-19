import json
from datetime import UTC, datetime

from server.database import get_connection


PILOTAGE_REUSE_YEARLY_SERIES_KEY = "reuse_yearly"
PILOTAGE_LM3_YEARLY_SERIES_KEY = "lm3_yearly"


def load_pilotage_yearly_cache_items(series_key: str) -> list[dict]:
    """
    Lit une série annuelle matérialisée.

    Retourne [] si la série n'est pas encore peuplée.
    Les routes conservent alors un fallback de recalcul live.
    """
    conn = get_connection()
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT item_json
        FROM pilotage_yearly_cache
        WHERE series_key = ?
        ORDER BY year ASC
    """, (series_key,)).fetchall()

    conn.close()

    return [
        json.loads(row["item_json"])
        for row in rows
    ]


def replace_pilotage_yearly_cache_series(
    series_key: str,
    items: list[dict],
    *,
    computed_at: str | None = None,
) -> dict:
    """
    Remplace intégralement une série annuelle matérialisée.
    """
    computed_at = computed_at or datetime.now(UTC).isoformat()

    normalized_rows = []

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Chaque item de cache annuel doit être un dictionnaire.")

        try:
            year = int(item["year"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Item annuel invalide, année absente ou non entière : {item!r}"
            ) from exc

        normalized_rows.append((
            series_key,
            year,
            json.dumps(item, ensure_ascii=False, sort_keys=True),
            computed_at,
        ))

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "DELETE FROM pilotage_yearly_cache WHERE series_key = ?",
            (series_key,),
        )

        cur.executemany("""
            INSERT INTO pilotage_yearly_cache (
                series_key,
                year,
                item_json,
                computed_at
            ) VALUES (?, ?, ?, ?)
        """, normalized_rows)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "series_key": series_key,
        "items_written": len(normalized_rows),
        "years": [row[1] for row in normalized_rows],
        "computed_at": computed_at,
    }
