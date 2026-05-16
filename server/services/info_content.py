import os
import tempfile
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INFO_MARKDOWN_FILE = DATA_DIR / "info.md"

DEFAULT_INFO_MARKDOWN = """# MLCFlux — Informations & méthodologie

Cette page documente progressivement les données, indicateurs et formules utilisés dans MLCFlux.

> Le contenu est éditable directement depuis l’interface, au format Markdown.

## Ce que mesure MLCFlux

MLCFlux vise prioritairement à analyser la **circulation économique de la Gonette numérique dans le réseau**.

Cette circulation économique correspond aux transactions entre acteurs identifiés :

| Flux | Lecture |
|---|---|
| `U → P` | Dépense d’un particulier vers un professionnel |
| `P → P` | Circulation interprofessionnelle |
| `P → U` | Flux d’un professionnel vers un particulier |
| `U → U` | Transfert entre particuliers |

## Ce qui doit être analysé séparément

Les opérations suivantes sont importantes, mais elles ne doivent pas être confondues avec la circulation économique :

- émissions ou crédits de monnaie ;
- reconversions ;
- annulations ou avoirs ;
- opérations techniques ou corrections.

## Formules à documenter

Cette vue a vocation à préciser progressivement :

- les acteurs actifs `P` et `U` ;
- le nombre de transactions de circulation ;
- le volume de circulation ;
- les montants moyens `U→P`, `P→P`, `P→U`, `U→U` ;
- le nombre moyen de transactions par jour ;
- les formules de taux de réutilisation ;
- les périmètres des analyses territoriales et sectorielles.

## État du chantier

Cette documentation sera consolidée au fil de l’audit analytique et des corrections des formules.
"""


def ensure_info_markdown_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not INFO_MARKDOWN_FILE.exists():
        write_info_markdown(DEFAULT_INFO_MARKDOWN)


def read_info_markdown():
    ensure_info_markdown_file()
    return INFO_MARKDOWN_FILE.read_text(encoding="utf-8")


def write_info_markdown(markdown):
    if not isinstance(markdown, str):
        raise TypeError("Le contenu Markdown doit être une chaîne de caractères.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        prefix=".info_",
        suffix=".md.tmp",
        dir=str(DATA_DIR),
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as tmp_file:
            tmp_file.write(markdown)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        os.replace(tmp_path, INFO_MARKDOWN_FILE)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
