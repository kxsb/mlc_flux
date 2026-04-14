import re
from pathlib import Path
import pandas as pd


class DataManager:
    REQUIRED_COLUMNS = ["Date", "Réalisé par", "Vers", "Montant"]
    EMPTY_COLUMNS = ["Date", "Réalisé par", "Vers", "Montant", "source_file"]

    def __init__(self, data_dir=None):
        self.df_total = pd.DataFrame(columns=self.EMPTY_COLUMNS)
        self.data_dir = Path(data_dir) if data_dir else None

        if self.data_dir:
            self.load_from_directory(self.data_dir)

    def load_excel(self, file_path):
        df = pd.read_excel(file_path, usecols=self.REQUIRED_COLUMNS)
        self._normalize_dataframe(df)
        df["source_file"] = Path(file_path).name
        return df

    def load_from_directory(self, data_dir):
        data_dir = Path(data_dir)

        if not data_dir.exists():
            raise FileNotFoundError(f"Dossier de données introuvable : {data_dir}")

        excel_files = sorted(data_dir.glob("*.xlsx"))

        if not excel_files:
            raise FileNotFoundError(f"Aucun fichier .xlsx trouvé dans : {data_dir}")

        dataframes = []
        for file_path in excel_files:
            try:
                df = self.load_excel(file_path)
                if not df.empty:
                    dataframes.append(df)
            except Exception as e:
                print(f"[DataManager] Fichier ignoré {file_path.name} : {e}")

        if dataframes:
            self.df_total = pd.concat(dataframes, ignore_index=True, copy=False)
            self.df_total.sort_values("Date", inplace=True)
            self.df_total.reset_index(drop=True, inplace=True)
        else:
            self.df_total = pd.DataFrame(columns=self.EMPTY_COLUMNS)

        self.data_dir = data_dir
        return self.df_total

    def reload(self):
        if not self.data_dir:
            self.df_total = pd.DataFrame(columns=self.EMPTY_COLUMNS)
            return self.df_total

        return self.load_from_directory(self.data_dir)

    def _normalize_dataframe(self, df):
        missing = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"Colonnes manquantes : {missing}")

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Réalisé par"] = df["Réalisé par"].fillna("").astype(str).str.strip()
        df["Vers"] = df["Vers"].fillna("").astype(str).str.strip()
        df["Montant"] = pd.to_numeric(df["Montant"], errors="coerce").fillna(0.0)

        df.dropna(subset=["Date"], inplace=True)

        # Réduction mémoire utile si beaucoup de répétitions
        df["Réalisé par"] = df["Réalisé par"].astype("category")
        df["Vers"] = df["Vers"].astype("category")

    def _mask_for_professional(self, num_professionnel, df=None):
        frame = self.df_total if df is None else df
        return (
            frame["Réalisé par"].astype(str).str.contains(num_professionnel, regex=False, na=False)
            | frame["Vers"].astype(str).str.contains(num_professionnel, regex=False, na=False)
        )

    def get_global_statistics(self):
        if self.df_total.empty:
            return None

        df = self.df_total
        stats = {}

        stats["periode"] = (
            f"{df['Date'].min().strftime('%d/%m/%Y')} - "
            f"{df['Date'].max().strftime('%d/%m/%Y')}"
        )

        acteurs = pd.Series(df[["Réalisé par", "Vers"]].astype(str).values.ravel("K"))
        acteurs = acteurs[acteurs.str.strip() != ""]
        stats["nb_utilisateurs"] = int(acteurs.nunique())

        transactions_pp = df[
            df["Réalisé par"].astype(str).str.startswith("P")
            & df["Vers"].astype(str).str.startswith("P")
        ]
        stats["moyenne_transactions_PP"] = (
            float(transactions_pp["Montant"].mean()) if not transactions_pp.empty else 0.0
        )

        paiements_up = df[
            df["Réalisé par"].astype(str).str.startswith("U")
            & df["Vers"].astype(str).str.startswith("P")
        ]
        stats["moyenne_paiement_UP"] = (
            float(paiements_up["Montant"].mean()) if not paiements_up.empty else 0.0
        )

        transactions_uu = df[
            df["Réalisé par"].astype(str).str.startswith("U")
            & df["Vers"].astype(str).str.startswith("U")
        ]
        stats["moyenne_transactions_UU"] = (
            float(transactions_uu["Montant"].mean()) if not transactions_uu.empty else 0.0
        )

        return stats

    def extraire_identifiants_professionnels(self):
        if self.df_total.empty:
            return []

        pattern = r"P\d{4}"
        data_concat = pd.concat(
            [
                self.df_total["Réalisé par"].astype(str),
                self.df_total["Vers"].astype(str),
            ],
            ignore_index=True,
        )
        identifiants = data_concat[
            data_concat.str.contains(pattern, regex=True, na=False)
        ].unique()

        professionnels_corriges = []
        for ident in identifiants:
            match_id = re.search(pattern, ident)
            if match_id:
                num_pro = match_id.group(0)
                nom_structure = ident.replace(num_pro, "").strip(" -")
                nom_structure = nom_structure.split(" - ")[0]
                label = f"{num_pro} - {nom_structure}".strip(" -")
                professionnels_corriges.append(label)

        return sorted(set(professionnels_corriges))

    def compute_professional_statistics(self, num_professionnel):
        if self.df_total.empty:
            return None

        df = self.df_total
        pro_mask = self._mask_for_professional(num_professionnel, df)

        df_user = df[
            pro_mask & (df["Vers"].astype(str) != "P0000")
        ]

        if df_user.empty:
            return None

        stats = {}

        vers_str = df_user["Vers"].astype(str)
        realise_str = df_user["Réalisé par"].astype(str)

        df_particuliers = df_user[
            vers_str.str.contains(num_professionnel, regex=False, na=False)
            & realise_str.str.startswith("U")
        ]
        stats["nb_particuliers"] = int(df_particuliers["Réalisé par"].nunique())

        df_professionnels = df_user[
            vers_str.str.contains(num_professionnel, regex=False, na=False)
            & realise_str.str.startswith("P")
        ]
        stats["nb_professionnels"] = int(df_professionnels["Réalisé par"].nunique())

        stats["premiere_date"] = df_user["Date"].min().strftime("%d/%m/%Y")
        stats["derniere_date"] = df_user["Date"].max().strftime("%d/%m/%Y")

        transactions_recues = df_user[
            vers_str.str.contains(num_professionnel, regex=False, na=False)
            & (~realise_str.str.contains("conversion", case=False, regex=False, na=False))
        ]
        stats["nb_transactions_recues"] = int(transactions_recues.shape[0])
        stats["somme_transactions_recues"] = float(transactions_recues["Montant"].sum())

        stats["montant_emis_vers_pro"] = float(
            df_user[
                realise_str.str.contains(num_professionnel, regex=False, na=False)
                & vers_str.str.startswith("P")
            ]["Montant"].sum()
        )

        stats["montant_emis_vers_particuliers"] = float(
            df_user[
                realise_str.str.contains(num_professionnel, regex=False, na=False)
                & vers_str.str.startswith("U")
            ]["Montant"].sum()
        )

        stats["montant_reconverti"] = float(
            df_user[
                realise_str.str.contains(num_professionnel, regex=False, na=False)
                & vers_str.str.contains("conversion", case=False, regex=False, na=False)
            ]["Montant"].sum()
        )

        stats["montant_converti"] = float(
            df_user[
                vers_str.str.contains(num_professionnel, regex=False, na=False)
                & realise_str.str.contains("conversion", case=False, regex=False, na=False)
            ]["Montant"].sum()
        )

        stats["total_montant_emis_sans_reconversion"] = float(
            stats["montant_emis_vers_pro"] + stats["montant_emis_vers_particuliers"]
        )

        return stats

    def get_professional_fullname(self, num_professionnel):
        if self.df_total.empty:
            return num_professionnel

        mask = self._mask_for_professional(num_professionnel)
        row = self.df_total.loc[mask, ["Réalisé par", "Vers"]].head(1)

        if row.empty:
            return num_professionnel

        realise_par = str(row["Réalisé par"].iloc[0])
        vers = str(row["Vers"].iloc[0])

        return realise_par if num_professionnel in realise_par else vers

    def compute_professionals_ranking(self):
        df = self.df_total
        if df.empty:
            return pd.DataFrame()

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

        return ranking

    def get_professional_transactions(self, num_professionnel):
        if self.df_total.empty:
            return pd.DataFrame(columns=["Date", "Réalisé par", "Vers", "Montant"])

        mask = self._mask_for_professional(num_professionnel)
        df_user = self.df_total.loc[mask, ["Date", "Réalisé par", "Vers", "Montant"]].copy()

        if df_user.empty:
            return df_user

        df_user["Date"] = df_user["Date"].dt.strftime("%d-%m-%Y")
        return df_user
