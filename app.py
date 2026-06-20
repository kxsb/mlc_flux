from server import create_app
from flask import render_template, request, jsonify

# AUTH_FLOW001_PUBLIC_SELECTOR
PUBLIC_AUTH_PATH_PREFIXES = (
    "/",
    "/login",
    "/logout",
    "/static/",
    "/favicon.ico",
    "/api/mlc-instances",
    "/api/current-mlc",
    "/api/mlc/current",
    "/api/version",
)

def is_public_auth_path(path):
    """Return True for routes visible before authentication."""
    if path == "/":
        return True
    return any(path == prefix or path.startswith(prefix) for prefix in PUBLIC_AUTH_PATH_PREFIXES if prefix != "/")

from server.services.monetary_indicators_adaptive import get_adaptive_monetary_indicators
import os

app = create_app()


@app.route("/")
def mlc_select():
    return render_template("mlc_select.html")


@app.route("/app")
def home():
    return render_template("index.html")


@app.route("/transactions-live")
def transactions_live():
    return render_template("transactions_live.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8002, debug=False)


@app.route("/api/monetary-indicators")
def api_monetary_indicators():
    """
    Indicateurs adaptatifs de masse monétaire / garantie.

    Contrat commun multi-MLC :
    - Gonette : source Odoo comptable si disponible.
    - Graine : source Cyclos technique cible, proxy par flux en attendant.
    """
    mlc_id = request.args.get("mlc") or os.environ.get("MLCFLUX_DEFAULT_MLC_ID") or "gonette"

    try:
        result = get_adaptive_monetary_indicators(mlc_id)
        return jsonify(result)
    except Exception as exc:
        return jsonify({
            "mlc_id": mlc_id,
            "source": "error",
            "available": False,
            "items": [],
            "latest": None,
            "warnings": [str(exc)],
        }), 500



# VERSION_UI001_RELEASE_NOTES_API
MLCFLUX_APP_VERSION = "v1.0.6"
MLCFLUX_RELEASE_LABEL = "MLCFlux bêta v1.0.6 multi — juin 2026"


def _extract_changelog_sections(markdown_text):
    import re

    text = str(markdown_text or "").replace("\r\n", "\n")
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE))
    sections = []

    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        markdown = text[start:end].strip()

        version_match = re.search(r"\b[vV]?(\d+\.\d+\.\d+)\b", title)
        version = f"v{version_match.group(1)}" if version_match else None

        sections.append({
            "title": title,
            "version": version,
            "markdown": markdown,
        })

    return sections


@app.route("/api/version")
def api_version():
    """Expose la version courante et les notes de version lues depuis CHANGELOG.md."""
    from pathlib import Path

    changelog_path = Path(__file__).resolve().parent / "CHANGELOG.md"

    try:
        changelog_markdown = changelog_path.read_text(encoding="utf-8")
    except Exception:
        changelog_markdown = ""

    sections = _extract_changelog_sections(changelog_markdown)
    current_section = next(
        (
            section for section in sections
            if section.get("version") == MLCFLUX_APP_VERSION
        ),
        sections[0] if sections else {
            "title": MLCFLUX_APP_VERSION,
            "version": MLCFLUX_APP_VERSION,
            "markdown": "",
        },
    )

    return jsonify({
        "version": MLCFLUX_APP_VERSION,
        "label": MLCFLUX_RELEASE_LABEL,
        "current": current_section,
        "sections": sections,
        "changelog_available": bool(changelog_markdown.strip()),
    })


# MLC_SELECT_MASS002_BACKEND_PUBLIC_SUMMARY
@app.after_request
def mlc_select_mass002_harmonize_instance_public_summary(response):
    """Harmonise la fiche publique des instances multi-MLC.

    Objectif :
    - exposer une nomenclature commune "Masse monétaire suivie" ;
    - afficher la masse totale suivie quand numérique + papier sont disponibles ;
    - permettre un override transitoire pour les instances dont le papier existe
      dans les KPI mais n'est pas encore remonté nativement par /api/mlc-instances.
    """
    try:
        from flask import request
        import json
        from pathlib import Path

        if request.path.rstrip("/") != "/api/mlc-instances":
            return response

        if not response.is_json:
            return response

        payload = response.get_json(silent=True)
        if not isinstance(payload, dict):
            return response

        instances = payload.get("instances")
        if not isinstance(instances, list):
            return response

        override_path = (
            Path(__file__).resolve().parent
            / "server"
            / "data"
            / "mlc_instance_public_summary_overrides.json"
        )

        overrides = {}
        if override_path.exists():
            try:
                overrides = json.loads(override_path.read_text(encoding="utf-8"))
            except Exception:
                overrides = {}

        def to_float(value):
            if value is None or value == "":
                return None
            if isinstance(value, (int, float)):
                return float(value)
            try:
                return float(str(value).replace(" ", "").replace(",", "."))
            except Exception:
                return None

        for instance in instances:
            if not isinstance(instance, dict):
                continue

            instance_id = str(instance.get("id") or "").strip()
            public_summary = instance.get("public_summary")

            if not isinstance(public_summary, dict):
                continue

            instance_override = overrides.get(instance_id) or {}
            summary_override = instance_override.get("public_summary") or {}

            if isinstance(summary_override, dict):
                public_summary.update(summary_override)

            numeric_value = to_float(public_summary.get("circulating_money_numeric_value"))
            paper_value = to_float(public_summary.get("circulating_money_paper_value"))

            if numeric_value is not None and paper_value is not None:
                public_summary["circulating_money"] = round(numeric_value + paper_value, 2)
                public_summary["circulating_money_label"] = "Masse monétaire suivie"

                if not public_summary.get("circulating_money_quality"):
                    public_summary["circulating_money_quality"] = "numeric_plus_paper_mass"

            # Harmonisation sémantique : quand une masse suivie est disponible,
            # la carte d'entrée parle de masse monétaire, pas de sous-composante.
            if public_summary.get("circulating_money") is not None:
                public_summary["circulating_money_label"] = "Masse monétaire suivie"

        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        response.set_data(body)
        response.content_type = "application/json; charset=utf-8"
        response.content_length = len(body.encode("utf-8"))
        return response

    except Exception:
        # Ne jamais casser l'API de sélection à cause d'une harmonisation d'affichage.
        return response

