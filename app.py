from server import create_app
from flask import render_template

app = create_app()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/transactions-live")
def transactions_live():
    return render_template("transactions_live.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8001, debug=False)