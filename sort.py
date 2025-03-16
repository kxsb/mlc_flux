# sort.py

import pandas as pd
import numpy as np

def compute_professionals_ranking(df):
    """
    Calcule le classement des professionnels à partir d'un DataFrame standardisé enrichi.
    
    Le DataFrame doit contenir les colonnes suivantes :
      - "Montant" : Valeurs numériques indiquant le montant de chaque transaction.
      - "Expéditeur", "Destinataire" : Noms des comptes.
      - "Type_Expéditeur", "Type_Destinataire" : Type du compte, avec :
           "P" pour Professionnel,
           "U" pour Particulier,
           "C" pour Coffre (non identifié comme pro ou particulier).
    
    Agrégations appliquées :
      - **B2B Reçu** : Somme des montants pour les transactions où le Destinataire est "P" et
                        l'Expéditeur est "P" ou "U".
      - **B2B Emis** : Somme des montants pour les transactions où Expéditeur et Destinataire sont "P".
      - **Rémunération** : Somme des montants pour les transactions où l'Expéditeur est "P" et
                          le Destinataire est "U".
      - **Reconversion** : Somme des montants pour les transactions où le Destinataire est "P" et
                           l'Expéditeur est "C".
      - **Total Reçu** : B2B Reçu + Reconversion.
    
    Retourne un DataFrame avec les colonnes :
      ['Professionnel', 'B2B Reçu', 'B2B Emis', 'Rémunération', 'Reconversion', 'Total Reçu']
    trié par Total Reçu décroissant.
    """
    if df.empty:
        return pd.DataFrame()
    
  
    # Vérification des colonnes attendues
    expected_columns = ["Montant", "Expéditeur", "Destinataire", "Type_Expéditeur", "Type_Destinataire"]
    missing_columns = [col for col in expected_columns if col not in df.columns]
    if missing_columns:
        print("Attention, colonnes manquantes dans le DataFrame :", missing_columns)
        # Optionnellement : return pd.DataFrame()

    # S'assurer que la colonne Montant est bien numérique
    df['Montant'] = pd.to_numeric(df['Montant'], errors='coerce').fillna(0)
    
    # Calcul de B2B Reçu :
    mask_b2b_recu = (df['Type_Destinataire'] == 'P') & (df['Type_Expéditeur'].isin(['P', 'U']))
    b2b_recu = df[mask_b2b_recu].groupby('Destinataire')['Montant'].sum().reset_index()
    b2b_recu = b2b_recu.rename(columns={'Destinataire': 'Professionnel', 'Montant': 'B2B Reçu'})
    print("B2B Reçu:", df[mask_b2b_recu].shape)
    print("Exemple B2B Reçu:", df[mask_b2b_recu].head())
    
    # Calcul de B2B Emis :
    mask_b2b_emis = (df['Type_Expéditeur'] == 'P') & (df['Type_Destinataire'] == 'P')
    b2b_emis = df[mask_b2b_emis].groupby('Expéditeur')['Montant'].sum().reset_index()
    b2b_emis = b2b_emis.rename(columns={'Expéditeur': 'Professionnel', 'Montant': 'B2B Emis'})
    print("B2B Emis:", df[mask_b2b_emis].shape)
    print("Exemple B2B Emis:", df[mask_b2b_emis].head())

    # Calcul de la Rémunération :
    mask_remu = (df['Type_Expéditeur'] == 'P') & (df['Type_Destinataire'] == 'U')
    remuneration = df[mask_remu].groupby('Expéditeur')['Montant'].sum().reset_index()
    remuneration = remuneration.rename(columns={'Expéditeur': 'Professionnel', 'Montant': 'Rémunération'})
    print("Rémunération:", df[mask_remu].shape)
    print("Exemple Rémunération:", df[mask_remu].head())

    # Calcul de la Reconversion :
    mask_reconv = (df['Type_Destinataire'] == 'P') & (df['Type_Expéditeur'] == 'C')
    reconversion = df[mask_reconv].groupby('Destinataire')['Montant'].sum().reset_index()
    reconversion = reconversion.rename(columns={'Destinataire': 'Professionnel', 'Montant': 'Reconversion'})
    print("Reconversion:", df[mask_reconv].shape)
    print("Exemple Reconversion:", df[mask_reconv].head())
    
    # Fusionner les agrégats sur la colonne "Professionnel"
    ranking = pd.merge(b2b_recu, b2b_emis, on='Professionnel', how='outer')
    ranking = pd.merge(ranking, remuneration, on='Professionnel', how='outer')
    ranking = pd.merge(ranking, reconversion, on='Professionnel', how='outer')
    ranking = ranking.fillna(0)
    
    # Calcul du Total Reçu = B2B Reçu + Reconversion
    ranking['Total Reçu'] = ranking['B2B Reçu'] + ranking['Reconversion']
    
    # Réorganisation des colonnes et tri par Total Reçu décroissant
    ranking = ranking[['Professionnel', 'B2B Reçu', 'B2B Emis', 'Rémunération', 'Reconversion', 'Total Reçu']]
    ranking = ranking.sort_values(by='Total Reçu', ascending=False)
    
    cols_to_round = ["B2B Reçu", "B2B Emis", "Rémunération", "Reconversion", "Total Reçu"]
    ranking[cols_to_round] = ranking[cols_to_round].apply(np.ceil).astype(int)

    print("Aperçu du ranking final :")
    print(ranking.head())
    
    return ranking
