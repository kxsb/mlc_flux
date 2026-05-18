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
