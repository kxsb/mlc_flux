# Tests MLCFlux Neutral

Ce répertoire contient le filet de tests posé avant la refactorisation
de `mlcflux_neutral_dev`.

## Tests synthétiques

`test_transaction_semantics_profiles.py`

Vérifie les profils transactionnels Gonette et Graine sur des cas
synthétiques contrôlés.

## Tests HTTP de caractérisation

`test_http_characterization.py`

Fige certains comportements de l'application au début du chantier
Neutral. Ces tests décrivent le comportement existant, y compris
certains comportements qui pourront volontairement être modifiés
ultérieurement.

## Tests sur snapshots réels

`test_real_snapshot_characterization.py`

Les bases et mappings réels ne sont jamais versionnés.

Les tests utilisent localement :

- `server/data/instances/gonette/mlcflux.db`
- `server/data/instances/graine/mlcflux.db`

La baseline versionnée ne contient que des empreintes SHA-256
d'agrégats sémantiques canoniques.

Snapshot de référence :

- date : 2026-09-12
- commit source : `ccd78a2c7ce9ab95e658d11f957d4a7a708437f8`
- archive runtime SHA-256 :
  `6b56d65b31f821e5be8d441341fe08456098853f26dd9c355f084afcbe6b7d63`

Si les snapshots locaux sont absents, les tests correspondants sont
ignorés avec `pytest.skip`.
