import json
import re
from pathlib import Path
import random

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRENOMS_FILE = DATA_DIR / "prenoms.csv"
MAPPING_FILE = DATA_DIR / "user_mapping.json"


def load_prenoms():
    if not PRENOMS_FILE.exists():
        return []

    with open(PRENOMS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


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


def extract_user_id(actor):
    if not actor:
        return ""

    user = actor.get("user", {})
    return str(user.get("id", "")).strip()


def get_or_create_private_pseudo(user_id):
    prenoms = load_prenoms()
    mapping = load_mapping()

    # si déjà connu
    if user_id in mapping:
        return mapping[user_id]

    used_pseudos = set(mapping.values())

    # pseudos disponibles
    available = [f"U_{p}" for p in prenoms if f"U_{p}" not in used_pseudos]

    if available:
        pseudo = random.choice(available)
    else:
        pseudo = f"U_user_{len(mapping) + 1}"

    mapping[user_id] = pseudo
    save_mapping(mapping)

    return pseudo
    
def is_conversion_label(display):
    lowered = display.lower()
    return "anonyme" in lowered


def is_private_label(display):
    return display.startswith("U")


def is_professional_label(display):
    return display.startswith("P")


def clean_professional_label(display):
    """
    Exemple :
    'P0732 - Les amis de Demain - x - x - lmc.comptacafe@gmail.com'
    devient :
    'P0732 - Les amis de Demain'
    """
    display = normalize_spaces(display)

    parts = [part.strip() for part in display.split(" - ") if part.strip()]
    if len(parts) >= 2:
        return f"{parts[0]} - {parts[1]}"

    return display


def anonymize_actor_label(actor):
    display = extract_user_display(actor)
    user_id = extract_user_id(actor)

    if not display:
        return "Acteur masqué"

    if is_conversion_label(display):
        return "Conversion"

    if is_private_label(display):
        if not user_id:
            return "U_inconnu"
        return get_or_create_private_pseudo(user_id)

    if is_professional_label(display):
        return clean_professional_label(display)

    return "Acteur masqué"


def extract_group_label(actor):
    if not actor:
        return ""

    actor_type = actor.get("type", {})
    return normalize_spaces(actor_type.get("name", ""))


def anonymize_transaction(tx):
    return {
        "date": tx.get("date"),
        "group": extract_group_label(tx.get("from")),
        "from": anonymize_actor_label(tx.get("from")),
        "to": anonymize_actor_label(tx.get("to")),
        "amount": tx.get("amount"),
        "type": tx.get("description"),
        "transactionNumber": tx.get("transactionNumber"),
    }


def anonymize_transactions(transactions):
    return [anonymize_transaction(tx) for tx in transactions]