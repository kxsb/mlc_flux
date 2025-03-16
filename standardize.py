# standardize.py

import os
import json
import pandas as pd
import math

def load_patterns(patterns_dir):
    """
    Charge les patterns de mapping depuis le dossier patterns_dir.
    """
    patterns = []
    for filename in ["comchain.json", "cyclos.json", "kohinos.json"]:
        path = os.path.join(patterns_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            patterns.append(json.load(f))
    return patterns

def detect_structure(data, patterns):
    """
    Détecte la structure du fichier en comparant la première ligne (les en-têtes)
    aux valeurs attendues dans le mapping horizontal de chaque pattern.
    """
    header = data[0]
    for pattern in patterns:
        expected_headers = list(pattern.get("horizontalMapping", {}).values())
        if all(item in header for item in expected_headers):
            return pattern
    return None

def transform_data(data, pattern):
    """
    Transforme les données brutes en se basant sur le mapping horizontal du pattern.
    Le résultat est un tableau de listes dont la première ligne contient les colonnes standardisées.
    """
    header = data[0]
    mapping = pattern.get("horizontalMapping", {})
    # Construction d'un dictionnaire d'index pour retrouver la position de chaque colonne
    index_mapping = {}
    for standard_field, original_field in mapping.items():
        if original_field in header:
            index_mapping[standard_field] = header.index(original_field)
    
    # Construction du tableau standardisé avec comme en-tête les clés du mapping
    standardized_data = [list(mapping.keys())]
    for row in data[1:]:
        new_row = []
        for field in mapping.keys():
            idx = index_mapping.get(field)
            new_row.append(row[idx] if idx is not None and idx < len(row) else None)
        standardized_data.append(new_row)
    return standardized_data

def identify_type_by_keywords(value, coffre_keywords, pro_keywords, part_keywords):
    """
    Identifie le type d'utilisateur en se basant sur des mots-clés.
    Retourne :
      - "P" si la valeur contient un mot-clé professionnel,
      - "U" si elle contient un mot-clé particulier,
      - "C" sinon (donc, considéré comme le coffre).
    """
    if not isinstance(value, str):
        return "C"
    
    val = value.lower().strip()

    for kw in coffre_keywords:
        if kw.lower() in val:
            return "C"

    for kw in pro_keywords:
        if kw.lower() in val:
            return "P"
        
    for kw in part_keywords:
        if kw.lower() in val:
            return "U"
    return "C"

def identify_type_by_mapping(value, mapping):
    """
    Utilise un mapping (ex. expTypeMapping ou destTypeMapping) pour déterminer la nature d'un utilisateur.
    Si le mot clé est trouvé dans la valeur, retourne "P" pour Professionnel ou "U" pour Particulier.
    Sinon, retourne "C" (pour Coffre).
    """
    if not isinstance(value, str):
        return "C"
    v = value.lower().strip()
    for key, mapped in mapping.items():
        if key.lower() in v:
            if mapped.lower() == "professionnel":
                return "P"
            elif mapped.lower() == "particulier":
                return "U"
    return "C"

def enrich_data_with_types(standardized_data, pattern):
    """
    Ajoute deux colonnes aux données standardisées : 
      - "Type_Expéditeur" et "Type_Destinataire"
    La détermination se base sur le pattern utilisé.
    """
    header = standardized_data[0]
    new_header = header + ["Type_Expéditeur", "Type_Destinataire"]
    new_data = [new_header]
    
    idx_expediteur = header.index("Expéditeur")
    idx_destinataire = header.index("Destinataire")
    
    # Pour les patterns autres que "cyclos", le traitement est simple
    if pattern["name"].lower() in ["comchain", "kohinos"]:
        for row in standardized_data[1:]:
            exp = row[idx_expediteur]
            dest = row[idx_destinataire]
            
            if pattern["name"].lower() == "comchain":
                keywords = pattern.get("verticalMappingRules", {}).get("keywords", {})
                coffre_keywords = []
                pro_keywords = keywords.get("Professionnel", [])
                part_keywords = keywords.get("Particulier", [])
                type_expediteur = identify_type_by_keywords(exp, coffre_keywords, pro_keywords, part_keywords)
                type_destinataire = identify_type_by_keywords(dest, coffre_keywords, pro_keywords, part_keywords)
            elif pattern["name"].lower() == "kohinos":
                exp_mapping = pattern.get("verticalMappingRules", {}).get("expTypeMapping", {})
                dest_mapping = pattern.get("verticalMappingRules", {}).get("destTypeMapping", {})
                type_expediteur = identify_type_by_mapping(exp, exp_mapping)
                type_destinataire = identify_type_by_mapping(dest, dest_mapping)
            
            new_row = row + [type_expediteur, type_destinataire]
            new_data.append(new_row)
    
    elif pattern["name"].lower() == "cyclos":
        # Récupérer la position des colonnes une seule fois
        idx_expediteur = header.index("Expéditeur")
        idx_destinataire = header.index("Destinataire")
        idx_groupe_expediteur = header.index("Groupe Expéditeur") if "Groupe Expéditeur" in header else None
        idx_groupe_destinataire = header.index("Groupe Destinataire") if "Groupe Destinataire" in header else None
        
        keywords = pattern.get("verticalMappingRules", {}).get("keywords", {})
        coffre_keywords = keywords.get("Coffre", [])
        pro_keywords = keywords.get("Professionnel", [])
        part_keywords = keywords.get("Particulier", [])
        empty_means_coffre = pattern.get("verticalMappingRules", {}).get("emptyMeansCoffre", False)
        
        # Traitement ligne par ligne
        for row in standardized_data[1:]:
            # Pour l'expéditeur
            exp_value = row[idx_expediteur]
            if idx_groupe_expediteur is not None:
                groupe_expediteur = row[idx_groupe_expediteur]
                # Gérer le NaN ou la chaîne vide
                if not isinstance(groupe_expediteur, str) or not groupe_expediteur.strip():
                    value = exp_value
                else:
                    value = groupe_expediteur
            else:
                value = exp_value
            
            if empty_means_coffre and (not value or str(value).strip() == ""):
                type_expediteur = "C"
            else:
                type_expediteur = identify_type_by_keywords(str(value), coffre_keywords, pro_keywords, part_keywords)
            
            # Pour le destinataire
            dest_value = row[idx_destinataire]
            if idx_groupe_destinataire is not None:
                groupe_destinataire = row[idx_groupe_destinataire]
                if not isinstance(groupe_destinataire, str) or not groupe_destinataire.strip():
                    value_dest = dest_value
                else:
                    value_dest = groupe_destinataire
            else:
                value_dest = dest_value
            
            if empty_means_coffre and (not value_dest or str(value_dest).strip() == ""):
                type_destinataire = "C"
            else:
                type_destinataire = identify_type_by_keywords(str(value_dest), coffre_keywords, pro_keywords, part_keywords)
            
            new_row = row + [type_expediteur, type_destinataire]
            new_data.append(new_row)    
    return new_data

def standardize_file(file_path, patterns_dir, output_folder):
    """
    Lit un fichier XLSX, détecte le pattern, transforme les données brutes en données standardisées,
    ajoute les colonnes d'identification et sauvegarde le résultat en JSON dans output_folder.
    
    Retourne le nom du fichier généré et le pattern utilisé.
    """
    # Chargement des patterns
    patterns = load_patterns(patterns_dir)
    
    try:
        # Lecture du fichier XLSX avec Pandas
        df = pd.read_excel(file_path)
    except Exception as e:
        raise Exception("Erreur lors de la lecture du fichier: " + str(e))
    
    # Conversion du DataFrame en liste de listes (la première ligne contient les en-têtes)
    data = [df.columns.tolist()] + df.values.tolist()
    
    # Détection du pattern
    pattern = detect_structure(data, patterns)
    if not pattern:
        raise Exception("Structure non reconnue")
    
    # Transformation horizontale
    standardized_data = transform_data(data, pattern)
    
    # Enrichissement avec les colonnes de type
    enriched_data = enrich_data_with_types(standardized_data, pattern)
    
    # Nettoyer les données pour remplacer les NaN par None
    enriched_data = clean_data(enriched_data)

    # Définition du nom de fichier de sortie
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    output_filename = base_filename + "_standardized.json"
    output_path = os.path.join(output_folder, output_filename)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enriched_data, f, ensure_ascii=False, indent=4, default=str)
    
    return output_filename, pattern

def clean_data(data):
    """
    Parcourt un tableau de listes et remplace toute valeur NaN par None.
    """
    new_data = []
    for row in data:
        new_row = []
        for val in row:
            if isinstance(val, float) and math.isnan(val):
                new_row.append(None)  # null en JSON
            else:
                new_row.append(val)
        new_data.append(new_row)
    return new_data
