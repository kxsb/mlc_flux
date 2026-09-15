# FINCORE002 — Publication lifecycle et reader cohérent

## Statut

Jalon de migration du backend Neutral.

FINCORE002 complète `financial-core-v0.1` sans modifier son schéma.

## Objectifs

1. Exposer la validation du Financial Core sans écriture SQL.
2. Rendre explicite le cycle :
   `prepare -> validate -> publish`.
3. Lire le Financial Core à partir d'une publication cohérente.
4. Interdire au reader de mélanger des lignes provenant de plusieurs
   publications.

## Reader

`read_current_financial_core(engine, dataset_id)` :

- ouvre une transaction de lecture ;
- résout `current_publication_id` une seule fois ;
- vérifie que cette publication appartient au dataset ;
- filtre toutes les relations par le même `publication_id` ;
- retourne un `FinancialCoreSnapshot`.

L'isolation `SERIALIZABLE` est demandée au niveau de la connexion afin
d'éviter qu'un changement de publication intervenant pendant la lecture
produise une vue hybride.

`get_current_publication_id()` existe uniquement comme fonction de diagnostic.
Un appelant qui veut lire des faits doit utiliser le snapshot.

## Lifecycle

`prepare_financial_core_candidate(payload)` valide le payload sans écrire.

Le candidat est volontairement en mémoire dans FINCORE002. Il n'existe donc
pas de staging durable supplémentaire et aucune table n'est ajoutée.

`publish_financial_core_candidate()` :

1. revalide le payload ;
2. appelle le writer atomique FINCORE001 ;
3. retourne le `publication_id`.

La revalidation évite qu'une structure mutable contenue dans un payload
puisse être modifiée silencieusement entre préparation et publication.

## Principe

Une publication candidate n'est pas une source de vérité.

Seule une publication ayant terminé le writer atomique peut devenir
`current_publication_id`.

Les lecteurs ordinaires ne lisent jamais les données en construction.

## Suite

FINCORE003 branchera un premier adapter réel sur ce lifecycle.

La première cible prévue est Lokavaluto / ComChain. Le raccord devra produire
des `FinancialEvent` et `AccountEffect` natifs puis appeler ce lifecycle,
sans passer par la table legacy `transactions` ni par INPUT001.
