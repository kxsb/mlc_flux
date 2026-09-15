# FINCORE003 — ComChain PostgreSQL read-only

## Objet

FINCORE003-A introduit le premier chemin fondé sur une source réelle
vers le nouveau Financial Core.

Il ne publie pas encore le batch dans le writer FINCORE002.

Le jalon valide d'abord la frontière :

PostgreSQL ComChain natif
-> facts provider
-> FinancialEvent / AccountEffect

## Source Lokavaluto observée

Sur le VPS de développement Lokavaluto, le 15 septembre 2026 :

- source native :
  `ext_pyc3l-sync_Lemanopolis.transactions`
- type PostgreSQL : foreign table
- 6 lignes
- 6 hashes distincts
- 8 adresses sender/receiver distinctes
- fonctions :
  - `nantTransfer`
  - `transferNantOnBehalf`
- contrat :
  `LEM-2`
- `status` vide pour les six lignes

La vue :

`public.transactions_pyc3l-sync_Lemanopolis`

contient 9 lignes pour les mêmes 6 hashes.

Elle joint `res_partner_backend` sur sender et receiver.
Elle n'est donc pas utilisée comme source financière autoritative.

## Décisions

- 1 hash natif = 1 FinancialEvent.
- Une ligne native `type=transfer` produit deux AccountEffect :
  débit sender et crédit receiver.
- `status=''` reste `execution_state=unknown`.
- `nantTransfer` et `transferNantOnBehalf` restent des sous-types natifs.
- aucune catégorie paiement/conversion/reconversion n'est déduite.
- aucune identité Odoo n'est nécessaire pour créer un compte financier.
- absence de match Odoo != acteur externe.
- la dimension monétaire est fournie explicitement par le profil
  d'installation et n'est pas déduite du nom de fonction.

## Connector

`ComChainPostgresSource` impose une transaction PostgreSQL READ ONLY.

Le nom du schéma est fourni par la configuration de l'installation.

## Suite

FINCORE003-B branchera ce batch sur :

FinancialCorePayload
-> prepare
-> validate
-> publish
-> coherent reader

dans une base locale/temporaire avant toute intégration runtime.
