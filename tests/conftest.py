import os
import sys
from pathlib import Path


# Garantit que les imports applicatifs (`app`, `server.*`) résolvent la racine
# du dépôt, y compris lorsque pytest est lancé via son script console du venv
# plutôt que via `python -m pytest`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT_TEXT = str(PROJECT_ROOT)
if PROJECT_ROOT_TEXT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_TEXT)


# Les tests représentent une installation standalone explicitement configurée.
# Les tests qui vérifient l'absence de configuration suppriment cette variable
# localement via monkeypatch.
os.environ.setdefault("MLCFLUX_DEFAULT_MLC_ID", "gonette")
