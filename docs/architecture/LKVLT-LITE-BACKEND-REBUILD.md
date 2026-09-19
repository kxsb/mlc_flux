# MLCFlux — chantier LKVLT-LITE et reconstruction du backend

État de référence : 2026-09-19

- Branche : `mlcflux_neutral_dev_lkvlt_lite`
- Base avant CLEAN001 : `4e843a2`
- Routes Flask après CLEAN001 : 63
- Tests de caractérisation après CLEAN001 : 17/17
- Modèle SQLite interne : 8 tables métier

## 1. Objet du chantier

Cette branche constitue la base simplifiée de MLCFlux destinée à recevoir un nouveau backend d'acquisition Lokavaluto.

L'objectif n'est plus de construire une chaîne générique abstraite autour de plusieurs contrats intermédiaires. L'architecture retenue est volontairement plus courte : un adaptateur traduit les données natives du provider vers le modèle interne stable de MLCFlux, puis le reste de l'application travaille uniquement sur ce modèle interne.

Architecture cible :

    Lokavaluto PostgreSQL
            |
            v
    server/adapters/lokavaluto/
            |
            v
    modèle interne stable MLCFlux
            |
            +--> analytics / caches dérivés
            |
            +--> API Flask
            |
            +--> interface existante

## 2. Décisions architecturales actées

Les couches expérimentales suivantes ont été supprimées pendant CLEAN001 :

- `input_contract` / INPUT001 ;
- CONTRACT001 / CONTRACT002 ;
- `financial_core` ;
- anciens `providers` génériques ;
- `resolver` et ses rulesets ;
- publication/shadow runtime ;
- anciens clients et synchronisations Cyclos/Odoo ;
- transaction semantics historique ;
- mécanismes d'intégrité et de synchronisation liés à ces anciennes couches.

Ces abstractions ne doivent pas être recréées automatiquement dans le nouveau backend.

La frontière souhaitée est désormais l'adaptateur provider lui-même.

## 3. Règle fondamentale de dépendance

Le code d'analyse, les routes API et le frontend ne doivent jamais importer directement un adaptateur Lokavaluto, Cyclos ou tout autre provider.

Seule la couche d'acquisition connaît le provider.

L'adaptateur écrit ou met à jour le modèle interne MLCFlux. Les analytics lisent ensuite ce modèle.

## 4. Modèle interne actuel

- `individual_daily_balances`
- `monetary_indicators_daily`
- `monetary_indicators_yearly`
- `pilotage_holdings_daily_cache`
- `pilotage_yearly_cache`
- `professional_daily_balances`
- `professional_enrichment`
- `transactions`

Les deux tables `pilotage_*_cache` sont des données dérivées. Elles ne constituent pas un contrat d'entrée pour un adaptateur.

## 5. Provenance

Les valeurs historiques de provenance spécifiques à un ancien provider sont conservées lorsqu'elles décrivent réellement l'origine des données.

Exemples actuellement présents :

### individual_daily_balances

- `cyclos_balances_history_daily` : 2324515
- `reconstructed_after_cyclos_404_from_last_balance_and_transactions` : 282

### monetary_indicators_daily

- `odoo_jsonrpc_daily_reconstruction` : 986

### monetary_indicators_yearly

- `odoo_jsonrpc` : 3

### professional_daily_balances

- `cyclos_professional_balances_history_daily` : 581718

### professional_enrichment

- `legacy_odoo_snapshot` : 201

Une provenance comme `odoo_jsonrpc` ou `cyclos_balances_history_daily` n'est donc pas considérée comme un couplage runtime.

Les nouvelles données Lokavaluto devront utiliser une provenance explicite, par exemple `lokavaluto_postgresql`, ou une valeur plus précise si plusieurs datasets natifs sont distingués.

## 6. Résultat important de l'audit Lokavaluto

Lors de l'audit FINCORE003, la table étrangère suivante a été identifiée comme candidate pour les transactions natives :

- `ext_pyc3l-sync_Lemanopolis.transactions`

Sur l'échantillon étudié :

- 6 lignes natives ;
- 6 hashes de transaction distincts ;
- 8 adresses sender/receiver distinctes.

La vue enrichie `public.transactions_pyc3l-sync_Lemanopolis` produisait 9 lignes pour ces mêmes 6 hashes, du fait de jointures avec les partenaires/backends Odoo.

Conséquence architecturale : l'adaptateur transactionnel doit partir autant que possible des faits natifs Lokavaluto/ComChain. L'enrichissement d'identité doit rester une étape distincte afin d'éviter de multiplier artificiellement les transactions.

Cette conclusion devra être revalidée sur la base PostgreSQL réelle au début de l'implémentation de l'adaptateur.

## 7. Principes attendus pour l'adaptateur Lokavaluto

L'adaptateur devra :

1. lire les structures PostgreSQL natives ;
2. identifier les transactions de façon stable ;
3. normaliser les identifiants des acteurs vers le modèle MLCFlux ;
4. écrire les transactions sans doublons ;
5. alimenter les historiques de soldes lorsque la source le permet ;
6. alimenter l'enrichissement professionnel depuis une source séparée des transactions ;
7. alimenter les indicateurs monétaires disponibles ;
8. enregistrer une provenance explicite ;
9. être relançable sans produire de duplication ;
10. permettre une synchronisation incrémentale.

## 8. Règles de données

- Les montants financiers doivent conserver leur précision native.
- Les dates doivent être normalisées de manière déterministe.
- Les identifiants externes doivent être conservés lorsqu'ils permettent l'idempotence.
- Les colonnes internes ne doivent pas être nommées d'après un provider.
- Les informations absentes chez un provider doivent rester absentes ou nulles, et ne doivent pas être fabriquées.
- Un enrichissement ne doit jamais modifier le nombre de faits transactionnels.

## 9. Géographie : chantier séparé

CLEAN001 a volontairement retiré une partie de l'ancien backend cartographique.

En revanche, plusieurs représentations géographiques utiles existent encore ou devront être rétablies :

- géolocalisation des professionnels ;
- fond de commerce des fiches professionnelles ;
- représentations territoriales ;
- cartographie des clusters.

La grosse cartographie dynamique historique de cette branche n'est pas la cible à conserver. La future reconstruction devra notamment étudier la version présente sur la branche `main`.

Les champs géographiques du registre professionnel ont été conservés.

Ne pas reconstruire la géographie pendant le chantier initial de l'adaptateur Lokavaluto : elle constitue un chantier distinct.

## 10. État après CLEAN001

- anciens providers runtime retirés ;
- anciens contrats intermédiaires retirés ;
- anciens hardcodes Gonette/Graine backend retirés ;
- noms physiques des tables et colonnes principales neutralisés ;
- frontend adapté aux nouveaux noms de contrat monétaire ;
- modèle interne SQLite préservé ;
- tests restants alignés avec l'architecture actuelle ;
- service de développement opérationnel.

## 11. Ordre recommandé pour la reprise

### Étape A — audit PostgreSQL Lokavaluto ciblé

Ne pas recommencer un audit général du dépôt.

Vérifier uniquement :

- table native des transactions ;
- identifiants sender/receiver ;
- unités et précision des montants ;
- timestamps ;
- statut/annulation éventuelle ;
- tables ou vues d'identité ;
- historiques ou snapshots de soldes ;
- informations nécessaires au registre professionnel ;
- informations monétaires globales éventuellement disponibles.

### Étape B — créer `server/adapters/lokavaluto/`

Commencer petit :

- connexion PostgreSQL ;
- lecteur transactionnel ;
- traduction vers `transactions` ;
- synchronisation idempotente ;
- tests de caractérisation.

### Étape C — compléter progressivement

Dans cet ordre recommandé :

1. transactions ;
2. professionnels / enrichissement ;
3. soldes professionnels ;
4. soldes particuliers ;
5. indicateurs monétaires ;
6. reconstruction des caches analytiques ;
7. chantier géographique séparé.

## 12. Critère de réussite

MLCFlux doit pouvoir changer de provider sans modification des analytics, des routes métier ou du frontend.

Le provider doit être une source d'alimentation du modèle interne, et non devenir le modèle métier de l'application.
