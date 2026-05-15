import json
import re
import secrets
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRENOMS_FILE = DATA_DIR / "prenoms.csv"
MAPPING_FILE = DATA_DIR / "user_mapping.json"

# Le dictionnaire de prénoms est volumineux et stable.
# On le charge une seule fois par processus, afin d'éviter
# de relire prenoms.csv à chaque utilisateur rencontré.
_PRENOMS_CACHE = None


def format_prenom(value):
    """
    Normalise l'affichage d'un prénom issu du dictionnaire.

    Le dictionnaire est actuellement stocké en minuscules.
    On conserve la graphie fournie, en remontant simplement
    la première lettre pour obtenir des pseudonymes plus lisibles :
    aaliyah -> Aaliyah
    aaron   -> Aaron
    """
    value = (value or "").strip()

    if not value:
        return ""

    return value[:1].upper() + value[1:]


def load_prenoms():
    global _PRENOMS_CACHE

    if _PRENOMS_CACHE is not None:
        return _PRENOMS_CACHE

    if not PRENOMS_FILE.exists():
        _PRENOMS_CACHE = []
        return _PRENOMS_CACHE

    prenoms = []

    with open(PRENOMS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            prenom = format_prenom(line)
            if prenom:
                prenoms.append(prenom)

    _PRENOMS_CACHE = prenoms
    return _PRENOMS_CACHE


def load_mapping():
    if not MAPPING_FILE.exists():
        return {}

    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_mapping(mapping):
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def normalize_spaces(value):
    return re.sub(r"\s+", " ", value or "").strip()


def extract_user_display(actor):
    if not actor:
        return ""

    user = actor.get("user", {})
    return normalize_spaces(user.get("display", ""))


def extract_private_actor_key(actor):
    """
    Retourne la clé stable utilisée pour pseudonymiser un acteur U.

    Cyclos expose systématiquement `actor.id` dans les transactions que nous
    avons auditées, y compris lorsque `user.id` est absent. Ce cas correspond
    précisément aux acteurs que l'ancien anonymiseur fusionnait à tort sous
    `U_inconnu`.

    On privilégie donc `actor.id`, qui est la clé la plus robuste pour suivre
    l'historique transactionnel. Le repli sur `user.id` est conservé seulement
    par sécurité si une structure atypique apparaissait sans `actor.id`.
    """
    if not actor:
        return ""

    actor_id = str(actor.get("id", "")).strip()
    if actor_id:
        return f"actor:{actor_id}"

    user = actor.get("user", {})
    user_id = str(user.get("id", "")).strip()
    if user_id:
        return f"user:{user_id}"

    return ""


def get_or_create_private_pseudo(private_actor_key):
    prenoms = load_prenoms()
    mapping = load_mapping()

    if private_actor_key in mapping:
        return mapping[private_actor_key]

    used_pseudos = set(mapping.values())
    available = [f"U_{p}" for p in prenoms if f"U_{p}" not in used_pseudos]

    if available:
        pseudo = secrets.choice(available)
    else:
        pseudo = f"U_user_{len(mapping) + 1}"

    mapping[private_actor_key] = pseudo
    save_mapping(mapping)

    return pseudo


def is_conversion_label(display):
    lowered = display.lower()
    return "anonyme" in lowered


def is_private_label(display):
    """
    Reconnaît les comptes particuliers Cyclos.

    Les historiques audit és contiennent les deux graphies :
    - U5384 - ...
    - u8247 - ...

    L'ancien test strict startswith("U") envoyait les comptes `u...`
    vers "Acteur masqué", ce qui déformait notamment les flux d'émission.
    """
    display = normalize_spaces(display)
    return display[:1].upper() == "U"


def _extract_professional_code(display):
    """
    Extrait un code professionnel de type P0008 depuis un libellé Cyclos.

    Deux formes ont été vérifiées dans les historiques :
    - P0008 - Monde Ethique
    - Monde Ethique - P0008 - Nom du titulaire

    Le code Pxxxx est la clé stable dont MLCFlux a besoin pour :
    - catégoriser correctement les flux professionnels ;
    - consolider les analyses P/U ;
    - joindre les enrichissements Odoo.
    """
    match = re.search(r"\b(P\d{4,})\b", normalize_spaces(display), flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).upper()


def is_professional_label(display):
    return bool(_extract_professional_code(display))


def clean_professional_label(display):
    """
    Normalise un professionnel au format canonique :

        P0008 - Monde Ethique

    que le libellé Cyclos arrive sous forme :
    - P0008 - Monde Ethique
    - Monde Ethique - P0008 - Nom du titulaire
    """
    display = normalize_spaces(display)
    code = _extract_professional_code(display)

    if not code:
        return display

    parts = [part.strip() for part in display.split(" - ") if part.strip()]

    code_index = None
    for index, part in enumerate(parts):
        if re.search(rf"\b{re.escape(code)}\b", part, flags=re.IGNORECASE):
            code_index = index
            break

    professional_name = ""

    if code_index is not None:
        if code_index == 0 and len(parts) >= 2:
            # Forme déjà canonique ou proche :
            # P0008 - Monde Ethique - ...
            professional_name = parts[1]
        elif code_index > 0:
            # Forme Cyclos auditée :
            # Monde Ethique - P0008 - Nom du titulaire
            professional_name = parts[code_index - 1]

    if professional_name:
        return f"{code} - {professional_name}"

    return code


def anonymize_actor_label(actor):
    display = extract_user_display(actor)
    private_actor_key = extract_private_actor_key(actor)

    if not display:
        return "Acteur masqué"

    if is_conversion_label(display):
        return "Conversion"

    # Les professionnels sont testés avant les particuliers :
    # certains libellés pros ne commencent pas par P mais contiennent
    # un code Pxxxx plus loin dans la chaîne.
    if is_professional_label(display):
        return clean_professional_label(display)

    if is_private_label(display):
        if not private_actor_key:
            return "U_inconnu"
        return get_or_create_private_pseudo(private_actor_key)

    return "Acteur masqué"


def extract_group_label(actor):
    if not actor:
        return ""

    actor_type = actor.get("type", {})
    return normalize_spaces(actor_type.get("name", ""))


def anonymize_transaction(tx):
    return {
        "id": tx.get("id"),
        "date": tx.get("date"),
        "group": extract_group_label(tx.get("from")),
        "from": anonymize_actor_label(tx.get("from")),
        "to": anonymize_actor_label(tx.get("to")),
        "amount": tx.get("amount"),
        "type": tx.get("description"),
        "transactionNumber": tx.get("transactionNumber"),
        "description": tx.get("description"),
    }


def anonymize_transactions(transactions):
    return [anonymize_transaction(tx) for tx in transactions]