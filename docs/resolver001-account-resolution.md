# RESOLVER001 — résolution métier pure des comptes INPUT001

**Statut :** première brique expérimentale, non branchée au dashboard.

## Objectif

RESOLVER001 introduit une frontière explicite entre les faits financiers normalisés par INPUT001 et leur interprétation métier.

```text
backend financier
    ↓
provider / projection
    ↓
INPUT001 : faits financiers neutres
    ↓
RESOLVER001 : règles métier déclaratives
    ↓
classification métier explicite
    ↓
future transaction semantics / analytics
```

Cette première étape ne remplace aucun calcul analytique existant. Elle ne modifie ni `mlcflux.db`, ni le dashboard, ni `transaction_semantics`.

## 1. Ce que le resolver reçoit

Le resolver reçoit une ligne `accounts` INPUT001 et un ruleset fourni explicitement par l'appelant.

RESOLVER001 autorise uniquement les faits suivants comme critères de règle :

- `source_system` ;
- `native_account_type` ;
- `native_account_kind` ;
- `native_status`.

Les champs suivants sont volontairement exclus des critères de classification :

- `display_label` ;
- `account_id` ;
- `native_account_number` ;
- `native_owner_id`.

Un identifiant ou un libellé peut servir à retrouver un compte ou à l'afficher ; il ne constitue pas, en lui-même, une preuve de sa catégorie métier.

## 2. Résultat

La sortie sépare la catégorie métier de l'état de résolution :

```text
family          catégorie produite par le ruleset, ou null
status          resolved | unknown | conflict
rule            règle unique ayant produit le résultat, sinon null
matched_rules   toutes les règles correspondantes
evidence        faits natifs réellement utilisés
ruleset_version version explicite du jeu de règles
```

`family` n'est volontairement pas codée en dur dans le moteur. Le ruleset peut utiliser une taxonomie descriptive (`individual`, `professional`, `technical`, etc.) ou une taxonomie de compatibilité définie ailleurs. Les valeurs `unknown` et `conflict` sont réservées aux statuts et ne peuvent pas être utilisées comme familles.

Cette décision évite que RESOLVER001 ne transforme implicitement les catégories legacy `P/U/UD/T/X` en nouveau contrat universel avant l'arbitrage métier.

## 3. Comportement déterministe

Une règle contient :

- un `rule_id` stable ;
- une `family` ;
- une ou plusieurs conditions exactes ;
- éventuellement une raison documentaire.

Toutes les conditions d'une règle doivent correspondre.

Si aucune règle ne correspond :

```text
status = unknown
family = null
```

Si plusieurs règles correspondent et produisent la même famille :

```text
status = resolved
family = cette famille
matched_rules = toutes les règles correspondantes
```

Si plusieurs règles correspondantes produisent des familles différentes :

```text
status = conflict
family = null
```

Aucune priorité implicite ne masque donc une contradiction de configuration ou de faits.

## 4. Caractérisation du legacy actuel

Le système existant contient plusieurs couches de classification qui ne doivent pas être confondues avec RESOLVER001.

### `server/services/cyclos_actor_classifier.py`

Cette couche :

- lit directement les profils Gonette/Graine ;
- transforme `actor.type.internalName` en familles `P/U/UD/T/X` ;
- fabrique ensuite des labels legacy (`P...`, `U...`, `T_...`) ;
- peut faire appel aux mappings professionnels/particuliers ;
- est spécifique à l'ingestion Cyclos legacy.

Elle mélange donc aujourd'hui classification métier, pseudonymisation et format de stockage legacy.

### `server/services/transaction_semantics.py`

Cette couche :

- lit `mlcflux.db` ;
- classe encore des acteurs à partir de labels legacy ;
- contient des fallbacks `U_`, `UD_`, `Pxxxx`, `T_` ;
- déduit aussi le medium du compte depuis des fragments de libellés ;
- mélange classification des acteurs, nature du compte, typologie des opérations et circuits monétaires ;
- possède encore un fallback implicite vers `gonette` lorsqu'aucune MLC n'est explicitement configurée.

Elle reste la couche de production historique et ne doit pas être supprimée avant caractérisation des parcours analytiques qui la consomment.

RESOLVER001 ne tente pas de reproduire tout cela. Il isole seulement la première responsabilité : **résoudre une catégorie métier à partir de faits INPUT001 explicites**.

## 5. Propriétés de pureté

`server/resolver/account_resolver.py` :

- n'importe ni Flask, ni SQLite, ni SQLAlchemy ;
- ne lit aucun profil depuis le disque ;
- n'accède à aucune variable d'environnement ;
- ne connaît aucun nom de monnaie ;
- ne contient aucune convention de type `Pxxxx` ;
- ne contacte ni Cyclos, ni ComChain, ni Odoo ;
- n'écrit rien.

Le même couple `account + ruleset` produit donc toujours le même résultat.

## 6. Ce qui reste volontairement hors RESOLVER001

Cette première brique ne résout pas encore :

- la construction du ruleset à partir de la future configuration Neutral ;
- les faits administratifs Odoo / Dolibarr / autre annuaire ;
- les sous-rôles (`operator`, bureau de change, stock, etc.) ;
- la nature `paper/digital/bonus/...` d'un compte ;
- la sémantique d'une transaction ;
- les comptes absents d'un côté d'un mouvement ;
- la temporalité d'une classification ;
- l'adaptation des résultats vers les colonnes legacy `P/U/UD/T/X` ;
- le branchement au dashboard.

Ces sujets doivent être ajoutés par couches, avec leurs propres tests.

## 7. Étape suivante proposée

Après validation de RESOLVER001 :

1. définir un petit ruleset Gonette à partir de `native_account_type` / `native_account_kind`, sans utiliser les labels legacy ;
2. comparer ce resolver aux classifications legacy sur un échantillon réel INPUT001, en lecture seule ;
3. mesurer `resolved / unknown / conflict` et inspecter les divergences ;
4. faire la même chose sur Graine lorsque les faits INPUT001 nécessaires sont disponibles ;
5. seulement ensuite définir l'adaptateur de compatibilité vers les analytics historiques.

Le critère de succès n'est pas « reproduire 100 % du legacy à tout prix ». Une divergence peut révéler soit une lacune du ruleset, soit une ancienne heuristique erronée.
