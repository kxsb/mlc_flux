from datetime import datetime
from server.database import get_connection


def _is_date_only(value):
    """
    Retourne True pour les dates calendaires au format YYYY-MM-DD.

    Les dates stockées en base sont des timestamps ISO complets.
    Pour un filtre utilisateur du type end=2026-05-14,
    il faut comparer sur la partie jour afin d'inclure toute la journée.
    """
    if not isinstance(value, str):
        return False

    value = value.strip()
    if len(value) != 10:
        return False

    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def fetch_transactions(start=None, end=None, year=None):
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT
            date,
            group_label,
            from_label,
            to_label,
            amount,
            type_label,
            transaction_number
        FROM transactions
        WHERE 1=1
    """
    params = []

    if start:
        if _is_date_only(start):
            query += " AND substr(date, 1, 10) >= ?"
        else:
            query += " AND date >= ?"
        params.append(start)

    if end:
        if _is_date_only(end):
            query += " AND substr(date, 1, 10) <= ?"
        else:
            query += " AND date <= ?"
        params.append(end)

    if year is not None:
        query += " AND substr(date, 1, 4) = ?"
        params.append(str(year))

    query += " ORDER BY date ASC"

    cur.execute(query, params)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_available_years():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT substr(date, 1, 4) AS year
        FROM transactions
        WHERE date IS NOT NULL AND date != ''
        ORDER BY year ASC
    """)

    years = [int(row["year"]) for row in cur.fetchall() if row["year"]]
    conn.close()
    return years


def get_available_period_bounds():
    """
    Retourne la première et la dernière date disponibles dans la base,
    au format YYYY-MM-DD.

    Ces bornes servent à initialiser le filtre global de période côté interface.
    """
    conn = get_connection()
    cur = conn.cursor()

    row = cur.execute("""
        SELECT
            MIN(substr(date, 1, 10)) AS min_date,
            MAX(substr(date, 1, 10)) AS max_date
        FROM transactions
        WHERE date IS NOT NULL AND date != ''
    """).fetchone()

    conn.close()

    if not row:
        return {
            "min_date": None,
            "max_date": None,
        }

    return {
        "min_date": row["min_date"],
        "max_date": row["max_date"],
    }


def compute_global_stats(start=None, end=None, year=None):
    rows = fetch_transactions(start=start, end=end, year=year)

    if not rows:
        return {
            "periode": "-",
            "nb_utilisateurs": 0,
            "moyenne_transactions_PP": 0.0,
            "moyenne_paiement_UP": 0.0,
            "moyenne_transactions_UU": 0.0,
            "transactions": []
        }

    dates = [row["date"] for row in rows if row.get("date")]
    if dates:
        start_date = datetime.fromisoformat(min(dates).replace("Z", "+00:00")).strftime("%d/%m/%Y")
        end_date = datetime.fromisoformat(max(dates).replace("Z", "+00:00")).strftime("%d/%m/%Y")
        periode = f"{start_date} - {end_date}"
    else:
        periode = "-"

    acteurs = set()
    for row in rows:
        from_label = str(row.get("from_label", "")).strip()
        to_label = str(row.get("to_label", "")).strip()
        if from_label:
            acteurs.add(from_label)
        if to_label:
            acteurs.add(to_label)

    pp = [
        row for row in rows
        if str(row.get("from_label", "")).startswith("P")
        and str(row.get("to_label", "")).startswith("P")
    ]

    up = [
        row for row in rows
        if str(row.get("from_label", "")).startswith("U")
        and str(row.get("to_label", "")).startswith("P")
    ]

    uu = [
        row for row in rows
        if str(row.get("from_label", "")).startswith("U")
        and str(row.get("to_label", "")).startswith("U")
    ]

    def avg_amount(items):
        if not items:
            return 0.0
        return float(sum(float(row.get("amount", 0) or 0) for row in items) / len(items))

    transactions = [
        {
            "Date": row["date"][:10],
            "Réalisé par": row.get("from_label", ""),
            "Vers": row.get("to_label", ""),
            "Montant": float(row.get("amount", 0) or 0),
        }
        for row in rows
    ]

    return {
        "periode": periode,
        "nb_utilisateurs": len(acteurs),
        "moyenne_transactions_PP": avg_amount(pp),
        "moyenne_paiement_UP": avg_amount(up),
        "moyenne_transactions_UU": avg_amount(uu),
        "transactions": transactions,
    }

def compute_network_data(start=None, end=None, year=None):
    rows = fetch_transactions(start=start, end=end, year=year)

    # même logique que la prod : seulement P -> P
    pp_rows = [
        row for row in rows
        if str(row.get("from_label", "")).startswith("P")
        and str(row.get("to_label", "")).startswith("P")
    ]

    if not pp_rows:
        return {"nodes": [], "edges": []}

    edge_weights = {}
    nodes_set = set()

    for row in pp_rows:
        source = str(row.get("from_label", "")).strip()
        target = str(row.get("to_label", "")).strip()
        amount = float(row.get("amount", 0) or 0)

        if not source or not target:
            continue

        nodes_set.add(source)
        nodes_set.add(target)

        key = (source, target)
        edge_weights[key] = edge_weights.get(key, 0.0) + amount

    nodes = [{"data": {"id": node, "label": node}} for node in sorted(nodes_set)]
    edges = [
        {
            "data": {
                "source": source,
                "target": target,
                "weight": float(weight),
            }
        }
        for (source, target), weight in edge_weights.items()
    ]

    return {"nodes": nodes, "edges": edges}


def compute_professionals_ranking(start=None, end=None, year=None):
    rows = fetch_transactions(start=start, end=end, year=year)

    if not rows:
        return []

    b2b_recu = {}
    b2b_emis = {}
    b2c = {}
    remuneration = {}
    pros = set()

    for row in rows:
        from_label = str(row.get("from_label", "")).strip()
        to_label = str(row.get("to_label", "")).strip()
        amount = float(row.get("amount", 0) or 0)

        from_is_pro = from_label.startswith("P")
        to_is_pro = to_label.startswith("P")
        from_is_user = from_label.startswith("U")
        to_is_user = to_label.startswith("U")

        if from_is_pro:
            pros.add(from_label)
        if to_is_pro:
            pros.add(to_label)

        if from_is_pro and to_is_pro:
            b2b_recu[to_label] = b2b_recu.get(to_label, 0.0) + amount
            b2b_emis[from_label] = b2b_emis.get(from_label, 0.0) + amount

        if from_is_user and to_is_pro:
            b2c[to_label] = b2c.get(to_label, 0.0) + amount

        if from_is_pro and to_is_user:
            remuneration[from_label] = remuneration.get(from_label, 0.0) + amount

    ranking = []
    for pro in pros:
        total_recu = b2b_recu.get(pro, 0.0) + b2c.get(pro, 0.0)

        ranking.append({
            "Professionnel": pro,
            "B2B Reçu": round(b2b_recu.get(pro, 0.0), 2),
            "B2B Emis": round(b2b_emis.get(pro, 0.0), 2),
            "B2C": round(b2c.get(pro, 0.0), 2),
            "Paiements Reçu B+C": round(total_recu, 2),
            "Rémunération": round(remuneration.get(pro, 0.0), 2),
            "Total Reçu": round(total_recu, 2),
        })

    ranking.sort(key=lambda x: x["Total Reçu"], reverse=True)
    return ranking

def get_professional_detail(num_professionnel, start=None, end=None, year=None):
    rows = fetch_transactions(start=start, end=end, year=year)

    related = []
    for row in rows:
        from_label = str(row.get("from_label", "")).strip()
        to_label = str(row.get("to_label", "")).strip()

        if num_professionnel in from_label or num_professionnel in to_label:
            related.append(row)

    if not related:
        return None

    received = [
        row for row in related
        if num_professionnel in str(row.get("to_label", ""))
        and "conversion" not in str(row.get("from_label", "")).lower()
    ]

    particuliers = {
        str(row.get("from_label", "")).strip()
        for row in related
        if num_professionnel in str(row.get("to_label", ""))
        and str(row.get("from_label", "")).startswith("U")
    }

    professionnels = {
        str(row.get("from_label", "")).strip()
        for row in related
        if num_professionnel in str(row.get("to_label", ""))
        and str(row.get("from_label", "")).startswith("P")
    }

    emis_vers_pro = sum(
        float(row.get("amount", 0) or 0)
        for row in related
        if num_professionnel in str(row.get("from_label", ""))
        and str(row.get("to_label", "")).startswith("P")
    )

    emis_vers_particuliers = sum(
        float(row.get("amount", 0) or 0)
        for row in related
        if num_professionnel in str(row.get("from_label", ""))
        and str(row.get("to_label", "")).startswith("U")
    )

    montant_reconverti = sum(
        float(row.get("amount", 0) or 0)
        for row in related
        if num_professionnel in str(row.get("from_label", ""))
        and "conversion" in str(row.get("to_label", "")).lower()
    )

    montant_converti = sum(
        float(row.get("amount", 0) or 0)
        for row in related
        if num_professionnel in str(row.get("to_label", ""))
        and "conversion" in str(row.get("from_label", "")).lower()
    )

    dates = [row["date"] for row in related if row.get("date")]
    stats = {
        "nb_particuliers": len(particuliers),
        "nb_professionnels": len(professionnels),
        "premiere_date": min(dates)[:10] if dates else "-",
        "derniere_date": max(dates)[:10] if dates else "-",
        "nb_transactions_recues": len(received),
        "somme_transactions_recues": float(sum(float(r.get("amount", 0) or 0) for r in received)),
        "montant_emis_vers_pro": float(emis_vers_pro),
        "montant_emis_vers_particuliers": float(emis_vers_particuliers),
        "montant_reconverti": float(montant_reconverti),
        "montant_converti": float(montant_converti),
        "total_montant_emis_sans_reconversion": float(emis_vers_pro + emis_vers_particuliers),
    }

    transactions = [
        {
            "Date": row["date"][:10],
            "Réalisé par": row.get("from_label", ""),
            "Vers": row.get("to_label", ""),
            "Montant": float(row.get("amount", 0) or 0),
        }
        for row in related
    ]

    fullname = next(
        (
            label for label in (
                str(related[0].get("from_label", "")),
                str(related[0].get("to_label", "")),
            )
            if num_professionnel in label
        ),
        num_professionnel
    )

    return {
        "professionnel": num_professionnel,
        "fullname": fullname,
        "stats": stats,
        "transactions": transactions,
    }


def compute_stats_charts(start=None, end=None, year=None):
    rows = fetch_transactions(start=start, end=end, year=year)

    if not rows:
        return {
            "daily": {"labels": [], "values": []},
            "weekly": {"labels": [], "values": []},
            "hourly": {"labels": [], "values": []},
            "weekday": {"labels": [], "values": []},
            "cumulative": {"labels": [], "values": []},
        }

    parsed = []
    for row in rows:
        raw_date = str(row.get("date", "")).strip()
        amount = float(row.get("amount", 0) or 0)

        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except Exception:
            continue

        parsed.append({
            "dt": dt,
            "amount": amount
        })

    if not parsed:
        return {
            "daily": {"labels": [], "values": []},
            "weekly": {"labels": [], "values": []},
            "hourly": {"labels": [], "values": []},
            "weekday": {"labels": [], "values": []},
            "cumulative": {"labels": [], "values": []},
        }

    # 1) daily count
    daily_counts = {}
    for row in parsed:
        day = row["dt"].date().isoformat()
        daily_counts[day] = daily_counts.get(day, 0) + 1

    daily_labels = sorted(daily_counts.keys())
    daily_values = [daily_counts[day] for day in daily_labels]

    # 2) weekly average amount
    weekly_buckets = {}
    for row in parsed:
        iso_year, iso_week, _ = row["dt"].isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        weekly_buckets.setdefault(key, {"sum": 0.0, "count": 0})
        weekly_buckets[key]["sum"] += row["amount"]
        weekly_buckets[key]["count"] += 1

    weekly_labels = sorted(weekly_buckets.keys())
    weekly_values = [
        weekly_buckets[key]["sum"] / weekly_buckets[key]["count"]
        if weekly_buckets[key]["count"] else 0.0
        for key in weekly_labels
    ]

    # 3) hourly count
    hourly_counts = {hour: 0 for hour in range(24)}
    for row in parsed:
        hourly_counts[row["dt"].hour] += 1

    hourly_labels = [f"{hour:02d}h" for hour in range(24)]
    hourly_values = [hourly_counts[hour] for hour in range(24)]

    # 4) weekday count
    weekday_labels = [
        "Lundi", "Mardi", "Mercredi",
        "Jeudi", "Vendredi", "Samedi", "Dimanche"
    ]
    weekday_counts = {i: 0 for i in range(7)}
    for row in parsed:
        weekday_counts[row["dt"].weekday()] += 1

    weekday_values = [weekday_counts[i] for i in range(7)]

    # 5) cumulative volume par jour
    daily_amounts = {}
    for row in parsed:
        day = row["dt"].date().isoformat()
        daily_amounts[day] = daily_amounts.get(day, 0.0) + row["amount"]

    cumulative_labels = sorted(daily_amounts.keys())
    cumulative_values = []
    running = 0.0

    for day in cumulative_labels:
        running += daily_amounts[day]
        cumulative_values.append(running)

    return {
        "daily": {
            "labels": daily_labels,
            "values": daily_values,
        },
        "weekly": {
            "labels": weekly_labels,
            "values": weekly_values,
        },
        "hourly": {
            "labels": hourly_labels,
            "values": hourly_values,
        },
        "weekday": {
            "labels": weekday_labels,
            "values": weekday_values,
        },
        "cumulative": {
            "labels": cumulative_labels,
            "values": cumulative_values,
        },
    }