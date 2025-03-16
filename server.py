import os
import json
import pandas as pd
from flask import Flask, request, jsonify, render_template

# Import des modules dédiés
from standardize import standardize_file
from sort import compute_professionals_ranking

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["DATA_FOLDER"] = "datas"
# Répertoire contenant les patterns (mapping vertical/horizontal)
app.config["PATTERNS_DIR"] = os.path.join(app.root_path, "static", "mapping", "patterns")

# Assurer que les dossiers existent
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["DATA_FOLDER"], exist_ok=True)

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "Fichier non fourni"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nom de fichier vide"}), 400

    # Sauvegarde temporaire du fichier uploadé
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(file_path)

    try:
        # Appel à la fonction de standardisation (définie dans standardize.py)
        output_filename, pattern_used = standardize_file(
            file_path,
            app.config["PATTERNS_DIR"],
            app.config["DATA_FOLDER"]
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "message": "Fichier transformé créé",
        "output": output_filename
    }), 200

@app.route('/data/<filename>')
def get_data(filename):
    output_path = os.path.join(app.config["DATA_FOLDER"], filename)
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/datasets')
def list_datasets():
    try:
        files = os.listdir(app.config["DATA_FOLDER"])
        # Ne garder que les fichiers JSON
        json_files = [f for f in files if f.endswith('.json')]
        return jsonify(json_files)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ranking/<filename>')
def get_ranking(filename):
    """
    Cet endpoint charge le fichier standardisé, convertit les données en DataFrame,
    calcule le classement via compute_professionals_ranking (sort.py) et renvoie le résultat au format JSON.
    """
    output_path = os.path.join(app.config["DATA_FOLDER"], filename)
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            standardized_data = json.load(f)
        # Conversion du JSON (liste de listes) en DataFrame
        df_standardized = pd.DataFrame(standardized_data[1:], columns=standardized_data[0])
        ranking_df = compute_professionals_ranking(df_standardized)
        ranking_json = ranking_df.to_dict(orient='records')
        return jsonify(ranking_json)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/newtable/<filename>')
def get_new_table(filename):
    output_path = os.path.join(app.config["DATA_FOLDER"], filename)
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            standardized_data = json.load(f)
        # Convertir le JSON (liste de listes) en DataFrame
        df_standardized = pd.DataFrame(standardized_data[1:], columns=standardized_data[0])
        # Calcul du nouveau tableau avec la fonction de tri
        new_table_df = compute_professionals_ranking(df_standardized)
        new_table_json = new_table_df.to_dict(orient='records')
        return jsonify(new_table_json)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
