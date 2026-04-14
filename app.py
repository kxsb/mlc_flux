from flask import Flask, jsonify, render_template, request
from data_manager import DataManager
import pandas as pd

app = Flask(__name__)

DATA_DIR = "/home/kxsb/mlcflux_app/data"
dm = DataManager(DATA_DIR)
stats_cache = {}
stats_charts_cache = {}
network_cache = {}
pros_cache = {}
years_cache = []


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/stats_charts")
def stats_charts():
    global stats_charts_cache

    year = request.args.get("year", default=None, type=int)
    cache_key = year if year is not None else "all"

    if cache_key in stats_charts_cache:
        return jsonify(stats_charts_cache[cache_key])

    df = dm.df_total

    if df.empty:
        result = {
            "daily": {"labels": [], "values": []},
            "weekly_avg": {"labels": [], "values": []},
            "hourly": {"labels": [], "values": []},
            "weekday": {"labels": [], "values": []},
            "cumulative": {"labels": [], "values": []}
        }
        stats_charts_cache[cache_key] = result
        return jsonify(result)

    if year is not None:
        df = df[df["Date"].dt.year == year]

    if df.empty:
        result = {
            "daily": {"labels": [], "values": []},
            "weekly_avg": {"labels": [], "values": []},
            "hourly": {"labels": [], "values": []},
            "weekday": {"labels": [], "values": []},
            "cumulative": {"labels": [], "values": []}
        }
        stats_charts_cache[cache_key] = result
        return jsonify(result)

    work = df.copy()
    work["day"] = work["Date"].dt.strftime("%d-%m-%Y")
    work["week_start"] = (
        work["Date"] - pd.to_timedelta(work["Date"].dt.weekday, unit="D")
    ).dt.strftime("%d-%m-%Y")
    work["hour"] = work["Date"].dt.hour
    work["weekday"] = work["Date"].dt.weekday

    daily_df = (
        work.groupby("day", sort=False)["Montant"]
        .size()
        .reset_index(name="count")
    )
    daily_df["sort_date"] = pd.to_datetime(daily_df["day"], format="%d-%m-%Y", errors="coerce")
    daily_df = daily_df.sort_values("sort_date")

    weekly_df = (
        work.groupby("week_start", sort=False)["Montant"]
        .mean()
        .reset_index(name="avg")
    )
    weekly_df["sort_date"] = pd.to_datetime(weekly_df["week_start"], format="%d-%m-%Y", errors="coerce")
    weekly_df = weekly_df.sort_values("sort_date")

    hourly_series = work.groupby("hour")["Montant"].size()
    hourly_labels = [f"{h:02d}h" for h in range(24)]
    hourly_values = [int(hourly_series.get(h, 0)) for h in range(24)]

    weekday_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    weekday_series = work.groupby("weekday")["Montant"].size()
    weekday_values = [int(weekday_series.get(i, 0)) for i in range(7)]

    cumulative_daily = (
        work.groupby("day", sort=False)["Montant"]
        .sum()
        .reset_index(name="sum")
    )
    cumulative_daily["sort_date"] = pd.to_datetime(cumulative_daily["day"], format="%d-%m-%Y", errors="coerce")
    cumulative_daily = cumulative_daily.sort_values("sort_date")
    cumulative_daily["cumulative"] = cumulative_daily["sum"].cumsum()

    result = {
        "daily": {
            "labels": daily_df["day"].tolist(),
            "values": daily_df["count"].astype(int).tolist()
        },
        "weekly_avg": {
            "labels": weekly_df["week_start"].tolist(),
            "values": weekly_df["avg"].astype(float).tolist()
        },
        "hourly": {
            "labels": hourly_labels,
            "values": hourly_values
        },
        "weekday": {
            "labels": weekday_names,
            "values": weekday_values
        },
        "cumulative": {
            "labels": cumulative_daily["day"].tolist(),
            "values": cumulative_daily["cumulative"].astype(float).tolist()
        }
    }

    stats_charts_cache[cache_key] = result
    return jsonify(result)

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/api/years")
def years():
    global years_cache

    if years_cache:
        return jsonify(years_cache)

    df = getattr(dm, "df_total", None)

    if df is None or df.empty or "Date" not in df.columns:
        return jsonify([])

    years_cache = (
        df["Date"]
        .dropna()
        .dt.year
        .dropna()
        .astype(int)
        .sort_values()
        .unique()
        .tolist()
    )

    return jsonify(years_cache)


@app.route("/api/stats")
def stats():
    global stats_cache

    year = request.args.get("year", default=None, type=int)
    cache_key = year if year is not None else "all"

    if cache_key in stats_cache:
        return jsonify(stats_cache[cache_key])

    df = dm.df_total

    if df.empty:
        result = {
            "periode": "-",
            "nb_utilisateurs": 0,
            "moyenne_transactions_PP": 0.0,
            "moyenne_paiement_UP": 0.0,
            "moyenne_transactions_UU": 0.0
        }
        stats_cache[cache_key] = result
        return jsonify(result)

    if year is not None:
        df = df[df["Date"].dt.year == year]

    if df.empty:
        result = {
            "periode": "-",
            "nb_utilisateurs": 0,
            "moyenne_transactions_PP": 0.0,
            "moyenne_paiement_UP": 0.0,
            "moyenne_transactions_UU": 0.0
        }
        stats_cache[cache_key] = result
        return jsonify(result)

    realise_str = df["Réalisé par"].astype(str)
    vers_str = df["Vers"].astype(str)

    acteurs = pd.Series(df[["Réalisé par", "Vers"]].astype(str).values.ravel("K"))
    acteurs = acteurs[acteurs.str.strip() != ""]

    transactions_pp = df[
        realise_str.str.startswith("P") & vers_str.str.startswith("P")
    ]

    paiements_up = df[
        realise_str.str.startswith("U") & vers_str.str.startswith("P")
    ]

    transactions_uu = df[
        realise_str.str.startswith("U") & vers_str.str.startswith("U")
    ]

    result = {
        "periode": (
            f"{df['Date'].min().strftime('%d/%m/%Y')} - "
            f"{df['Date'].max().strftime('%d/%m/%Y')}"
        ),
        "nb_utilisateurs": int(acteurs.nunique()),
        "moyenne_transactions_PP": float(transactions_pp["Montant"].mean()) if not transactions_pp.empty else 0.0,
        "moyenne_paiement_UP": float(paiements_up["Montant"].mean()) if not paiements_up.empty else 0.0,
        "moyenne_transactions_UU": float(transactions_uu["Montant"].mean()) if not transactions_uu.empty else 0.0
    }

    stats_cache[cache_key] = result
    return jsonify(result)

@app.route("/api/network")
def api_network():
    global network_cache

    year = request.args.get("year", default=None, type=int)
    cache_key = year if year is not None else "all"

    if cache_key in network_cache:
        return jsonify(network_cache[cache_key])

    df = dm.df_total

    if df.empty:
        result = {"nodes": [], "edges": []}
        network_cache[cache_key] = result
        return jsonify(result)

    if year is not None:
        df = df[df["Date"].dt.year == year]

    if df.empty:
        result = {"nodes": [], "edges": []}
        network_cache[cache_key] = result
        return jsonify(result)

    realise_str = df["Réalisé par"].astype(str)
    vers_str = df["Vers"].astype(str)

    df_pp = df[
        realise_str.str.startswith("P") & vers_str.str.startswith("P")
    ][["Réalisé par", "Vers", "Montant"]]

    if df_pp.empty:
        result = {"nodes": [], "edges": []}
        network_cache[cache_key] = result
        return jsonify(result)

    edges_df = (
        df_pp.groupby(["Réalisé par", "Vers"], observed=True)["Montant"]
        .sum()
        .reset_index()
    )

    nodes = pd.unique(
        pd.concat([edges_df["Réalisé par"], edges_df["Vers"]], ignore_index=True)
    )

    result = {
        "nodes": [
            {"data": {"id": node, "label": node}}
            for node in nodes
        ],
        "edges": [
            {
                "data": {
                    "source": row["Réalisé par"],
                    "target": row["Vers"],
                    "weight": float(row["Montant"])
                }
            }
            for _, row in edges_df.iterrows()
        ]
    }

    network_cache[cache_key] = result
    return jsonify(result)

@app.route("/api/pros")
def pros():
    global pros_cache

    year = request.args.get("year", default=None, type=int)
    cache_key = year if year is not None else "all"

    if cache_key in pros_cache:
        return jsonify(pros_cache[cache_key])

    df = dm.df_total

    if df.empty:
        pros_cache[cache_key] = []
        return jsonify([])

    if year is not None:
        df = df[df["Date"].dt.year == year]

    if df.empty:
        pros_cache[cache_key] = []
        return jsonify([])

    realise_str = df["Réalisé par"].astype(str)
    vers_str = df["Vers"].astype(str)

    somme_b2b_recu = (
        df[
            vers_str.str.startswith("P")
            & realise_str.str.startswith("P")
        ]
        .groupby("Vers", observed=True)["Montant"]
        .sum()
        .reset_index()
        .rename(columns={"Montant": "B2B Reçu", "Vers": "Professionnel"})
    )

    somme_b2b_emis = (
        df[
            realise_str.str.startswith("P")
            & vers_str.str.startswith("P")
        ]
        .groupby("Réalisé par", observed=True)["Montant"]
        .sum()
        .reset_index()
        .rename(columns={"Montant": "B2B Emis", "Réalisé par": "Professionnel"})
    )

    somme_b2c = (
        df[
            realise_str.str.startswith("U")
            & vers_str.str.startswith("P")
        ]
        .groupby("Vers", observed=True)["Montant"]
        .sum()
        .reset_index()
        .rename(columns={"Montant": "B2C", "Vers": "Professionnel"})
    )

    somme_remuneration = (
        df[
            realise_str.str.startswith("P")
            & vers_str.str.startswith("U")
        ]
        .groupby("Réalisé par", observed=True)["Montant"]
        .sum()
        .reset_index()
        .rename(columns={"Montant": "Rémunération", "Réalisé par": "Professionnel"})
    )

    ranking = pd.merge(somme_b2b_recu, somme_b2b_emis, on="Professionnel", how="outer")
    ranking = pd.merge(ranking, somme_b2c, on="Professionnel", how="outer").fillna(0)
    ranking = pd.merge(ranking, somme_remuneration, on="Professionnel", how="outer").fillna(0)

    ranking["Total Reçu"] = ranking["B2B Reçu"] + ranking["B2C"]
    ranking["Paiements Reçu B+C"] = ranking["Total Reçu"]

    ranking.sort_values(by="Total Reçu", ascending=False, inplace=True)

    ranking = ranking[
        [
            "Professionnel",
            "B2B Reçu",
            "B2B Emis",
            "B2C",
            "Paiements Reçu B+C",
            "Rémunération",
            "Total Reçu",
        ]
    ]

    result = ranking.to_dict(orient="records")
    pros_cache[cache_key] = result
    return jsonify(result)


@app.route("/api/professionnels")
def professionnels():
    return jsonify(dm.extraire_identifiants_professionnels())


@app.route("/api/pro/<num_professionnel>")
def pro_detail(num_professionnel):
    stats = dm.compute_professional_statistics(num_professionnel)
    fullname = dm.get_professional_fullname(num_professionnel)
    transactions = dm.get_professional_transactions(num_professionnel)

    if stats is None:
        return jsonify({"error": "Professionnel introuvable"}), 404

    return jsonify(
        {
            "professionnel": num_professionnel,
            "fullname": fullname,
            "stats": stats,
            "transactions": transactions.to_dict(orient="records"),
        }
    )


@app.route("/api/reload", methods=["POST"])
def reload_data():
    global stats_cache, stats_charts_cache, network_cache, pros_cache, years_cache

    try:
        stats_cache = {}
        stats_charts_cache = {}
        network_cache = {}
        pros_cache = {}
        years_cache = []

        return jsonify(
            {
                "status": "ok",
                "rows": int(len(df)),
                "message": "Données rechargées avec succès",
            }
        )
    except Exception as e:
        return jsonify(
            {
                "status": "error",
                "message": str(e),
            }
        ), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
