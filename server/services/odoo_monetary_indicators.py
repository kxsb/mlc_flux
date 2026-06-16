from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from server.database import get_connection
from server.services.odoo_client import OdooJsonRpcClient


ACCOUNT_MOVE_LINE_MODEL = "account.move.line"

BASE_ACCOUNT_MOVE_LINE_DOMAIN = [
    ["display_type", "not in", ["line_section", "line_note"]],
    ["parent_state", "!=", "cancel"],
    ["parent_state", "=", "posted"],
]

NUMERIC_CIRCULATION_ACCOUNT_FILTER = [
    ["account_id", "ilike", "46762"],
]

PAPER_CIRCULATION_ACCOUNT_FILTER = [
    ["account_id", "ilike", "467000"],
]

NUMERIC_GUARANTEE_ACCOUNT_CODES = [
    "51700003",
    "51700002",
    "51700001",
    "58200001",
    "53110002",
]

PAPER_GUARANTEE_ACCOUNT_CODES = [
    "51710007",
    "51710003",
    "51710005",
    "58200003",
    "51710002",
    "53110001",
    "58200008",
]


def _validate_year(year: int) -> int:
    """
    Valide l'année demandée avant envoi vers Odoo.
    """
    try:
        normalized_year = int(year)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Année invalide : {year!r}") from exc

    if normalized_year < 2000 or normalized_year > 2100:
        raise ValueError(f"Année hors plage attendue : {normalized_year}")

    return normalized_year


def _year_date_domain(year: int) -> list[list[str]]:
    """
    Domaine temporel adapté à un indicateur de stock.

    On ne cherche pas le mouvement intervenu pendant l'année Y,
    mais le solde comptable cumulé constaté à la fin de l'année Y.

    Exemple :
    - 2024 => stock cumulé jusqu'au 2024-12-31 ;
    - 2025 => stock cumulé jusqu'au 2025-12-31 ;
    - année courante => valeur à date, les écritures futures n'existant pas.
    """
    return [
        ["date", "<=", f"{year}-12-31"],
    ]


def _or_chain(conditions: list[list[str]]) -> list:
    """
    Produit une chaîne OR plate compatible avec le format de domaine Odoo.

    Exemple à 3 conditions :
    [
        "|",
        condition_1,
        "|",
        condition_2,
        condition_3,
    ]
    """
    if not conditions:
        raise ValueError("Impossible de construire un OR Odoo sans condition.")

    if len(conditions) == 1:
        return [conditions[0]]

    domain = []

    for index, condition in enumerate(conditions):
        if index < len(conditions) - 1:
            domain.append("|")
        domain.append(condition)

    return domain


def _account_codes_or_domain(account_codes: list[str]) -> list:
    """
    Domaine OR sur account_id, reproduisant la logique validée
    contre le dashboard Odoo.
    """
    conditions = [
        ["account_id", "=", account_code]
        for account_code in account_codes
    ]
    return _or_chain(conditions)


def _build_domain(year: int, account_domain: list) -> list:
    """
    Assemble :
    - filtres de lignes comptables ;
    - filtre annuel ;
    - filtre de comptes propre à l'indicateur.
    """
    return [
        *BASE_ACCOUNT_MOVE_LINE_DOMAIN,
        *_year_date_domain(year),
        *account_domain,
    ]


def _money(value) -> float:
    """
    Normalise une valeur financière en float arrondi à 2 décimales.
    """
    return round(float(value or 0.0), 2)


def _extract_balance_sum(read_group_rows: list[dict]) -> float:
    """
    Extrait proprement le total balance:sum renvoyé par Odoo.

    Odoo restitue habituellement la somme sous la clé 'balance',
    mais on garde ici un fallback défensif.
    """
    if not read_group_rows:
        return 0.0

    first_row = read_group_rows[0] or {}

    for key in ("balance", "balance_sum", "balance:sum"):
        if key in first_row:
            return _money(first_row.get(key))

    raise ValueError(
        "Réponse read_group inattendue : aucune clé de somme balance détectée. "
        f"Clés disponibles : {sorted(first_row.keys())}"
    )


def _read_balance_sum(client: OdooJsonRpcClient, domain: list) -> float:
    """
    Exécute le read_group Odoo commun à tous les indicateurs.
    """
    rows = client.read_group(
        model=ACCOUNT_MOVE_LINE_MODEL,
        domain=domain,
        fields=["balance:sum"],
        groupby=[],
        lazy=False,
        timeout=90,
    )
    return _extract_balance_sum(rows)


def fetch_odoo_monetary_indicators(year: int) -> dict:
    """
    Récupère les indicateurs monétaires Odoo pour une année donnée.

    Les gonettes numériques et papier en circulation sont converties
    en valeur positive avec abs(balance), conformément à l'affichage
    du dashboard Odoo reproduit lors de l'audit initial.

    Les fonds de garantie sont conservés avec leur signe comptable
    renvoyé par Odoo, puis les écarts sont calculés côté MLCFlux.
    """
    normalized_year = _validate_year(year)
    client = OdooJsonRpcClient()

    numeric_circulation_balance = _read_balance_sum(
        client,
        _build_domain(
            normalized_year,
            NUMERIC_CIRCULATION_ACCOUNT_FILTER,
        ),
    )

    paper_circulation_balance = _read_balance_sum(
        client,
        _build_domain(
            normalized_year,
            PAPER_CIRCULATION_ACCOUNT_FILTER,
        ),
    )

    numeric_guarantee_balance = _read_balance_sum(
        client,
        _build_domain(
            normalized_year,
            _account_codes_or_domain(NUMERIC_GUARANTEE_ACCOUNT_CODES),
        ),
    )

    paper_guarantee_balance = _read_balance_sum(
        client,
        _build_domain(
            normalized_year,
            _account_codes_or_domain(PAPER_GUARANTEE_ACCOUNT_CODES),
        ),
    )

    gonettes_num_circulation = _money(abs(numeric_circulation_balance))
    gonettes_paper_circulation = _money(abs(paper_circulation_balance))
    gonettes_total_circulation = _money(
        gonettes_num_circulation + gonettes_paper_circulation
    )

    fonds_garantie_num = _money(numeric_guarantee_balance)
    fonds_garantie_paper = _money(paper_guarantee_balance)

    ecart_num = _money(
        fonds_garantie_num - gonettes_num_circulation
    )
    ecart_paper = _money(
        fonds_garantie_paper - gonettes_paper_circulation
    )

    return {
        "year": normalized_year,
        "gonettes_num_circulation": gonettes_num_circulation,
        "gonettes_paper_circulation": gonettes_paper_circulation,
        "gonettes_total_circulation": gonettes_total_circulation,
        "fonds_garantie_num": fonds_garantie_num,
        "fonds_garantie_paper": fonds_garantie_paper,
        "ecart_num": ecart_num,
        "ecart_paper": ecart_paper,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "odoo_jsonrpc",
    }



def upsert_odoo_monetary_indicators(snapshot: dict) -> dict:
    """
    Insère ou met à jour en SQLite les indicateurs monétaires annuels
    récupérés depuis Odoo.

    Le stockage est volontairement annuel :
    - les années clôturées peuvent être figées ou rafraîchies ponctuellement ;
    - l'année en cours pourra être recalculée régulièrement.
    """
    required_fields = [
        "year",
        "gonettes_num_circulation",
        "gonettes_paper_circulation",
        "gonettes_total_circulation",
        "fonds_garantie_num",
        "fonds_garantie_paper",
        "ecart_num",
        "ecart_paper",
        "fetched_at",
        "source",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in snapshot
    ]

    if missing_fields:
        raise ValueError(
            "Snapshot monétaire Odoo incomplet : "
            + ", ".join(missing_fields)
        )

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO odoo_monetary_indicators_yearly (
                year,
                gonettes_num_circulation,
                gonettes_paper_circulation,
                gonettes_total_circulation,
                fonds_garantie_num,
                fonds_garantie_paper,
                ecart_num,
                ecart_paper,
                fetched_at,
                source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(year) DO UPDATE SET
                gonettes_num_circulation=excluded.gonettes_num_circulation,
                gonettes_paper_circulation=excluded.gonettes_paper_circulation,
                gonettes_total_circulation=excluded.gonettes_total_circulation,
                fonds_garantie_num=excluded.fonds_garantie_num,
                fonds_garantie_paper=excluded.fonds_garantie_paper,
                ecart_num=excluded.ecart_num,
                ecart_paper=excluded.ecart_paper,
                fetched_at=excluded.fetched_at,
                source=excluded.source
        """, (
            int(snapshot["year"]),
            float(snapshot["gonettes_num_circulation"]),
            float(snapshot["gonettes_paper_circulation"]),
            float(snapshot["gonettes_total_circulation"]),
            float(snapshot["fonds_garantie_num"]),
            float(snapshot["fonds_garantie_paper"]),
            float(snapshot["ecart_num"]),
            float(snapshot["ecart_paper"]),
            snapshot["fetched_at"],
            snapshot["source"],
        ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "year": int(snapshot["year"]),
        "fetched_at": snapshot["fetched_at"],
        "source": snapshot["source"],
    }



def _parse_snapshot_date(value: str | date) -> date:
    """
    Normalise une date ISO YYYY-MM-DD ou un objet date.
    """
    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Date invalide : {value!r}") from exc


def _build_cutoff_domain(cutoff_day: date, account_domain: list) -> list:
    """
    Domaine Odoo de stock cumulé à une date de coupe précise.
    """
    return [
        *BASE_ACCOUNT_MOVE_LINE_DOMAIN,
        ["date", "<=", cutoff_day.isoformat()],
        *account_domain,
    ]


def _build_range_domain(date_from: date, date_to: date, account_domain: list) -> list:
    """
    Domaine Odoo de variations comptables intervenues dans une plage de dates.
    """
    return [
        *BASE_ACCOUNT_MOVE_LINE_DOMAIN,
        ["date", ">=", date_from.isoformat()],
        ["date", "<=", date_to.isoformat()],
        *account_domain,
    ]


def _direct_cumulative_balance_at_date(
    client: OdooJsonRpcClient,
    cutoff_day: date,
    account_domain: list,
) -> float:
    """
    Lit directement dans Odoo un stock comptable cumulé à une date donnée.
    """
    return _read_balance_sum(
        client,
        _build_cutoff_domain(cutoff_day, account_domain),
    )


def _extract_grouped_day(row: dict) -> str:
    """
    Extrait le jour ISO depuis une ligne read_group Odoo groupée par date:day.

    Sur l'Odoo de La Gonette, row["date:day"] est localisé en français
    (ex. "01 janv. 2025"), tandis que row["__range"]["date:day"]["from"]
    fournit une date ISO robuste.
    """
    range_block = row.get("__range") or {}
    day_range = range_block.get("date:day") or {}
    day_from = day_range.get("from")

    if day_from:
        return str(day_from)[:10]

    direct_value = row.get("date:day")
    if direct_value:
        text = str(direct_value)
        if len(text) >= 10 and text[:10].count("-") == 2:
            return text[:10]

    raise ValueError(
        "Impossible d'extraire le jour groupé depuis la ligne Odoo : "
        f"{row}"
    )


def _grouped_daily_balance_deltas(
    client: OdooJsonRpcClient,
    date_from: date,
    date_to: date,
    account_domain: list,
) -> dict[str, float]:
    """
    Agrège les variations de balance Odoo par jour sur une période.
    """
    rows = client.read_group(
        model=ACCOUNT_MOVE_LINE_MODEL,
        domain=_build_range_domain(date_from, date_to, account_domain),
        fields=["balance:sum"],
        groupby=["date:day"],
        lazy=False,
        limit=10000,
        timeout=180,
    )

    deltas = defaultdict(float)

    for row in rows:
        grouped_day = _extract_grouped_day(row)

        balance = None
        for key in ("balance", "balance_sum", "balance:sum"):
            if key in row:
                balance = _money(row.get(key))
                break

        if balance is None:
            raise ValueError(
                "Somme balance absente dans une ligne groupée Odoo : "
                f"{row}"
            )

        deltas[grouped_day] += balance

    return {
        day: _money(value)
        for day, value in deltas.items()
    }


def _iter_days(date_from: date, date_to: date):
    """
    Itère sur tous les jours calendaires inclusifs d'une période.
    """
    current = date_from
    while current <= date_to:
        yield current
        current += timedelta(days=1)


def _build_daily_raw_balance_series(
    date_from: date,
    date_to: date,
    opening_balance: float,
    daily_deltas: dict[str, float],
) -> dict[str, float]:
    """
    Reconstruit un stock quotidien brut par cumul :
    stock_jour = stock_précédent + delta_du_jour.
    """
    running_balance = _money(opening_balance)
    series = {}

    for current_day in _iter_days(date_from, date_to):
        day_key = current_day.isoformat()
        running_balance = _money(
            running_balance + _money(daily_deltas.get(day_key, 0.0))
        )
        series[day_key] = running_balance

    return series


def fetch_odoo_monetary_indicators_daily(
    date_from: str | date,
    date_to: str | date,
) -> dict:
    """
    Reconstruit quotidiennement les indicateurs monétaires Odoo
    entre deux dates inclusives.

    Méthode :
    - lecture du stock d'ouverture au jour précédent ;
    - lecture des variations groupées par date:day ;
    - cumul progressif pour reconstituer chaque snapshot quotidien.
    """
    normalized_from = _parse_snapshot_date(date_from)
    normalized_to = _parse_snapshot_date(date_to)

    if normalized_from > normalized_to:
        raise ValueError(
            f"Période invalide : {normalized_from} > {normalized_to}"
        )

    opening_cutoff = normalized_from - timedelta(days=1)
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds")

    client = OdooJsonRpcClient()

    raw_metric_domains = {
        "raw_num": NUMERIC_CIRCULATION_ACCOUNT_FILTER,
        "raw_paper": PAPER_CIRCULATION_ACCOUNT_FILTER,
        "fdg_num": _account_codes_or_domain(NUMERIC_GUARANTEE_ACCOUNT_CODES),
        "fdg_paper": _account_codes_or_domain(PAPER_GUARANTEE_ACCOUNT_CODES),
    }

    opening_balances = {
        metric: _direct_cumulative_balance_at_date(
            client,
            opening_cutoff,
            account_domain,
        )
        for metric, account_domain in raw_metric_domains.items()
    }

    grouped_deltas = {
        metric: _grouped_daily_balance_deltas(
            client,
            normalized_from,
            normalized_to,
            account_domain,
        )
        for metric, account_domain in raw_metric_domains.items()
    }

    raw_series = {
        metric: _build_daily_raw_balance_series(
            normalized_from,
            normalized_to,
            opening_balances[metric],
            grouped_deltas[metric],
        )
        for metric in raw_metric_domains
    }

    items = []

    for current_day in _iter_days(normalized_from, normalized_to):
        snapshot_date = current_day.isoformat()

        raw_num = raw_series["raw_num"][snapshot_date]
        raw_paper = raw_series["raw_paper"][snapshot_date]
        fdg_num = raw_series["fdg_num"][snapshot_date]
        fdg_paper = raw_series["fdg_paper"][snapshot_date]

        gonettes_num = _money(abs(raw_num))
        gonettes_paper = _money(abs(raw_paper))
        gonettes_total = _money(gonettes_num + gonettes_paper)

        items.append({
            "snapshot_date": snapshot_date,
            "year": current_day.year,
            "month": current_day.month,
            "day": current_day.day,
            "gonettes_num_circulation": gonettes_num,
            "gonettes_paper_circulation": gonettes_paper,
            "gonettes_total_circulation": gonettes_total,
            "fonds_garantie_num": _money(fdg_num),
            "fonds_garantie_paper": _money(fdg_paper),
            "ecart_num": _money(fdg_num - gonettes_num),
            "ecart_paper": _money(fdg_paper - gonettes_paper),
            "fetched_at": fetched_at,
            "source": "odoo_jsonrpc_daily_reconstruction",
        })

    return {
        "date_from": normalized_from.isoformat(),
        "date_to": normalized_to.isoformat(),
        "opening_cutoff": opening_cutoff.isoformat(),
        "fetched_at": fetched_at,
        "source": "odoo_jsonrpc_daily_reconstruction",
        "count": len(items),
        "items": items,
    }


def upsert_odoo_monetary_indicators_daily(snapshot: dict) -> dict:
    """
    Insère ou met à jour les snapshots quotidiens reconstruits en SQLite.
    """
    items = snapshot.get("items") or []
    fetched_at = snapshot.get("fetched_at")
    source = snapshot.get("source") or "odoo_jsonrpc_daily_reconstruction"

    if not fetched_at:
        raise ValueError("Snapshot daily invalide : fetched_at manquant.")

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN")

        for item in items:
            cur.execute("""
                INSERT INTO odoo_monetary_indicators_daily (
                    snapshot_date,
                    year,
                    month,
                    day,
                    gonettes_num_circulation,
                    gonettes_paper_circulation,
                    gonettes_total_circulation,
                    fonds_garantie_num,
                    fonds_garantie_paper,
                    ecart_num,
                    ecart_paper,
                    fetched_at,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_date) DO UPDATE SET
                    year=excluded.year,
                    month=excluded.month,
                    day=excluded.day,
                    gonettes_num_circulation=excluded.gonettes_num_circulation,
                    gonettes_paper_circulation=excluded.gonettes_paper_circulation,
                    gonettes_total_circulation=excluded.gonettes_total_circulation,
                    fonds_garantie_num=excluded.fonds_garantie_num,
                    fonds_garantie_paper=excluded.fonds_garantie_paper,
                    ecart_num=excluded.ecart_num,
                    ecart_paper=excluded.ecart_paper,
                    fetched_at=excluded.fetched_at,
                    source=excluded.source
            """, (
                item["snapshot_date"],
                int(item["year"]),
                int(item["month"]),
                int(item["day"]),
                float(item["gonettes_num_circulation"]),
                float(item["gonettes_paper_circulation"]),
                float(item["gonettes_total_circulation"]),
                float(item["fonds_garantie_num"]),
                float(item["fonds_garantie_paper"]),
                float(item["ecart_num"]),
                float(item["ecart_paper"]),
                item.get("fetched_at") or fetched_at,
                item.get("source") or source,
            ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "stored_rows": len(items),
        "date_from": snapshot.get("date_from"),
        "date_to": snapshot.get("date_to"),
        "fetched_at": fetched_at,
        "source": source,
    }
