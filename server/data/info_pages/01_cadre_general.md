# MLCFlux — Méthodologie, périmètres d’analyse et lecture des indicateurs

## Introduction

MLCFlux est un outil d’analyse de la **Gonette numérique**. Il ne se contente pas de compter des transactions : il cherche à comprendre **comment la monnaie circule dans le réseau**, comment elle est reçue, réemployée, concentrée, conservée ou reconvertie, et comment ces dynamiques s’organisent entre particuliers, professionnels, secteurs d’activité et territoires.

L’outil repose sur une idée simple : **toutes les écritures monétaires n’ont pas le même sens économique**.

Un paiement d’un particulier chez un professionnel, une alimentation de compte, une reconversion, un mouvement entre comptes techniques ou l’évolution d’un fonds de garantie ne décrivent pas le même phénomène. Les additionner sans distinction produirait des chiffres difficiles à interpréter.

MLCFlux distingue donc plusieurs registres d’analyse :

1. **l’activité économique**, c’est-à-dire la circulation de la Gonette entre acteurs ordinaires du réseau ;
2. **les alimentations et sorties du circuit**, qui décrivent les entrées et sorties de monnaie numérique ;
3. **les opérations associatives ou techniques**, nécessaires au fonctionnement du système mais distinctes de l’activité économique courante ;
4. **la masse monétaire et les garanties**, qui relèvent d’une lecture comptable des stocks et non d’une lecture transactionnelle des flux ;
5. **la détention et le réemploi**, qui permettent d’interroger la capacité de la monnaie à rester vivante dans le réseau.

Cette page expose les choix méthodologiques qui structurent MLCFlux. Elle précise ce que mesurent les indicateurs, ce qu’ils excluent, et la manière dont ils doivent être lus.

---

# 1. Ce que MLCFlux cherche à observer

MLCFlux vise à rendre visibles plusieurs dimensions de la vie économique de la Gonette numérique.

L’outil permet notamment d’étudier :

- le volume et le nombre de transactions réalisées en Gonette numérique ;
- les paiements des particuliers vers les professionnels ;
- les échanges interprofessionnels ;
- les flux de redistribution des professionnels vers les particuliers ;
- les transferts entre particuliers ;
- les alimentations des comptes et les sorties du circuit ;
- la place des opérations associatives et techniques ;
- l’évolution de la masse monétaire et de ses garanties ;
- la détention de Gonettes par les particuliers et les professionnels ;
- la concentration ou la dispersion de l’activité ;
- les dynamiques territoriales et sectorielles ;
- la place spécifique de certains dispositifs ponctuels dans l’activité observée.

MLCFlux n’a donc pas pour objet de produire une simple comptabilité exhaustive de toutes les écritures présentes dans les systèmes sources. Il cherche plutôt à **organiser les données en phénomènes interprétables**.

---

# 2. Trois réalités à ne pas confondre : flux, stocks et opérations de gestion

La méthodologie de MLCFlux repose d’abord sur une distinction fondamentale entre trois types de grandeurs.

## 2.1. Les flux

Un **flux** est un mouvement de monnaie observé pendant une période.

Exemples :

- un particulier paie un professionnel ;
- un professionnel règle un autre professionnel ;
- un compte est alimenté en Gonettes ;
- un professionnel reconvertit des Gonettes ;
- une correction technique est enregistrée.

Les flux répondent à la question :

> **qu’est-ce qui a bougé pendant la période étudiée ?**

Ils sont principalement analysés à partir des **transactions Cyclos**.

---

## 2.2. Les stocks

Un **stock** désigne une quantité de monnaie observée à une date donnée, ou moyennée sur une période.

Exemples :

- masse numérique ;
- masse papier ;
- fonds de garantie ;
- stock positif détenu par les particuliers ;
- stock positif détenu par les professionnels.

Les stocks répondent à la question :

> **où se trouve la monnaie, ou quelle quantité de monnaie existe à une date donnée ?**

Ils sont analysés à partir :

- des **soldes Cyclos**, pour la détention de Gonettes numériques par type d’acteur ;
- des **données comptables Odoo**, pour les masses monétaires et garanties.

---

## 2.3. Les opérations de gestion

Certaines transactions sont nécessaires au fonctionnement de la Gonette numérique, mais ne correspondent pas directement à une circulation économique entre usagers ordinaires du réseau.

Exemples :

- alimentations ;
- reconversions ;
- opérations impliquant les comptes opérateurs ;
- mouvements de régularisation ;
- opérations entre comptes techniques.

Ces opérations doivent rester visibles, car elles participent à la compréhension du système monétaire. Mais elles doivent être **séparées** de l’analyse de l’activité économique proprement dite.

---

## 2.4. Pourquoi cette distinction est indispensable

Une monnaie peut :

- avoir une **masse importante** mais circuler faiblement ;
- produire beaucoup de **transactions** sans que sa masse augmente ;
- connaître beaucoup d’**alimentations** mais aussi beaucoup de **sorties** ;
- être fortement détenue par certains acteurs sans être réemployée rapidement.

C’est précisément pour éviter ces confusions que MLCFlux distingue les flux, les stocks et les opérations de gestion.

---

# 3. Sources de données utilisées

MLCFlux croise plusieurs sources de données, chacune correspondant à une dimension différente de l’analyse.

## 3.1. Transactions Cyclos

Les transactions numériques analysées par MLCFlux proviennent de l’API Cyclos de la Gonette.

Elles sont importées, normalisées, pseudonymisées puis stockées dans la base analytique locale de l’application.

Parmi les informations utiles à l’analyse figurent notamment :

| Élément | Rôle méthodologique |
|---|---|
| Identifiant technique Cyclos | Garantir l’unicité des opérations importées |
| Numéro fonctionnel de transaction, lorsqu’il existe | Faciliter le suivi et les rapprochements |
| Date et heure | Situer les flux dans le temps |
| Acteur émetteur | Déterminer l’origine du flux |
| Acteur destinataire | Déterminer sa destination |
| Montant | Calculer les volumes |
| Type ou libellé d’opération | Documenter certains cas, avec prudence |

### Principe de classification

MLCFlux privilégie les **règles structurelles** pour classer les flux :

- famille de l’émetteur ;
- famille du destinataire ;
- présence éventuelle d’un compte technique ;
- présence éventuelle d’un compte opérateur ;
- sens économique de l’opération.

Les libellés textuels Cyclos peuvent aider à interpréter certains cas, mais ils ne constituent pas à eux seuls la base de la typologie analytique.

---

## 3.2. Soldes Cyclos

Les historiques de soldes permettent d’analyser la **détention** de Gonettes numériques.

Ils servent notamment à étudier :

- le stock positif détenu par les particuliers ;
- le stock positif détenu par les professionnels ;
- la concentration de la monnaie ;
- la dormance ou l’absence d’activité récente de certains comptes ;
- la mobilisation effective des stocks vers l’activité économique.

Les soldes ne mesurent pas l’intensité des paiements. Ils renseignent une **position de monnaie détenue**.

---

## 3.3. Données comptables Odoo

Les données comptables issues d’Odoo sont utilisées pour documenter :

- la masse monétaire numérique ;
- la masse monétaire papier ;
- la masse monétaire totale ;
- le fonds de garantie numérique ;
- le fonds de garantie papier ;
- les éventuels écarts entre masses monétaires et garanties.

### Point méthodologique important

Les valeurs annuelles présentées dans MLCFlux correspondent à un **stock cumulé observé à une date de clôture**, et non à la somme des opérations enregistrées pendant l’année.

Autrement dit, une donnée affichée pour une année donnée doit être lue comme :

> **la situation comptable à la fin de cette année**,

et non comme :

> **le total des mouvements survenus pendant cette année**.

---

## 3.4. Enrichissement des professionnels

Les analyses territoriales et sectorielles s’appuient sur des informations complémentaires associées aux professionnels :

- nom d’affichage ;
- secteur ou secteurs d’activité ;
- adresse ;
- code postal ;
- commune ;
- coordonnées géographiques lorsqu’elles sont disponibles.

Ces données permettent de produire :

- des cartes ;
- des regroupements par territoire ;
- des regroupements par secteur ;
- des fiches professionnelles plus lisibles.

---

# 4. Période analysée et règles temporelles

## 4.1. Le filtre global de période

Les indicateurs transactionnels sont calculés sur la **période sélectionnée** par l’utilisateur.

Cette période est définie par :

- une date de début ;
- une date de fin.

Chaque graphique, chaque volume et chaque moyenne doit donc être interprété dans le cadre de cette fenêtre d’observation.

---

## 4.2. Inclusion de la date de fin

Lorsqu’une date est choisie au format calendaire simple, elle est interprétée comme un **jour civil complet**.

Exemple :

```Début = 2026-04-21 Fin = 2026-04-21```

signifie :

> toutes les transactions du 21 avril 2026, de 00:00:00 à 23:59:59, heure de Paris.

Cette règle évite de perdre les transactions intervenues pendant la journée de fin de période.

---

## 4.3. Des sources qui n’ont pas toujours la même profondeur historique

Les différentes sources mobilisées par MLCFlux ne couvrent pas nécessairement :

- les mêmes périodes ;
- les mêmes niveaux de détail ;
- les mêmes fréquences de mesure.

Les transactions sont suivies opération par opération. Les soldes peuvent être reconstruits à une granularité quotidienne. Les données comptables sont généralement interprétées comme des stocks de fin de période.

Lorsqu’un indicateur croise plusieurs sources, il doit être lu sur le **périmètre réellement commun** entre ces séries.

---
