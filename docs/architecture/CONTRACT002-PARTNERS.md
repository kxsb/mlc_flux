# CONTRACT002 — partenaires / profils administratifs

Version : `PARTNERS002`

## Objectif

Fournir à MLCFlux un profil administratif minimal associé aux
`partner_id` présents dans CONTRACT001.

Ce contrat appartient à MLCFlux.

Il ne décrit ni les comptes financiers natifs, ni la structure interne
d'Odoo, ComChain ou Cyclos.

## Grain

Une ligne = un partenaire administratif identifié par `partner_id`
dans une instance source donnée.

`partner_id` n'est pas un identifiant global inter-instance.

Un partenaire n'est pas nécessairement un professionnel.

## Champs

- `partner_id`
- `name`
- `is_company`
- `member_type`
- `industry_code`
- `industry_name`
- `siret`
- `siren`
- `legal_activity_code`
- `city`
- `zip`
- `latitude`
- `longitude`
- `active`
- `is_published`

Les champs autres que `partner_id` peuvent être absents (`NULL`).

## Nomenclatures

Les identifiants techniques locaux ne traversent pas le contrat.

Exemple :

    res_partner.industry_id = 17

n'est pas exposé comme valeur métier.

L'adaptateur transforme la nomenclature en :

    industry_code = "Q"
    industry_name = "Santé/Social"

Même principe pour `member_type` : le contrat transporte le libellé
métier, pas l'ID Odoo.

## Identité légale

`siret`, `siren` et `legal_activity_code` sont transportés lorsqu'ils
existent.

MLCFlux ne les déduit pas et ne remplace pas une valeur manquante.

## Géographie

`0.0` et `NULL` restent distincts.

Le contrat ne suppose donc jamais qu'une coordonnée nulle signifie
une donnée absente.

## Adaptateur Odoo

`server/providers/odoo_partners_postgres.py` constitue un adaptateur
source spécifique.

Il peut lire notamment :

- `res_partner`
- `member_type`
- `res_partner_industry`

Ces tables ne font pas partie du contrat.

Une autre source administrative pourra produire exactement
PARTNERS002 sans reproduire le schéma Odoo.
