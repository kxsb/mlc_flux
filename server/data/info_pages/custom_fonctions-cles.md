# Questions dev front

|Thème|Question courantes|Réponse courte et solide|Où l’illustrer dans le code|
|---|---|---|---|
|Architecture|Pourquoi ne pas avoir utilisé React/Vue ?|Le projet est resté en JavaScript vanilla pour avancer vite avec une architecture simple, mais l’interface est devenue assez riche pour justifier désormais une modularisation progressive.|templates/index.html ; static/js/app.js|
|Architecture|Quel est le principal risque front aujourd’hui ?|Le monolithe `app.js` : il fonctionne, mais il concentre beaucoup de responsabilités. La factorisation a commencé avec `professional_consumption_map.js`.|static/js/app.js ; static/js/professional_consumption_map.js|
|Navigation|Comment une vue est-elle ouverte ?|Le menu sélectionne une valeur `dataView`, puis le dispatch appelle la fonction `render...View()` correspondante.|templates/index.html ; render...View()|
|État|Où est stocké l’état UI ?|Dans `appState`, qui mémorise la vue courante, les caches, les charts, les cartes, le réseau et les tickets.|static/js/app.js : `const appState`|
|Période|Comment le filtre de période agit-il partout ?|Il met à jour l’état global de période, construit une query string et recharge uniquement la vue active avec les nouveaux paramètres.|initPeriodFilter ; getPeriodQueryParam ; reloadCurrentViewForPeriod|
|Période|Pourquoi avoir basculé vers l’année en cours par défaut ?|Pour éviter de charger d’emblée tout l’historique depuis 2019 et améliorer le temps d’entrée dans l’application.|logique `analysisPeriod` / discussions PERF et PERIOD001|
|UX|Qu’avez-vous fait pour réduire la sensation de lenteur ?|Hydratation progressive, refresh doux, conservation du contexte visible et réduction des animations Chart.js.|runProgressiveViewHydration ; shouldPreservePeriodRefreshView ; configureGlobalChartPerformanceDefaults|
|UX|Pourquoi préserver le scroll ?|Parce que les vues sont longues et analytiques ; perdre sa position après un recalcul casse la lecture.|audits UXLOAD002B ; logique de refresh|
|Graphes|Les graphes recalculent-ils les données côté front ?|Non. Le backend livre des séries agrégées ; le front choisit seulement le rendu, les toggles et l’aide.|renderStatsView ; /api/stats_charts|
|Graphes|Pourquoi un toggle Nombre / Volume ?|Parce qu’un volume économique et un nombre d’opérations racontent des choses différentes ; le même graphe peut être lu sous les deux angles.|buildStatsChartMetricToggle|
|Graphes|Pourquoi conserver les séries masquées ?|Pour respecter l’exploration de l’utilisateur et éviter de réinitialiser ses choix à chaque interaction.|applyStatsChartHiddenDatasets|
|Cartographie|Pourquoi MapLibre + deck.gl ?|Pour disposer d’une cartographie moderne capable d’afficher des couches de flux évolutives et performantes.|template libs ; renderCartographyView|
|Cartographie|La carte de bassin de paiement révèle-t-elle les particuliers ?|Non. Les origines sont agrégées par zone postale anonymisée et les routes visibles sont soumises à un seuil de payeurs distincts.|professional consumption map|
|Cartographie|Pourquoi afficher seulement certaines routes ?|Pour protéger l’anonymat et réduire le bruit visuel.|coverage / visible routes dans la carte bassin|
|Cartographie|Que mesure la cartographie des professionnels ?|Elle montre l’offre géolocalisée des professionnels, enrichie et contrôlée, pas la totalité des comptes bruts Cyclos.|renderCartographyView ; `/api/professionals-map`|
|Network|Pourquoi Cytoscape ?|Parce qu’il est mieux adapté à un graphe interactif de relations qu’une librairie de chart classique.|renderNetworkView ; renderNetworkGraph|
|Network|Le network représente quoi aujourd’hui ?|Principalement les relations P→P, avec un état de filtrage et de sélection géré côté front.|appState.network|
|Pros|Pourquoi avoir mis des onglets dans la vue professionnels ?|Pour séparer synthèse, circulation, cartographie/territoires, analyse sectorielle et fiches, sans exploser le menu principal.|setProfessionalAnalysisTab ; updateProfessionalAnalysisTabs|
|Pros|Pourquoi intégrer une carte de bassin dans les fiches/circulation ?|Parce qu’elle apporte une lecture territoriale très parlante des zones d’origine des paiements vers les professionnels.|professional_consumption_map|
|Pros|Comment éviter qu’une fiche pro ouverte depuis le network casse ?|La référence professionnelle est normalisée avant rendu du détail.|normalizeProfessionalDetailRef ; renderProDetail|
|Info|Pourquoi une page méthodologique éditable ?|Parce que MLCFlux produit des indicateurs interprétables uniquement avec leur périmètre ; cette documentation doit évoluer avec l’outil.|renderInfoView ; `/api/info-content`|
|Info|Comment sécuriser le Markdown éditable ?|Markdown parsé puis nettoyé avec DOMPurify avant insertion.|renderInfoMarkdown|
|Sécurité|Les contenus JSON affichés sont-ils échappés ?|Les libellés dynamiques passent par des fonctions d’échappement HTML quand ils sont injectés dans des templates.|escapeHtml|
|Perf|Quel gain a le passage aux agrégats backend ?|On évite de faire transiter tout l’historique transactionnel vers le navigateur pour afficher des KPI et graphes.|OPT001 ; `/api/stats` ; usages front|
|Perf|Pourquoi désactiver les animations Chart.js ?|Les longues séries et nombreux graphiques rendent ces animations coûteuses sans bénéfice fonctionnel notable.|configureGlobalChartPerformanceDefaults|
|CSS|Le design est-il factorisé ?|Il existe des patterns réutilisés — cards, grids, disclosures, aides, modales — mais le CSS a beaucoup grandi et pourra être découpé plus tard.|static/css/style.css|
|Fiabilité|Comment vous évitez les erreurs JS après patch ?|Patchs petits, sauvegardes, diff, puis `node --check` avant restart.|scripts d’audit / pratiques de patch|
|Roadmap|Quel chantier front serait le plus utile pour la suite ?|Continuer la modularisation de `app.js` et stabiliser la nouvelle architecture de navigation « Professionnels & particuliers ».|app.js + modules extraits|
