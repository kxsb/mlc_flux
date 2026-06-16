import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INFO_PAGES_DIR = DATA_DIR / "info_pages"
CUSTOM_INFO_PAGES_FILE = DATA_DIR / "info_pages_custom.json"
INFO_PAGE_OVERRIDES_FILE = DATA_DIR / "info_pages_overrides.json"
LEGACY_INFO_MARKDOWN_FILE = DATA_DIR / "info.md"

INFO_PAGES = (
    {
        "slug": "cadre-general",
        "filename": "01_cadre_general.md",
        "kicker": "Fondations",
        "title": "Cadre général & sources",
        "summary": (
            "Ce que MLCFlux cherche à observer, les différences entre flux, "
            "stocks et opérations de gestion, les sources utilisées et les règles temporelles."
        ),
    },
    {
        "slug": "acteurs-et-activite",
        "filename": "02_acteurs_et_activite.md",
        "kicker": "Doctrine analytique",
        "title": "Acteurs, conventions & activité économique",
        "summary": (
            "Les familles P, U, UD, T, les comptes opérateurs, "
            "et la définition centrale de l’activité économique."
        ),
    },
    {
        "slug": "statistiques-globales",
        "filename": "03_statistiques_globales.md",
        "kicker": "Lecture des indicateurs",
        "title": "Statistiques globales",
        "summary": (
            "Les onglets d’activité, d’alimentations, d’opérations techniques "
            "et de masse monétaire, avec les formules associées."
        ),
    },
    {
        "slug": "pilotage-monetaire",
        "filename": "04_pilotage_monetaire.md",
        "kicker": "Analyse économique",
        "title": "Pilotage monétaire",
        "summary": (
            "Circulation, garanties, détention, dormance "
            "et rapprochements entre stocks et flux."
        ),
    },
    {
        "slug": "professionnels-et-fiches",
        "filename": "05_professionnels_et_fiches.md",
        "kicker": "Usage du réseau",
        "title": "Professionnels, particuliers & fiches",
        "summary": (
            "Les indicateurs centrés sur les professionnels, "
            "les fonds de commerce Gonette, les dynamiques et les perspectives."
        ),
    },
    {
        "slug": "cartographie-territoires-secteurs",
        "filename": "06_cartographie_territoires_secteurs.md",
        "kicker": "Spatialisation",
        "title": "Cartographie, territoires & secteurs",
        "summary": (
            "Les cartes de clusters, l’analyse territoriale "
            "et les lectures sectorielles."
        ),
    },
    {
        "slug": "reemploi-et-multiplicateurs",
        "filename": "07_reemploi_et_multiplicateurs.md",
        "kicker": "Réemploi",
        "title": "Circulation, réemploi & multiplicateurs",
        "summary": (
            "Taux d’émission sur recettes, propension de réemploi, "
            "multiplicateur interne et LM3 estimé."
        ),
    },
    {
        "slug": "limites-glossaire-doctrine",
        "filename": "08_limites_glossaire_doctrine.md",
        "kicker": "Précautions",
        "title": "Limites, glossaire & doctrine",
        "summary": (
            "Les limites d’interprétation, les précautions méthodologiques, "
            "le glossaire et la doctrine analytique de synthèse."
        ),
    },
)

DEFAULT_INFO_PAGE_MARKDOWNS = {
    "cadre-general": """# Cadre général & sources

Cette fiche documente les fondations de la méthodologie MLCFlux.
""",
    "acteurs-et-activite": """# Acteurs, conventions & activité économique

Cette fiche documente les familles d’acteurs et la définition de l’activité économique.
""",
    "statistiques-globales": """# Statistiques globales

Cette fiche documente les indicateurs de la vue « Statistiques globales ».
""",
    "pilotage-monetaire": """# Pilotage monétaire

Cette fiche documente les indicateurs de pilotage monétaire.
""",
    "professionnels-et-fiches": """# Professionnels, particuliers & fiches

Cette fiche documente les analyses centrées sur les professionnels et leurs fiches.
""",
    "cartographie-territoires-secteurs": """# Cartographie, territoires & secteurs

Cette fiche documente les analyses spatiales et sectorielles.
""",
    "reemploi-et-multiplicateurs": """# Circulation, réemploi & multiplicateurs

Cette fiche documente les indicateurs de réemploi et les multiplicateurs.
""",
    "limites-glossaire-doctrine": """# Limites, glossaire & doctrine

Cette fiche rassemble les précautions d’interprétation et la doctrine analytique.
""",
}


def _public_page(page):
    return {
        "slug": page["slug"],
        "kicker": page["kicker"],
        "title": page["title"],
        "summary": page["summary"],
        "custom": bool(page.get("custom", False)),
    }


def _atomic_write_text(target_path, text, prefix):
    target_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        prefix=prefix,
        suffix=".tmp",
        dir=str(target_path.parent),
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as tmp_file:
            tmp_file.write(text)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        os.replace(tmp_path, target_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _atomic_write_markdown(target_path, markdown, prefix):
    _atomic_write_text(target_path, markdown, prefix=prefix)


def _atomic_write_json(target_path, payload, prefix):
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _atomic_write_text(target_path, text, prefix=prefix)


def _slugify(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_like = "".join(
        char for char in normalized
        if not unicodedata.combining(char)
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_like.lower()).strip("-")
    return slug


def _clean_required_text(value, field_name, max_length):
    cleaned = str(value or "").strip()

    if not cleaned:
        raise ValueError(f"Le champ « {field_name} » est obligatoire.")

    if len(cleaned) > max_length:
        raise ValueError(
            f"Le champ « {field_name} » dépasse {max_length} caractères."
        )

    return cleaned


def _clean_optional_text(value, fallback, max_length, field_name):
    cleaned = str(value or "").strip()

    if not cleaned:
        return fallback

    if len(cleaned) > max_length:
        raise ValueError(
            f"Le champ « {field_name} » dépasse {max_length} caractères."
        )

    return cleaned


def _normalize_custom_page(item):
    if not isinstance(item, dict):
        return None

    slug = str(item.get("slug") or "").strip()
    filename = str(item.get("filename") or "").strip()
    title = str(item.get("title") or "").strip()
    kicker = str(item.get("kicker") or "Documentation").strip()
    summary = str(item.get("summary") or "").strip()

    if not slug or not filename or not title:
        return None

    if "/" in filename or "\\" in filename:
        return None

    return {
        "slug": slug,
        "filename": filename,
        "kicker": kicker or "Documentation",
        "title": title,
        "summary": summary,
        "custom": True,
    }


def _load_custom_info_pages():
    if not CUSTOM_INFO_PAGES_FILE.exists():
        return []

    raw = json.loads(CUSTOM_INFO_PAGES_FILE.read_text(encoding="utf-8"))

    if not isinstance(raw, list):
        return []

    pages = []

    for item in raw:
        page = _normalize_custom_page(item)
        if page is not None:
            pages.append(page)

    return pages


def _write_custom_info_pages(pages):
    serialized = []

    for page in pages:
        serialized.append({
            "slug": page["slug"],
            "filename": page["filename"],
            "kicker": page["kicker"],
            "title": page["title"],
            "summary": page["summary"],
        })

    _atomic_write_json(
        CUSTOM_INFO_PAGES_FILE,
        serialized,
        prefix=".info_pages_custom_",
    )


def _load_info_page_overrides():
    if not INFO_PAGE_OVERRIDES_FILE.exists():
        return {}

    raw = json.loads(INFO_PAGE_OVERRIDES_FILE.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        return {}

    overrides = {}

    for slug, item in raw.items():
        if not isinstance(slug, str) or not isinstance(item, dict):
            continue

        cleaned = {}

        title = item.get("title")
        kicker = item.get("kicker")
        summary = item.get("summary")

        if isinstance(title, str) and title.strip():
            cleaned["title"] = title.strip()

        if isinstance(kicker, str) and kicker.strip():
            cleaned["kicker"] = kicker.strip()

        if isinstance(summary, str):
            cleaned["summary"] = summary.strip()

        if cleaned:
            overrides[slug] = cleaned

    return overrides


def _write_info_page_overrides(overrides):
    _atomic_write_json(
        INFO_PAGE_OVERRIDES_FILE,
        overrides,
        prefix=".info_pages_overrides_",
    )


def _apply_info_page_overrides(page):
    override = _load_info_page_overrides().get(page["slug"], {})

    return {
        **page,
        "title": override.get("title", page["title"]),
        "kicker": override.get("kicker", page["kicker"]),
        "summary": override.get("summary", page["summary"]),
    }


def _all_info_pages():
    standard_pages = [
        _apply_info_page_overrides(page)
        for page in INFO_PAGES
    ]

    return [
        *standard_pages,
        *_load_custom_info_pages(),
    ]


def _page_by_slug(page_slug):
    normalized = str(page_slug or "").strip()

    for page in _all_info_pages():
        if page["slug"] == normalized:
            return page

    raise KeyError(f"Fiche de documentation inconnue : {normalized}")


def get_default_info_page_slug():
    return INFO_PAGES[0]["slug"]


def ensure_info_pages():
    INFO_PAGES_DIR.mkdir(parents=True, exist_ok=True)

    for page in INFO_PAGES:
        page_path = INFO_PAGES_DIR / page["filename"]

        if page_path.exists():
            continue

        default_markdown = DEFAULT_INFO_PAGE_MARKDOWNS.get(
            page["slug"],
            f"# {page['title']}\n",
        )

        _atomic_write_markdown(
            page_path,
            default_markdown,
            prefix=f".{page['slug']}_",
        )

    for page in _load_custom_info_pages():
        page_path = INFO_PAGES_DIR / page["filename"]

        if page_path.exists():
            continue

        fallback_markdown = (
            f"# {page['title']}\n\n"
            "Cette fiche est à compléter.\n"
        )

        _atomic_write_markdown(
            page_path,
            fallback_markdown,
            prefix=f".{page['slug']}_",
        )


def list_info_pages():
    ensure_info_pages()
    return [_public_page(page) for page in _all_info_pages()]


def read_info_page(page_slug=None):
    ensure_info_pages()

    slug = page_slug or get_default_info_page_slug()
    page = _page_by_slug(slug)
    page_path = INFO_PAGES_DIR / page["filename"]

    return _public_page(page), page_path.read_text(encoding="utf-8")


def write_info_page(page_slug, markdown):
    if not isinstance(markdown, str):
        raise TypeError("Le contenu Markdown doit être une chaîne de caractères.")

    ensure_info_pages()

    page = _page_by_slug(page_slug)
    page_path = INFO_PAGES_DIR / page["filename"]

    _atomic_write_markdown(
        page_path,
        markdown,
        prefix=f".{page['slug']}_",
    )

    return _public_page(page)


def update_info_page_metadata(page_slug, title, kicker=None, summary=None):
    ensure_info_pages()

    page = _page_by_slug(page_slug)

    cleaned_title = _clean_required_text(title, "titre", 140)
    cleaned_kicker = _clean_optional_text(
        kicker,
        fallback="Documentation",
        max_length=80,
        field_name="sous-titre",
    )
    cleaned_summary = _clean_optional_text(
        summary,
        fallback="",
        max_length=600,
        field_name="résumé",
    )

    if page.get("custom", False):
        custom_pages = _load_custom_info_pages()
        updated_pages = []
        found = False

        for custom_page in custom_pages:
            if custom_page["slug"] == page["slug"]:
                custom_page = {
                    **custom_page,
                    "title": cleaned_title,
                    "kicker": cleaned_kicker,
                    "summary": cleaned_summary,
                }
                found = True

            updated_pages.append(custom_page)

        if not found:
            raise KeyError(f"Fiche personnalisée introuvable : {page_slug}")

        _write_custom_info_pages(updated_pages)
    else:
        overrides = _load_info_page_overrides()
        overrides[page["slug"]] = {
            "title": cleaned_title,
            "kicker": cleaned_kicker,
            "summary": cleaned_summary,
        }
        _write_info_page_overrides(overrides)

    updated_page = _page_by_slug(page["slug"])
    return _public_page(updated_page)


def create_info_page(title, kicker=None, summary=None):
    ensure_info_pages()

    cleaned_title = _clean_required_text(title, "titre", 140)
    cleaned_kicker = _clean_optional_text(
        kicker,
        fallback="Documentation",
        max_length=80,
        field_name="repère",
    )
    cleaned_summary = _clean_optional_text(
        summary,
        fallback="Nouvelle fiche méthodologique à compléter.",
        max_length=600,
        field_name="résumé",
    )

    base_slug = _slugify(cleaned_title) or "nouvelle-fiche"
    existing_slugs = {page["slug"] for page in _all_info_pages()}

    candidate_slug = base_slug
    suffix = 2

    while candidate_slug in existing_slugs:
        candidate_slug = f"{base_slug}-{suffix}"
        suffix += 1

    filename = f"custom_{candidate_slug}.md"

    page = {
        "slug": candidate_slug,
        "filename": filename,
        "kicker": cleaned_kicker,
        "title": cleaned_title,
        "summary": cleaned_summary,
        "custom": True,
    }

    markdown = (
        f"# {cleaned_title}\n\n"
        "> Nouvelle fiche créée depuis MLCFlux. "
        "Son contenu peut être édité directement ici.\n\n"
    )

    _atomic_write_markdown(
        INFO_PAGES_DIR / filename,
        markdown,
        prefix=f".{candidate_slug}_",
    )

    custom_pages = _load_custom_info_pages()
    custom_pages.append(page)
    _write_custom_info_pages(custom_pages)

    return _public_page(page), markdown
