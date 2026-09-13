import os


# Les tests représentent une installation standalone explicitement configurée.
# Les tests qui vérifient l'absence de configuration suppriment cette variable
# localement via monkeypatch.
os.environ.setdefault("MLCFLUX_DEFAULT_MLC_ID", "gonette")
