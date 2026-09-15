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

Le `hash` est l'identifiant de l'événement financier fourni par le backend.

Le grain financier est donc :

> un hash = un événement financier.

La relation SQL source peut cependant contenir plusieurs lignes portant le
même hash lorsque le compte source ou destination est associé à plusieurs
partenaires administratifs.

Exemple :

    hash ABC / sender_partner_id 10 / receiver_partner_id 30
    hash ABC / sender_partner_id 20 / receiver_partner_id 30

Ces deux lignes représentent un seul événement financier ABC, avec deux
associations administratives côté sender.

MLCFlux :

- déduplique les doublons strictement identiques ;
- accepte plusieurs partner_id pour un même hash ;
- exige que amount, received_at, type, fn_abi et les flags external soient
  identiques pour toutes les lignes portant le même hash ;
- rejette explicitement un même hash portant des faits financiers divergents.

Le comptage des transactions et des volumes est toujours effectué au grain
du hash, jamais au grain des associations partenaires.

## Identité administrative

`sender_partner_id` et `receiver_partner_id` sont les identifiants
administratifs fournis par le contrat.

MLCFlux n'a pas besoin de connaître l'adresse financière native
utilisée pour établir cette correspondance.

Les flags :

- `is_sender_external`
- `is_receiver_external`

sont conservés sans interprétation supplémentaire.


## Comptes partagés et associations administratives

CONTRACT001 ne suppose pas qu'un endpoint financier possède un unique
propriétaire administratif.

Une transaction peut être associée à zéro, un ou plusieurs partner_id de
chaque côté.

Le stockage local sépare donc :

- `contract001_transactions` : un événement financier par hash ;
- `contract001_transaction_partners` : les associations
  `(hash, side, partner_id)`.

Cette séparation permet à la fois :

- de compter chaque transaction exactement une fois ;
- de retrouver une transaction depuis chacun des propriétaires d'un compte
  partagé.

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


## Sémantique de `type` et `fn_abi`

`type` conserve la famille d'opération exposée par le producteur.

`fn_abi` est conservé comme code/sous-type natif de l'opération.
Malgré son nom historiquement lié à ComChain, MLCFlux ne l'interprète
pas comme un concept blockchain.

Il peut porter une information analytique importante.

Exemples observés :

- ComChain : `nantTransfer`, `transferNantOnBehalf`
- Cyclos possède un concept analogue via le code natif du type
  d'opération (`type.internalName`).

CONTRACT001 conserve donc cette information sans lui attribuer
directement une catégorie métier MLCFlux.

## Projection Financial Core

Financial Core reste une projection optionnelle.

TRANSACTIONS001 ne fournit pas l'identité des comptes financiers natifs et
MLCFlux ne fabrique pas `1 partner_id = 1 compte`.

Lorsqu'une projection Financial Core est utilisée :

- un événement est créé une seule fois par hash ;
- un endpoint analytique est créé une seule fois par côté ;
- plusieurs partner_id peuvent produire plusieurs IdentityLinks vers le
  même endpoint analytique ;
- les AccountEffects ne sont jamais multipliés par le nombre de
  propriétaires.

La couche contractuelle TRANSACTIONS001 reste la frontière principale du
runtime normalisé.
