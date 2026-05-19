import fcntl
import json
import os
import re
import secrets
import tempfile
from contextlib import contextmanager
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRENOMS_FILE = DATA_DIR / "prenoms.csv"
MAPPING_FILE = DATA_DIR / "user_mapping.json"
MAPPING_LOCK_FILE = DATA_DIR / "user_mapping.json.lock"
DEVICE_PRIVATE_ACTOR_REGISTRY_FILE = DATA_DIR / "device_private_actor_registry.json"
_DEVICE_PRIVATE_ACTOR_IDS_CACHE = None

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


@contextmanager
def _mapping_file_lock():
    """
    Verrou inter-processus pour user_mapping.json.

    La stabilité des pseudonymes doit être protégée entre syncs ordinaires
    d'une même instance, y compris si deux traitements se chevauchent.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(MAPPING_LOCK_FILE, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _load_mapping_unlocked():
    if not MAPPING_FILE.exists():
        return {}

    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    if not isinstance(mapping, dict):
        raise ValueError("user_mapping.json doit contenir un objet JSON.")

    return mapping


def load_mapping():
    with _mapping_file_lock():
        return _load_mapping_unlocked()


def _save_mapping_unlocked(mapping):
    if not isinstance(mapping, dict):
        raise ValueError("Le mapping d'anonymisation doit être un dictionnaire.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix=f"{MAPPING_FILE.name}.",
        suffix=".tmp",
        dir=str(MAPPING_FILE.parent),
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, MAPPING_FILE)

    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def save_mapping(mapping):
    with _mapping_file_lock():
        _save_mapping_unlocked(mapping)


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


def get_or_create_private_pseudo(private_actor_key, *, prefix="U"):
    """
    Retourne un pseudonyme stable pour un acteur particulier.

    prefix="U"  : particulier ordinaire
    prefix="UD" : compte particulier de dispositif / temporaire

    Le mapping reste fondé sur la clé stable actor:* déjà utilisée par MLCFlux.
    """
    prefix = str(prefix or "U").strip() or "U"

    prenoms = load_prenoms()

    # Le verrou couvre tout le cycle lecture -> attribution -> écriture.
    # Cela évite qu'un second processus lise un état périmé puis écrase
    # la modification du premier.
    with _mapping_file_lock():
        mapping = _load_mapping_unlocked()

        if private_actor_key in mapping:
            return mapping[private_actor_key]

        used_pseudos = set(mapping.values())

        available = [
            f"{prefix}_{prenom}"
            for prenom in prenoms
            if f"{prefix}_{prenom}" not in used_pseudos
        ]

        if available:
            pseudo = secrets.choice(available)
        else:
            pseudo = f"{prefix}_user_{len(mapping) + 1}"

        mapping[private_actor_key] = pseudo
        _save_mapping_unlocked(mapping)

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
    vers un libellé indifférencié, ce qui déformait notamment les flux d'émission.
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


def _actor_type_internal_name(actor):
    if not actor:
        return ""

    actor_type = actor.get("type", {})
    if not isinstance(actor_type, dict):
        return ""

    return normalize_spaces(actor_type.get("internalName", ""))


def _actor_kind(actor):
    if not actor:
        return ""

    return normalize_spaces(actor.get("kind", ""))


def load_device_private_actor_ids():
    """
    Charge les actor.id des comptes particuliers de dispositif identifiés
    par l'audit UMASK001-FIX1.

    Le registre ne contient que des identifiants techniques nécessaires
    à la reproductibilité de la catégorisation historique.
    """
    global _DEVICE_PRIVATE_ACTOR_IDS_CACHE

    if _DEVICE_PRIVATE_ACTOR_IDS_CACHE is not None:
        return _DEVICE_PRIVATE_ACTOR_IDS_CACHE

    if not DEVICE_PRIVATE_ACTOR_REGISTRY_FILE.exists():
        _DEVICE_PRIVATE_ACTOR_IDS_CACHE = set()
        return _DEVICE_PRIVATE_ACTOR_IDS_CACHE

    with open(DEVICE_PRIVATE_ACTOR_REGISTRY_FILE, "r", encoding="utf-8") as f:
        payload = json.load(f)

    actor_ids = payload.get("actor_ids") or []
    _DEVICE_PRIVATE_ACTOR_IDS_CACHE = {
        str(actor_id).strip()
        for actor_id in actor_ids
        if str(actor_id).strip()
    }

    return _DEVICE_PRIVATE_ACTOR_IDS_CACHE


def is_device_private_actor(actor):
    if not actor:
        return False

    actor_id = str(actor.get("id", "")).strip()
    if not actor_id:
        return False

    return actor_id in load_device_private_actor_ids()


def _technical_actor_label(actor):
    internal_name = _actor_type_internal_name(actor)

    if internal_name == "emission":
        return "T_Émission"

    if internal_name == "Conversion":
        return "T_Conversion"

    return "T_Technique"


def anonymize_actor_label(actor):
    """
    Produit le libellé anonymisé / analytique exposé par MLCFlux.

    Ordre de décision :
    1. compte technique Cyclos -> T_*
    2. compte particulier -> U_* ou UD_* selon le registre de dispositif
    3. compte professionnel -> Pxxxx si identifiable
    4. compatibilités historiques sur le display
    5. résiduel explicite « Acteur non catégorisé »
    """
    actor = actor or {}
    display = extract_user_display(actor)
    private_actor_key = extract_private_actor_key(actor)
    actor_type = _actor_type_internal_name(actor)
    actor_kind = _actor_kind(actor)

    # 1. Comptes techniques Cyclos
    if actor_kind == "system":
        return _technical_actor_label(actor)

    # 2. Comptes particuliers, y compris les formes atypiques
    #    qui ne commencent pas par Uxxxx.
    if actor_type == "compteparticulier":
        if not private_actor_key:
            return "U_inconnu"

        prefix = "UD" if is_device_private_actor(actor) else "U"
        return get_or_create_private_pseudo(private_actor_key, prefix=prefix)

    # 3. Comptes professionnels
    if actor_type == "comptepro":
        if display and is_professional_label(display):
            return clean_professional_label(display)
        return "P_non_référencé"

    # 4. Compatibilités de repli si la structure brute est atypique
    if display:
        if is_conversion_label(display):
            return "T_Conversion"

        if is_professional_label(display):
            return clean_professional_label(display)

        if is_private_label(display):
            if not private_actor_key:
                return "U_inconnu"
            return get_or_create_private_pseudo(private_actor_key, prefix="U")

    # 5. Résiduel explicitement nommé, non fusionné
    return "Acteur non catégorisé"

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