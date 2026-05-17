# 12. Réemploi, circulation et multiplicateurs

MLCFlux propose plusieurs indicateurs pour approcher la capacité de la Gonette numérique à être **réutilisée** dans le réseau plutôt qu’immédiatement immobilisée ou reconvertie.

Ces indicateurs n’ont pas tous la même portée. Il est essentiel de les distinguer.

---

## 12.1. Taux d’émission sur recettes

Le taux d’émission sur recettes compare ce qu’un acteur ou un groupe d’acteurs émet à ce qu’il reçoit.

```Taux d’émission sur recettes = volume émis / volume reçu```

Ce ratio peut dépasser 100 % lorsqu’un acteur dépense pendant la période un stock constitué antérieurement.

Il s’agit d’un indicateur descriptif de comportement de circulation, pas d’un multiplicateur.

---

## 12.2. Propension de réemploi interne

Pour estimer de manière prudente la part des recettes effectivement réinjectée dans le réseau sur une même période, MLCFlux peut plafonner le réemploi acteur par acteur.

Pour un acteur `i` :

```Réemploi plafonné i = min(volume reçu i, volume émis i)```

Puis :

```Propension de réemploi interne = somme des réemplois plafonnés / somme des volumes reçus```

Cette méthode évite qu’un acteur qui dépense massivement un stock ancien donne artificiellement l’impression d’un réemploi de période très élevé.

---

## 12.3. Multiplicateur interne estimé

À partir de la propension de réemploi interne `c`, on peut construire un multiplicateur simplifié :

```Multiplicateur interne estimé = 1 / (1 - c)```

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
