from server import create_app
from flask import render_template, request, jsonify, redirect

from server.services.monetary_indicators_adaptive import get_adaptive_monetary_indicators
import os

app = create_app()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/app")
def legacy_app_entrypoint():
    return redirect("/")


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
    from server.mlc_context import get_default_mlc_id

    mlc_id = get_default_mlc_id()

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
MLCFLUX_APP_VERSION = "v1.0.7"
MLCFLUX_RELEASE_LABEL = "MLCFlux bêta v1.0.7 multi — juin 2026"


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
