# 5. Catégories d’acteurs et conventions de lecture

MLCFlux repose sur une typologie d’acteurs explicite. Cette typologie permet de classifier les flux sans confondre des réalités différentes.

## 5.1. Professionnels — `P`

Les professionnels sont les acteurs économiques du réseau : commerces, associations, structures partenaires et autres entités recevant ou émettant des Gonettes dans le cadre de leur activité.

Ils sont identifiés par un code de type :

```P0008 P0300 P0752```

Lorsque l’information est disponible, MLCFlux les affiche sous une forme plus lisible :

```P0677 — Graines Électroniques```

---

## 5.2. Particuliers ordinaires — `U_*`

Les particuliers sont pseudonymisés lors de l’import des données.

Ils apparaissent sous une forme de type :

```U_Alice U_Benoît U_Deb```

Cette pseudonymisation permet de :

- suivre l’activité d’un même compte dans le temps ;
- conserver une lisibilité suffisante dans les analyses ;
- préserver la confidentialité des personnes concernées.

MLCFlux ne stocke pas, dans sa base analytique finale, les identifiants bruts nécessaires à une réidentification simple des particuliers.

---

## 5.3. Particuliers de dispositif — `UD_*`

Certains comptes particuliers sont associés à des dispositifs spécifiques, ponctuels ou expérimentaux. Ils sont distingués par un préfixe particulier :

```UD_Ana UD_Louis UD_Maya```

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

```T_Émission T_Conversion```

Ils servent à identifier des opérations telles que :

- les alimentations ;
- certaines sorties du circuit ;
- des mouvements de régularisation ;
- d’autres opérations non assimilables à un paiement ordinaire entre usagers.

---

## 5.5. Comptes opérateurs — `P0000` et `P9999`

Deux comptes professionnels ont un rôle méthodologique particulier :

```P0000 P9999```

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

```Nb opérations économiques = Nb(U→P) + Nb(P→P) + Nb(P→U) + Nb(U→U)```

### Volume d’activité économique

```Volume d’activité économique = Vol(U→P) + Vol(P→P) + Vol(P→U) + Vol(U→U)```

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
