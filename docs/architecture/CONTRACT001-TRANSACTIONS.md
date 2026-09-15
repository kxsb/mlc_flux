# CONTRACT001 — Transactions SQL normalisées

## But

Définir la frontière d'entrée financière consommée par MLCFlux.

MLCFlux ne dépend pas des détails d'implémentation des backends
financiers ComChain, Cyclos ou autres.

Le producteur fournit une relation SQL normalisée `transactions_*`.

## Version

`TRANSACTIONS001`

## Colonnes

- `amount`
- `received_at`
- `hash`
- `fn_abi`
- `type`
- `sender_partner_id`
- `receiver_partner_id`
- `is_sender_external`
- `is_receiver_external`

## Grain

Le `hash` est l'identifiant de la transaction fourni par le backend
financier.

Le contrat cible est :

> un hash = une transaction normalisée.

Pendant la correction de la fixture Lemanopolis, MLCFlux tolère
uniquement plusieurs lignes strictement identiques.

Deux lignes divergentes avec le même hash constituent une ambiguïté
et provoquent une erreur d'ingestion.

## Identité administrative

`sender_partner_id` et `receiver_partner_id` sont les identifiants
administratifs fournis par le contrat.

MLCFlux n'a pas besoin de connaître l'adresse financière native
utilisée pour établir cette correspondance.

Les flags :

- `is_sender_external`
- `is_receiver_external`

sont conservés sans interprétation supplémentaire.

## Ce qui est explicitement hors contrat

CONTRACT001 ne lit pas :

- les tables ou foreign tables pyc3l internes ;
- les adresses de wallet ;
- `res_partner_backend` ;
- `res_alt_currency` ;
- les contrats blockchain ;
- les identifiants de comptes Cyclos.

Ces éléments appartiennent à l'implémentation du producteur.

## PostgreSQL

`NormalizedTransactionsPostgresSource` :

- reçoit le nom de la relation par configuration ;
- effectue uniquement des `SELECT` ;
- ouvre une transaction `READ ONLY` ;
- ne demande que les neuf colonnes CONTRACT001.

## Prochaine étape

Après validation du contrat avec Lokavaluto :

CONTRACT001
→ projection minimale vers Financial Core

Cette projection sera construite à partir du contrat normalisé,
et non à partir des backends financiers natifs.

## Nullabilité des partenaires et flags external

Les champs administratifs et les flags `external` sont conservés
indépendamment.

MLCFlux ne doit pas déduire :

- `partner_id IS NULL` => `external = true`
- `partner_id IS NOT NULL` => `external = false`

La fixture Lemanopolis observée le 15/09/2026 contient notamment
des transactions avec `receiver_partner_id IS NULL` et
`is_receiver_external = false`.

Cette combinaison est donc valide au niveau CONTRACT001 tant que
le producteur du contrat n'en précise pas une contrainte plus forte.
