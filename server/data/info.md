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

```text
Début = 2026-04-21
Fin   = 2026-04-21
```

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

# 5. Catégories d’acteurs et conventions de lecture

MLCFlux repose sur une typologie d’acteurs explicite. Cette typologie permet de classifier les flux sans confondre des réalités différentes.

## 5.1. Professionnels — `P`

Les professionnels sont les acteurs économiques du réseau : commerces, associations, structures partenaires et autres entités recevant ou émettant des Gonettes dans le cadre de leur activité.

Ils sont identifiés par un code de type :

```text
P0008
P0300
P0752
```

Lorsque l’information est disponible, MLCFlux les affiche sous une forme plus lisible :

```P0677 — Graines Électroniques```

---

## 5.2. Particuliers ordinaires — `U_*`

Les particuliers sont pseudonymisés lors de l’import des données.

Ils apparaissent sous une forme de type :

```text
U_Alice
U_Benoît
U_Deb
```

Cette pseudonymisation permet de :

- suivre l’activité d’un même compte dans le temps ;
- conserver une lisibilité suffisante dans les analyses ;
- préserver la confidentialité des personnes concernées.

MLCFlux ne stocke pas, dans sa base analytique finale, les identifiants bruts nécessaires à une réidentification simple des particuliers.

---

## 5.3. Particuliers de dispositif — `UD_*`

Certains comptes particuliers sont associés à des dispositifs spécifiques, ponctuels ou expérimentaux. Ils sont distingués par un préfixe particulier :

```text
UD_Ana
UD_Louis
UD_Maya
```

Ces comptes restent des **particuliers** du point de vue de l’analyse économique. Ils sont donc inclus dans la famille `U` lorsqu’ils participent à des paiements ordinaires.

Ils sont néanmoins distingués parce qu’un dispositif spécifique peut peser fortement sur :

- le nombre de transactions ;
- le volume de paiements ;
- l’activité d’un ou plusieurs professionnels ;
- la lecture d’un mois ou d’une période courte.

Les isoler ne signifie donc pas les exclure. Cela permet de **contextualiser** correctement certaines dynamiques.

---

## 5.4. Comptes techniques — `T_*`

Les comptes techniques correspondent à des fonctions particulières du système monétaire.

Exemples :

```text
T_Émission
T_Conversion
```

Ils servent à identifier des opérations telles que :

- les alimentations ;
- certaines sorties du circuit ;
- des mouvements de régularisation ;
- d’autres opérations non assimilables à un paiement ordinaire entre usagers.

---

## 5.5. Comptes opérateurs — `P0000` et `P9999`

Deux comptes professionnels ont un rôle méthodologique particulier :

```text
P0000
P9999
```

Ils sont conservés dans les données, car ils sont utiles au suivi du fonctionnement global de la Gonette. Mais ils ne doivent pas être traités comme des professionnels ordinaires dans les indicateurs d’activité économique.

### Doctrine retenue

- ils sont **exclus** des KPI qui cherchent à décrire les professionnels du réseau ;
- ils sont **analysés séparément** dans les opérations associatives ou techniques ;
- ils peuvent être réintroduits dans certaines lectures de stock ou de rapprochement lorsque cela est nécessaire.

---

## 5.6. Conventions utilisées dans les formules

Dans la suite du document :

| Notation | Désigne |
|---|---|
| `U` | Les particuliers ordinaires et, sauf mention contraire, les particuliers de dispositif `UD_*` |
| `UD` | Les particuliers de dispositif lorsqu’ils sont isolés |
| `P` | Les professionnels ordinaires du réseau, hors comptes opérateurs `P0000` et `P9999`, sauf précision |
| `T` | Les comptes techniques |
| `O` | Les comptes opérateurs `P0000` et `P9999`, lorsque cette notation est utilisée pour simplifier une explication |

---

# 6. Définition centrale : l’activité économique

## 6.1. Principe

L’**activité économique** correspond aux mouvements de Gonette numérique entre les acteurs ordinaires du réseau : particuliers et professionnels.

Elle vise à mesurer la circulation effectivement réalisée à travers des paiements ou transferts entre usagers, sans la confondre avec les opérations d’entrée, de sortie ou de gestion du système.

---

## 6.2. Les quatre familles de flux incluses

| Flux | Lecture économique |
|---|---|
| `U → P` | Paiement d’un particulier vers un professionnel |
| `P → P` | Échange interprofessionnel |
| `P → U` | Paiement, remboursement, indemnité ou autre reversement d’un professionnel vers un particulier |
| `U → U` | Transfert entre particuliers |

---

## 6.3. Formules générales

### Nombre d’opérations économiques

```text
Nb opérations économiques
= Nb(U→P) + Nb(P→P) + Nb(P→U) + Nb(U→U)
```

### Volume d’activité économique

```text
Volume d’activité économique
= Vol(U→P) + Vol(P→P) + Vol(P→U) + Vol(U→U)
```

---

## 6.4. Ce qui n’est pas inclus dans l’activité économique

L’activité économique exclut par défaut :

- les alimentations ;
- les reconversions ou sorties de circuit ;
- les opérations impliquant directement les comptes techniques `T_*` ;
- les opérations mettant en jeu les comptes opérateurs `P0000` / `P9999` lorsqu’elles ne traduisent pas une transaction ordinaire du réseau ;
- les régularisations et corrections.

Ces flux sont conservés et analysés, mais dans d’autres onglets.

---

## 6.5. Une attention particulière pour les flux `P → U`

Les flux `P → U` sont inclus dans l’activité économique, car ils matérialisent un transfert monétaire entre acteurs ordinaires du réseau.

Leur interprétation est toutefois plus composite que celle des paiements `U → P`. Ils peuvent correspondre, selon les cas, à :

- des remboursements ;
- des reversements ;
- des indemnités ;
- des salaires ;
- d’autres paiements ponctuels.

Ils doivent donc être lus comme une famille économique réelle, mais plus hétérogène.

---

# 7. Statistiques globales

La vue **Statistiques globales** repose sur quatre onglets complémentaires. Chacun répond à une question différente.

| Onglet | Question principale |
|---|---|
| Activité économique | Que circule-t-il entre particuliers et professionnels ? |
| Alimentations / sorties du circuit | Qu’est-ce qui entre et sort du circuit numérique ? |
| Opérations associatives / techniques | Quels mouvements relèvent du fonctionnement interne ou de traitements spécifiques ? |
| Masse monétaire & garanties | Quel est l’état comptable des stocks monétaires et de leur couverture ? |

---

## 7.1. Onglet « Activité économique »

Cet onglet mesure le cœur de la circulation en Gonette numérique entre les acteurs ordinaires du réseau.

### 7.1.1. Professionnels actifs

Un professionnel actif est un professionnel distinct impliqué dans au moins une opération économique pendant la période étudiée.

```text
Nb professionnels actifs
= nombre de P distincts apparaissant dans les flux U→P, P→P ou P→U
```

---

### 7.1.2. Particuliers actifs

Un particulier actif est un particulier distinct impliqué dans au moins une opération économique pendant la période étudiée.

```text
Nb particuliers actifs
= nombre de U distincts apparaissant dans les flux U→P, P→U ou U→U
```

---

### 7.1.3. Acteurs actifs dans la circulation

```Acteurs actifs = professionnels actifs + particuliers actifs```

---

### 7.1.4. Nombre total d’opérations économiques

```text
Nb opérations économiques
= Nb(U→P) + Nb(P→P) + Nb(P→U) + Nb(U→U)
```

---

### 7.1.5. Volume total d’activité économique

```text
Volume économique
= Vol(U→P) + Vol(P→P) + Vol(P→U) + Vol(U→U)
```

---

### 7.1.6. Nombre moyen de transactions par jour

```text
Moyenne transactions / jour
= nombre total d’opérations économiques
  / nombre de jours calendaires couverts par la période
```

Le dénominateur correspond aux jours calendaires de la période, qu’il y ait eu ou non des transactions chaque jour.

---

### 7.1.7. Montants moyens par type de flux

#### Montant moyen `U → P`

```text
Montant moyen U→P
= Vol(U→P) / Nb(U→P)
```

Cet indicateur peut être lu comme un **panier moyen de paiement des particuliers vers les professionnels**.

---

#### Montant moyen `P → P`

```text
Montant moyen P→P
= Vol(P→P) / Nb(P→P)
```

Il mesure l’intensité moyenne des échanges interprofessionnels.

---

#### Montant moyen `P → U`

```text
Montant moyen P→U
= Vol(P→U) / Nb(P→U)
```

Il renseigne des flux sortants vers les particuliers, à interpréter avec prudence en raison de leur diversité.

---

#### Montant moyen `U → U`

```text
Montant moyen U→U
= Vol(U→U) / Nb(U→U)
```

---

### 7.1.8. Graphiques quotidiens — lecture en nombre ou en volume

Les graphiques quotidiens peuvent être affichés selon deux modes :

| Mode | Ce qui est représenté |
|---|---|
| Nombre | Le nombre d’opérations réalisées chaque jour |
| Volume | Le montant total des opérations réalisées chaque jour |

#### Nombre de paiements au jour `d`

```text
Nb paiements au jour d
= Nb(U→P,d) + Nb(P→P,d) + Nb(P→U,d) + Nb(U→U,d)
```

#### Volume de paiements au jour `d`

```text
Vol paiements au jour d
= Vol(U→P,d) + Vol(P→P,d) + Vol(P→U,d) + Vol(U→U,d)
```

Cette double lecture permet de distinguer :

- une journée comportant beaucoup de petites opérations ;
- une journée comportant peu d’opérations mais des montants importants.

---

### 7.1.9. Montant moyen hebdomadaire

Pour une semaine `s` :

```text
Montant moyen semaine s
= volume économique de la semaine s
  / nombre d’opérations économiques de la semaine s
```

---

### 7.1.10. Répartition par heure

Ce graphique montre le nombre d’opérations économiques réalisées selon l’heure de la journée.

```text
Nb transactions à l’heure h
= nombre d’opérations économiques dont l’heure = h
```

Il permet de repérer les rythmes quotidiens d’usage.

---

### 7.1.11. Répartition par jour de semaine

Ce graphique montre le nombre d’opérations économiques selon le jour de la semaine.

```text
Nb transactions le jour j
= nombre d’opérations économiques réalisées ce jour-là
```

---

### 7.1.12. Volume cumulé d’activité économique

Pour un jour `d` :

```text
Volume cumulé au jour d
= somme des volumes économiques de tous les jours ≤ d
```

---

### 7.1.13. Visibilité spécifique des comptes `UD_*`

Lorsqu’un dispositif spécifique représente une part significative de l’activité, MLCFlux peut faire apparaître un encadré dédié aux comptes `UD_*`.

Cet encadré permet notamment de documenter :

- le nombre d’opérations concernées ;
- leur volume ;
- leur poids dans l’activité économique de la période ;
- la part relevant d’un phénomène ponctuel ou fortement concentré.

Cette lecture évite d’attribuer à une dynamique structurelle ce qui peut relever d’un dispositif localisé dans le temps.

---

## 7.2. Onglet « Alimentations / sorties du circuit »

Cet onglet observe les flux qui font entrer ou sortir des Gonettes numériques du circuit.

Il ne mesure pas directement une activité de paiement, mais la dynamique d’approvisionnement et de fuite potentielle du circuit.

---

### 7.2.1. Alimentations

Les alimentations désignent les entrées de Gonettes numériques vers des comptes ordinaires.

```text
Alimentations
= T→U + T→P
```

Elles peuvent bénéficier :

- à des particuliers ;
- à des professionnels.

Une alimentation accroît la capacité d’usage d’un acteur, mais elle ne constitue pas encore en elle-même une transaction économique entre acteurs du réseau.

---

### 7.2.2. Sorties du circuit

Les sorties correspondent principalement aux flux de reconversion ou de retrait depuis des comptes professionnels vers un compte technique.

```text
Sorties du circuit
= P→T
```

Elles indiquent qu’une partie des Gonettes quitte la dynamique de circulation numérique étudiée.

---

### 7.2.3. Écart net entre alimentations et sorties

```text
Écart net alimentations - sorties
= Vol(alimentations) - Vol(sorties)
```

### Important

Cet indicateur est un **solde de flux sur la période**.

Il ne doit pas être confondu avec :

- une masse monétaire ;
- un stock présent dans les comptes ;
- une mesure complète de la monnaie disponible.

---

### 7.2.4. Lecture des graphiques

Les graphiques de cet onglet peuvent notamment montrer :

- l’évolution mensuelle des alimentations ;
- l’évolution mensuelle des sorties ;
- le solde net de période ;
- la répartition des alimentations selon leurs destinataires ;
- la dynamique cumulée des entrées et sorties.

---

## 7.3. Onglet « Opérations associatives / techniques »

Cet onglet regroupe les flux qui doivent rester visibles pour comprendre le fonctionnement réel du système, mais qui ne relèvent pas du cœur de l’activité économique entre usagers ordinaires.

Il s’agit d’un espace de **transparence analytique** : MLCFlux ne masque pas ces mouvements, mais les présente dans une catégorie distincte afin d’éviter toute confusion.

---

### 7.3.1. Flux impliquant les comptes opérateurs

Les comptes opérateurs `P0000` et `P9999` peuvent apparaître dans plusieurs familles de mouvements :

- professionnel vers compte opérateur ;
- compte opérateur vers professionnel ;
- particulier vers compte opérateur ;
- compte opérateur vers particulier ;
- flux entre comptes opérateurs.

Ces mouvements ont leur importance pour comprendre certains circuits internes, mais ne doivent pas être additionnés aux paiements économiques ordinaires.

---

### 7.3.2. Flux impliquant les comptes techniques

Certains mouvements concernent directement les comptes `T_*`.

Selon les cas, ils peuvent renvoyer à :

- des opérations de correction ;
- des écritures particulières ;
- des traitements de régularisation ;
- des interactions entre technique et opérateur.

Leur présentation séparée permet de conserver une analyse complète sans brouiller les indicateurs centraux.

---

### 7.3.3. Comment lire cet onglet

Cet onglet ne signale pas des erreurs. Il permet de rappeler qu’un système monétaire réel comprend aussi :

- des fonctions de gestion ;
- des fonctions d’émission ;
- des fonctions de correction ;
- des comptes dédiés au pilotage opérationnel.

La question analytique n’est donc pas :

> « Pourquoi ces transactions existent-elles ? »

mais plutôt :

> **« Comment les distinguer de l’activité économique afin de ne pas en fausser la lecture ? »**

---

## 7.4. Onglet « Masse monétaire & garanties »

Cet onglet change de registre. Il ne décrit plus des transactions individuelles, mais des **stocks comptables**.

Il permet d’observer l’état général de la structure monétaire de la Gonette.

---

### 7.4.1. Masse monétaire numérique

La masse numérique correspond au stock de Gonettes numériques en circulation tel qu’il est établi à partir des données comptables.

---

### 7.4.2. Masse monétaire papier

La masse papier correspond au stock de Gonettes papier en circulation.

---

### 7.4.3. Masse monétaire totale

```text
Masse totale
= masse numérique + masse papier
```

---

### 7.4.4. Fonds de garantie

Les fonds de garantie représentent les contreparties en euros associées aux masses de Gonettes en circulation.

MLCFlux distingue :

- fonds de garantie numérique ;
- fonds de garantie papier.

---

### 7.4.5. Écarts entre masse et garantie

```text
Écart numérique
= fonds de garantie numérique - masse numérique
```

```text
Écart papier
= fonds de garantie papier - masse papier
```

Ces écarts doivent être interprétés à partir de la logique comptable propre au système. Ils ne sont pas, pris isolément, des indicateurs d’activité économique.

---

### 7.4.6. Taux de couverture

```text
Taux de couverture numérique
= fonds de garantie numérique / masse numérique
```

```text
Taux de couverture papier
= fonds de garantie papier / masse papier
```

Ces ratios constituent des indicateurs de rapprochement entre stocks monétaires et garanties associées.

---

### 7.4.7. Variation de la masse numérique

Lorsque plusieurs dates comptables sont comparables :

```text
Variation de masse numérique
= masse numérique à la date 2 - masse numérique à la date 1
```

---

### 7.4.8. Rapprochement entre flux nets et variation de stock

Un rapprochement utile consiste à comparer :

- l’évolution de la masse numérique ;
- le solde net entre alimentations et sorties.

```text
Écart de rapprochement
= variation de masse numérique
  - (alimentations - sorties)
```

Cet écart peut traduire :

- des différences de périmètre ;
- des décalages temporels ;
- des opérations non incluses dans l’un des deux calculs ;
- des points à auditer plus finement.

Il ne doit pas être automatiquement interprété comme une anomalie.

---

# 8. Pilotage monétaire

La vue **Pilotage monétaire** vise à relier les dimensions précédentes dans une lecture plus synthétique :

- ce qui circule ;
- ce qui entre ;
- ce qui sort ;
- ce qui reste détenu ;
- ce que cette combinaison raconte de l’ancrage de la Gonette numérique.

Elle permet de passer d’une lecture descriptive à une lecture davantage orientée vers la compréhension des dynamiques du système.

---

## 8.1. Circulation et rendement de la masse numérique

Un premier ensemble d’indicateurs rapproche le volume d’activité économique d’un stock monétaire de référence.

### Intensité de circulation

```text
Intensité de circulation numérique
= volume d’activité économique / masse numérique de référence
```

Cet indicateur renseigne la quantité d’activité produite relativement au stock monétaire mobilisable.

Il ne doit pas être interprété comme une vitesse de circulation macroéconomique au sens strict de la comptabilité nationale. Il s’agit ici d’un **indicateur interne de rendement circulatoire** de la monnaie numérique observée.

---

## 8.2. Entrées, sorties et garanties

Le pilotage monétaire permet également de mettre en regard :

- les alimentations ;
- les sorties ;
- l’évolution des stocks comptables ;
- les garanties associées.

Cette lecture aide à mieux comprendre :

- si les Gonettes numériques restent dans le circuit ;
- si les sorties augmentent ou diminuent relativement aux entrées ;
- si la structure monétaire évolue de manière cohérente avec les flux observés.

---

## 8.3. Détention et ancrage

L’onglet consacré à la détention cherche à répondre à une question simple :

> **où la Gonette numérique reste-t-elle stockée, et dans quelle mesure cette détention se transforme-t-elle en activité ?**

---

### 8.3.1. Stock positif moyen détenu par les particuliers

```text
Stock positif moyen U
= moyenne quotidienne du stock positif total détenu par les particuliers
```

Lorsqu’il est croisé avec la masse numérique comptable, le calcul doit porter sur les jours effectivement comparables entre les séries mobilisées.

---

### 8.3.2. Masse numérique moyenne de référence

```text
Masse numérique moyenne
= moyenne de la masse numérique comptable
  sur les jours retenus pour le rapprochement
```

---

### 8.3.3. Part du stock particulier dans la masse numérique

Deux formes de calcul peuvent coexister et ne doivent pas être confondues.

#### Ratio des moyennes

```text
Part moyenne U / masse numérique
= stock positif moyen U / masse numérique moyenne
```

#### Moyenne des ratios journaliers

```text
Moyenne journalière des parts U
= moyenne(stock U jour / masse numérique jour)
```

Ces deux mesures sont proches dans certains contextes, mais elles ne sont pas mathématiquement équivalentes.

---

### 8.3.4. Mobilisation du stock particulier

Cet indicateur rapproche :

- ce que les particuliers détiennent en moyenne ;
- ce qu’ils dépensent vers les professionnels pendant la période.

```text
Mobilisation du stock particulier
= volume U→P / stock positif moyen U
```

On peut également l’exprimer pour 100 Gonettes de stock moyen :

```text
Volume U→P pour 100 G de stock particulier moyen
= 100 × volume U→P / stock positif moyen U
```

Cette mesure éclaire la capacité du stock détenu par les particuliers à se transformer en activité économique visible pour le réseau professionnel.

---

### 8.3.5. Dormance

La dormance désigne l’absence de transaction impliquant un compte pendant une durée donnée.

Elle permet de distinguer :

- des comptes récemment actifs ;
- des comptes dont le stock existe mais reste immobile ;
- des stocks potentiellement remobilisables.

La dormance n’est pas un jugement porté sur les usagers. C’est un outil de lecture de la circulation monétaire.

---

### 8.3.6. Détention professionnelle et comptes opérateurs

Pour analyser la détention professionnelle, MLCFlux distingue :

1. le stock détenu par les **professionnels ordinaires du réseau** ;
2. le stock porté par les **comptes opérateurs** ;
3. le total professionnel consolidé lorsqu’un besoin de rapprochement l’exige.

Dans les indicateurs visant à comprendre l’ancrage économique de la Gonette chez les professionnels, la lecture principale doit porter sur :

```text
stock professionnel du réseau hors comptes opérateurs
```

---

# 9. Professionnels & particuliers

La vue **Professionnels & particuliers** cherche à comprendre comment la Gonette numérique s’inscrit dans le réseau d’usage.

Elle ne se contente pas d’identifier les professionnels qui reçoivent le plus. Elle cherche aussi à qualifier :

- ceux qui redistribuent ;
- ceux qui concentrent fortement les recettes ;
- ceux qui structurent certaines circulations ;
- ceux qui forment des pôles territoriaux ou sectoriels ;
- ceux dont l’activité Gonette repose sur un fond de commerce diversifié ou au contraire très concentré.

---

## 9.1. Volume reçu par un professionnel

Le volume reçu économiquement par un professionnel correspond aux Gonettes reçues dans la circulation ordinaire du réseau.

```text
Volume reçu P
= Vol(U→P vers ce P) + Vol(P→P vers ce P)
```

---

## 9.2. Volume émis par un professionnel

Le volume émis économiquement par un professionnel correspond aux Gonettes réinjectées dans la circulation ordinaire du réseau.

```text
Volume émis P
= Vol(P→P depuis ce P) + Vol(P→U depuis ce P)
```

---

## 9.3. Lire un professionnel autrement que par son chiffre reçu

Un professionnel peut :

- recevoir beaucoup sans réémettre fortement ;
- recevoir moins mais jouer un rôle important de redistribution ;
- être très central dans les échanges interprofessionnels ;
- avoir une activité Gonette concentrée sur quelques contreparties ;
- disposer d’un fond de commerce Gonette large et diversifié ;
- participer à un cluster territorial ou sectoriel structurant.

MLCFlux propose donc une lecture plus riche qu’un simple classement par volume encaissé.

---

# 10. Cartographie, territoires et secteurs

## 10.1. Cartographie des clusters

La cartographie permet de visualiser les structures spatiales de la circulation en Gonette numérique.

Elle peut mettre en évidence :

- la localisation des professionnels ;
- les pôles d’activité ;
- les territoires les plus alimentés en paiements ;
- les grands axes agrégés de circulation ;
- les relations entre certaines zones de dépense et les professionnels concernés.

La carte n’est pas un outil de traçabilité individuelle. Elle propose une lecture **agrégée** de dynamiques collectives.

---

## 10.2. Analyse territoriale

L’analyse territoriale regroupe les volumes et acteurs à partir de la localisation des professionnels.

Elle permet notamment d’observer :

- le nombre de professionnels actifs par territoire ;
- le volume reçu par les professionnels d’un territoire ;
- le volume émis par ces mêmes professionnels ;
- les contrastes entre zones très actives et zones peu alimentées ;
- l’éventuel rôle de certains territoires comme pôles de circulation.

### Volume reçu par territoire

```text
Volume reçu territoire t
= somme des volumes reçus par les professionnels situés dans t
```

### Volume émis par territoire

```text
Volume émis territoire t
= somme des volumes émis par les professionnels situés dans t
```

Ces analyses dépendent de la qualité et de la complétude des données de localisation disponibles.

---

## 10.3. Analyse sectorielle

L’analyse sectorielle regroupe les professionnels selon leur domaine d’activité.

Elle permet de poser plusieurs questions :

- quels secteurs reçoivent le plus de Gonettes ?
- quels secteurs en réémettent le plus ?
- où la circulation paraît-elle la plus dense ?
- quels secteurs semblent jouer un rôle de débouché final ?
- quels secteurs apparaissent moins intégrés aux circuits de réemploi ?

### Volume reçu par secteur

```text
Volume reçu secteur s
= somme des volumes reçus par les professionnels rattachés au secteur s
```

### Volume émis par secteur

```text
Volume émis secteur s
= somme des volumes émis par les professionnels rattachés au secteur s
```

---

# 11. Fiches professionnelles

Les fiches professionnelles donnent une lecture détaillée d’un acteur du réseau.

Elles sont conçues pour comprendre non seulement **combien** un professionnel reçoit, mais **comment** son activité Gonette se compose et **quelle place** il occupe dans l’écosystème.

---

## 11.1. Fond de commerce Gonette

Cette partie décrit les recettes Gonette du professionnel.

Elle permet notamment d’analyser :

- les paiements reçus de particuliers ;
- les paiements reçus d’autres professionnels ;
- la diversité des contreparties ;
- la concentration des recettes ;
- les temporalités de l’activité ;
- les provenances agrégées lorsque des représentations cartographiques sont proposées.

Elle répond à la question :

> **de quoi se compose l’activité Gonette visible de ce professionnel ?**

---

## 11.2. Dynamiques & réseau

Cette partie situe le professionnel dans la circulation générale.

Elle peut mettre en évidence :

- les volumes reçus ;
- les volumes émis ;
- la balance nette ;
- la diversité des relations ;
- un rôle de récepteur, de relais, de redistributeur ou de pivot ;
- la structure des flux avec ses principales contreparties.

Elle répond à la question :

> **comment ce professionnel s’insère-t-il dans le réseau monétaire ?**

---

## 11.3. Perspectives

Cette partie propose une lecture d’accompagnement.

Elle peut faire apparaître, par exemple :

- une activité Gonette déjà bien installée ;
- un potentiel de réemploi plus important ;
- une forte dépendance à quelques flux ou contreparties ;
- une place intéressante dans un réseau local ou sectoriel ;
- un potentiel de mise en relation avec d’autres acteurs.

Ces éléments doivent rester des **pistes de lecture**, et non des jugements automatiques.

---

# 12. Réemploi, circulation et multiplicateurs

MLCFlux propose plusieurs indicateurs pour approcher la capacité de la Gonette numérique à être **réutilisée** dans le réseau plutôt qu’immédiatement immobilisée ou reconvertie.

Ces indicateurs n’ont pas tous la même portée. Il est essentiel de les distinguer.

---

## 12.1. Taux d’émission sur recettes

Le taux d’émission sur recettes compare ce qu’un acteur ou un groupe d’acteurs émet à ce qu’il reçoit.

```text
Taux d’émission sur recettes
= volume émis / volume reçu
```

Ce ratio peut dépasser 100 % lorsqu’un acteur dépense pendant la période un stock constitué antérieurement.

Il s’agit d’un indicateur descriptif de comportement de circulation, pas d’un multiplicateur.

---

## 12.2. Propension de réemploi interne

Pour estimer de manière prudente la part des recettes effectivement réinjectée dans le réseau sur une même période, MLCFlux peut plafonner le réemploi acteur par acteur.

Pour un acteur `i` :

```text
Réemploi plafonné i
= min(volume reçu i, volume émis i)
```

Puis :

```text
Propension de réemploi interne
= somme des réemplois plafonnés
  / somme des volumes reçus
```

Cette méthode évite qu’un acteur qui dépense massivement un stock ancien donne artificiellement l’impression d’un réemploi de période très élevé.

---

## 12.3. Multiplicateur interne estimé

À partir de la propension de réemploi interne `c`, on peut construire un multiplicateur simplifié :

```text
Multiplicateur interne estimé
= 1 / (1 - c)
```

Cet indicateur vise à représenter, sous forme synthétique, la capacité d’une unité de monnaie à produire plusieurs vagues de circulation dans le réseau.

Il ne doit pas être interprété comme :

- un multiplicateur macroéconomique exhaustif ;
- une mesure comptable directe ;
- une preuve causale.

Il s’agit d’un **estimateur de dynamique interne de réemploi**, dépendant du périmètre choisi.

---

## 12.4. LM3 — multiplicateur d’injection local estimé

Le LM3 vise à suivre la prolongation d’une injection monétaire à travers plusieurs vagues successives de circulation.

Dans son principe général, il observe :

1. l’injection initiale de monnaie ;
2. une première vague de dépenses dans le réseau ;
3. une deuxième vague de réemploi par les premiers receveurs ;
4. éventuellement une troisième vague observable.

Le LM3 permet de s’interroger sur une question centrale :

> **que devient une Gonette une fois injectée dans le circuit ?**

Plus elle est réutilisée par les acteurs qui la reçoivent, plus le multiplicateur estimé augmente.

Le LM3 ne remplace pas les autres indicateurs de réemploi. Il apporte une lecture complémentaire, orientée vers le **prolongement d’une injection dans le temps et dans le réseau**.

---

# 13. Limites et précautions d’interprétation

MLCFlux vise une lecture exigeante et transparente des données. Cette exigence implique de rendre explicites ses limites.

---

## 13.1. Transactions et soldes ne posent pas les mêmes questions

Les transactions historiques permettent d’analyser les flux sur un périmètre consolidé.

Les séries de soldes demandent une vigilance spécifique, notamment lorsque certains comptes ont été supprimés, purgés ou ne sont plus exposés de la même manière dans les systèmes sources.

Les analyses de détention historique doivent donc être lues avec une prudence particulière tant que tous les audits de reconstitution de soldes ne sont pas considérés comme définitivement clos.

Cette prudence concerne surtout :

- les stocks historiques par catégorie d’acteurs ;
- les courbes de détention ;
- les analyses fines sur les comptes inactifs ou retirés.

---

## 13.2. Qualité des données territoriales et sectorielles

Les analyses territoriales et sectorielles dépendent de la qualité des métadonnées professionnelles disponibles.

Certaines limites doivent être gardées en tête :

- professionnels non géolocalisés ;
- secteurs non renseignés ou ambigus ;
- multi-activité difficile à résumer dans une seule catégorie ;
- évolutions possibles des informations de référence dans le temps.

---

## 13.3. Effets des dispositifs spécifiques

Les comptes `UD_*` permettent de mieux isoler l’impact de certains dispositifs ponctuels.

Un tel dispositif peut modifier fortement :

- le nombre de transactions sur une période ;
- la concentration d’activité sur quelques professionnels ;
- la géographie visible des flux ;
- certains indicateurs moyens.

Ces effets sont économiquement réels, mais ils doivent être contextualisés afin de ne pas être interprétés comme une tendance générale de fond.

---

## 13.4. Un ratio n’est jamais un jugement automatique

Un ratio élevé n’est pas toujours « bon ». Un ratio faible n’est pas toujours « mauvais ».

Une même valeur peut traduire :

- une dynamique vertueuse de réemploi ;
- un effet de structure ;
- un effet de période ;
- un phénomène de concentration ;
- la présence d’un dispositif exceptionnel.

MLCFlux fournit des outils de lecture. L’interprétation reste un travail d’analyse.

---

# 14. Glossaire

| Terme | Définition |
|---|---|
| Activité économique | Ensemble des flux `U→P`, `P→P`, `P→U`, `U→U` |
| Alimentation | Entrée de Gonettes numériques depuis un compte technique vers un compte ordinaire |
| Sortie du circuit | Flux de reconversion ou retrait vers un compte technique |
| Flux | Mouvement monétaire observé pendant une période |
| Stock | Quantité de monnaie observée à une date, ou moyenne sur une période |
| Masse numérique | Stock comptable de Gonettes numériques en circulation |
| Masse papier | Stock comptable de Gonettes papier en circulation |
| Masse totale | Somme des masses numérique et papier |
| Fonds de garantie | Contrepartie en euros associée à une masse de monnaie locale |
| Compte particulier `U_*` | Compte de particulier pseudonymisé |
| Compte de dispositif `UD_*` | Compte particulier associé à un dispositif spécifique ou ponctuel |
| Compte technique `T_*` | Compte servant à qualifier des mouvements non assimilables à l’activité économique ordinaire |
| Comptes opérateurs | Comptes `P0000` et `P9999`, analysés séparément des professionnels ordinaires |
| Réemploi | Remise en circulation des Gonettes reçues |
| Taux d’émission sur recettes | Rapport entre volume émis et volume reçu |
| Propension de réemploi interne | Estimation prudente de la part des recettes effectivement réémises dans le réseau |
| Multiplicateur interne | Estimateur de prolongement de la circulation à partir d’une propension de réemploi |
| LM3 | Estimateur de plusieurs vagues successives de circulation après injection de monnaie |
| Dormance | Absence de transaction impliquant un compte pendant une durée donnée |

---

# 15. Résumé de doctrine analytique

MLCFlux repose sur quelques principes simples, mais structurants.

> **1. Les flux économiques, les entrées-sorties de monnaie, les opérations techniques et les stocks comptables ne doivent pas être confondus.**

> **2. L’activité économique est définie par un périmètre clair : les transactions entre acteurs ordinaires du réseau.**

> **3. Les comptes opérateurs et techniques doivent être visibles, mais séparés de l’activité économique centrale.**

> **4. Les particuliers de dispositif sont inclus dans l’analyse lorsqu’ils participent à l’activité, mais isolés lorsqu’ils expliquent une dynamique atypique.**

> **5. Les indicateurs de réemploi, de circulation et de multiplicateur sont des outils d’interprétation, pas des verdicts automatiques.**

> **6. Toute métrique importante doit pouvoir être reliée à une définition, une formule et un périmètre assumé.**

En résumé :

> **MLCFlux cherche à rendre intelligible la vie économique de la Gonette numérique : ce qui entre, ce qui sort, ce qui circule, ce qui reste détenu, ce qui se réemploie, et la manière dont ces mouvements structurent un réseau d’acteurs, de territoires et de secteurs.**

