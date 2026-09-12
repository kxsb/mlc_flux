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

## Audit d'identité Cyclos — La Graine production

Audit read-only réalisé sur une fenêtre glissante de 7 jours sur
l'instance Cyclos réelle de La Graine.

Résultats :

- 134 transactions ;
- 268 positions d'acteurs ;
- 0 acteur absent ;
- `actor.id` présent sur 268 / 268 positions ;
- `actor.number` présent sur 268 / 268 positions ;
- `actor.user.id` absent sur 39 positions ;
- 107 `actor.id` distincts ;
- 107 `actor.number` distincts ;
- 90 `actor.user.id` distincts ;
- aucune relation 1 `actor.id` -> plusieurs `actor.number` observée ;
- aucune relation 1 `actor.number` -> plusieurs `actor.id` observée ;
- aucune relation 1 `actor.id` -> plusieurs `actor.user.id` observée ;
- 14 `actor.user.id` sont reliés à plusieurs `actor.id` ;
- aucune variation de type natif pour un même `actor.id` observée.

Types natifs observés :

- `monCompte` : 93 ;
- `MonComptePro` : 69 ;
- `stockBch` : 35 ;
- `emissionNum` : 33 ;
- `compteBillets` : 29 ;
- `stockCoffreCentral` : 4 ;
- `compteProBillets` : 2 ;
- `conversionNumerique` : 2 ;
- `histoDepotPrestataire` : 1.

### Conclusion croisée Gonette / Graine

Les deux instances Cyclos réelles observées convergent sur la même
séparation des identités :

- `actor.id` représente l'identité technique du compte / acteur financier ;
- `actor.number` est une référence native de compte, utile mais non
  disponible universellement ;
- `actor.user.id` représente l'identité du propriétaire / utilisateur et
  ne peut pas servir d'identité de compte : sur La Graine, plusieurs
  `actor.id` peuvent partager le même `actor.user.id`.

Décision du provider Cyclos :

- `account_id` = `actor.id` ;
- `native_account_number` = `actor.number` ;
- `native_owner_id` = `actor.user.id` ;
- `native_account_type` = `actor.type.internalName`.

Aucun fallback automatique de `account_id` vers `actor.number` ou
`actor.user.id` n'est autorisé.

Ces constats portent sur des fenêtres réelles de 7 jours et ne prétendent
pas démontrer l'immutabilité historique absolue de `actor.id`. Ils sont
néanmoins cohérents sur deux configurations Cyclos indépendantes et
suffisent pour fixer le contrat du provider actuel.

## Audit monétaire Cyclos — Gonette / La Graine

Audit read-only réalisé sur les mêmes fenêtres de 7 jours.

### La Graine

- 134 transactions observées ;
- `amount` est fourni sous forme de chaîne ;
- les 134 montants observés utilisent 2 décimales ;
- `transaction.currency` est présent sur les 134 transactions ;
- la valeur native observée est `graine34`.

### La Gonette

- 549 transactions observées ;
- `amount` est fourni sous forme de chaîne ;
- les 549 montants observés utilisent 2 décimales ;
- `transaction.currency` est présent sur les 549 transactions ;
- la valeur native observée est `unit`.

### Décision PROVIDER001

`transaction.currency` est conservé comme `native_currency_id`.

Il n'est pas assimilé directement à `currency_code` : les valeurs
observées (`graine34`, `unit`) sont des identifiants natifs Cyclos et non
une nomenclature portable garantie.

Le provider reçoit donc une spécification explicite associant :

- `native_currency_id` ;
- `currency_code` normalisé pour le dataset ;
- `currency_exponent`.

Le montant natif est lu avec `Decimal`, puis converti en `amount_minor`
uniquement si sa précision est compatible avec l'exposant déclaré.
Aucun arrondi silencieux n'est autorisé.

Les 683 transactions observées utilisent 2 décimales, mais cette
observation ne constitue pas une raison pour coder implicitement
`currency_exponent = 2` dans le provider.
