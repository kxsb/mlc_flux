# Audit et nettoyage standalone — 12 septembre 2026

## Périmètre et méthode

Branche exclusive : `mlcflux_neutral_dev`, HEAD initial
`96bef2aa88dc3a56d21f8dfb68d5cbe064ccf1b6`. Les commits `1039433`, `f55e0c7`
et `96bef2a` ont été étudiés avant modification : configuration par environnement,
suppression du portail/sélecteur HTTP, puis suppression Tickets/Roadmap.

Audit des fichiers suivis, imports, enregistrements de blueprints, appels JS,
scripts CLI, fonctions de stockage/classification et requêtes d'enrichissement.
« Sans appelant » signifie sans appelant trouvé dans cette branche ; les anciens
cron ou liens externes non versionnés ne sont pas observables depuis ce clone.
Aucun cron n'a été changé, aucune synchronisation distante n'a été lancée.

Les profils Gonette/Graine, classifications, `transaction_semantics`, formules
analytiques, schéma des transactions et mappings actifs restent inchangés.
Aucune base réelle, donnée runtime ou configuration secrète n'a été modifiée.
Les modifications restent locales, sans commit, push, fusion ni déploiement.

## Décisions et justification

| Classe | Élément | Décision et preuve |
|---|---|---|
| Suppression sûre maintenant | `run_multi_daily_sync.sh`, `server/sync_all_instances.py` | Le premier ne faisait que lancer le second sur Graine puis Gonette ; le second ne faisait que relancer `sync_mlc_instance`. Aucun autre appelant trouvé. L'orchestrateur unitaire et toutes ses étapes restent disponibles. |
| Suppression sûre maintenant | `static/js/landing_loading.js`, `landing_polish.js` et leurs CSS | Assets des cartes d'instances du portail supprimé. Aucun chargement dans les templates ou JS actifs. Le loader attendait explicitement les deux cartes Gonette/Graine. |
| Suppression sûre maintenant | `static/js_old/`, `static/utils_old/` | Anciennes copies jamais chargées par les templates, jamais importées côté serveur ; `js_old/app.js` référençait même un sous-dossier `utils` absent. Les modules actifs de `static/js/` et `server/utils/anonymizer.py` sont conservés. |
| Suppression sûre maintenant | Bloc CSS Kanban/Gantt et variantes Tickets | 744 lignes retirées. Chaque sélecteur est conditionné par une classe absente des JS/templates actifs. Le reste de la feuille est identique. Les classes `ticket-*` réutilisées par l'administration restent présentes. |
| Suppression sûre maintenant | `get_active_mlc_profile`, `ensure_all_mlc_instance_dirs`, `describe_mlc_data_context` | Helpers du contexte sans appelant restant. Aucune suppression de profil ou de répertoire runtime. |
| Suppression sûre maintenant | `sync_cyclos_transactions_sample`, `reset_transactions_table` | La fonction d'échantillon n'a aucun appelant et référence `reset` sans le définir. Le helper DELETE n'était appelé que par elle. Le service `sync_cyclos_transactions`, appelé par les CLI, reste identique. |
| Suppression sûre maintenant | `server/routes/stored_transactions.py` | Blueprint jamais importé ni enregistré ; aucun consommateur trouvé pour `/api/v2/stored-transactions`. Aucun endpoint exposé n'est retiré. |
| Suppression sûre maintenant | Compteur `tickets` dans `build_mlc_db._db_counts` | Reliquat de rapport après retrait du sous-système ; suppression de la seule entrée du compteur, sans DDL ni suppression de table runtime. |
| Refactor sûr maintenant | Chemin SQLite | Le contexte standalone retourne toujours le profil configuré ou lève une erreur. Le retour `None`, son fallback vers `server/data/mlcflux.db` et les constantes `DB_PATH`/`LEGACY_DB_PATH` sans consommateur sont donc inutiles. Le chemin effectif reste `server/data/instances/<id>/mlcflux.db`. |
| Refactor sûr maintenant | Invalidation de cache DB dans les CLI de build/sync | `get_db_path` n'a aucun décorateur de cache ni `cache_clear` ; ces blocs ne faisaient rien. |
| Refactor sûr maintenant | `DEFAULT_INSTANCES` | Les choix du CLI unitaire sont dérivés des profils déclarés, puis validés par `normalize_mlc_id`. Cela ne garantit pas à lui seul la compatibilité métier d'un futur profil. |
| Refactor sûr maintenant | Génération des fonds postaux | Suppression de la boucle par défaut Graine + Gonette. Une invocation traite le profil configuré, ou le `--mlc` explicite. Les fonctions géographiques et la structure du rapport JSON, liste à une entrée, restent inchangées. |
| Refactor sûr maintenant | Messages de sync HTTP | `legacy_api` réutilise le formatter existant de `routes/sync`. Payloads, aliases `inserted`, statuts, token d'accès et pipeline appelés restent inchangés. |
| Correction prouvée | Session après login | `f55e0c7` avait supprimé aussi `session.clear()` et l'enregistrement de l'utilisateur. `authenticate_user` retourne un utilisateur sans créer de session. Rétablissement des seuls champs utilisateur ; aucun état de sélection MLC. |
| Refactor sûr maintenant | Entrée de l'application et documentation des données | Les libellés d'accueil ne présentent plus une page « multi-instance » ; le README précise qu'un seul sous-dossier de données est utilisé par installation. |
| À conserver provisoirement | `/app`, `/api/current-mlc`, routes `/api/*` dites legacy | `/app` reste un redirect de compatibilité ; `/api/current-mlc` alimente le frontend ; `legacy_api` porte encore les principales analytics et le rechargement. |
| À conserver provisoirement | Droits par MLC et demandes de comptes | Données et contrats encore lus/écrits par l'administration et la CLI. Leur migration dépasse une suppression de code mort. Ils ne sélectionnent pas la base analytique de la requête. |
| Futur provider/input | Anonymiseur historique, tables Odoo, hardcodes métier | Leur retrait exige une caractérisation des données, des identités et des priorités de sources. Détails ci-dessous. |

## Synchronisation : graphe d'appels et différences

```text
static/js/app.js : bouton de rechargement
  -> POST /api/reload                    (routes/legacy_api.py)
POST /api/v2/sync                       (routes/sync.py)
run_daily_sync.sh -> python -m server.sync_transactions
  -> sync_transactions.run_sync
     -> create_app / init_db
     -> cyclos_client.get_transactions
     -> utils.anonymizer.anonymize_transactions
     -> insert_transactions -> SQLite transactions
     -> sync_state['daily_sync']

python -m server.sync_mlc_instance --mlc <profil>
  -> configure_instance (contexte de processus, pas de session HTTP)
  -> sync_transactions_service
     -> cyclos_transaction_sync.sync_cyclos_transactions
        -> cyclos_client.get_transactions
        -> classify_transaction_for_storage
           -> cyclos_actor_classifier.classify_cyclos_transaction
           -> profils + private_actor_mapping / professional_ref_mapping
        -> _store_classified_transaction_rows -> SQLite transactions
     -> sync_state['daily_sync']
  -> rebuild_semantics -> transaction_semantics
  -> liens acteurs, enrichissements, soldes, caches, intégrité

python -m server.build_mlc_db --mlc <profil> ...
  -> même service moderne sync_cyclos_transactions
  -> enrichissement professionnel optionnel + smoke analytics
```

`/api/v2/transactions`, utilisé par l'explorateur live, appelle également
`get_transactions -> anonymize_transactions`, sans écrire de transactions SQLite.
Il peut néanmoins créer des pseudonymes persistants via l'anonymiseur.

| Aspect | Historique | Moderne |
|---|---|---|
| Source/période | Même client Cyclos ; sans arguments, 48 h glissantes | Même client ; l'orchestrateur choisit par défaut une période calendaire de 3 jours |
| Acteurs | Types/affichages historiques Gonette ; label pro comprenant souvent son nom | Règles du profil ; référence professionnelle canonique, familles explicites |
| Pseudonymes U/UD | `server/data/user_mapping.json`, clés `actor:*` ou `user:*`, registre de dispositif global | `instances/<id>/private_actor_mapping.json`, clés préfixées `U:actor:*`, `UD:actor:*`, etc. ; mapping professionnel séparé |
| `group_label` | Nom du type de l'acteur source : `from.type.name` | `kind`, sinon `creationType`, de la transaction |
| `type_label` | `transaction.description` | `transaction.type.name`, sinon `internalName` |
| Montant | `float(value)` ; entrée invalide lève une erreur | Parseur tolérant virgule/texte ; invalide donne `None`. Le zéro numérique est également traité comme `None` actuellement |
| Identifiant absent | Upsert SQL direct, sans substitution explicite du numéro | Numéro substitué par `cyclos_id` ; ligne ignorée si les deux manquent |
| Upsert | `ON CONFLICT DO UPDATE`, sans changer `transaction_number` | Recherche d'abord par `cyclos_id`, puis numéro ; UPDATE par rowid, y compris numéro |
| Acteur inconnu | Libellé résiduel stocké | Famille X : erreur avant stockage du lot, après classification |
| Résultat | `fetched`, `written` | `fetched`, `selected`, `inserted`, `updated`, `skipped`, inconnus/erreur |
| Sémantique/cache | HTTP : pas de rebuild sémantique ; ancien shell rafraîchit certains caches | L'orchestrateur a une étape sémantique explicite et une suite d'enrichissements plus étendue |

Contre-exemple synthétique exécuté sur les fonctions de transformation extraites :

| Champ | Historique | Moderne Gonette |
|---|---|---|
| Acteur source | `P0008 - Boutique fictive` | `P0008` |
| Type | `Panier fictif` | `Paiement professionnel` |
| Groupe | `Compte professionnel` | `payment` |

Ces différences suffisent à réfuter l'équivalence. Aucun mapping réel n'a été
utilisé dans ce diagnostic. **L'ancien pipeline et ses deux routes sont conservés.**
Le nom « legacy » ne prouve pas qu'une route est obsolète.

Après retrait du wrapper multi-installations, la commande existante reste :
`python -m server.sync_mlc_instance --mlc <profil-installé> ...`.
Le `--mlc` explicite conserve sa priorité sur le fichier d'environnement ; ce CLI
ne devient pas une API HTTP de changement de monnaie. `run_daily_sync.sh` reste un
ancien chemin distinct, non migré silencieusement vers le pipeline moderne.

Le CLI postal garde ses seules dépendances standard et peut toujours s'exécuter
directement : `python server/sync_payment_basin_postal_areas.py --mlc <profil> ...`.
Sans `--mlc`, il exige `MLCFLUX_DEFAULT_MLC_ID` exporté dans l'environnement ; il
ne charge pas `.env` et ne choisit plus implicitement deux monnaies. Une
configuration absente ou un identifiant inconnu échoue avant tout appel réseau.

## Cartographie des couplages à Odoo à conserver pour INPUT

| Fichier | Accès ou responsabilité restant couplé |
|---|---|
| `server/analytics.py` | `_get_odoo_professional_enrichment_index` joint le générique et Odoo ; `_get_professional_detail_enrichment` et `_get_odoo_professional_enrichment` gardent le fallback ; `get_professionals_map_data`, `compute_zip_territorial_activity`, `_load_sector_activity_professional_display_index`, `compute_sector_activity` gardent des lectures/jointures Odoo. |
| `services/professional_detail_dynamics.py` | `_professional_identity`, `_b2b_direction_rows` : identité et enrichissement des contreparties B2B. |
| `services/professional_reuse_prospects.py` | `_professional_identity`, `_professional_lookup`, `_same_sector_peers` : identité, recherche et pairs sectoriels ; le complément générique ne remplace pas toutes les requêtes. |
| `services/professional_consumption_map_analytics.py` | `get_professional_consumption_map_payload` : plusieurs jointures Odoo pour les professionnels et la géographie ; chemin de fallback générique distinct. |
| `services/professional_payment_basin_map.py` | `_professional_center`, `_professional_inbound_rows` : centre géographique et flux entrants enrichis. |
| `services/user_postal_cluster_analytics.py` | `_table_rows` : coordonnées et données professionnelles Odoo. |
| `services/user_to_professional_map_analytics.py` | `_load_professional_identity` : lecture Odoo conditionnelle et provenance d'identité explicite. |
| `sync_consumption_postal_areas.py` | `fetch_consumption_postal_codes` : jointure directe avec les professionnels Odoo. |
| `sync_actor_territorial_enrichment.py` | `_fallback_from_existing_tables` : priorités distinctes entre générique, adresse Cyclos stockée dans Odoo et adresse Odoo. |
| `services/odoo_professional_enrichment.py` | Extraction, rapprochement et remplacement atomique de `odoo_professional_enrichment` et `odoo_professional_secondary_industries`. Ne remplit pas automatiquement toute la table générique. |
| `sync_odoo_professional_enrichment.py`, `sync_mlc_instance.py` | Commande de synchronisation et orchestration de la source Odoo. |
| `database.py`, `services/db_integrity.py`, `build_mlc_db.py` | Schéma Odoo, contrats/contrôles de cohérence et comptages conservés. |
| `services/odoo_client.py`, `config.py` | Transport JSON-RPC, authentification et configuration Odoo. |
| `services/odoo_individual_enrichment.py`, `sync_odoo_individual_enrichment.py` | Enrichissement des particuliers et liens Cyclos/Odoo, également consommés par plusieurs analyses territoriales. |
| `services/odoo_monetary_indicators.py`, `sync_odoo_monetary_indicators*.py` | Source comptable, snapshots annuels/quotidiens et colonnes historiques `gonettes_*`. |
| `services/monetary_indicators_adaptive.py`, `routes/monetary_indicators.py`, caches de pilotage | Choix de la source comptable/technique et fallbacks, lecture des tables monétaires Odoo. Ce couplage dépasse le seul enrichissement professionnel. |

Dans cette table, les chemins sans préfixe explicite sont relatifs à `server/`.
Les fonctions d'analyse combinent des priorités et des champs différents ; une
simple substitution du nom de table n'est pas une migration équivalente.

## Éléments suspects et compatibilités maintenus

- `MLCFLUX_ACTIVE_MLC_ID` reste synchronisé avec `MLCFLUX_DEFAULT_MLC_ID` par les
  scripts : `transaction_semantics` privilégie DEFAULT, tandis que
  `professional_chain_fate_analytics` privilégie ACTIVE. Supprimer une variable
  seule peut changer le profil sémantique ou le chemin d'un cache.
- Sans configuration, `mlc_context` privilégie Graine, alors que certaines
  analytics/sémantiques se replient sur Gonette. Définir explicitement
  `MLCFLUX_DEFAULT_MLC_ID` reste nécessaire pour une installation cohérente.
  Les règles de fallback ne sont pas modifiées dans cette passe.
- `get_active_mlc_id(fallback_to_default=...)` conserve son paramètre ignoré,
  encore appelé et caractérisé par les tests. Le helper DB n'en a plus besoin.
- `sync_mlc_instance` active encore Odoo par défaut pour Gonette et les soldes
  système pour Graine. Ces choix ont une portée métier ; ils ne sont pas remplacés
  par des capacités provider dans cette intervention. D'autres CLI gardent les
  choix Gonette/Graine pour la reconstruction et les résumés de chaînes.
- `build_mlc_db.DEFAULT_SECRETS_FILE` vise encore un ancien chemin
  `/opt/mlcflux-secrets/mlcflux-multi-dev.env` ; `run_daily_sync.sh` vise
  `/opt/mlcflux-dev`. Ces outils nécessitent encore une préparation de déploiement.
  Le contenu des fichiers secrets et les cron externes n'ont pas été consultés.
- `reset=True` dans le service moderne est actuellement un paramètre sans effet ;
  `build_mlc_db --reset-transactions` le transmet encore. Le rendre destructif
  pendant ce nettoyage aurait changé le comportement. Paramètre/rapport conservés.
- Un `--dry-run` moderne peut encore initialiser les schémas via `create_app` et
  attribuer des mappings pendant la classification. Aucun dry-run réel n'a été
  utilisé pour valider cette passe ; seules des fonctions sans I/O ont été exercées.
- `sync_mlc_instance.run_subprocess_module` retourne `ok=False` sur échec enfant,
  mais `add_step` marque actuellement « ok » une fonction qui retourne ce dict
  sans lever. À corriger avec tests d'échec de subprocess dans un chantier fiabilité.
- `control_user_mlc_access`, `list_user_mlc_access`, `grant_mlc_access`,
  `manage_users`, `routes/admin_accounts`, `routes/account_requests` et le frontend
  conservent les droits par monnaie et la liste des profils. Les familles de rôles
  CLI et UI diffèrent aussi. Le garde d'accès standalone accepte un utilisateur
  authentifié sans sélectionner sa base via ces droits. Migration d'autorisation
  à traiter explicitement, sans effacer les droits stockés pendant un nettoyage.
- `auth.py`, `admin_accounts.py`, `account_requests.py` dupliquent la découverte
  des schémas/tables de comptes ; il faut établir le contrat du contrôle d'accès
  avant de retirer leurs fallbacks.
- Les mentions « multi-MLC » dans les commentaires d'analytics/enrichissement
  décrivent souvent les différences de profils ou les fallbacks hors Odoo. Elles
  restent à reformuler avec INPUT ; pas de remplacements dispersés dans les
  fichiers métier. Les descriptions JSON des profils restent intactes.
- Les noms JS `gonettes`, champs `gonettes_*`, références opérateur et chemins
  de mappings ne sont pas renommés. Les blocs « roadmap » d'analyse professionnelle
  encore rendus par `app.js` ne sont pas les anciennes routes Tickets/Roadmap.

## Validation et limites

- Avant modification : tentative de `pytest -q tests/` avec les bibliothèques
  disponibles ; trois erreurs de collecte dues à `ModuleNotFoundError: fcntl`.
- Après chaque lot : syntaxe Python, `git diff --check`, nouvelle tentative pytest.
  À la fin : syntaxe des 109 fichiers Python actuels validée ; quatre erreurs de
  collecte, le nouveau fichier de tests rencontrant la même dépendance Unix.
  **La baseline annoncée « 21 passed » n'a pas pu être reproduite ici.**
- Huit cas de tests supplémentaires : création/absence de session après login,
  sélection d'une seule MLC pour les fonds postaux sur chaque profil, maintien des
  arguments du CLI sur les deux profils, rejet d'un profil inconnu et absence
  de profil postal configuré. Ils sont
  présents mais la suite complète n'a pas pu les exécuter sur cet hôte Windows.
- `node --check static/js/app.js` et compilation des scripts inline du template :
  OK. `app.js` n'est pas modifié. Vérification structurelle du CSS retiré : tous
  les sélecteurs étaient conditionnés par des classes absentes des vues actives ;
  aucun autre bloc CSS n'a changé. Pas de validation visuelle dans un navigateur.
- Diagnostic local indépendant, limité aux fonctions extraites par AST : défaut
  de login reproduit avant correction, succès/échec validés ensuite avec Flask ;
  rapports plan-only identiques avant/après sur les deux profils ; six cas de CLI
  postal avec constructeur simulé, sans réseau ni données runtime.
  **Ces diagnostics ne sont pas une exécution de la suite pytest ni de l'app complète.**
- CLI postal chargé également comme module intact : six cas avec constructeur
  simulé passent, ainsi que le rejet d'une configuration absente/inconnue avant
  tout I/O du constructeur. L'exécution directe de `--help` fonctionne sur Windows.
- Comparaison AST : toutes les fonctions conservées du pipeline transactionnel
  moderne sont identiques ; toutes les fonctions géographiques hors `main` sont
  identiques. Le contre-exemple de classification ci-dessus a été reproduit sans
  données réelles. Aucune règle HTTP exposée n'est ajoutée ou retirée par le diff ;
  le test existant attend toujours 76 règles, sans réduire son assertion.
- Snapshots réels absents du clone : les empreintes Gonette/Graine n'ont pas été
  vérifiées. Les tests et empreintes existants restent inchangés. Aucun fichier DB
  n'a été créé par les diagnostics.

À valider avant intégration : exécuter `pytest -q tests/` dans l'environnement
Linux prévu avec une configuration de test isolée, puis les caractérisations sur
les copies de snapshots de référence. Ne pas utiliser de base de production.

## Prochaine étape provider Cyclos / ComChain

Figer des fixtures d'entrée et de sortie pour les deux chemins Cyclos, y compris
les mappings stables, puis introduire un adaptateur vers les huit champs actuels
de `transactions`. Comparer les agrégats avant de remplacer un appelant historique.
Ajouter ensuite ComChain/Lokavaluto au même contrat, sans renommer `cyclos_id` ni
modifier la sémantique ; traiter l'enrichissement Odoo dans un lot distinct.

## Fichiers du diff

Modifiés :

```text
server/build_mlc_db.py
server/data/instances/README.md
server/database.py
server/mlc_context.py
server/routes/auth.py
server/routes/legacy_api.py
server/services/cyclos_transaction_sync.py
server/sync_mlc_instance.py
server/sync_payment_basin_postal_areas.py
static/css/style.css
templates/index.html
tests/test_http_characterization.py
```

Supprimés :

```text
run_multi_daily_sync.sh
server/routes/stored_transactions.py
server/sync_all_instances.py
static/css/landing_loading.css
static/css/landing_polish.css
static/js/landing_loading.js
static/js/landing_polish.js
static/js_old/app.js
static/utils_old/__init__.py
static/utils_old/actors.js
static/utils_old/anonymizer.py
static/utils_old/api.js
static/utils_old/charts-data.js
static/utils_old/dates.js
static/utils_old/formatters.js
```

Ajoutés : `tests/test_standalone_sync.py`, ce rapport
`docs/standalone-cleanup-audit.md`.
