from server import create_app
from flask import render_template, request, jsonify
from server.services.monetary_indicators_adaptive import get_adaptive_monetary_indicators
import os

app = create_app()


@app.route("/")
def mlc_select():
    return render_template("mlc_select.html")


@app.route("/app")
def home():
    return render_template("index.html")


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
    mlc_id = request.args.get("mlc") or os.environ.get("MLCFLUX_DEFAULT_MLC_ID") or "gonette"

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

