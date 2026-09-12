# INPUT001 — Audit du contrat Cyclos actuel

Statut : photographie iso-fonctionnelle avant introduction d'un contrat financier normalisé.

## 1. Données Cyclos actuellement consommées

### Transaction

Le pipeline utilise actuellement :

- `transaction.id`
- `transaction.transactionNumber`
- `transaction.date`
- `transaction.amount`
- `transaction.kind`
- `transaction.creationType`
- `transaction.type.name`
- `transaction.type.internalName`
- `transaction.from`
- `transaction.to`

### Acteur / compte

Pour `from` et `to` :

- `actor.type.internalName`
- `actor.id`
- `actor.number`
- `actor.user.id`
- `actor.user.display`

## 2. Responsabilités actuellement mélangées

`cyclos_actor_classifier.py` réalise aujourd'hui plusieurs opérations différentes :

1. extraction de la structure native Cyclos ;
2. interprétation de `actor.type.internalName` via le profil MLC ;
3. résolution vers `P / U / UD / T / X` ;
4. génération des labels techniques ;
5. création/récupération des références professionnelles ;
6. création/récupération des pseudonymes particuliers.

Le futur adaptateur Cyclos ne devra conserver que la première responsabilité :
exposer fidèlement les faits natifs nécessaires au contrat.

La classification MLC restera une responsabilité distincte du profil/resolver.

## 3. Différences déjà observées entre profils Cyclos

### Gonette

Exemples de types natifs :

- `compteparticulier`
- `comptepro`
- `emission`
- `Conversion`

### Graine

Exemples de types natifs :

- `monCompte`
- `MonComptePro`
- `emissionNum`
- `stockBch`
- `compteBillets`
- `conversionNumerique`
- plusieurs autres comptes techniques

Conclusion :

Cyclos ne fournit pas à lui seul une nomenclature métier universelle.
Le type natif doit être conservé comme fait source puis interprété par le profil.

## 4. Stockage transactionnel actuel

La table historique `transactions` reçoit huit champs :

- `transaction_number`
- `cyclos_id`
- `date`
- `group_label`
- `from_label`
- `to_label`
- `amount`
- `type_label`

Ce schéma reste inchangé pendant INPUT001 et PROVIDER001.

Le contrat normalisé est une couche en amont ; il ne constitue pas encore
une migration du stockage analytique existant.

## 5. Écarts entre le contrat cible et le pipeline actuel

### Identité des comptes

Les identifiants natifs Cyclos sont utilisés pendant la classification mais
ne sont pas conservés dans la table historique `transactions`.

Le contrat devra les exposer explicitement.

### Montants

Le pipeline actuel convertit le montant en `float` avant stockage SQLite.

Le contrat cible devra conserver une représentation exacte
(entier en unité minimale ou représentation décimale explicite).

Cette évolution ne doit pas modifier immédiatement la table historique.

### Temporalité

Le pipeline courant utilise essentiellement l'état/type d'acteur fourni
avec la transaction Cyclos.

Le contrat devra distinguer l'identité du compte et, lorsque la source le
permet, son état/type dans le temps.

### Provenance

Le stockage historique utilise encore le nom `cyclos_id`.

Le contrat générique utilisera un identifiant de transaction source stable,
tout en laissant `cyclos_id` inchangé dans le stockage actuel pendant la
transition.

## 6. Invariants pour PROVIDER001

Le refactor Cyclos devra conserver :

- les mêmes transactions sélectionnées ;
- les mêmes familles `P / U / UD / T / X` ;
- les mêmes labels stockés ;
- les mêmes règles spécifiques Gonette/Graine ;
- la même politique de rejet d'un lot contenant `X` ;
- les mêmes résultats de `transaction_semantics`.

Aucune heuristique de classification supplémentaire ne doit être introduite.
