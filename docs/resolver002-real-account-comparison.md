# RESOLVER002 — confrontation du resolver aux comptes réels

## Statut

RESOLVER002 reste un audit en lecture seule. Il ne remplace ni le classifieur
legacy, ni `transaction_semantics`, ni les analytics, ni le dashboard.

Le but est de mesurer ce que RESOLVER001 sait réellement conclure depuis les
faits INPUT001 avant toute migration métier.

## Ruleset de référence Gonette

Le ruleset est déclaratif et séparé du moteur :

`server/data/resolver_rulesets/gonette.json`

Il utilise uniquement :

- `source_system` ;
- `native_account_type`.

Les faits Gonette actuellement approuvés comme règles de référence sont :

- `compteparticulier` → `individual` ;
- `comptepro` → `professional` ;
- `emission` / `Conversion` → `technical`.

Aucun compte, identifiant, label `Pxxxx`, préfixe `U_` / `T_`, propriétaire ou
nom d'organisation n'est utilisé comme preuve.

`native_account_kind` est volontairement observé dans le rapport mais n'est pas
encore utilisé dans le ruleset : RESOLVER002 doit d'abord montrer ses valeurs
réelles et leur stabilité.

## Rapport réel

Commande sur une installation explicitement configurée :

```bash
python -m server.resolver.account_report --mlc gonette
```

Le rapport ouvre `input001.db` et `mlcflux.db` en mode SQLite `mode=ro`.
Aucune table n'est créée ou modifiée.

Il produit uniquement des agrégats :

- nombre total de comptes ;
- `resolved` / `unknown` / `conflict` ;
- familles résolues ;
- comptes sans `native_account_type` / `native_account_kind` ;
- combinaisons observées de faits natifs ;
- comparaison agrégée avec les familles de `transaction_semantics`, lorsqu'elle
  existe.

Le rapport ne doit jamais exposer :

- `account_id` ;
- `display_label` ;
- `native_owner_id` ;
- `native_account_number` ;
- une liste d'identités individuelles ou professionnelles.

## Comparaison avec le legacy

La comparaison ne prétend pas que le legacy est la vérité métier.
Elle sert uniquement à caractériser les divergences avant migration.

Pour relier les deux mondes :

1. `INPUT001.transactions.transaction_id` est rapproché de
   `transaction_semantics.cyclos_id` ;
2. les familles legacy observées sur chaque côté d'une transaction sont
   agrégées par `account_id` INPUT001 ;
3. une seule famille legacy observée rend le compte `legacy_classifiable` ;
4. plusieurs familles legacy pour le même compte sont comptées comme
   `legacy_conflict` ;
5. aucune identité de compte n'est sortie du rapport.

Normalisation de comparaison :

- `individual` et `individual_device` → `individual` ;
- `professional` → `professional` ;
- `system` et `exchange_office_or_stock` → `technical` ;
- `operator` reste `operator`.

Le dernier point est volontaire. Les comptes opérateurs legacy peuvent avoir le
même type natif Cyclos qu'un compte professionnel ordinaire. Si INPUT001 ne
porte pas encore de fait fiable permettant de les distinguer, le nouveau
resolver doit montrer la divergence au lieu de la masquer avec une règle sur
un identifiant `P0000` / `P9999`.

## Critères avant RESOLVER003

Le rapport réel doit être examiné avant toute extension du ruleset.

Une nouvelle règle n'est acceptable que si elle repose sur un fait natif ou
administratif explicitement documenté et stable. Un libellé, un préfixe de
pseudonyme ou un identifiant particulier ne doit pas être réintroduit comme
heuristique cachée.

RESOLVER002 ne modifie pas la production analytique. Son résultat doit servir à
identifier :

- les types natifs non couverts ;
- les éventuels conflits ;
- les catégories legacy impossibles à reproduire avec les faits actuels ;
- les faits supplémentaires qu'il faudrait éventuellement demander au provider
  ou à une source administrative.
