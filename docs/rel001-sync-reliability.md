# REL001 — fiabilité de la synchronisation

## Base vérifiée

Branche distante `kxsb/mlc_flux:mlcflux_neutral_dev` vérifiée par `git ls-remote`
avant modification : `e121294db15adcdec330174d6aa612158914aa57`,
`refactor(neutral): clean standalone legacy architecture`.
Même HEAD dans le clone propre utilisé pour REL001. Aucun commit, push ou déploiement.

## Échecs enfants

Cause : `run_subprocess_module` retournait normalement un dictionnaire contenant
`returncode != 0` et `ok=False`. La fonction imbriquée `add_step` ne traitait que
les exceptions et marquait donc ce résultat comme une réussite.

Correction locale dans `add_step` : un dictionnaire avec `ok is False`, ou avec un
`returncode` présent différent de zéro, déclenche le traitement d'erreur existant.
L'étape devient `error`, le rapport est marqué `ok=False` et le payload est gardé,
y compris module, code de sortie et stdout/stderr déjà filtrés par le lanceur.
Le cas succès ne change pas.

- Sans `--continue-on-error` : exception immédiate, aucun enfant suivant lancé.
  Comme avant pour les exceptions, pas d'émission du JSON final ni de fichier
  `--json-out` sur ce chemin ; le rapport en mémoire est marqué en échec.
- Avec `--continue-on-error` : les étapes suivantes sont exécutées ; le JSON final
  garde l'étape `error`, `ok=false`, et `main` retourne `1`.

## Contrat du reset et appelants

Recherche de tous les appels de `sync_cyclos_transactions` et de son writer :

| Appelant | Contrat observé |
|---|---|
| `server/sync_mlc_instance.py:sync_transactions_service` | Passe explicitement `reset=False`, `limit=None`, `write=not dry_run`. La synchronisation quotidienne ne vide donc pas la table. |
| `server/build_mlc_db.py:main` | Transmet `reset=args.reset_transactions`, `write=not args.dry_run`, la période et `limit` (100 par défaut sans reset). En reset, exige `--limit none` et les deux bornes explicites `--date-from` / `--date-to` avant tout I/O métier. Le nom public `--reset-transactions`, le champ `deleted` et l'ancien helper `reset_transactions_table` de l'historique confirment le remplacement de toute la table, pas la suppression d'une seule période. |
| `_store_classified_transaction_rows` | Seul appelant : le service ci-dessus, après classification et refus des familles X. |

Cause : le paramètre `reset` était exposé, mais jamais transmis au writer ;
`deleted` restait initialisé à zéro. L'ancien helper de suppression avait été
retiré comme code sans appelant lors de la passe précédente.

Correction : le writer reçoit `reset`. Dans une même transaction SQLite, il
exécute uniquement `DELETE FROM transactions` si demandé, relève le nombre de
lignes effectivement supprimées via `cursor.rowcount`, puis applique l'upsert
existant. Toute exception annule le DELETE et les écritures partielles ; la
connexion est fermée aussi en erreur.

Ordre conservé : fetch → classification → refus éventuel des acteurs inconnus →
si `write=True`, reset éventuel + écriture atomique. Si `write=False` ou si le lot
est refusé, le writer et son `init_db` ne sont pas appelés, et `deleted=0`.

Le reset explicite remplace toute la table par **le lot sélectionné**, même vide.
La CLI `build_mlc_db` exige `--limit none` et une période explicite avec
`--date-from` **et** `--date-to`. Une limite numérique (y compris la valeur par
défaut 100), une borne absente ou vide provoque une erreur CLI dans `main`, avant
le chargement du `.env`, les imports Flask/métier et tout accès DB ou réseau.
Ces garde-fous s'appliquent aussi avec `--dry-run`.

Les dates sont transmises normalement au service ; `days` reste inchangé, mais
`get_transactions` donne déjà priorité à `date_from`. Le reset ne peut donc plus
utiliser silencieusement la période par défaut de 7 jours. Aucun changement de
`cyclos_client`. Sans reset, les valeurs par défaut restent `limit=100`, `days=7`.
Ces contraintes CLI ne changent pas le contrat du service appelé directement.
Les lignes sans identifiant restent ignorées par le writer comme auparavant.
Aucune autre table n'est vidée ; le schéma canonique ne définit pas de cascade
depuis `transactions`.

Les caches et `transaction_semantics` restent inchangés par ce reset : ils peuvent
devenir obsolètes après un remplacement. Leur reconstruction doit être organisée
séparément, sans supprimer ces tables dans REL001. Les fichiers de mappings ne
participent pas à la transaction SQLite et ne sont pas annulés par son rollback.

## Audit du dry-run : écritures encore possibles

REL001 ne transforme pas le dry-run en exécution sans effets de bord.

| Chemin | Effets possibles et emplacement |
|---|---|
| `sync_mlc_instance.sync_transactions_service` → import de `app` → `create_app` | `init_db`, `init_professional_enrichment_db`, `init_control_db` créent/complètent les schémas. L'appel explicite `init_db` dans le service les répète. |
| `build_mlc_db.main`, même avec `--dry-run` | Importe aussi `app`, puis appelle explicitement les deux initialisations analytiques ; le flag ne protège pas ce démarrage. |
| `database.get_connection` / `get_db_path` | Répertoires `server/data/instances/<id>/`, `runtime/`, `runtime/locks/` ; SQLite `mlcflux.db` dans ce sous-dossier ; `PRAGMA journal_mode=WAL` persistant et éventuels fichiers SQLite `-wal` / `-shm`. Des connexions de lecture métier passent aussi par ce helper. |
| `database.init_db` / `init_professional_enrichment_db` | Tables et index, plus `ALTER TABLE` pour les colonnes manquantes. Cela inclut les schémas d'enrichissement/Odoo existants. Aucun changement de ces fonctions dans REL001. |
| `control_db.init_control_db` | Création de `server/data/control.db`, de ses tables et index. L'import de `app` suffit à déclencher l'initialisation, sans requête HTTP. |
| Classification U/UD → `private_actor_mapping.get_or_create_private_ref` | Pour une nouvelle clé : création du dossier parent si nécessaire, `instances/<id>/private_actor_mapping.json`, fichier intermédiaire `private_actor_mapping.json.tmp`, incrément de séquence, renommage et permissions `0600`. Une clé connue retourne son label sans réécrire ce mapping. |
| Classification pro → `professional_ref_mapping.get_or_create_professional_ref` | Selon la stratégie du profil et l'absence de référence pro préservable : `instances/<id>/<professional_mapping.mapping_file>`, par défaut `professional_mapping.json`, et fichier `.tmp` adjacent. Crée `runtime/locks/` et ouvre `professional_mapping.lock` en mode `w`, même si la référence existe déjà. |
| Validation des familles X | Arrive après la classification de tout le lot. Des mappings peuvent donc avoir été attribués avant le refus d'un autre acteur. Aucun DELETE/INSERT de transactions dans ce cas, mais pas de rollback des mappings. |
| `build_mlc_db --dry-run --sync-professionals` | `fetch_professional_profile_enrichment_sample` collecte les acteurs, peut attribuer des références professionnelles et ouvre des sessions Cyclos. N'appelle pas `save_professional_enrichment_rows` sur ce chemin. |
| `build_mlc_db --dry-run` sans `--skip-smoke` | Lance encore les trois lectures de smoke analytics ; leurs connexions utilisent les helpers DB existants. REL001 ne les a pas exécutées. |
| `sync_mlc_instance --json-out` | Écrit le rapport au chemin demandé même en dry-run/plan-only. Cette sortie explicite est distincte des écritures runtime involontaires. |
| `configure_instance` / `load_env_file` | Lit la configuration et modifie l'environnement du processus (DEFAULT/ACTIVE compris), sans écrire le fichier `.env`. |

`write=False` continue à appeler Cyclos et à classifier le lot : ce n'est pas un
mode hors ligne. `get_transactions` crée notamment une session distante via POST
puis lit les transactions. Aucune requête Cyclos/Odoo n'a été effectuée pour REL001.
Les étapes sémantiques, enfants, enrichissements Odoo, soldes, caches et intégrité
de l'orchestrateur restent sautées en dry-run ; `daily_sync` n'est pas enregistré.
Le `--plan-only` de cet orchestrateur évite les fonctions d'étapes, mais configure
l'environnement et peut écrire le fichier de rapport explicitement demandé.

Supprimer un seul `init_db` ne suffit pas : `create_app` initialise déjà plusieurs
bases, et les mappings sont attribués dans les fonctions de classification.
Aucune correction supplémentaire du dry-run n'est appliquée dans REL001.

REL002 devra :

1. Découpler le démarrage CLI de `app/create_app` et ouvrir les bases existantes
   en lecture seule sans mkdir, migrations ni modification du mode de journal.
2. Fournir aux fonctions d'attribution une vue en mémoire des mappings existants
   et des nouvelles attributions simulées ; ne pas changer les règles de famille
   ni les labels, et ne pas ouvrir les fichiers de verrou en écriture.
3. Définir explicitement l'autorisation du rapport de sortie et des sessions
   distantes, puis vérifier les empreintes de tous les fichiers avant/après les
   dry-runs, sur données temporaires, y compris inconnus et erreurs.

## Tests et validation

`tests/test_rel001_sync.py` contient **25 cas exécutés avec succès** :

- subprocess succès, échec avec arrêt, échec avec poursuite et rapport final faux ;
- deux cas de signaux incohérents `ok` / `returncode` ;
- `reset=False`, conservation et idempotence de l'upsert ;
- reset effectif et compteur `deleted` ; reset + `write=False` sans ouvrir le stockage ;
- lot refusé pour source X ou destination X, sans reset préalable ;
- erreur SQL après une première insertion : restauration du lot précédent ;
- échec de fetch sans accès au stockage ; reset explicite d'un lot vide ;
- CLI reset : rejet avant I/O des limites numériques (défaut, 100, 0, 1,
  et 100 en dry-run) et de la limite vide ;
- CLI reset avec `--limit none` : rejet avant I/O sans dates, avec seulement
  `--date-from`, ou avec seulement `--date-to` ;
- CLI reset autorisé avec limite `none` et les deux dates, transmises au service ;
- CLI sans reset : limite explicite 100 et valeurs par défaut inchangées.

Chaque test SQLite utilise `tmp_path`, le contrat canonique de `transactions`, et
une table sentinelle dont le contenu doit rester intact. Les connexions doivent
être fermées à la fin. Les tests d'orchestration simulent `subprocess.run`, les
deux étapes métier initiales et la lecture de configuration ; aucun enfant réel.
Les trois modules sources sont chargés entiers via importlib, avec leurs frontières
I/O simulées et restaurées par monkeypatch. Aucun shim `fcntl`, aucun code métier
recopié/extrait pour les faire passer, aucun import de l'application Flask.

Exécution ciblée : `pytest -q tests/test_rel001_sync.py` → **25 passed**.
Hôte de validation : Windows, Python 3.13.9, pytest 8.4.2 disponible localement
(le dépôt épingle pytest 9.1.1 pour son environnement de développement).
Lors de la validation initiale, contre les deux fichiers originaux de `e121294`,
les 13 tests précédant les garde-fous CLI donnaient
6 échecs, 7 succès et une erreur de teardown (connexion non fermée sur erreur SQL).
Cela reproduit les défauts avant correction.

Suite complète tentée avant/après : `pytest -q tests/` est bloqué à la collecte
sur cet hôte Windows par `ModuleNotFoundError: fcntl` dans les tests existants.
**La baseline Linux de 29 tests n'a pas été revalidée ici.** Les snapshots réels
ne sont pas installés et n'ont pas été ouverts. Les erreurs de collecte empêchent
l'exécution de la suite entière ; les 25 succès proviennent du lancement ciblé.

Compilation Python des 110 fichiers lors de la validation initiale : OK.
Après les garde-fous CLI, compilation des deux fichiers Python retouchés et
`git diff --check` : OK.
Aucun fichier de route, frontend, profil, classification, sémantique, formule,
schéma ou ancien `server/sync_transactions.py` modifié. Les 76 règles/75 chemins
de la baseline n'ont pas été recomptés en exécutant Flask sous Windows.

Fichiers modifiés : `server/sync_mlc_instance.py`,
`server/services/cyclos_transaction_sync.py`, `server/build_mlc_db.py` (garde-fous et aide CLI).
Fichiers ajoutés : `tests/test_rel001_sync.py`, ce rapport.
