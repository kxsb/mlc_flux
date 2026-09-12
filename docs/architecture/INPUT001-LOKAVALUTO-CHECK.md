# INPUT001 — confrontation Lokavaluto Cyclos / ComChain

## Objet

Ce document confronte le contrat financier INPUT001 à deux implémentations
réelles fournies par Lokavaluto :

- le chemin Cyclos de `currency-stats/hooks/post_deploy` ;
- le chemin ComChain du même composant ;
- le modèle analytique `model_transactions_data.sql`.

L'objectif n'est pas de reproduire les conventions Lokavaluto ni Odoo,
mais de vérifier que le contrat MLCFlux peut représenter leurs données
sans hypothèse spécifique au backend.

## 1. Principe commun

Le contrat reste indépendant :

- du backend financier ;
- du SGBD utilisé pour exposer les données ;
- du fait que les relations soient des tables ou des vues ;
- du système administratif associé.

Architecture visée :

    Cyclos   ┐
    ComChain ├── provider / driver ──> contrat financier SQL
    Kohinos  │                              ↓
    CSV      ┘                           MLCFlux

Le producteur peut exposer le contrat via PostgreSQL, SQLite ou tout
autre moteur compatible avec la couche SQLAlchemy utilisée par MLCFlux.

## 2. Référence Lokavaluto — Cyclos

L'implémentation Lokavaluto importe depuis PostgreSQL :

- `transactions` ;
- `accounts` ;
- `users`.

Les transactions sont reliées :

    transaction.from_id / to_id
        ↓
    accounts.id
        ↓
    accounts.user_id
        ↓
    users.id

Cette structure confirme que l'identité d'un compte et celle de son
propriétaire doivent rester distinctes.

Cela correspond à INPUT001 :

- `accounts.account_id` ;
- `accounts.native_owner_id`.

Cette séparation est également confirmée empiriquement sur La Graine :
plusieurs comptes Cyclos peuvent appartenir au même utilisateur.

## 3. Référence Lokavaluto — ComChain

L'implémentation Lokavaluto lit une table SQLite `transactions` contenant
notamment :

- `sender` ;
- `receiver` ;
- `amount` ;
- `received_at` ;
- `hash` ;
- `fn_abi` ;
- `type`.

Le rapprochement administratif se fait ensuite avec Odoo via
`res_partner_backend.comchain_id`.

INPUT001 ne doit pas dépendre de ce rapprochement.

Un provider ComChain peut produire :

    sender / receiver
        ↓
    account_id

et générer la relation `accounts` à partir des comptes connus ou, au
minimum, des identifiants distincts observés dans les transactions.

Les attributs non connus côté ComChain peuvent rester NULL :

- `native_account_number` ;
- `native_account_type` ;
- `native_status` ;
- `native_owner_id`.

La relation `accounts` reste donc compatible avec un backend dont la
source native n'expose initialement qu'une liste de transactions.

## 4. Montants

Les exemples Lokavaluto montrent que les unités natives ne doivent pas
être supposées identiques entre backends.

Le chemin Cyclos convertit le montant avant exposition analytique,
tandis que le chemin ComChain reprend un montant déjà représenté dans
une autre unité.

INPUT001 impose donc uniquement la représentation finale :

- `amount_minor` ;
- `currency_code` ;
- `currency_exponent`.

La conversion depuis l'unité native appartient au provider.

Aucun `currency_exponent` implicite n'est autorisé dans le contrat.

## 5. Identité de devise

Cyclos expose dans les transactions observées par MLCFlux :

- La Graine : `graine34` ;
- La Gonette : `unit`.

Ces valeurs sont conservées comme `native_currency_id`, mais ne sont pas
assimilées automatiquement à `currency_code`.

Un backend qui ne fournit pas d'identifiant de devise natif peut laisser
`native_currency_id` à NULL et fournir la devise normalisée au niveau du
provider ou du dataset.

## 6. Notion d'acteur externe

La notion d'acteur "external" observée dans les exemples Lokavaluto n'est
pas suffisamment universelle pour faire partie du noyau INPUT001.

Dans le chemin Cyclos Lokavaluto, un acteur peut être considéré externe
par absence de correspondance Odoo.

Dans le chemin ComChain, certains comptes techniques sont explicitement
considérés externes.

Ces deux mécanismes ne sont pas équivalents.

Décision :

- INPUT001 conserve les faits financiers ;
- la classification externe/interne relève du resolver et du profil MLC ;
- l'absence d'une entité administrative ne signifie pas automatiquement
  que le compte financier est externe.

## 7. Temporalité et remplacements de comptes

ComChain permet notamment :

- la désactivation de comptes ;
- le remplacement d'un compte par un nouveau compte ;
- des changements de nature/statut de comptes.

INPUT001 prévoit donc comme capacités optionnelles :

- `account_states` ;
- `balances` ;
- `account_replacements`.

Ces relations ne sont pas obligatoires pour qu'un backend soit compatible.

Elles servent à préserver les statistiques historiques lorsqu'une source
est capable de fournir cette information.

## 8. Frontière administrative

Les exemples Lokavaluto croisent actuellement les données financières
avec Odoo.

INPUT001 ne normalise pas Odoo.

La future couche administrative devra être traitée séparément :

    financial contract
           │
           └── liaison compte / entité
                       │
    administrative / directory contract
                       │
                       ↓
                    analytics

Le système administratif pourra à terme être Odoo, Dolibarr, Kohinos,
CSV ou une autre source.

Cette future abstraction ne doit pas être nécessaire à la validation du
contrat financier actuel.

## 9. Conclusion

La confrontation Cyclos / ComChain ne révèle pas de dépendance
structurelle à Cyclos dans le noyau INPUT001.

Les principaux invariants restent :

- transaction financière ;
- comptes source / destination ;
- montant exact en unité minimale ;
- devise explicite ;
- identité de compte distincte de l'identité propriétaire ;
- données temporelles optionnelles ;
- aucune classification métier MLC dans le provider.

Points à soumettre à la revue Astra :

1. vérifier que `accounts` obligatoire reste une abstraction raisonnable
   pour les backends transaction-only comme ComChain ;
2. vérifier la neutralité des identités et des devises ;
3. vérifier la modélisation des remplacements et états temporels ;
4. identifier toute hypothèse Cyclos encore présente dans INPUT001 ;
5. préparer la frontière future entre contrat financier et contrat
   administratif sans introduire Odoo dans le contrat financier.
