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

Une ligne représente **un mouvement financier normalisé unique**.

Le grain du contrat est le mouvement financier, et non nécessairement
l’opération native telle qu’elle est stockée par le backend.

Une opération native peut donc produire :

- un seul mouvement normalisé ;
- plusieurs mouvements normalisés si la source représente plusieurs effets
  financiers distincts dans une même opération.

Inversement, les deux écritures comptables d’un même transfert ne doivent
pas être comptées deux fois comme deux mouvements économiques lorsque la
source permet d’identifier qu’elles représentent le même transfert.

Champs minimaux :

- `transaction_id` — identifiant stable du mouvement normalisé dans l’espace
  du dataset ;
- `native_transaction_number` — référence ou numéro natif si disponible ;
- `occurred_at` — instant effectif du mouvement selon la référence temporelle
  documentée par le provider ;
- `source_account_id` — compte source, nullable si la source ne fournit pas
  l’acteur ;
- `destination_account_id` — compte destination, nullable si la source ne
  fournit pas l’acteur ;
- `amount_minor` — montant exact en unité minimale ;
- `native_currency_id` — identifiant natif de devise si disponible ;
- `currency_code` — identifiant de devise normalisé pour le dataset ;
- `currency_exponent` — nombre de décimales correspondant à l’unité minimale ;
- `native_transaction_type` — type natif si disponible ;
- `native_transaction_label` — libellé natif si disponible ;
- `native_transaction_group` — groupe natif si disponible.

`transaction_id` n’est pas défini comme « l’ID natif du backend ».
Un provider peut construire un identifiant de mouvement à partir d’un
identifiant d’opération native et d’un sous-identifiant stable lorsque la
source l’exige.

Le lien avec l’opération native doit rester récupérable sans ambiguïté.
Le contrat pourra donc transporter explicitement un identifiant natif
d’opération lorsque le deuxième provider réel confirme ce besoin.

`amount_minor` est exprimé dans l’unité minimale de la devise ;
`currency_exponent` permet d’en reconstruire l’échelle sans supposer
implicitement deux décimales.

Le signe du montant ne doit pas être utilisé pour deviner source et
destination. La convention de signe appartient au provider et doit produire
une représentation cohérente dans le contrat.

La relation `transactions` ne contient que les mouvements que le provider
considère réalisés / comptabilisables selon une politique de finalité
documentée pour la source. Un état pending, failed ou équivalent ne doit pas
être silencieusement assimilé à un mouvement réalisé.

### 4.2. `accounts` — obligatoire

Une ligne représente une identité financière stable **dans l’espace
d’identités défini par le dataset**.

La relation peut être :

- exhaustive, lorsque la source fournit un registre complet de comptes ;
- observée, lorsqu’elle est construite à partir des identifiants financiers
  effectivement rencontrés dans les transactions, soldes, états ou
  remplacements.

Construire un compte minimal à partir d’un identifiant source/destination
déjà présent dans une transaction ne constitue pas une invention
d’identité. En revanche, aucun propriétaire, type, statut ou libellé ne doit
être inventé pour compléter ce compte.

Une relation `accounts` observée ne peut pas servir, à elle seule, à compter
le nombre total de comptes ou de membres du backend.

Champs minimaux :

- `account_id` — identifiant financier stable ;
- `native_account_number` — numéro/référence native du compte si disponible ;
- `native_account_type` — type/rôle natif si disponible ;
- `native_status` — état natif courant si disponible ;
- `display_label` — optionnel, uniquement informatif ;
- `native_owner_id` — optionnel ;
- `source_system` — provenance.

Un libellé ne constitue jamais une identité stable.

L’absence d’un compte sur un côté d’une transaction reste représentable par une référence nulle. Elle ne doit pas provoquer la création d’une fausse identité financière ; son interprétation éventuelle reste une règle du profil/resolver.

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

Décrit le jeu de données fourni.

`dataset_id` définit l’**espace d’identités stable** dans lequel les clés
`account_id` et `transaction_id` sont interprétées.

Deux installations distinctes d’un même logiciel financier ne partagent
donc pas implicitement le même espace d’identités, même si elles exposent
des identifiants natifs identiques.

`snapshot_ref` identifie, lorsqu’il existe, une publication, extraction ou
version particulière de cet espace. Il ne remplace pas `dataset_id`.

Les métadonnées décrivent notamment :

- version du contrat ;
- source / backend ;
- espace d’identités du dataset ;
- couverture temporelle connue ;
- référence de publication / instantané ;
- capacités disponibles ;
- caractère exhaustif, observé ou inconnu du registre de comptes ;
- caractère historique ou état courant des informations exposées ;
- limites connues d’exhaustivité ou de finalité.

`coverage_from` et `coverage_to` décrivent des bornes connues du dataset.
Elles ne constituent pas, à elles seules, une preuve d’exhaustivité entre
ces deux bornes.

Un dataset peut être vide tout en restant conforme si ses relations et ses
métadonnées sont valides.

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

Tous les instants du contrat représentent des **instants UTC**.

Le stockage physique peut différer selon le dialecte SQL, mais la lecture
par MLCFlux doit restituer une sémantique UTC non ambiguë. Le fuseau utilisé
pour agréger des journées civiles est une information distincte de
l’instant UTC.

Sémantique temporelle :

- `occurred_at` : instant de réalisation du mouvement selon la référence
  documentée par le provider ; ce n’est pas la date d’import ;
- `valid_from` : début inclusif d’un état attesté ;
- `valid_to` : fin exclusive d’un état attesté, nullable si l’état est
  toujours courant ou si sa fin n’est pas connue ;
- `effective_at` : instant d’effet attesté d’un remplacement ;
- `observed_at` : instant auquel un stock / solde est valable selon la
  sémantique documentée de la source, et non automatiquement l’heure de
  collecte.

Une date de découverte par l’adaptateur ne doit pas être transformée en
date d’effet métier.

Une source qui ne fournit qu’une date civile sans instant ne doit pas
inventer silencieusement une heure. Cette limite doit être déclarée par le
provider ou le dataset.

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

### 5.1. Portée des identifiants

Les identifiants du contrat sont opaques.

Le Core MLCFlux ne doit pas leur appliquer de normalisation générique de
casse, de préfixe ou de format.

Les règles d’égalité appartiennent au provider correspondant à la source.

En particulier :

- `account_id` n’est pas une personne ;
- `native_owner_id` n’est pas automatiquement un identifiant administratif ;
- deux comptes partageant le même propriétaire restent deux comptes ;
- deux comptes appartenant à deux datasets différents ne sont jamais
  assimilés sur la seule égalité de leur chaîne d’identifiant.

### 5.2. Cohérence d’un snapshot

Lorsque les relations du contrat sont exposées dynamiquement par des vues,
elles doivent représenter un jeu cohérent pendant une lecture analytique.

MLCFlux ne doit pas supposer qu’une succession de connexions indépendantes
constitue automatiquement un même snapshot.

Le mécanisme exact de cohérence — publication immuable, transaction SQL,
niveau d’isolation ou matérialisation — dépend du producteur et du dialecte,
mais doit être documentable.

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

### Portée actuelle des cas de référence

Les cas disponibles ne constituent pas encore une validation d’une installation utilisant intégralement les conventions Lokavaluto.

- **La Graine** n’est pas une monnaie cliente de Lokavaluto. Elle constitue un cas Cyclos indépendant, utile pour vérifier que le contrat MLCFlux ne dépend pas des conventions Lokavaluto.
- **La Gonette** est cliente de Lokavaluto mais se trouve en cours de migration. Son environnement actuel est hybride et les données utilisées par MLCFlux proviennent encore notamment de Cyclos et d’Odoo. Elle ne constitue donc pas un cas de référence « full Lokavaluto ».
- **Le cas ComChain actuellement présent dans les fixtures est synthétique.** Il permet d’éprouver les concepts de comptes, états et remplacements, mais il ne constitue pas encore une validation sur les vues et conventions réelles d’une monnaie entièrement déployée sur l’infrastructure Lokavaluto.

En conséquence, les tests INPUT001 actuels valident la portabilité du **modèle de contrat**, mais ne doivent pas être présentés comme une validation complète de compatibilité Lokavaluto. Cette validation nécessitera soit un jeu de données réel représentatif, soit les vues SQL et conventions formellement garanties par Lokavaluto.

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
