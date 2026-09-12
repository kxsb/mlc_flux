from html import unescape
import re
from flask import Blueprint, jsonify, request
from server.database import get_connection
from server.analytics import (
    compute_global_stats,
    get_available_years,
    get_available_period_bounds,
    compute_network_data,
    compute_professionals_ranking,
    get_professional_detail,
    get_professionals_map_data,
    compute_zip_territorial_activity,
    compute_sector_activity,
    compute_stats_charts,
)
from server.utils.sync_auth import require_sync_token
from server.routes.sync import _format_sync_message

legacy_api_bp = Blueprint("legacy_api", __name__)


@legacy_api_bp.route("/api/health", methods=["GET"])
def legacy_health():
    return jsonify({"status": "ok"})


@legacy_api_bp.route("/api/years", methods=["GET"])
def years():
    return jsonify(get_available_years())


@legacy_api_bp.route("/api/period-bounds", methods=["GET"])
def period_bounds():
    return jsonify(get_available_period_bounds())


@legacy_api_bp.route("/api/stats", methods=["GET"])
def stats():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")
    return jsonify(compute_global_stats(start=start, end=end, year=year))



def _professional_display_label(professional_ref, metadata):
    display_name = metadata.get("display_name") if metadata else None

    if professional_ref and display_name:
        return f"{professional_ref} - {display_name}"

    return professional_ref or display_name


def _enrich_professional_identity_dict(item, display_index):
    if not isinstance(item, dict):
        return item

    # Ne jamais modifier les endpoints d'arêtes réseau.
    # source/target doivent rester des identifiants stables Pxxxx.
    is_edge_like = "source" in item and "target" in item
    if is_edge_like:
        return item

    candidate_values = [
        item.get("professional_ref"),
        item.get("ref"),
        item.get("id"),
        item.get("label"),
        item.get("name"),
        item.get("Professionnel"),
    ]

    professional_ref = None
    for value in candidate_values:
        professional_ref = _extract_professional_ref_from_label(value)
        if professional_ref:
            break

    if not professional_ref:
        return item

    metadata = display_index.get(professional_ref)
    if not metadata:
        return item

    display_name = metadata.get("display_name")
    display_label = _professional_display_label(professional_ref, metadata)

    item["professional_ref"] = professional_ref
    item["display_name"] = display_name
    item["display_label"] = display_label

    # Les graphes gardent id/source/target en Pxxxx, mais les libellés lisibles
    # peuvent porter le nom réel.
    if item.get("label") in (None, "", professional_ref):
        item["label"] = display_label

    if item.get("name") in (None, "", professional_ref):
        item["name"] = display_label

    if item.get("title") in (None, "", professional_ref):
        item["title"] = display_label

    item["search_text"] = " ".join(
        str(value)
        for value in [
            professional_ref,
            display_name,
            metadata.get("legal_name"),
            metadata.get("industry_name"),
            metadata.get("short_description"),
            metadata.get("keywords"),
            metadata.get("zip"),
            metadata.get("city"),
        ]
        if value
    )

    return item


def _enrich_professional_payload_for_display(payload):
    display_index = _load_professional_display_index()

    if not display_index:
        return payload

    def walk(value):
        if isinstance(value, list):
            return [walk(item) for item in value]

        if isinstance(value, dict):
            enriched = {
                key: walk(child)
                for key, child in value.items()
            }

            data = enriched.get("data")
            if isinstance(data, dict):
                enriched["data"] = _enrich_professional_identity_dict(
                    data,
                    display_index,
                )

            return _enrich_professional_identity_dict(
                enriched,
                display_index,
            )

        return value

    return walk(payload)


@legacy_api_bp.route("/api/network", methods=["GET"])
def network():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")

    include_operators_raw = str(
        request.args.get("include_operators", default="", type=str) or ""
    ).strip().lower()

    include_operators = include_operators_raw in {
        "1",
        "true",
        "yes",
        "on",
    }

    payload = compute_network_data(
        start=start,
        end=end,
        year=year,
        include_operators=include_operators,
    )
    return jsonify(_enrich_professional_payload_for_display(payload))



def _clean_professional_display_value(value):
    if value is None:
        return None

    cleaned = unescape(str(value)).replace("\ufeff", "").strip()
    return cleaned or None


def _extract_professional_ref_from_label(value):
    if value is None:
        return None

    match = re.search(r"\bP\d{4,}\b", str(value))
    if match:
        return match.group(0)

    match = re.search(r"\bP\d+\b", str(value))
    if match:
        return match.group(0)

    return None


def _load_professional_display_index():
    conn = get_connection()
    cur = conn.cursor()

    try:
        rows = cur.execute("""
            SELECT
                professional_ref,
                display_name,
                legal_name,
                industry_name,
                short_description,
                keywords,
                zip,
                city,
                actor_type_internal,
                cyclos_group_set
            FROM professional_enrichment
        """).fetchall()
    except Exception:
        conn.close()
        return {}
    finally:
        try:
            conn.close()
        except Exception:
            pass

    index = {}

    for row in rows:
        ref = row["professional_ref"]
        if not ref:
            continue

        actor_type = _clean_professional_display_value(row["actor_type_internal"])
        actor_type_lower = actor_type.lower() if actor_type else ""

        # Évite d'afficher des noms de particuliers si professional_enrichment
        # contient aussi des comptes particuliers, cas observé côté Graine.
        if actor_type_lower in {"moncompte", "comptebillets"}:
            continue

        display_name = (
            _clean_professional_display_value(row["display_name"])
            or _clean_professional_display_value(row["legal_name"])
        )

        if not display_name:
            continue

        index[ref] = {
            "display_name": display_name,
            "legal_name": _clean_professional_display_value(row["legal_name"]),
            "industry_name": _clean_professional_display_value(row["industry_name"]),
            "short_description": _clean_professional_display_value(row["short_description"]),
            "keywords": _clean_professional_display_value(row["keywords"]),
            "zip": _clean_professional_display_value(row["zip"]),
            "city": _clean_professional_display_value(row["city"]),
            "actor_type_internal": actor_type,
            "cyclos_group_set": _clean_professional_display_value(row["cyclos_group_set"]),
        }

    return index


def _enrich_professional_rows_for_display(rows):
    if not rows:
        return rows

    display_index = _load_professional_display_index()
    if not display_index:
        return rows

    enriched_rows = []

    for original_row in rows:
        row = dict(original_row)
        professional_label = row.get("Professionnel")
        professional_ref = (
            row.get("Référence pro")
            or row.get("professional_ref")
            or _extract_professional_ref_from_label(professional_label)
        )

        metadata = display_index.get(professional_ref)
        if not metadata:
            enriched_rows.append(row)
            continue

        display_name = metadata["display_name"]
        display_label = f"{professional_ref} - {display_name}"

        row["Référence pro"] = professional_ref
        row["Nom professionnel"] = display_name
        row["Libellé professionnel"] = display_label

        # Champ historique utilisé par le tableau et la recherche front.
        row["Professionnel"] = display_label

        if metadata.get("legal_name"):
            row["Raison sociale"] = metadata["legal_name"]

        if metadata.get("industry_name") and not row.get("Secteur d’activité"):
            row["Secteur d’activité"] = metadata["industry_name"]

        if metadata.get("zip") and not row.get("Code postal"):
            row["Code postal"] = metadata["zip"]

        if metadata.get("city"):
            row["Ville"] = metadata["city"]

        row["Recherche professionnel"] = " ".join(
            str(value)
            for value in [
                professional_ref,
                display_name,
                metadata.get("legal_name"),
                metadata.get("industry_name"),
                metadata.get("short_description"),
                metadata.get("keywords"),
                metadata.get("zip"),
                metadata.get("city"),
            ]
            if value
        )

        enriched_rows.append(row)

    return enriched_rows


@legacy_api_bp.route("/api/pros", methods=["GET"])
def pros():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")
    rows = compute_professionals_ranking(start=start, end=end, year=year)
    return jsonify(_enrich_professional_rows_for_display(rows))


@legacy_api_bp.route("/api/professionals-map", methods=["GET"])
def professionals_map():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")

    return jsonify(
        get_professionals_map_data(
            start=start,
            end=end,
            year=year,
        )
    )


@legacy_api_bp.route("/api/territories/zip", methods=["GET"])
def territories_zip():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")

    return jsonify(
        compute_zip_territorial_activity(
            start=start,
            end=end,
            year=year,
        )
    )


@legacy_api_bp.route("/api/sectors/activity", methods=["GET"])
def sectors_activity():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")
    sector_mode = request.args.get("sector_mode") or request.args.get("mode") or "internal"

    return jsonify(
        compute_sector_activity(
            start=start,
            end=end,
            year=year,
            sector_mode=sector_mode,
        )
    )


@legacy_api_bp.route("/api/professionnels", methods=["GET"])
def professionnels():
    ranking = compute_professionals_ranking()
    pros = [row["Professionnel"] for row in ranking if row.get("Professionnel")]
    return jsonify(pros)


@legacy_api_bp.route("/api/pro/<num_professionnel>", methods=["GET"])
def pro_detail(num_professionnel):
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")

    result = get_professional_detail(
        num_professionnel,
        start=start,
        end=end,
        year=year,
    )

    if result is None:
        return jsonify({"error": "Professionnel introuvable"}), 404

    return jsonify(result)


@legacy_api_bp.route("/api/stats_charts", methods=["GET"])
def stats_charts():
    year = request.args.get("year", default=None, type=int)
    start = request.args.get("start")
    end = request.args.get("end")

    result = compute_stats_charts(start=start, end=end, year=year)

    # compat ancienne version frontend
    if "weekly" in result and "weekly_avg" not in result:
        result["weekly_avg"] = result["weekly"]

    return jsonify(result)


@legacy_api_bp.route("/api/reload", methods=["POST"])
def reload_data():
    auth_error = require_sync_token()
    if auth_error is not None:
        return auth_error

    from server.sync_transactions import run_sync

    result = run_sync()
    fetched = result["fetched"]
    written = result["written"]

    return jsonify({
        "status": "ok",
        "rows": written,
        "fetched": fetched,
        "written": written,
        # Alias de compatibilité pour d'éventuels appelants historiques.
        "inserted": written,
        "message": _format_sync_message(fetched, written),
    })
