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

```Nb professionnels actifs = nombre de P distincts apparaissant dans les flux U→P, P→P ou P→U```

---

### 7.1.2. Particuliers actifs

Un particulier actif est un particulier distinct impliqué dans au moins une opération économique pendant la période étudiée.

```Nb particuliers actifs = nombre de U distincts apparaissant dans les flux U→P, P→U ou U→U```

---

### 7.1.3. Acteurs actifs dans la circulation

```Acteurs actifs = professionnels actifs + particuliers actifs```

---

### 7.1.4. Nombre total d’opérations économiques

```Nb opérations économiques = Nb(U→P) + Nb(P→P) + Nb(P→U) + Nb(U→U)```

---

### 7.1.5. Volume total d’activité économique

```Volume économique = Vol(U→P) + Vol(P→P) + Vol(P→U) + Vol(U→U)```

---

### 7.1.6. Nombre moyen de transactions par jour

```Moyenne transactions / jour = nombre total d’opérations économiques / nombre de jours calendaires couverts par la période```

Le dénominateur correspond aux jours calendaires de la période, qu’il y ait eu ou non des transactions chaque jour.

---

### 7.1.7. Montants moyens par type de flux

#### Montant moyen `U → P`

```Montant moyen U→P = Vol(U→P) / Nb(U→P)```

Cet indicateur peut être lu comme un **panier moyen de paiement des particuliers vers les professionnels**.

---

#### Montant moyen `P → P`

```Montant moyen P→P = Vol(P→P) / Nb(P→P)```

Il mesure l’intensité moyenne des échanges interprofessionnels.

---

#### Montant moyen `P → U`

```Montant moyen P→U = Vol(P→U) / Nb(P→U)```

Il renseigne des flux sortants vers les particuliers, à interpréter avec prudence en raison de leur diversité.

---

#### Montant moyen `U → U`

```Montant moyen U→U = Vol(U→U) / Nb(U→U)```

---

### 7.1.8. Graphiques quotidiens — lecture en nombre ou en volume

Les graphiques quotidiens peuvent être affichés selon deux modes :

| Mode | Ce qui est représenté |
|---|---|
| Nombre | Le nombre d’opérations réalisées chaque jour |
| Volume | Le montant total des opérations réalisées chaque jour |

#### Nombre de paiements au jour `d`

```Nb paiements au jour d = Nb(U→P,d) + Nb(P→P,d) + Nb(P→U,d) + Nb(U→U,d)```

#### Volume de paiements au jour `d`

```Vol paiements au jour d = Vol(U→P,d) + Vol(P→P,d) + Vol(P→U,d) + Vol(U→U,d)```

Cette double lecture permet de distinguer :

- une journée comportant beaucoup de petites opérations ;
- une journée comportant peu d’opérations mais des montants importants.

---

### 7.1.9. Montant moyen hebdomadaire

Pour une semaine `s` :

```Montant moyen semaine s = volume économique de la semaine s / nombre d’opérations économiques de la semaine s```

---

### 7.1.10. Répartition par heure

Ce graphique montre le nombre d’opérations économiques réalisées selon l’heure de la journée.

```Nb transactions à l’heure h = nombre d’opérations économiques dont l’heure = h```

Il permet de repérer les rythmes quotidiens d’usage.

---

### 7.1.11. Répartition par jour de semaine

Ce graphique montre le nombre d’opérations économiques selon le jour de la semaine.

```Nb transactions le jour j = nombre d’opérations économiques réalisées ce jour-là```

---

### 7.1.12. Volume cumulé d’activité économique

Pour un jour `d` :

```Volume cumulé au jour d = somme des volumes économiques de tous les jours ≤ d```

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

```Alimentations = T→U + T→P```

Elles peuvent bénéficier :

- à des particuliers ;
- à des professionnels.

Une alimentation accroît la capacité d’usage d’un acteur, mais elle ne constitue pas encore en elle-même une transaction économique entre acteurs du réseau.

---

### 7.2.2. Sorties du circuit

Les sorties correspondent principalement aux flux de reconversion ou de retrait depuis des comptes professionnels vers un compte technique.

```Sorties du circuit = P→T```

Elles indiquent qu’une partie des Gonettes quitte la dynamique de circulation numérique étudiée.

---

### 7.2.3. Écart net entre alimentations et sorties

```Écart net alimentations - sorties = Vol(alimentations) - Vol(sorties)```

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

```Masse totale = masse numérique + masse papier```

---

### 7.4.4. Fonds de garantie

Les fonds de garantie représentent les contreparties en euros associées aux masses de Gonettes en circulation.

MLCFlux distingue :

- fonds de garantie numérique ;
- fonds de garantie papier.

---

### 7.4.5. Écarts entre masse et garantie

```Écart numérique = fonds de garantie numérique - masse numérique```

```Écart papier = fonds de garantie papier - masse papier```

Ces écarts doivent être interprétés à partir de la logique comptable propre au système. Ils ne sont pas, pris isolément, des indicateurs d’activité économique.

---

### 7.4.6. Taux de couverture

```Taux de couverture numérique = fonds de garantie numérique / masse numérique```

```Taux de couverture papier = fonds de garantie papier / masse papier```

Ces ratios constituent des indicateurs de rapprochement entre stocks monétaires et garanties associées.

---

### 7.4.7. Variation de la masse numérique

Lorsque plusieurs dates comptables sont comparables :

```Variation de masse numérique = masse numérique à la date 2 - masse numérique à la date 1```

---

### 7.4.8. Rapprochement entre flux nets et variation de stock

Un rapprochement utile consiste à comparer :

- l’évolution de la masse numérique ;
- le solde net entre alimentations et sorties.

```Écart de rapprochement = variation de masse numérique - (alimentations - sorties)```

Cet écart peut traduire :

- des différences de périmètre ;
- des décalages temporels ;
- des opérations non incluses dans l’un des deux calculs ;
- des points à auditer plus finement.

Il ne doit pas être automatiquement interprété comme une anomalie.

---
