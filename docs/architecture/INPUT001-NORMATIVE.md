# INPUT001-NORMATIVE — Contrat financier d’entrée MLCFlux

**Statut :** proposition normative v0.1
**Objet :** définir la frontière entre les backends financiers et MLCFlux avant l’implémentation des providers/adaptateurs.
**Périmètre :** données financières uniquement. Les enrichissements administratifs (Odoo, Dolibarr, Kohinos en tant qu’annuaire/CRM, etc.) restent hors de ce contrat initial.

---

## 1. Principe d’architecture

MLCFlux ne doit pas dépendre directement du modèle de données de Cyclos, ComChain, Kohinos ou d’un autre backend.

Chaque source financière fournit, directement ou via un adaptateur, un **jeu de relations normalisées** conforme au contrat MLCFlux.

```text
Cyclos ───────┐
ComChain ─────┤
Kohinos ──────┤  adaptateur / driver
Autre ────────┘
              ▼
      Contrat financier MLCFlux
              │
       accès SQL abstrait
       SQLite / PostgreSQL
              │
              ▼
          Profil MLC
              │
              ▼
        ActorResolver
          P/U/UD/T/X
              │
              ▼
 transaction_semantics / analytics
```

Le contrat porte sur les **faits financiers disponibles dans la source**. Il ne doit pas encoder directement l’interprétation métier finale de MLCFlux.

---

## 2. Responsabilités

### 2.1. Backend / adaptateur

L’adaptateur **DOIT** :

- exposer les transactions et identités financières nécessaires ;
- conserver les identifiants natifs stables lorsqu’ils existent ;
- conserver les types, rôles et états natifs disponibles ;
- préserver la provenance des données ;
- signaler explicitement les données absentes ou non disponibles ;
- produire des montants exacts, sans perte liée aux flottants.

L’adaptateur **NE DOIT PAS** :

- attribuer directement les familles MLCFlux `P`, `U`, `UD`, `T` ou `X` ;
- déduire la nature d’un acteur depuis son nom, son libellé ou une heuristique ;
- transformer « absent d’Odoo » en « acteur externe » ;
- fabriquer un historique à partir du seul état courant ;
- appliquer des règles métier propres à une monnaie sans qu’elles soient déclarées dans son profil.

### 2.2. Profil MLC

Le profil MLC contient l’**interprétation approuvée pour une installation**.

Il définit notamment :

- les correspondances entre faits natifs et catégories MLCFlux ;
- les règles propres à la monnaie ;
- les comptes ou rôles techniques connus ;
- les éventuelles conventions spécifiques à un déploiement.

Le profil **NE DOIT PAS** contenir les secrets de connexion, le moteur de synchronisation ni une copie de la base des acteurs.

### 2.3. ActorResolver

Le resolver applique de manière déterministe :

```text
faits financiers
+ faits administratifs autorisés, si disponibles
+ profil MLC
→ P / U / UD / T / X
```

Si les faits disponibles ne permettent pas une classification certaine, le résultat **DOIT rester `X`**.

### 2.4. Enrichissement administratif

Odoo, Dolibarr, Kohinos ou une autre source administrative peuvent fournir des faits supplémentaires :

- identifiant partenaire ;
- SIRET ;
- statut personne / organisation ;
- lien explicite entre compte financier et entité administrative ;
- données territoriales ;
- fonds de garantie ou autres indicateurs administratifs.

Ces sources **NE classifient pas directement** les acteurs MLCFlux. Elles fournissent des faits utilisables par le resolver selon les règles du profil.

---

## 3. Propriété et accès aux données

Le producteur du contrat financier reste propriétaire de ses relations.

MLCFlux **DOIT considérer les relations financières externes comme en lecture seule**.

MLCFlux reste propriétaire de ses propres données :

- profils ;
- caches ;
- tables dérivées ;
- résultats analytiques ;
- métadonnées de synchronisation ;
- éventuelles tables internes matérialisées.

Les opérations d’initialisation, migration, reset ou purge de MLCFlux **NE DOIVENT JAMAIS** s’appliquer implicitement à une source externe.

PostgreSQL n’est pas le contrat. Le contrat doit pouvoir être exposé au minimum via :

- PostgreSQL ;
- SQLite.

Un export CSV ou une autre source pourra être supporté via un adaptateur qui matérialise ou expose les mêmes relations.

---

## 4. Relations minimales

Les noms ci-dessous sont provisoires mais leur sémantique constitue le contrat à éprouver.

### 4.1. `transactions` — obligatoire

Une ligne représente un mouvement financier unique.

Champs minimaux :

- `transaction_id` — identifiant stable dans la source ;
- `occurred_at` — date/heure effective ;
- `source_account_id` — compte source ;
- `destination_account_id` — compte destination ;
- `amount_minor` — montant exact en unité minimale ;
- `currency_code` ou équivalent ;
- `native_transaction_type` — type natif si disponible ;
- `native_transaction_label` — libellé natif si disponible.

Le contrat devra préciser explicitement si une ligne représente un mouvement unique ou une écriture comptable.

### 4.2. `accounts` — obligatoire

Une ligne représente une identité financière stable.

Champs minimaux :

- `account_id` — identifiant financier stable ;
- `native_account_type` — type/rôle natif si disponible ;
- `native_status` — état natif courant si disponible ;
- `display_label` — optionnel, uniquement informatif ;
- `native_owner_id` — optionnel ;
- `source_system` — provenance.

Un libellé ne constitue jamais une identité stable.

### 4.3. `account_states` — obligatoire si la source fournit la temporalité

Permet de représenter l’évolution d’un compte.

Champs conceptuels :

- `account_id` ;
- `valid_from` ;
- `valid_to` ;
- `native_account_type` ;
- `native_status`.

Si la source ne sait fournir que l’état courant, elle **DOIT le déclarer comme tel**. MLCFlux ne doit pas inventer l’historique.

### 4.4. `dataset_metadata` — obligatoire

Décrit le jeu de données fourni :

- version du contrat ;
- source / backend ;
- couverture temporelle ;
- date ou instantané de référence ;
- capacités disponibles ;
- caractère historique ou état courant de chaque relation.

### 4.5. `balances` — optionnel

Pour les stocks financiers observables :

- `account_id` ;
- `observed_at` ;
- `balance_component` ;
- `amount_minor` ;
- provenance.

Un stock ne doit pas être reconstruit à partir d’une période partielle de transactions sans solde initial fiable.

### 4.6. `account_replacements` — optionnel

Relation explicite entre comptes lorsqu’un backend sait représenter un remplacement :

- `old_account_id` ;
- `new_account_id` ;
- `effective_at` ;
- `native_reason` / provenance.

Cette relation ne doit pas être inventée lorsqu’elle n’existe pas dans la source.

---

## 5. Temporalité, remplacement et comptes désactivés

Le modèle doit distinguer :

1. l’identité financière durable ;
2. l’état du compte à une date donnée ;
3. le traitement économique du compte dans un calcul donné.

Un compte désactivé peut rester nécessaire pour interpréter correctement les transactions historiques.

La désactivation d’un compte **NE DOIT PAS** entraîner automatiquement :

- la suppression de son historique ;
- son exclusion de tous les indicateurs historiques ;
- l’interprétation d’un compte de remplacement comme nouvelle émission ou conversion.

Les effets exacts de la désactivation et du remplacement restent à préciser pour ComChain.

---

## 6. Classification des acteurs

Le contrat financier expose des **faits**, pas la famille MLCFlux finale.

Exemple autorisé :

```text
native_account_type = "business"
+ règle explicite du profil
→ P
```

Exemple interdit :

```text
display_label = "Boulangerie Martin"
→ semble professionnel
→ P
```

La résolution doit être explicable et reproductible.

En cas de données insuffisantes ou contradictoires :

```text
→ X
```

Aucun fallback silencieux vers `U`, `P` ou `T` n’est autorisé.

---

## 7. Indicateurs et capacités

La disponibilité d’un indicateur dépend de ses **prérequis de données**, pas du nom de la source utilisée.

Chaque indicateur devra progressivement déclarer ses besoins, par exemple :

- transactions classifiées ;
- historique complet ;
- soldes datés ;
- fonds de garantie observé ;
- données territoriales ;
- enrichissement administratif.

MLCFlux devra distinguer clairement :

- valeur observée ;
- valeur estimée ;
- donnée indisponible.

---

## 8. Abstraction SQL

La piste de référence pour le prototype est **SQLAlchemy Core**.

Objectif initial :

- lire le même contrat depuis SQLite et PostgreSQL ;
- permettre aux filtres, jointures et agrégations d’être exécutés par le moteur distant lorsque pertinent ;
- ne pas migrer immédiatement tout le stockage interne de MLCFlux.

L’introduction de SQLAlchemy doit rester iso-fonctionnelle. Les dépendances SQLite existantes (`PRAGMA`, `sqlite_master`, `rowid`, fonctions spécifiques, etc.) seront traitées explicitement lorsqu’elles sont rencontrées.

Alembic pourra être utilisé ultérieurement pour les schémas **possédés par MLCFlux**, jamais pour administrer automatiquement les vues ou tables d’un producteur externe.

---

## 9. Jeux de référence à valider avant généralisation

Le contrat doit être éprouvé au minimum sur les cas suivants :

### Cyclos / Gonette
- transaction particulier → professionnel ;
- professionnel → professionnel ;
- compte technique ;
- type d’acteur inconnu ;
- données actuelles donnant exactement les mêmes familles que le pipeline existant.

### Cyclos / Graine
- vocabulaire natif différent de la Gonette ;
- compatibilité avec ses règles historiques spécifiques.

### ComChain
- compte `personal` ;
- compte `business` ;
- compte administratif / technique ;
- compte désactivé ;
- remplacement d’un compte perdu ;
- données disponibles sans Odoo ;
- partenaire administratif absent.

Le contrat n’est considéré suffisamment générique que s’il représente ces situations **sans ajouter de règle spécifique au backend dans MLCFlux Core**.

---

## 10. Questions restant ouvertes

Ces points ne bloquent pas la rédaction du contrat mais doivent être confirmés avant finalisation du provider ComChain :

- effets exacts d’une désactivation sur les différents soldes et le nantissement ;
- existence d’une relation native entre ancien et nouveau compte ;
- disponibilité d’un historique des types et états de comptes ;
- règle permettant de choisir un état confirmé/reproductible côté ComChain ;
- sémantique exacte des comptes administratifs et techniques ;
- éventuelles conventions Lokavaluto garanties au niveau du déploiement.

---

## 11. Critères d’acceptation de INPUT001

INPUT001 est considéré validé lorsque :

1. les relations minimales et leur sémantique sont documentées ;
2. les champs obligatoires et optionnels sont distingués ;
3. l’ownership lecture/écriture est explicite ;
4. les données inconnues restent représentables sans heuristique ;
5. les cas Cyclos/Gonette, Cyclos/Graine et ComChain peuvent être décrits par le même modèle ;
6. un prototype SQLAlchemy Core lit des fixtures identiques depuis SQLite et PostgreSQL ;
7. aucune modification fonctionnelle n’est introduite dans `transaction_semantics` ou les analytics existants.

---

## 12. Étape suivante

Après validation de ce document :

```text
PROVIDER001-CYCLOS
```

Objectif :

```text
Cyclos brut
→ adaptateur
→ contrat financier normalisé
→ profil existant
→ ActorResolver
→ mêmes P/U/UD/T/X
→ mêmes transactions stockées
→ mêmes résultats analytiques
```

Le provider ComChain sera le second test réel du contrat avant toute généralisation supplémentaire du modèle.
