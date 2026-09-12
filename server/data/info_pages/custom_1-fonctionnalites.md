# Fonctionnalités

## 1. Cette carte explique

* ce que chaque vue permet de comprendre ;
* comment les chiffres sont mis en forme ;
* quelles interprétations sont possibles ;
* quelles précautions de lecture garder en tête ;
* quelles données sont mobilisées ;
* quelles routes API et fonctions principales sont concernées ;
* quels graphiques ou cartes sont affichés dans MLCFlux ;
* quelles formules générales structurent les calculs.


La logique générale est la suivante :

Sources de données (Cyclos, Odoo) → synchronisation / enrichissement
→ tables SQLite
→ services analytiques Python
→ routes API Flask
→ rendu frontend JavaScript
→ KPI, graphiques, cartes et aides de lecture

Les fonctionnalités ci-dessous n’ont pas toutes le même niveau de maturité. Certaines sont déjà centrales pour le pilotage. D’autres sont encore exploratoires ou en cours de stabilisation méthodologique.

---

## 2. Suivi de l’activité économique

### Finalité

Le suivi de l’activité économique cherche à répondre à une question simple :

> La monnaie circule-t-elle réellement entre les acteurs économiques du réseau ?

Cette vue permet d’observer le nombre d’opérations, les volumes échangés, les familles de flux et l’évolution dans le temps. Elle est utile pour comprendre si la monnaie locale est utilisée comme moyen d’échange, ou si elle reste principalement stockée, convertie, reconvertie ou mobilisée dans des opérations techniques.

### Où la trouver dans MLCFlux ?

Localisation principale :

Vue : Statistiques globales
Onglet : Activité économique
Selon l’état de l’interface, cette fonctionnalité peut être reliée aux blocs de synthèse générale, aux graphiques mensuels et aux aides méthodologiques associées aux KPI.

### Mise en forme

L’activité économique est généralement présentée sous forme de :

* cartes KPI ;
* séries temporelles mensuelles ;
* graphiques en nombre d’opérations ;
* graphiques en volume monétaire ;
* boutons de bascule “Nombre / Volume” ;
* aides méthodologiques expliquant le périmètre.

La séparation entre nombre et volume est importante. Un mois peut avoir peu d’opérations mais de gros montants, ou beaucoup d’opérations de faible montant.

### Interprétation possible

Une hausse de l’activité économique peut signaler :

* davantage d’usage réel de la monnaie ;
* une campagne réussie ;
* un événement ou dispositif particulier ;
* une meilleure circulation entre particuliers et professionnels ;
* une augmentation ponctuelle liée à quelques gros paiements.

Une baisse peut signaler :

* un ralentissement d’usage ;
* une saisonnalité ;
* une perte d’acteurs actifs ;
* un changement technique ;
* une période creuse ;
* une donnée manquante ou mal classée.

L’activité économique doit toujours être croisée avec :

* la masse monétaire disponible ;
* les conversions ;
* les reconversions ;
* les soldes ;
* les connaissances du terrain.

### Logique de calcul

Avant de présenter les formules, il faut définir une notion centrale de MLCFlux : la sémantique transactionnelle.

La table `transaction_semantics` constitue une couche d’interprétation appliquée aux transactions brutes issues de Cyclos. Son rôle est de qualifier chaque transaction selon sa signification économique ou fonctionnelle. Une transaction n’est donc pas analysée uniquement à partir de son montant ou de ses comptes source et destination, mais aussi à partir de sa catégorie analytique.

Cette qualification est réalisée par le moteur de sémantique transactionnelle de MLCFlux, qui applique une série de règles déterministes à chaque transaction à partir des métadonnées disponibles : type de compte source, type de compte cible, rôles des acteurs, comptes techniques identifiés, listes de comptes de conversion ou de reconversion, et éventuelles règles spécifiques à la MLC.

Concrètement, la fonction de qualification examine la combinaison « émetteur → destinataire » et attribue une catégorie analytique unique ou prioritaire. Cette logique permet notamment de distinguer :

* les transactions économiques entre particuliers et professionnels ;
* les transactions économiques entre professionnels ;
* les transactions entre particuliers ;
* les conversions identifiées via les comptes ou circuits d’alimentation ;
* les reconversions identifiées via les comptes ou circuits de sortie ;
* les opérations impliquant des comptes techniques ;
* les opérations associatives ou opérateur lorsqu'elles sont explicitement identifiées ;
* les mouvements internes entre comptes appartenant à un même acteur ou à une même structure ;
* les corrections, régularisations ou opérations administratives reconnues ;
* les flux liés à des dispositifs spécifiques configurés dans la MLC ;
* les transactions restant non classées ou relevant d'une catégorie résiduelle définie par la méthodologie locale.

L'objectif de cette étape n'est pas seulement de décrire la transaction telle qu'elle apparaît dans Cyclos, mais de lui attribuer une signification économique exploitable pour les indicateurs, graphiques et analyses de circulation.

La sémantique transactionnelle est une notion pivot : la plupart des indicateurs, graphiques et KPI de MLCFlux reposent directement ou indirectement sur cette classification. Une même transaction brute peut donc être incluse ou exclue d’un calcul selon la catégorie qui lui est attribuée.

Formules générales :

Nombre d’opérations économiques = nombre total de transactions classées comme activité économique

Volume économique = somme des montants de toutes les transactions classées comme activité économique

Montant moyen par opération économique = Volume économique / Nombre d’opérations économiques

Évolution mensuelle de l’activité économique = agrégation des transactions économiques par mois calendaire, avec calcul pour chaque mois du nombre d’opérations, du volume total et, le cas échéant, du montant moyen

Part d’une famille de flux = (Volume ou nombre d’opérations appartenant à une famille de flux donnée) / (Volume ou nombre total d’opérations du périmètre observé)

Famille de flux = catégorie analytique regroupant des transactions partageant les mêmes caractéristiques de source, de destination ou de nature économique (par exemple U→P, P→P, U→U, conversion, reconversion, etc.)

Périmètre observé = ensemble des transactions retenues pour le calcul après application des filtres de période, de territoire, de type d’acteur et des règles d’exclusion méthodologiques

Le point méthodologique essentiel est la qualification des transactions. Toutes les transactions Cyclos ne sont pas automatiquement de l’activité économique. Certaines peuvent être des conversions, des reconversions, des opérations associatives, des opérations techniques, des dispositifs spécifiques ou des corrections.

### Chemin principal des données

→ transactions Cyclos  

→ table transactions

→ table transaction_semantics

→ fonctions analytiques de statistiques globales

→ routes /api/stats et /api/stats_charts

→ renderStatsView()

→ cartes KPI et graphiques d’activité

### Fonctions et fichiers principalement concernés

Repères principaux :

Backend :
- server/analytics.py
- server/routes/legacy_api.py
- services de sémantique transactionnelle

Routes API :
- /api/stats
- /api/stats_charts
- /api/period-bounds

Frontend :
- static/js/app.js
- renderStatsView()
- helpers de graphiques statistiques
- aides méthodologiques des KPI et graphes

### Graphiques concernés

Graphiques typiques :

Vue Statistiques globales
→ Activité économique mensuelle
→ Décomposition des flux
→ Graphiques Nombre / Volume
→ KPI de synthèse activité

---

## 3. Analyse des transactions et des flux

### Finalité

Cette fonctionnalité sert à comprendre la structure des mouvements monétaires.

Elle ne cherche pas seulement à compter des transactions, mais à distinguer des familles de flux :

* particulier vers professionnel ;
* professionnel vers professionnel ;
* professionnel vers particulier ;
* particulier vers particulier ;
* conversion ;
* reconversion ;
* opération associative ;
* opération technique ;
* dispositif spécifique ;
* flux à auditer.

### Où la trouver dans MLCFlux ?

Localisation principale :

Vue : Statistiques globales
Vues associées : Réseau, Professionnels & particuliers, Cartographie
Les flux sont aussi visibles indirectement dans les cartes, les fiches professionnelles, les graphes de réseau et les indicateurs de réemploi.

### Mise en forme

Les flux sont représentés par :

* graphiques de répartition ;
* séries temporelles ;
* tableaux de détails ;
* graphes de réseau ;
* cartes de relations ;
* aides de lecture associées.

Le même flux peut être lu de plusieurs manières :

Comme transaction individuelle
Comme agrégat mensuel
Comme relation entre familles d’acteurs
Comme lien entre deux acteurs
Comme contribution à un KPI
Comme segment d’un graphe ou d’une carte

### Interprétation possible

L’analyse des flux permet de repérer :

* les circuits vivants ;
* les circuits faibles ;
* les acteurs centraux ;
* les dépendances à certains pôles ;
* les zones où la monnaie entre mais ne ressort pas ;
* les zones où elle circule mais ne se renouvelle pas ;
* les flux techniques qui polluent une lecture économique naïve.

### Logique de calcul

Formules générales :

Flux A → B = transactions dont la source appartient à A et la cible appartient à B

Volume A → B = SUM(montant des transactions A → B)

Nombre A → B = COUNT(transactions A → B)

Part de A → B = Volume A → B / Volume total du périmètre

Solde relationnel A/B = Volume A → B - Volume B → A

Les familles A et B peuvent être :

U = particuliers
P = professionnels
T = comptes techniques
O = comptes opérateurs ou associatifs selon doctrine
UD = particuliers de dispositif

Ces notations doivent être lues comme des catégories analytiques, pas comme des identités personnelles.

### Chemin principal des données

transactions

→ classification des acteurs
→ transaction_semantics
→ agrégations par famille de flux
→ routes statistiques, réseau, professionnels ou cartographie
→ graphes, cartes et tableaux

### Fonctions et fichiers principalement concernés

Backend :
- server/services/transaction_semantics.py
- server/analytics.py
- server/routes/legacy_api.py
- services professionnels et cartographiques

Routes API :
- /api/stats
- /api/stats_charts
- /api/network
- /api/pros
- /api/user-to-professional-map
- /api/pro/<professional_ref>/dynamics

Frontend :
- renderStatsView()
- renderNetworkGraph()
- drawProsTable()
- renderProDetail()

### Graphiques concernés

Statistiques globales :
- Graphiques de familles de flux
- Graphiques mensuels Nombre / Volume

Réseau :
- Graphe relationnel des acteurs

Professionnels & particuliers :
- Graphiques de circulation
- Fiches détaillées

Cartographie :
- Flux territoriaux
- Carte U → P

---

## 4. Conversions et reconversions

### Finalité

Les conversions et reconversions permettent de suivre les entrées et sorties du circuit numérique.

Une conversion correspond à une entrée de monnaie locale numérique dans le système. Une reconversion correspond à une sortie ou un retour hors du circuit numérique.

Cette distinction est essentielle : une monnaie peut afficher beaucoup d’activité parce qu’elle est beaucoup alimentée, mais cela ne signifie pas forcément qu’elle circule bien ensuite.

### Où la trouver dans MLCFlux ?

Localisation principale :
Vue : Statistiques globales
Onglet : Alimentation / sorties du circuit

Vues associées :
- Pilotage monétaire
- Professionnels & particuliers
- Fiches professionnelles

### Mise en forme

Les conversions et reconversions sont affichées sous forme de :

* KPI d’entrée et sortie ;
* évolution mensuelle ;
* comparaison alimentations / sorties ;
* écarts cumulés ;
* destinations ou origines des alimentations ;
* contribution aux indicateurs de pilotage.

### Interprétation possible

Une hausse des conversions peut signaler :

* une campagne d’acquisition ;
* une entrée de nouveaux utilisateurs ;
* une alimentation exceptionnelle ;
* une action institutionnelle ou associative.

Une hausse des reconversions peut signaler :

* une sortie de monnaie du circuit ;
* des professionnels qui ne trouvent pas assez de débouchés ;
* une clôture de comptes ;
* un besoin de travailler le réseau de réemploi ;
* une opération technique ou corrective.

### Logique de calcul

Formules générales :
Total converti = SUM(montant des flux identifiés comme conversions)

Total reconverti = SUM(montant des flux identifiés comme reconversions)

Écart net conversions / reconversions = Total converti - Total reconverti

Taux de reconversion apparent = Total reconverti / Total converti

Attention : l’écart net entre conversions et reconversions n’est pas équivalent à une masse monétaire en circulation. La masse est un stock. Les conversions et reconversions sont des flux.

### Chemin principal des données

transactions Cyclos
→ identification des comptes ou familles de conversion / reconversion
→ transaction_semantics
→ agrégats conversions / reconversions
→ /api/stats, /api/stats_charts, /api/monetary-indicators/*
→ graphiques et KPI

### Fonctions et fichiers principalement concernés
Backend :
- server/services/transaction_semantics.py
- server/analytics.py
- server/routes/monetary_indicators.py

Routes API :
- /api/stats
- /api/stats_charts
- /api/monetary-indicators/period-summary
- /api/monetary-indicators/pilotage-summary

Frontend :
- renderStatsView()
- fonctions de rendu du pilotage monétaire
- helpers méthodologiques des graphes

### Graphiques concernés

Statistiques globales :
- Alimentations / sorties
- Écart conversions / reconversions
- Évolution mensuelle des entrées et sorties

Pilotage monétaire :
- Indicateurs de circulation et de réemploi

---

## 5. Masse monétaire, monnaie papier et garanties

### Finalité

Cette fonctionnalité observe les stocks monétaires.

Elle répond à des questions différentes de celles des flux :

> Combien de monnaie existe dans le système ?
> Quelle part est numérique ?
> Quelle part est papier ?
> Quelles garanties existent en face ?
> Y a-t-il un écart entre masse numérique, monnaie papier, fonds de garantie et circulation observée ?

### Où la trouver dans MLCFlux ?

Localisation principale :

Vue : Pilotage monétaire
Vues associées : Statistiques globales, Professionnels & particuliers

### Mise en forme

Les données de masse et de garanties sont présentées sous forme de :

* KPI de masse moyenne ;
* séries journalières ;
* séries périodiques ;
* comparaisons numérique / papier ;
* indicateurs de garantie ;
* écarts ou résiduels ;
* graphiques de pilotage.

### Interprétation possible

Une masse élevée n’est pas forcément positive si elle ne circule pas.

Une masse faible n’est pas forcément négative si elle circule intensément.

Le pilotage monétaire doit donc croiser :

masse disponible
activité économique
soldes détenus
réemploi
conversions
reconversions
garanties

### Logique de calcul

Formules générales :
Masse numérique moyenne = AVG(masse numérique journalière sur la période)

Masse totale moyenne = AVG(masse numérique + masse papier)

Fonds de garantie moyen = AVG(fonds de garantie sur la période)

Écart de garantie = Fonds de garantie - Masse correspondante

Rotation économique = Volume d’activité économique / Masse numérique moyenne

Rotation annualisée = Rotation sur période recalculée sur une base annuelle

Selon les MLC, toutes les sources ne sont pas disponibles. La Gonette peut disposer d’indicateurs issus d’Odoo. La Graine peut reposer davantage sur Cyclos et les caches de pilotage.

### Chemin principal des données

Odoo ou Cyclos
→ tables d’indicateurs monétaires journaliers
→ caches de pilotage
→ routes monetary_indicators
→ vues de pilotage monétaire

### Fonctions et fichiers principalement concernés

Backend :
- server/routes/monetary_indicators.py
- server/services/odoo_monetary_indicators.py
- server/services/monetary_indicators_adaptive.py
- server/services/pilotage_holdings_daily_cache.py
- server/services/pilotage_yearly_cache.py

Tables possibles :
- odoo_monetary_indicators_daily
- odoo_monetary_indicators_yearly
- pilotage_holdings_daily_cache
- pilotage_yearly_cache
- cyclos_*_daily_balances

Routes API :
- /api/monetary-indicators
- /api/monetary-indicators/daily
- /api/monetary-indicators/latest
- /api/monetary-indicators/period-summary
- /api/monetary-indicators/yearly
- /api/monetary-indicators/pilotage-summary
- /api/monetary-indicators/pilotage-timeseries
- /api/monetary-indicators/pilotage-holdings-summary
- /api/monetary-indicators/pilotage-holdings-timeseries

### Graphiques concernés

Pilotage monétaire :
- séries de masse numérique
- séries de masse papier
- garanties
- écarts
- rotation
- indicateurs de réemploi
- séries de détention

---

## 6. Professionnels et dynamiques d’activité

### Finalité

La vue “Professionnels & particuliers” permet de comprendre le rôle des professionnels dans la circulation de la monnaie.

Elle répond notamment à ces questions :

Quels professionnels reçoivent le plus ?
Quels professionnels réémettent la monnaie ?
Quels professionnels reconvertissent ?
Quels professionnels jouent un rôle de redistribution ?
Quels professionnels sont isolés ?
Quels secteurs ou territoires semblent actifs ?


### Où la trouver dans MLCFlux ?

Localisation principale :

Vue : Professionnels & particuliers
Onglets possibles :
- Synthèse
- Circulation
- Cartographie des clusters
- Analyse sectorielle
- Liste & fiches

### Mise en forme

La vue combine :

* tableaux de professionnels ;
* cartes KPI ;
* fiches détaillées ;
* filtres par période ;
* onglets d’analyse ;
* graphes de circulation ;
* cartes de consommation ;
* indicateurs de réemploi.

### Interprétation possible

Un professionnel peut être important de plusieurs manières :

Il reçoit beaucoup.
Il réémet beaucoup.
Il sert de pont entre plusieurs familles d’acteurs.
Il attire des particuliers.
Il redistribue vers d’autres professionnels.
Il garde beaucoup de monnaie.
Il reconvertit fortement.

Il ne faut donc pas lire uniquement le volume reçu. Un acteur peut être central parce qu’il redistribue, pas seulement parce qu’il encaisse.

### Logique de calcul

Formules générales :

Total reçu = SUM(flux entrants vers le professionnel)

Total émis = SUM(flux sortants du professionnel)

Reçu des particuliers = SUM(U → P)

Reçu des professionnels = SUM(P → P entrant)

Émis vers particuliers = SUM(P → U)

Émis vers professionnels = SUM(P → P sortant)

Total converti = SUM(conversions reçues par le professionnel)

Total reconverti = SUM(reconversions émises par le professionnel)

Taux de réutilisation = Total émis / (Total reçu + Total converti)

Ces formules doivent être interprétées selon le périmètre choisi. Certaines opérations peuvent être exclues si elles relèvent de corrections, de dispositifs spécifiques ou d’opérations techniques.

### Chemin principal des données

transactions + transaction_semantics
→ enrichissements professionnels
→ services professional_activity et professional detail
→ routes /api/pros et /api/pro/*
→ tableaux, fiches et panels frontend

### Fonctions et fichiers principalement concernés

Backend :
- server/services/professional_activity_analytics.py
- server/services/professional_detail_dynamics.py
- server/services/professional_chain_fate_analytics.py
- server/services/professional_reuse_prospects.py
- server/services/professional_consumption_map_analytics.py
- server/routes/professional_activity.py
- server/routes/professional_detail_dynamics.py
- server/routes/professional_payment_basin_map.py
- server/routes/professional_reuse_prospects.py

Routes API :
- /api/pros
- /api/professionals/activity-summary
- /api/professionals/circulation-timeseries
- /api/professionals/chain-fate-summary
- /api/pro/<professional_ref>
- /api/pro/<professional_ref>/dynamics
- /api/pro/<professional_ref>/payment-basin-map
- /api/pro/<professional_ref>/reuse-prospects

Frontend :
- drawProsTable()
- renderProfessionalSummaryPanel()
- renderProfessionalCirculationPanel()
- renderProfessionalCirculationCharts()
- buildProfessionalCirculationFlowsChartConfig()
- renderProDetail()

### Graphiques concernés
Professionnels & particuliers :
- Synthèse des professionnels
- Graphiques de circulation professionnelle
- Tableau des professionnels
- Fiches professionnelles
- Bassin de paiement
- Perspectives de réemploi

---

## 7. Relations particuliers → professionnels

### Finalité

Cette fonctionnalité cherche à lire la relation entre les particuliers et les professionnels.

Elle répond à une question centrale pour une monnaie locale :

> Les particuliers utilisent-ils réellement leur monnaie chez les professionnels du réseau ?

C’est une des lectures les plus importantes pour comprendre la vitalité d’un circuit local.

### Où la trouver dans MLCFlux ?

Localisation principale :

Vue : Professionnels & particuliers
Onglet : Cartographie des clusters
Carte : flux U → P

### Mise en forme

La vue peut prendre la forme :

* d’une carte ;
* de flux entre zones ;
* de points particuliers anonymisés ;
* de points professionnels ;
* de clusters postaux ;
* d’un panneau latéral ;
* de filtres par période ;
* de survol/clic/recherche.

### Interprétation possible

Cette carte peut aider à repérer :
Les zones d’usage fort.
Les professionnels qui attirent des paiements.
Les territoires où les particuliers sont présents mais utilisent peu.
Les relations entre bassins de vie et bassins commerciaux.
Les déséquilibres territoriaux.
Il faut cependant lire cette carte avec prudence. Les points particuliers sont anonymisés ou agrégés. La précision cartographique ne doit jamais être confondue avec une surveillance des personnes.

### Logique de calcul

Formules générales :
Flux U → P = transactions dont la source est un particulier et la cible un professionnel

Volume U → P = SUM(montant U → P)

Nombre U → P = COUNT(transactions U → P)

Flux territorial = agrégation des U → P par zone source et destination professionnelle

Part d’un professionnel = Volume reçu du groupe observé / Volume total U → P

### Chemin principal des données

transactions
→ transaction_semantics
→ actor_territorial_enrichment
→ actor_map_locations
→ service user_to_professional_map
→ /api/user-to-professional-map
→ carte U → P

### Fonctions et fichiers principalement concernés

Backend :
- server/services/user_to_professional_map_analytics.py
- server/services/user_postal_cluster_analytics.py
- server/routes/user_to_professional_map.py
- server/routes/user_postal_clusters.py

Routes API :
- /api/user-to-professional-map
- /api/user-postal-clusters

Frontend :
- static/js/professional_consumption_map.js
- renderProfessionalConsumptionMapCanvas()
- getProfessionalConsumptionMapFinalRenderPayload()
- resetProfessionalConsumptionMapRenderCaches()

### Graphiques et cartes concernés

Professionnels & particuliers :
- Carte U → P
- Clusters particuliers
- Flux vers professionnels
- Recherche de professionnels sur carte
- Panneau latéral de lecture

---

## 8. Cartographie des usages, territoires et secteurs

### Finalité

La cartographie sert à spatialiser les usages.

Elle répond à des questions comme :

Où sont les professionnels ?
Quels territoires concentrent l’activité ?
Quels codes postaux sont les plus actifs ?
Quels secteurs semblent dynamiques ?
Quels territoires sont peu couverts ?

### Où la trouver dans MLCFlux ?

Localisations principales :

Vue : Professionnels & particuliers
Onglet : Cartographie des clusters

Vue ou onglet associé :
- Analyse sectorielle


Certaines anciennes vues comme “Territoires”, “Cartographie” ou “Secteurs” peuvent avoir été absorbées ou déplacées dans la nouvelle organisation de l’interface.

### Mise en forme

Les données territoriales peuvent être affichées sous forme de :

* carte de professionnels ;
* points cartographiques ;
* clusters ;
* tableaux par code postal ;
* tableaux par secteur ;
* indicateurs de couverture ;
* cartes de flux.

### Interprétation possible

La cartographie permet de repérer :


Les zones fortes.
Les zones faibles.
Les zones couvertes mais peu actives.
Les zones sans professionnels.
Les secteurs qui structurent l’usage.
Les lieux où une action d’animation pourrait être prioritaire.


La carte n’explique pas tout. Elle doit être croisée avec la connaissance du terrain : mobilité, habitudes d’achat, densité urbaine, événements, histoire militante, stratégie de développement, présence bénévole.

### Logique de calcul

Formules générales :


Activité par territoire = SUM(volume des transactions rattachées au territoire)

Nombre d’acteurs par territoire = COUNT(acteurs localisés)

Couverture territoriale = acteurs cartographiables / acteurs totaux

Part d’un secteur = Volume ou nombre du secteur / Total observé

Score cartographique = combinaison de présence, activité, volume, fréquence ou récence selon le modèle utilisé

### Chemin principal des données

acteurs Cyclos / Odoo / référentiels locaux
→ actor_territorial_enrichment
→ actor_map_locations
→ routes cartographiques et territoriales
→ cartes, clusters, secteurs

### Fonctions et fichiers principalement concernés

Backend :
- server/sync_actor_territorial_enrichment.py
- server/sync_actor_map_locations.py
- server/sync_actor_map_postal_points.py
- server/sync_actor_map_geocoding.py
- server/services/user_postal_cluster_analytics.py
- server/services/professional_consumption_map_analytics.py
- server/routes/user_postal_clusters.py
- server/routes/user_to_professional_map.py
- server/routes/legacy_api.py

Routes API :
- /api/professionals-map
- /api/territories/zip
- /api/sectors/activity
- /api/user-postal-clusters
- /api/user-to-professional-map

Frontend :
- destroyCartographyMap()
- buildCartographyTooltip()
- formatCartographyLocation()
- renderers cartographiques

### Graphiques et cartes concernés

Cartographie :
- Carte des professionnels
- Carte des clusters
- Carte U → P
- Tableaux territoriaux
- Analyse sectorielle


---

## 9. Soldes et détention monétaire

### Finalité

Les soldes permettent d’observer la détention de monnaie.

Ils répondent à une question différente de celle des transactions :

> Où la monnaie est-elle stockée ?

Les transactions décrivent des mouvements. Les soldes décrivent des stocks.

### Où la trouver dans MLCFlux ?

Localisations principales :

Vue : Pilotage monétaire
Vue associée : Professionnels & particuliers
Routes associées : soldes particuliers et détention

### Mise en forme

Les soldes peuvent être présentés sous forme de :

* séries journalières ;
* distributions ;
* soldes moyens ;
* comparaisons par familles d’acteurs ;
* indicateurs de concentration ;
* cache de détention.

### Interprétation possible

Une forte détention peut signaler :

Une réserve utile.
Un acteur qui prépare des dépenses.
Une accumulation faute de débouchés.
Un blocage de circulation.
Un déséquilibre entre réception et réemploi.

Les soldes doivent être lus avec prudence. Une monnaie stockée n’est pas forcément un problème, mais une accumulation durable peut poser une question de circulation.

### Logique de calcul

Formules générales :


Solde moyen = AVG(solde journalier)

Solde total famille = SUM(solde des acteurs de la famille)

Détention relative = Solde famille / Masse numérique totale

Distribution des soldes = regroupement des acteurs par classes de solde

Évolution de détention = Solde à date B - Solde à date A


### Chemin principal des données


historique de soldes Cyclos
→ cyclos_individual_daily_balances
→ cyclos_professional_daily_balances
→ cyclos_system_daily_balances si disponible
→ caches de détention
→ routes individual-balances et monetary-indicators
→ graphiques de pilotage


### Fonctions et fichiers principalement concernés

Backend :
- server/services/cyclos_individual_daily_balances.py
- server/services/cyclos_professional_daily_balances.py
- server/services/cyclos_system_daily_balances.py
- server/services/individual_balance_analytics.py
- server/services/monetary_holdings_analytics.py
- server/routes/individual_balances.py
- server/routes/monetary_indicators.py

Routes API :
- /api/individual-balances/daily
- /api/individual-balances/distribution
- /api/individual-balances/period-summary
- /api/individual-balances/status
- /api/monetary-indicators/pilotage-holdings-summary
- /api/monetary-indicators/pilotage-holdings-timeseries

### Graphiques concernés
Pilotage monétaire :
- Détention par familles
- Séries de soldes
- Distribution des soldes
- Indicateurs de concentration ou stockage

---

## 10. Réemploi, circulation et multiplicateurs

### Finalité

Le réemploi cherche à savoir ce que devient la monnaie après réception.

Il ne suffit pas qu’un professionnel reçoive de la monnaie locale. La question est aussi :

> La monnaie est-elle ensuite réutilisée dans le réseau ?

Cette fonctionnalité est importante pour mesurer la qualité de circulation d’une monnaie locale.

### Où la trouver dans MLCFlux ?

Localisations principales :

Vue : Pilotage monétaire
Vue : Professionnels & particuliers
Onglet : Circulation
Fiches professionnelles

### Mise en forme

Les indicateurs de réemploi peuvent apparaître sous forme de :

* KPI ;
* séries annuelles ;
* chaînes de circulation ;
* graphes de destinée des flux ;
* fiches par professionnel ;
* perspectives de réemploi.

### Interprétation possible

Un bon réemploi peut signaler :

Un réseau professionnel dense.
Des débouchés suffisants.
Une monnaie qui reste dans le circuit.
Des acteurs capables de redistribuer.

Un faible réemploi peut signaler :

Un manque de fournisseurs.
Une difficulté à dépenser la monnaie.
Une reconversion élevée.
Une concentration chez certains acteurs.
Un besoin d’animation économique.

### Logique de calcul

Formules générales :

Taux de réemploi = Montant réémis / Montant reçu

Taux de réemploi corrigé = Montant réémis / (Montant reçu + conversions reçues)

Chaîne de réemploi = suivi des destinations successives d’une unité ou d’un flux agrégé

Multiplicateur local simplifié = Volume économique généré / Entrée initiale de monnaie

Ces formules doivent être utilisées avec prudence. Le terme “multiplicateur” peut donner une impression de précision scientifique plus forte que ce que les données permettent réellement. Il doit être documenté et relié à son périmètre.

### Chemin principal des données

transactions
→ transaction_semantics
→ agrégats de réemploi
→ services pilotage / professional_chain_fate
→ routes pilotage et professionnels
→ KPI, séries et graphes de circulation

### Fonctions et fichiers principalement concernés

Backend :
- server/services/professional_chain_fate_analytics.py
- server/services/professional_reuse_prospects.py
- server/routes/monetary_indicators.py
- server/routes/professional_reuse_prospects.py

Routes API :
- /api/monetary-indicators/pilotage-reuse-yearly
- /api/monetary-indicators/pilotage-lm3-yearly
- /api/monetary-indicators/pilotage-lm3-chains
- /api/professionals/chain-fate-summary
- /api/pro/<professional_ref>/reuse-prospects

Frontend :
- renderProfessionalCirculationPanel()
- renderProfessionalCirculationCharts()
- rendu des blocs de pilotage monétaire

### Graphiques concernés

Pilotage monétaire :
- Réemploi annuel
- LM3 annuel
- Chaînes LM3

Professionnels & particuliers :
- Circulation professionnelle
- Destinée des flux
- Perspectives de réemploi

---

## 11. Documentation méthodologique

### Finalité

La documentation méthodologique permet d’expliquer l’outil depuis l’intérieur.

Elle doit répondre à trois besoins :

Comprendre ce que l’on voit.
Comprendre comment c’est calculé.
Comprendre quelles limites garder en tête.

### Où la trouver dans MLCFlux ?

Localisation principale :

Vue : Info & méthodologie
Onglets :
- Guide d’usage
- Tables de données
- Archives

### Mise en forme

La documentation est structurée en cartes Markdown.

Chaque carte peut contenir :

* titres ;
* texte explicatif ;
* tableaux ;
* formules ;
* blocs de code ;
* listes ;
* sommaire automatique.

Le rendu Markdown est converti en HTML puis assaini avant affichage, afin de limiter les risques liés à du contenu éditable.

### Logique de fonctionnement

fichiers Markdown
→ service info_content
→ /api/info-content
→ renderInfoView()
→ renderInfoMarkdown()
→ renderInfoMarkdownToc()
→ affichage dans la vue Info & méthodologie

### Fonctions et fichiers principalement concernés
Backend :
- server/services/info_content.py
- server/routes/info_content.py
- server/data/info_pages/
- server/data/info_pages_custom.json
- server/data/info_pages_overrides.json

Routes API :
- GET /api/info-content
- GET /api/info-search-index
- POST /api/info-content
- POST /api/info-pages
- POST /api/info-pages/<page_slug>/metadata

Frontend :
- renderInfoView()
- renderInfoMarkdown()
- renderInfoMarkdownToc()
- bindInfoPageCards()
- bindInfoPageCreator()
- bindInfoEditor()

### Graphiques concernés

Aucun graphique métier direct.

La documentation sert plutôt d’aide transversale à tous les graphiques, KPI et cartes.

---

## 12. Tickets, demandes et améliorations

### Finalité

La partie tickets permet de conserver les retours, demandes, anomalies et pistes d’amélioration.

Elle sert à ne pas perdre les idées et à rendre visible l’évolution du logiciel.

### Où la trouver dans MLCFlux ?

Localisation principale :

Vue : Tickets / Roadmap

### Mise en forme

La vue peut afficher :

* une liste de tickets ;
* des statuts ;
* des messages ;
* une roadmap ;
* des échanges Markdown ;
* des filtres.

### Interprétation possible

Les tickets ne sont pas seulement des bugs. Ils peuvent être :

Des demandes utilisateur.
Des problèmes d’ergonomie.
Des pistes de recherche.
Des limites méthodologiques.
Des besoins de documentation.
Des anomalies de données.
Des idées de nouveaux indicateurs.

### Chemin principal des données

formulaire ou action utilisateur
→ route tickets
→ service tickets
→ tables tickets/messages
→ rendu frontend

### Fonctions et fichiers principalement concernés

Backend :
- server/services/tickets.py
- server/routes/tickets.py

Routes API :
- /api/tickets
- /api/tickets/roadmap
- /api/tickets/<slug>
- /api/tickets/<slug>/messages
- /api/tickets/<slug>/status

Frontend :
- vues tickets dans static/js/app.js
- renderInfoMarkdown() pour les messages Markdown

### Graphiques concernés

Aucun graphique métier direct.

Cette partie relève plutôt du pilotage du développement de MLCFlux.

---

## 13. Administration, comptes et accès

### Finalité

L’administration permet de gérer l’accès à l’outil lorsque l’instance est protégée.

Elle sert à répondre à des questions comme :

Qui peut accéder à quelle MLC ?
Quel rôle possède tel compte ?
Quelles demandes d’accès sont en attente ?
L’intégrité technique est-elle saine ?

### Où la trouver dans MLCFlux ?

Localisations principales :

Page de sélection MLC
Administration des comptes
Administration intégrité

### Mise en forme

L’administration peut afficher :

* état de connexion ;
* instances disponibles ;
* demandes de compte ;
* droits par MLC ;
* rôles ;
* rapports d’intégrité ;
* actions protégées.

### Logique de fonctionnement
utilisateur / session
→ control.db
→ routes auth / admin
→ authentification
→ accès à l'instance MLC configurée


### Fonctions et fichiers principalement concernés

Backend :
- server/routes/auth.py
- server/routes/current_mlc.py
- server/routes/admin_accounts.py
- server/routes/account_requests.py
- server/routes/admin_integrity.py
- server/control_db.py
- server/auth_guards.py
- server/security_middleware.py

Routes API :
- /api/me
- /api/me/password
- /api/current-mlc
- /api/account-requests
- /api/admin/account-requests
- /api/admin/accounts
- /api/admin/integrity/latest
- /api/admin/integrity/reports
- /api/admin/integrity/run

### Graphiques concernés

Aucun graphique métier direct.

L’administration protège l’accès aux données et au pilotage, mais ne constitue pas elle-même une vue d’analyse monétaire.

---

## 14. Résumé transversal des familles fonctionnelles

| Famille                     | Question principale                                       | Données principales                | Vues principales                  |
| --------------------------- | --------------------------------------------------------- | ---------------------------------- | --------------------------------- |
| Activité économique         | La monnaie circule-t-elle ?                               | Transactions qualifiées            | Statistiques globales             |
| Flux                        | Qui échange avec qui ?                                    | Transactions + sémantique          | Stats, réseau, pros, cartes       |
| Conversions / reconversions | Qu’est-ce qui entre ou sort du circuit ?                  | Transactions classées              | Stats, pilotage                   |
| Masse / garanties           | Combien de monnaie existe et avec quelles garanties ?     | Soldes, Odoo, caches               | Pilotage monétaire                |
| Professionnels              | Quels acteurs structurent l’usage ?                       | Transactions, enrichissements pros | Professionnels & particuliers     |
| U → P                       | Les particuliers utilisent-ils la monnaie chez les pros ? | Transactions + localisations       | Carte U → P                       |
| Territoires / secteurs      | Où et dans quels secteurs ça circule ?                    | Enrichissements territoriaux       | Cartographie, analyse sectorielle |
| Soldes                      | Où la monnaie est-elle détenue ?                          | Soldes quotidiens                  | Pilotage, détention               |
| Réemploi                    | La monnaie reçue est-elle réutilisée ?                    | Chaînes de flux                    | Pilotage, circulation pro         |
| Documentation               | Comment lire l’outil ?                                    | Markdown                           | Info & méthodologie               |
| Tickets                     | Comment suivre les besoins et anomalies ?                 | Tickets/messages                   | Roadmap                           |
| Administration              | Qui accède à quoi ?                                       | control.db, sessions, rôles        | Sélection MLC, admin              |

---

## 15. Précautions générales de lecture

Les fonctionnalités de MLCFlux doivent être lues comme des couches complémentaires.

Aucune vue ne suffit seule.

Un bon diagnostic croise généralement :

activité économique
+ masse monétaire

+ conversions / reconversions

+ soldes

+ réemploi

+ carte territoriale

+ connaissance du terrain

Quelques règles de prudence :

* un chiffre élevé n’est pas automatiquement une bonne nouvelle ;


* un chiffre faible n’est pas automatiquement une mauvaise nouvelle ;

* une hausse peut venir d’un événement ponctuel ;

* une baisse peut venir d’une saisonnalité ;

* une carte donne une lecture spatiale, pas une explication complète ;
* un graphe rend visible une structure, mais pas toujours son sens politique ;

* une formule doit toujours être reliée à son périmètre ;

* une donnée sensible doit rester protégée ;

* toute interprétation doit pouvoir être discutée.