import base64
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo

import requests
from flask import current_app


LOCAL_CALENDAR_TIMEZONE = ZoneInfo("Europe/Paris")


def build_basic_auth(username, password):
    raw = f"{username}:{password}"
    encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
    return f"Basic {encoded}"


def create_session_token():
    base_url = current_app.config["CYCLOS_BASE_URL"]
    username = current_app.config["CYCLOS_USERNAME"]
    password = current_app.config["CYCLOS_PASSWORD"]

    if not username or not password:
        raise ValueError("CYCLOS_USERNAME ou CYCLOS_PASSWORD manquant dans .env")

    url = f"{base_url}/auth/session?cookie=true&fields=sessionToken"
    headers = {
        "Authorization": build_basic_auth(username, password)
    }

    response = requests.post(url, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()
    session_token_json = data.get("sessionToken", "")
    session_token_cookie = response.cookies.get("Session-Token", "")

    if not session_token_json or not session_token_cookie:
        raise ValueError("Session-Token incomplet récupéré depuis Cyclos")

    return f"{session_token_json}{session_token_cookie}"


def _is_date_only(value):
    """
    Retourne True pour une date calendaire simple YYYY-MM-DD.
    """
    if not isinstance(value, str):
        return False

    value = value.strip()
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return len(value) == 10
    except ValueError:
        return False


def _parse_date(value):
    if not value:
        return None

    value = value.strip()

    # accepte YYYY-MM-DD
    #
    # Une date simple désigne un jour civil français côté usage :
    # 2024-08-09 signifie donc 2024-08-09 00:00 Europe/Paris,
    # pas 2024-08-09 00:00 UTC.
    #
    # On convertit ensuite en UTC pour l'appel API Cyclos.
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.replace(tzinfo=LOCAL_CALENDAR_TIMEZONE).astimezone(UTC)
    except ValueError:
        pass

    # accepte aussi ISO complet
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        raise ValueError(f"Format de date invalide: {value}")


def _extract_transaction_items(data):
    """
    Normalise les formats de réponse possibles.
    Sur l'instance Cyclos de la Gonette, /transactions renvoie normalement une liste.
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        if "list" in data and isinstance(data["list"], list):
            return data["list"]
        if "pageItems" in data and isinstance(data["pageItems"], list):
            return data["pageItems"]

    return []


def get_transactions(days=None, date_from=None, date_to=None, *, max_period_days=None):
    """
    Récupère les transactions Cyclos sur une période donnée, avec pagination complète.

    Paramètres exposés côté MLCFlux :
    - days=N : période glissante de N jours
    - date_from=YYYY-MM-DD ou ISO
    - date_to=YYYY-MM-DD ou ISO
    - max_period_days=N : garde-fou optionnel utilisé par les routes publiques

    Paramètres utilisés côté Cyclos :
    - datePeriod : filtre temporel
    - page / pageSize : pagination
    - orderBy=dateDesc : transactions les plus récentes d'abord
    """
    base_url = current_app.config["CYCLOS_BASE_URL"]

    now = datetime.now(UTC)

    if date_from:
        start_date = _parse_date(date_from)
    elif days is not None:
        start_date = now - timedelta(days=days)
    else:
        start_date = now - timedelta(hours=48)

    end_date = _parse_date(date_to) if date_to else None

    # Pour l'interface / CLI, une date de fin calendaire
    # date_to=YYYY-MM-DD signifie "inclure toute cette journée".
    #
    # Cyclos reçoit une borne datePeriod de fin exclusive :
    # on envoie donc le lendemain à 00:00 Europe/Paris,
    # puis on convertit en UTC.
    #
    # On ne fait pas simplement end_date + timedelta(days=1) en UTC :
    # aux changements d'heure, une journée locale peut durer 23 ou 25 heures.
    #
    # Les dates ISO complètes conservent leur sémantique exacte.
    if date_to and _is_date_only(date_to):
        next_local_day = (
            datetime.strptime(date_to.strip(), "%Y-%m-%d")
            + timedelta(days=1)
        ).strftime("%Y-%m-%d")
        end_date = _parse_date(next_local_day)

    if end_date and end_date < start_date:
        raise ValueError("date_to doit être postérieure ou égale à date_from")

    if max_period_days is not None:
        try:
            normalized_max_period_days = int(max_period_days)
        except (TypeError, ValueError) as exc:
            raise ValueError("max_period_days doit être un entier positif.") from exc

        if normalized_max_period_days <= 0:
            raise ValueError("max_period_days doit être un entier positif.")

        effective_end_date = end_date or now
        max_period = timedelta(days=normalized_max_period_days)

        if effective_end_date - start_date > max_period:
            raise ValueError(
                "Période trop large : "
                f"{normalized_max_period_days} jours maximum pour cette route."
            )

    # Le token Cyclos n'est demandé qu'après validation complète de la période.
    # Une requête publique invalide ne doit pas déclencher d'appel externe inutile.
    session_token = create_session_token()

    url = f"{base_url}/transactions"

    headers = {
        "Session-Token": session_token,
        "Accept": "application/json",
    }

    page_size = 500
    page = 0
    max_pages = 10000
    all_transactions = []

    while True:
        params = {
            "datePeriod": [start_date.isoformat(timespec="seconds")],
            "pageSize": page_size,
            "page": page,
            "orderBy": "dateDesc",
        }

        if end_date:
            params["datePeriod"].append(end_date.isoformat(timespec="seconds"))

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=60,
        )
        response.raise_for_status()

        page_items = _extract_transaction_items(response.json())
        all_transactions.extend(page_items)

        has_next = str(
            response.headers.get("X-Has-Next-Page", "")
        ).strip().lower()

        if has_next == "true":
            page += 1

            if page >= max_pages:
                raise RuntimeError(
                    f"Pagination Cyclos interrompue : plus de {max_pages} pages demandées."
                )

            continue

        if has_next == "false":
            break

        # Fallback défensif si l'en-tête disparaissait :
        # une page incomplète implique généralement la fin des résultats.
        if len(page_items) < page_size:
            break

        # Si l'en-tête est absent et que la page est pleine,
        # mieux vaut échouer que tronquer silencieusement.
        raise RuntimeError(
            "Pagination Cyclos indéterminée : header X-Has-Next-Page absent "
            "alors que la page est pleine."
        )

    return all_transactions


class CyclosAddressError(RuntimeError):
    """Erreur lors de la récupération d'une adresse primaire Cyclos."""


def get_primary_address(user_ref, session_token=None):
    """
    Récupère l'adresse primaire Cyclos d'un utilisateur / professionnel.

    Paramètre attendu :
    - user_ref : identifiant Cyclos utilisable dans l'API, par exemple P0080.

    Retour :
    - None si Cyclos répond 204 (aucune adresse primaire) ;
    - un dictionnaire normalisé sinon.
    """
    base_url = current_app.config["CYCLOS_BASE_URL"]

    if not user_ref:
        raise ValueError("user_ref manquant pour get_primary_address()")

    token = session_token or create_session_token()

    response = requests.get(
        f"{base_url}/{user_ref}/addresses/primary",
        headers={
            "Session-Token": token,
            "Accept": "application/json",
        },
        timeout=30,
    )

    if response.status_code == 204:
        return None

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise CyclosAddressError(
            f"Échec lecture adresse primaire Cyclos pour {user_ref} "
            f"(HTTP {response.status_code})"
        ) from exc

    data = response.json()
    location = data.get("location") or {}

    return {
        "cyclos_address_id": data.get("id"),
        "cyclos_address_line1": data.get("addressLine1"),
        "cyclos_zip": data.get("zip"),
        "cyclos_city": data.get("city"),
        "cyclos_latitude": location.get("latitude"),
        "cyclos_longitude": location.get("longitude"),
    }
