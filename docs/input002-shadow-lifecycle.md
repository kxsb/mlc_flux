# INPUT002 — lifecycle et santé du shadow INPUT001

## Périmètre

`input001.db` reste un cache de contrôle possédé par MLCFlux. Il représente le dernier lot INPUT001 matérialisé et ne constitue ni l'historique financier de référence ni la base analytique actuellement consommée par le dashboard.

Ce chantier ne change pas le contrat financier `input001-v0.1`. Il ajoute un cycle de vie **physique** du cache, indépendant de `contract_version`.

## Deux versions distinctes

- `contract_version` décrit la sémantique publique des relations INPUT001 ;
- `storage_schema_version` décrit la forme physique attendue du cache shadow géré par cette version de MLCFlux.

La version physique courante est `1`.

Une évolution de colonnes du cache ne doit donc plus être masquée par un `CREATE TABLE ... checkfirst=True` alors que `contract_version` reste inchangé.

## Préparation avant matérialisation

Avant chaque écriture shadow :

1. les relations INPUT001 existantes sont inspectées ;
2. les relations requises et leurs colonnes minimales sont contrôlées ;
3. la version physique enregistrée est lue ;
4. un cache ancien ou incomplet est reconstruit ;
5. une version physique plus récente que le code courant est refusée afin d'éviter un downgrade destructif silencieux.

La reconstruction ne touche que les relations INPUT001 connues. Elle ne touche jamais `mlcflux.db`.

Le cache étant reconstructible à partir de la source, cette stratégie est volontairement plus simple qu'un système de migrations historiques ligne par ligne.

## État de santé privé du runtime

La table `_input001_shadow_runtime_state` n'appartient pas au contrat INPUT001. Le lecteur contractuel la masque explicitement.

Elle conserve :

- la version physique du cache ;
- le dernier essai ;
- le dernier succès ;
- le statut courant (`unknown`, `running`, `success`, `error`) ;
- le type et le message de la dernière erreur ;
- le dataset et la version de contrat du dernier succès ;
- le `snapshot_ref` du dernier succès ;
- les bornes de couverture attestées du dernier succès.

Une erreur shadow n'efface pas les informations du dernier succès.

Un lot valide suivant remet l'état à `success` et efface l'erreur précédente.

## Relation avec le pipeline legacy

Le comportement fail-open reste inchangé :

- l'écriture legacy dans `mlcflux.db` reste prioritaire ;
- une erreur INPUT001 est enregistrée comme dégradation du shadow ;
- cette erreur ne transforme pas une synchronisation legacy réussie en échec ;
- le dashboard continue pour l'instant de lire le pipeline historique.

INPUT002 améliore donc l'observabilité et la reprise du shadow sans effectuer de bascule analytique.

## Ce qui n'est pas traité ici

Ce lot ne traite pas :

- la construction du resolver métier ;
- la migration du dashboard vers INPUT001 ;
- un historique complet dans `input001.db` ;
- PostgreSQL comme runtime principal de MLCFlux ;
- Docker / Compose ;
- Django ;
- les suppressions ou annulations de transactions côté source.

Ces sujets restent des chantiers distincts.
