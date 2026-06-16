from flask import Blueprint, jsonify, request

from server.services.info_content import (
    create_info_page,
    get_default_info_page_slug,
    list_info_pages,
    read_info_page,
    update_info_page_metadata,
    write_info_page,
)


info_content_bp = Blueprint("info_content", __name__)

MAX_INFO_MARKDOWN_LENGTH = 500_000


@info_content_bp.route("/api/info-content", methods=["GET"])
def get_info_content():
    page_slug = request.args.get("page") or get_default_info_page_slug()

    try:
        page, markdown = read_info_page(page_slug)
    except KeyError:
        return jsonify({
            "error": f"Fiche de documentation inconnue : {page_slug}"
        }), 404

    return jsonify({
        "pages": list_info_pages(),
        "page": page,
        "markdown": markdown,
    })


@info_content_bp.route("/api/info-search-index", methods=["GET"])
def get_info_search_index():
    items = []

    for page in list_info_pages():
        page_data, markdown = read_info_page(page["slug"])
        items.append({
            "page": page_data,
            "markdown": markdown,
        })

    return jsonify({
        "items": items,
    })


@info_content_bp.route("/api/info-content", methods=["POST"])
def save_info_content():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "Corps JSON invalide."
        }), 400

    page_slug = payload.get("page")
    markdown = payload.get("markdown")

    if not isinstance(page_slug, str) or not page_slug.strip():
        return jsonify({
            "error": "Le champ 'page' doit être une fiche de documentation valide."
        }), 400

    if not isinstance(markdown, str):
        return jsonify({
            "error": "Le champ 'markdown' doit être une chaîne."
        }), 400

    if len(markdown) > MAX_INFO_MARKDOWN_LENGTH:
        return jsonify({
            "error": (
                "Le contenu Markdown est trop volumineux "
                f"(maximum {MAX_INFO_MARKDOWN_LENGTH} caractères)."
            )
        }), 413

    try:
        page = write_info_page(page_slug, markdown)
    except KeyError:
        return jsonify({
            "error": f"Fiche de documentation inconnue : {page_slug}"
        }), 404

    return jsonify({
        "status": "ok",
        "message": f"Fiche « {page['title']} » enregistrée.",
        "page": page,
        "length": len(markdown),
    })


@info_content_bp.route("/api/info-pages/<page_slug>/metadata", methods=["POST"])
def update_info_page_metadata_route(page_slug):
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "Corps JSON invalide."
        }), 400

    try:
        page = update_info_page_metadata(
            page_slug=page_slug,
            title=payload.get("title"),
            kicker=payload.get("kicker"),
            summary=payload.get("summary"),
        )
    except ValueError as exc:
        return jsonify({
            "error": str(exc)
        }), 400
    except KeyError:
        return jsonify({
            "error": f"Fiche de documentation inconnue : {page_slug}"
        }), 404

    return jsonify({
        "status": "ok",
        "message": f"Métadonnées de la fiche « {page['title']} » enregistrées.",
        "page": page,
        "pages": list_info_pages(),
    })


@info_content_bp.route("/api/info-pages", methods=["POST"])
def create_info_page_route():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "Corps JSON invalide."
        }), 400

    try:
        page, markdown = create_info_page(
            title=payload.get("title"),
            kicker=payload.get("kicker"),
            summary=payload.get("summary"),
        )
    except ValueError as exc:
        return jsonify({
            "error": str(exc)
        }), 400

    return jsonify({
        "status": "ok",
        "message": f"Carte « {page['title']} » créée.",
        "page": page,
        "pages": list_info_pages(),
        "markdown": markdown,
    }), 201
