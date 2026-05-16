# MLCFlux — Documentation des indicateurs, périmètres et formules

## Index

1. [Finalité analytique de MLCFlux](#1-finalité-analytique-de-mlcflux)
2. [Source des données](#2-source-des-données)
3. [Filtre de période](#3-filtre-de-période)
4. [Catégories d’acteurs](#4-catégories-dacteurs)
5. [Définition centrale : la circulation économique](#5-définition-centrale--la-circulation-économique)
6. [Indicateurs de synthèse — définitions et formules](#6-indicateurs-de-synthèse--définitions-et-formules)
7. [Graphiques de la vue de synthèse](#7-graphiques-de-la-vue-de-synthèse)
8. [Analyse des professionnels — principes de calcul](#8-analyse-des-professionnels--principes-de-calcul)
9. [Analyse territoriale — principes de calcul](#9-analyse-territoriale--principes-de-calcul)
10. [Analyse sectorielle — principes de calcul](#10-analyse-sectorielle--principes-de-calcul)
11. [Flux complémentaires à analyser séparément](#11-flux-complémentaires-à-analyser-séparément)
12. [Évolutions prévues de la vue “Info”](#12-évolutions-prévues-de-la-vue-info)
13. [Points restant à consolider après reconstruction de la base](#13-points-restant-à-consolider-après-reconstruction-de-la-base)
14. [Résumé de doctrine analytique](#14-résumé-de-doctrine-analytique)

---

## Objet de ce document

Ce document prépare la future **vue “Info” / “Méthodologie”** de MLCFlux. Il vise à expliquer clairement :

- ce que mesure l’outil ;
- quelles données sont prises en compte ;
- comment sont calculés les indicateurs ;
- ce qui relève de la **circulation économique de la monnaie dans le réseau** ;
- ce qui relève d’autres mouvements monétaires : émissions, reconversions, annulations, opérations techniques, etc.

Il s’agit d’un **document de travail évolutif**. Certaines sections seront consolidées après la reconstruction complète de la base de données et la reprise de l’audit analytique.

---

# 1. Finalité analytique de MLCFlux

MLCFlux n’a pas pour objet principal de comptabiliser indistinctement toutes les écritures enregistrées dans Cyclos. Son objectif central est d’analyser :

> **la circulation économique de la Gonette numérique dans le réseau d’acteurs.**

Autrement dit, MLCFlux cherche prioritairement à comprendre :

- comment la monnaie circule entre particuliers et professionnels ;
- quelle part de l’activité relève de la consommation des particuliers ;
- quelle part relève de la circulation interprofessionnelle ;
- quels territoires, secteurs et professionnels concentrent l’activité ;
- comment ces dynamiques évoluent dans le temps.

Cette orientation implique de distinguer soigneusement :

1. **les transactions de circulation économique**, qui constituent le cœur des analyses ;
2. **les mouvements d’entrée, de sortie ou de gestion du système monétaire**, qui peuvent faire l’objet d’analyses complémentaires mais ne doivent pas être confondus avec la circulation économique.

---

# 2. Source des données

Les données transactionnelles analysées par MLCFlux proviennent de l’API Cyclos de la Gonette.

Chaque transaction stockée dans la base MLCFlux contient notamment :

| Champ | Rôle |
|---|---|
| `transaction_number` | Identifiant fonctionnel unique de la transaction |
| `date` | Date et heure de la transaction |
| `group_label` | Type de compte de l’émetteur dans Cyclos |
| `from_label` | Acteur émetteur, après anonymisation / normalisation |
| `to_label` | Acteur destinataire, après anonymisation / normalisation |
| `amount` | Montant de la transaction |
| `type_label` | Libellé ou description de l’opération dans Cyclos |

Les transactions sont importées depuis Cyclos, anonymisées, puis stockées dans une base SQLite locale.

---

# 3. Filtre de période

L’ensemble des indicateurs et visualisations est calculé sur la **période sélectionnée** par l’utilisateur.

## 3.1. Principe général

Le filtre global permet de choisir :

- une date de début ;
- une date de fin.

Les données affichées correspondent uniquement aux transactions dont la date est comprise dans cette période.

## 3.2. Inclusion de la date de fin

Lorsqu’une date est choisie au format calendaire simple, par exemple :

```2026-04-21```

elle est interprétée comme un **jour civil français complet**.

Ainsi :

- `début = 2026-04-21`
- `fin = 2026-04-21`

signifie bien :

> toutes les transactions du 21 avril 2026, de 00h00 à 23h59:59, heure de Paris.

Cette précision est importante pour garantir des comparaisons temporelles rigoureuses.

---

# 4. Catégories d’acteurs

MLCFlux regroupe les acteurs en plusieurs grandes familles.

## 4.1. Professionnels — `P`

Les professionnels sont identifiés par un code Cyclos de type :

```P0008, P0300, P0752```

MLCFlux normalise leur affichage au format :

```P0008 - Nom du professionnel```

Ces acteurs représentent les commerces, associations, structures partenaires et autres acteurs professionnels du réseau.

## 4.2. Particuliers — `U`

Les particuliers sont pseudonymisés à l’import. Un particulier apparaît sous une forme telle que :

```U_Alice, U_Benoît, U_Deb```

Cette pseudonymisation permet :

- de suivre les comportements transactionnels d’un même compte dans le temps ;
- de préserver la confidentialité des utilisateurs ;
- de produire des analyses agrégées sans exposer d’identité individuelle.

## 4.3. Acteur masqué

Certains acteurs ne peuvent pas, à ce stade, être catégorisés de façon suffisamment fiable dans les familles `P` ou `U`.

Ils apparaissent temporairement comme :

```Acteur masqué```

Cette catégorie ne doit pas être interprétée comme un acteur unique réel. Elle peut regrouper plusieurs situations :

- compte technique ;
- compte institutionnel ou d’émission ;
- acteur dont l’affichage Cyclos ne permet pas encore une classification fiable ;
- cas particuliers restant à auditer.

## 4.4. Conversion

Certaines opérations sont associées à un acteur ou un libellé de conversion. Elles sont actuellement isolées sous la catégorie :

```Conversion```

Ces mouvements ne relèvent pas directement de la circulation économique entre acteurs du réseau.

---

# 5. Définition centrale : la circulation économique

## 5.1. Définition

Dans MLCFlux, la **circulation économique de la monnaie dans le réseau** désigne les transactions monétaires entre acteurs clairement identifiés comme :

- particuliers (`U`) ;
- professionnels (`P`).

Elle comprend donc les quatre familles de flux suivantes :

| Flux | Lecture économique |
|---|---|
| `U → P` | Dépense d’un particulier chez un professionnel |
| `P → P` | Circulation interprofessionnelle |
| `P → U` | Flux d’un professionnel vers un particulier : remboursement, salaire, indemnité, reversement… |
| `U → U` | Transfert entre particuliers |

## 5.2. Formule générale

La circulation économique peut être calculée en nombre de transactions et en volume monétaire.

### Nombre de transactions de circulation économique

```Nb circulation = Nb(U→P) + Nb(P→P) + Nb(P→U) + Nb(U→U)```

### Volume de circulation économique

``` Volume circulation = Volume(U→P) + Volume(P→P) + Volume(P→U) + Volume(U→U) ```

## 5.3. Ce qui n’est pas inclus dans la circulation économique

Ne sont pas inclus par défaut dans cette notion :

- les crédits automatiques mensuels ;
- les émissions de monnaie ;
- les conversions et reconversions ;
- les annulations ;
- les avoirs ;
- les écritures de correction ;
- les opérations impliquant des acteurs non catégorisés de manière fiable.

Ces flux peuvent être essentiels pour comprendre la vie monétaire du système, mais ils relèvent d’un autre niveau d’analyse.

---

# 6. Indicateurs de synthèse — définitions et formules

Cette section décrit les indicateurs destinés à apparaître dans la vue de synthèse.

## 6.1. Acteurs professionnels actifs

### Définition

Nombre de professionnels distincts ayant participé à au moins une transaction de circulation économique sur la période sélectionnée.

### Formule

``` Nb P actifs = nombre de labels distincts commençant par P impliqués dans les flux U→P, P→P, P→U ou U→U ```

En pratique, un professionnel est compté s’il apparaît au moins une fois :

- comme émetteur dans `P→P` ou `P→U` ;
- comme destinataire dans `U→P` ou `P→P`.

---

## 6.2. Particuliers actifs

### Définition

Nombre de particuliers pseudonymisés distincts ayant participé à au moins une transaction de circulation économique sur la période sélectionnée.

### Formule

``` Nb U actifs = nombre de labels distincts commençant par U_ impliqués dans les flux U→P, P→U ou U→U ```

Un particulier est compté s’il apparaît au moins une fois :

- comme émetteur dans `U→P` ou `U→U` ;
- comme destinataire dans `P→U` ou `U→U`.

---

## 6.3. Acteurs actifs dans la circulation

### Définition

Nombre total d’acteurs distincts, particuliers et professionnels, ayant participé à la circulation économique sur la période.

### Formule

``` Acteurs actifs = P actifs + U actifs ```

Cette mesure exclut les acteurs non catégorisés, les comptes techniques et les opérations hors circulation économique.

---

## 6.4. Nombre total de transactions de circulation économique

### Définition

Nombre total de transactions relevant de la circulation économique entre acteurs P/U.

### Formule

```Nb transactions de circulation = Nb(U→P) + Nb(P→P) + Nb(P→U) + Nb(U→U) ```

---

## 6.5. Volume total de circulation économique

### Définition

Somme des montants de toutes les transactions relevant de la circulation économique entre acteurs P/U.

### Formule

``` Volume de circulation = Somme(U→P) + Somme(P→P) + Somme(P→U) + Somme(U→U) ```

---

## 6.6. Nombre moyen de transactions par jour

### Définition recommandée

Moyenne quotidienne des transactions de circulation économique sur la période sélectionnée.

### Formule

``` Moyenne tx/jour = Nombre total de transactions de circulation / Nombre de jours calendaires dans la période ```

### Point méthodologique

Le dénominateur doit correspondre au **nombre de jours calendaires couverts par le filtre**, et non au nombre de jours effectivement actifs.

Ainsi, pour une période allant du 1er janvier au 31 janvier :

``` Nombre de jours = 31 ```

même si aucune transaction n’a eu lieu certains jours.

---

## 6.7. Montant moyen U→P

### Définition

Montant moyen des paiements des particuliers vers les professionnels.

### Formule

``` Montant moyen U→P = Somme des montants U→P / Nombre de transactions U→P ```

### Interprétation

Cet indicateur peut être lu comme un **panier moyen de dépense des particuliers chez les professionnels**, sous réserve de conserver une définition stricte des flux `U→P`.

---

## 6.8. Montant moyen P→P

### Définition

Montant moyen des transactions entre professionnels.

### Formule

``` Montant moyen P→P = Somme des montants P→P / Nombre de transactions P→P ```

### Interprétation

Cet indicateur renseigne sur l’intensité moyenne des échanges interprofessionnels en Gonette numérique.

---

## 6.9. Montant moyen P→U

### Définition

Montant moyen des transactions émises par des professionnels vers des particuliers.

### Formule

``` Montant moyen P→U = Somme des montants P→U / Nombre de transactions P→U ```

### Interprétation

Ce flux est hétérogène. Il peut notamment comprendre :

- remboursements ;
- versements assimilables à des salaires ou indemnités ;
- reversements ponctuels.

L’indicateur est utile, mais son interprétation doit rester plus prudente que celle du panier moyen `U→P`.

---

## 6.10. Montant moyen U→U

### Définition

Montant moyen des transactions entre particuliers.

### Formule

``` Montant moyen U→U = Somme des montants U→U / Nombre de transactions U→U ```

---

# 7. Graphiques de la vue de synthèse



## 7.1. transactions par jour

### Définition recommandée

Nombre et volume quotidien de transactions de circulation économique sur la période.
## Lecture des graphiques quotidiens : nombre ou volume

Le graphique quotidien peut être affiché selon deux lectures complémentaires :

| Mode | Ce qui est représenté |
|---|---|
| **Nombre** | Le nombre de transactions réalisées chaque jour |
| **Volume** | Le montant total des transactions réalisées chaque jour |

Cette distinction est importante :

- un pic en **nombre** peut correspondre à beaucoup de petites opérations ;
- un pic en **volume** peut correspondre à quelques opérations de montant élevé ;
- les conversions automatiques mensuelles apparaissent très nettement dans ces deux lectures, mais ne doivent pas être confondues avec l’activité de paiement ordinaire du réseau.

### Formule

Pour chaque date `d` :

``` Nb paiements au jour d = Nb(U→P, d) + Nb(P→P, d) + Nb(P→U, d) + Nb(U→U, d) ```

``` Nb conversions au jour d = Nb(A→U, d) + Nb(A→P, d) Nb reconversions au jour d = Nb(P→A, d) ```

``` Nb annulations / régularisations au jour d = Nb(U→A, d) + Nb(A→A, d) + cas techniques résiduels ```

### Remarque

Le graphe actuel doit être recalibré pour éviter de compter les émissions, reconversions ou opérations techniques dans l’activité économique courante.

---

## 7.2. Montant moyen hebdomadaire des transactions

### Définition recommandée

Montant moyen des transactions de circulation économique, agrégé par semaine.

### Formule

Pour chaque semaine `s` :

``` Montant moyen semaine s = Volume de circulation économique de la semaine s / Nombre de transactions de circulation de la semaine```

---

## 7.3. Répartition des transactions par heure

### Définition recommandée

Nombre de transactions de circulation économique réparties selon l’heure de réalisation.

### Formule

Pour chaque heure `h` :

``` Nb tx à l’heure h = nombre de transactions de circulation dont l’heure = h ```

### Interprétation

Ce graphique permet d’identifier les rythmes d’usage de la monnaie au cours de la journée.

---

## 7.4. Répartition des transactions par jour de semaine

### Définition recommandée

Nombre de transactions de circulation économique réparties selon le jour de la semaine.

### Formule

Pour chaque jour `j` :

``` Nb tx le jour j = nombre de transactions de circulation dont weekday = j ```

---

## 7.5. Volume cumulé de circulation économique

### Définition recommandée

Somme cumulée, jour après jour, des montants correspondant uniquement à la circulation économique entre acteurs P/U.

### Formule

Pour chaque jour `d` :

``` Volume cumulé au jour d = Somme des volumes de circulation économique de tous les jours ≤ d ```

### Important

Le graphe historique “volume cumulé des transactions” ne doit pas mélanger :

- circulation économique ;
- émissions ;
- reconversions ;
- annulations ;
- opérations techniques.

Une évolution possible de MLCFlux consistera à proposer plusieurs courbes distinctes :

| Courbe | Contenu |
|---|---|
| Circulation économique | U→P + P→P + P→U + U→U |
| Émissions / crédits | À définir précisément |
| Reconversions / sorties | À définir précisément |
| Corrections / annulations | À définir si utile |

---

# 8. Analyse des professionnels — principes de calcul

Cette section sera consolidée plus tard, mais les grands principes peuvent déjà être posés.

## 8.1. Volume reçu par un professionnel

### Définition

Somme des montants reçus par un professionnel sur la période.

### Périmètre à préciser

Deux niveaux sont possibles :

1. **volume reçu dans la circulation économique** :
   - U→P ;
   - P→P.
2. **volume reçu total** incluant certains flux hors circulation, si l’interface souhaite les documenter séparément.

Pour le classement principal, la définition recommandée est :

``` Volume reçu économique d’un P = Somme(U→P vers ce P) + Somme(P→P vers ce P) ```

---

## 8.2. Volume émis par un professionnel

### Définition recommandée

Somme des montants envoyés par ce professionnel vers d’autres acteurs P/U dans la circulation économique.

``` Volume émis économique d’un P = Somme(P→P depuis ce P) + Somme(P→U depuis ce P) ```

---

## 8.3. Taux de réutilisation / réemploi

### Définition possible

Indicateur mesurant la part des Gonettes reçues par un professionnel qui sont réinjectées vers d’autres acteurs du réseau.

### Formule pressentie

``` Taux de réutilisation = Volume émis économique / Volume reçu économique ```

### Point d’attention

Cette formule doit être consolidée avec soin :

- selon que l’on inclut ou non certains flux de reconversion ;
- selon l’objectif précis de l’indicateur ;
- selon le traitement souhaité pour les professionnels qui émettent plus qu’ils ne reçoivent sur la période.

Cette partie fera l’objet d’un audit analytique dédié.

---

# 9. Analyse territoriale — principes de calcul

La vue territoriale regroupe les activités monétaires par code postal, à partir des données enrichies des professionnels.

## 9.1. Professionnels territorialisés

Nombre de professionnels pour lesquels une information territoriale exploitable est disponible.

## 9.2. Volume reçu territorialisé

Somme des volumes reçus par les professionnels rattachés à un territoire donné.

### Définition recommandée

Pour chaque territoire `t` :

``` Volume reçu t = somme des flux économiques reçus par les professionnels situés dans t ```

## 9.3. Volume émis territorialisé

Somme des volumes économiques réémis par les professionnels situés dans un territoire donné.

## 9.4. Taux de réutilisation territorial

### Formule pressentie

``` Taux de réutilisation territorial = Volume émis économique des P du territoire / Volume reçu économique des P du territoire ```

Cette formule devra être revue lors de l’audit spécifique des agrégations territoriales.

---

# 10. Analyse sectorielle — principes de calcul

La vue sectorielle regroupe les activités monétaires par secteur d’activité, à partir de l’enrichissement Odoo des professionnels.

## 10.1. Professionnels sectorisés

Nombre de professionnels auxquels un secteur a pu être associé.

## 10.2. Volume reçu par secteur

### Définition recommandée

``` Volume reçu secteur s = somme des flux économiques reçus par les professionnels appartenant au secteur s ```

## 10.3. Volume émis par secteur

### Définition recommandée

``` Volume émis secteur s = somme des flux économiques émis par les professionnels appartenant au secteur s ```

## 10.4. Taux de réutilisation sectoriel

### Formule pressentie

``` Taux de réutilisation secteur s = Volume émis économique du secteur s / Volume reçu économique du secteur s ```

Cette formule devra être vérifiée en détail lors de l’audit sectoriel.

---

# 11. Flux complémentaires à analyser séparément

MLCFlux pourra, dans un second niveau d’analyse, suivre des mouvements qui ne relèvent pas directement de la circulation économique mais sont essentiels pour comprendre la dynamique monétaire globale.

## 11.1. Émissions / crédits

Exemples :

- crédits automatiques mensuels ;
- crédits d’indemnité ;
- crédits particuliers ou professionnels.

Ces flux alimentent les comptes en Gonettes numériques mais ne constituent pas en eux-mêmes une circulation économique entre acteurs du réseau.

## 11.2. Reconversions / sorties

Exemples :

- conversion en euros ;
- demandes de reconversion ;
- autres sorties du circuit.

Ces flux renseignent sur la capacité de la monnaie à rester en circulation ou à sortir du réseau.

## 11.3. Annulations et corrections

Exemples :

- annulations de crédits automatiques ;
- avoirs ;
- corrections d’écriture.

Ces mouvements doivent être isolés pour ne pas perturber l’interprétation des indicateurs principaux.

---

# 12. Évolutions prévues de la vue “Info”

La future vue pourra prendre plusieurs formes complémentaires.

## 12.1. Une page méthodologique générale

Avec :

- le périmètre de MLCFlux ;
- la définition de la circulation économique ;
- la distinction entre circulation, émission et reconversion ;
- les principes d’anonymisation.

## 12.2. Des helpers contextuels dans l’interface

Par exemple sous forme de :

- icônes `?` près des indicateurs ;
- infobulles ;
- petits panneaux dépliables ;
- liens “Comment est calculé cet indicateur ?”.

## 12.3. Une documentation détaillée par indicateur

Chaque métrique pourrait afficher :

- son nom ;
- sa définition ;
- sa formule ;
- ses limites éventuelles ;
- les flux inclus / exclus.

---

# 13. Points restant à consolider après reconstruction de la base

Les éléments suivants doivent être revus une fois la base reconstruite avec l’anonymisation corrigée :

1. répartition exacte des flux après récupération des P et U auparavant masqués ;
2. volume total de circulation économique ;
3. nombre exact de P/U actifs sur l’historique complet ;
4. périmètre définitif des graphes de synthèse ;
5. typologie propre des émissions, reconversions et corrections ;
6. formule définitive du taux de réutilisation ;
7. adéquation des vues territoriales et sectorielles avec la définition de circulation économique.

---

# 14. Résumé de doctrine analytique

La doctrine que MLCFlux doit suivre peut se résumer ainsi :

> **Les indicateurs principaux mesurent la circulation économique de la Gonette numérique entre acteurs identifiés du réseau : particuliers et professionnels.**

> **Les émissions, reconversions, annulations et opérations techniques sont importantes, mais elles doivent être analysées séparément et ne pas brouiller la lecture de la circulation économique.**

> **Chaque indicateur affiché doit pouvoir être expliqué par une définition simple, une formule explicite et un périmètre clairement assumé.**


