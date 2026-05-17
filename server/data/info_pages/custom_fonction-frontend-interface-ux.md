# Fonctions front clés

|Domaine|Fichier|Fonction / objet|Rôle technique|Déclencheur / contexte|Donnée ou endpoint lié|Explication humaine|Priorité|
|---|---|---|---|---|---|---|---|
|État|static/js/app.js|appState|Objet global d’état UI : vues, caches, cartes, charts, tickets, network, périodes.|Toute l’application|—|La mémoire vive de l’interface.|Essentiel|
|Performance|static/js/app.js|configureGlobalChartPerformanceDefaults()|Désactive les animations Chart.js pour les dashboards lourds.|Au chargement JS|Chart.js|Les graphes vont au résultat sans animation coûteuse.|Très utile|
|Période|static/js/app.js|initPeriodFilter()|Initialise le sélecteur de période et ses écouteurs.|Démarrage interface|/api/period-bounds|Prépare le filtre d’analyse global.|Essentiel|
|Période|static/js/app.js|applyAnalysisPeriod()|Valide la période choisie puis déclenche le refresh de la vue.|Bouton Appliquer|query `start/end`|On change l’horizon temporel de tout l’écran.|Essentiel|
|Période|static/js/app.js|resetAnalysisPeriod()|Réinitialise la période vers le preset défini.|Bouton Réinitialiser|—|Retour à une période de référence.|Très utile|
|Période|static/js/app.js|getPeriodQueryParam()|Construit la query string envoyée aux APIs.|À chaque fetch filtré|?start=...&end=...|Convertit l’état UI en paramètres serveur.|Essentiel|
|Période|static/js/app.js|reloadCurrentViewForPeriod()|Recharge uniquement la vue active avec la nouvelle période.|Changement de période|render...View(true)|Le même écran se recalcule sans changer de section.|Essentiel|
|UX chargement|static/js/app.js|runProgressiveViewHydration(...)|Affiche un état léger puis hydrate les données.|Entrée dans certaines vues|Selon la vue|On évite la sensation d’écran vide.|Très utile|
|UX refresh|static/js/app.js|shouldPreservePeriodRefreshView(viewKey, forceReload)|Décide si la vue visible doit rester affichée pendant le refresh.|Changement de période|—|Garde le contexte visuel pendant le recalcul.|Très utile|
|Navigation|static/js/app.js|renderStatsView()|Rendu de la vue Statistiques globales.|Vue `stats`|/api/stats ; /api/stats_charts|Porte d’entrée macro de MLCFlux.|Essentiel|
|Navigation|static/js/app.js|renderMonetaryPilotageView()|Rendu de la vue Pilotage monétaire.|Vue `monetary-pilotage`|/api/monetary-indicators/...|Vue croisée flux/stock/pilotage.|Essentiel|
|Navigation|static/js/app.js|renderProsView()|Rendu de la vue professionnels / particuliers.|Vue `pros`|/api/pros + endpoints associés|Espace d’analyse des acteurs du réseau.|Essentiel|
|Navigation|static/js/app.js|renderCartographyView()|Rendu de la cartographie des professionnels.|Vue `cartography`|/api/professionals-map|Carte spatiale de l’offre pro.|Très utile|
|Navigation|static/js/app.js|renderTerritoriesView()|Rendu de l’analyse territoriale.|Vue `territories`|/api/territories/zip|Lecture agrégée par zones.|Très utile|
|Navigation|static/js/app.js|renderSectorsView()|Rendu de l’analyse sectorielle.|Vue `sectors`|route sectorielle dédiée|Lecture par familles d’activité.|Très utile|
|Navigation|static/js/app.js|renderNetworkView()|Rendu de la vue réseau Cytoscape.|Vue `network` / onglet déplacé selon refonte|/api/network|Graphe relationnel interactif.|Très utile|
|Navigation|static/js/app.js|renderTicketsView()|Rendu de la liste de tickets.|Vue `tickets`|/api/tickets|Suivi des retours dans l’interface.|Contexte|
|Navigation|static/js/app.js|renderTicketDetail(slug, feedbackMessage = '')|Rendu du détail d’un ticket.|Ouverture d’un ticket|/api/tickets/<slug>|Lecture fine d’un retour ou d’une discussion.|Contexte|
|Navigation|static/js/app.js|renderInfoView(forceReload = false)|Charge et affiche la page Info & méthodologie.|Vue `info`|/api/info-content|Documentation méthodologique dans l’app.|Très utile|
|Info|static/js/app.js|renderInfoMarkdown(markdown)|Convertit Markdown -> HTML puis sanitise.|Vue Info + tickets messages markdown|marked + DOMPurify|Rendre lisible du texte riche en restant sûr.|Essentiel|
|Info|static/js/app.js|renderInfoMarkdownToc(reader)|Construit le sommaire dynamique à partir des titres.|Après rendu markdown|DOM|Créer un index de navigation dans la méthodo.|Très utile|
|Carto|static/js/app.js|destroyCartographyMap()|Détruit proprement carte + overlay deck.gl.|Changement de vue / rerender|MapLibre + deck.gl|Évite les artefacts et doublons de carte.|Très utile|
|Carto|static/js/app.js|formatCartographyLocation(professional)|Formate ville/code postal pour la tooltip.|Tooltip carto|payload pro carto|Affichage humain de la localisation.|Contexte|
|Carto|static/js/app.js|buildCartographyTooltip(professional)|Construit l’infobulle détaillée d’un professionnel.|Hover/clic carto|payload `/api/professionals-map`|Donne du contexte sans quitter la carte.|Très utile|
|Pros|static/js/app.js|renderProfessionalSummaryKpiCard(label, value, subtext)|Génère une card KPI pour les panels pros.|Synthèse/Circulation|—|Composant visuel réutilisable.|Très utile|
|Pros|static/js/app.js|renderProfessionalSummaryReferenceCard(label, value, subtext)|Génère une card de référence complémentaire.|Synthèse pros|—|Encarts secondaires de lecture.|Contexte|
|Pros|static/js/app.js|renderProfessionalSummaryPanel(flowSummary, holdingsSummary, pilotageSummary)|Assemble la synthèse P/U.|Onglet Synthèse|payloads pros + holdings + pilotage|Vue de haut niveau du rôle des acteurs.|Essentiel|
|Pros|static/js/app.js|destroyProfessionalCirculationCharts()|Détruit les graphs de circulation pro avant rerender.|Refresh onglet circulation|Chart.js|Évite d’empiler des canvas actifs.|Très utile|
|Pros|static/js/app.js|buildProfessionalCirculationFlowsChartConfig(items)|Prépare la config Chart.js des séries de circulation.|Avant création du chart|/api/professionals/circulation-timeseries|Transforme la timeseries en graphe lisible.|Très utile|
|Pros|static/js/app.js|renderProfessionalCirculationCharts()|Rend les graphiques de l’onglet Circulation.|Activation onglet Circulation|timeseries + réemploi pro|Affiche les tendances après ouverture de l’onglet.|Essentiel|
|Pros|static/js/app.js|renderProfessionalCirculationPanel(...)|Assemble les KPI et cartes de circulation professionnelle.|Onglet Circulation|flowSummary + pilotage + chain fate + consumption map|Le grand tableau de bord dynamique des pros.|Essentiel|
|Pros|static/js/app.js|setProfessionalAnalysisTab(tabName)|Change l’onglet actif de la vue pros.|Clic utilisateur|—|Passage d’un angle d’analyse à l’autre.|Essentiel|
|Pros|static/js/app.js|bindProfessionalAnalysisTabs()|Pose les listeners de clic sur les onglets.|Après rendu de la vue pros|DOM|Rend les onglets interactifs.|Très utile|
|Pros|static/js/app.js|updateProfessionalAnalysisTabs()|Synchronise état actif des boutons/panels.|Après clic / init|DOM|Montre le bon panneau et masque les autres.|Très utile|
|Pros|static/js/app.js|drawProsTable()|Rend la liste/tabulation des professionnels.|Vue pros / onglet liste|/api/pros|La liste navigable des professionnels.|Très utile|
|Pros détail|static/js/app.js|renderProDetail(numProf, ...)|Rendu complet d’une fiche professionnel.|Clic dans la liste, network ou autre entrée|/api/pro/<ref>|La fiche détaillée d’un acteur pro.|Essentiel|
|Pros détail|static/js/app.js|normalizeProfessionalDetailRef(...)|Normalise la référence professionnelle avant d’ouvrir la fiche.|Entrées multiples vers une fiche|ref `Pxxxx`|Évite que la fiche casse selon l’origine du clic.|Très utile|
|Consommation map|static/js/app.js|resetProfessionalConsumptionMapRenderCaches()|Réinitialise les caches de rendu de la carte bassin de paiement.|Changement période / payload|consumption map|Évite de redessiner avec de vieux objets.|Très utile|
|Consommation map|static/js/app.js|getProfessionalConsumptionMapFinalRenderPayload(...)|Prépare le payload final utilisable par le renderer canvas.|Après fetch API|/api/professionals/consumption-map|Met en forme les données avant peinture.|Très utile|
|Consommation map|static/js/app.js|restoreProfessionalConsumptionMapDynamicTheme()|Restaure le thème dynamique de la carte.|Après reset/rerender|thème UI|Assure que la carte reste lisible dans le thème courant.|Contexte|
|Consommation map|static/js/app.js / static/js/professional_consumption_map.js|renderProfessionalConsumptionMapCanvas()|Dessine la carte canvas des flux agrégés.|Après rendu du panel circulation|payload final de consommation|Rend visible le bassin de paiement.|Essentiel|
|Stats UX|static/js/app.js|getStatsChartHiddenDatasetMap(chartKey)|Lit l’état des séries masquées pour un graphe.|Graphes stats|appState / cache JS|Se souvenir de ce que l’utilisateur a caché.|Contexte|
|Stats UX|static/js/app.js|applyStatsChartHiddenDatasets(chartKey, chart)|Réapplique la visibilité mémorisée, sans update superflu.|Après création d’un chart|Chart.js|Respecter les choix utilisateur.|Très utile|
|Stats UX|static/js/app.js|buildStatsChartMetricToggle(chartKey, metric)|Construit le switch Nombre / Volume.|Graphes stats|DOM|Comparer les mêmes séries sous deux angles.|Très utile|
|Stats UX|static/js/app.js|famille d’helpers `...HELP` / modal d’aide|Décrit un KPI ou graphe : lecture, périmètre, formule, sources.|Clic bouton aide|catalogues JS|L’interface explique ses propres indicateurs.|Très utile|
|Pilotage|static/js/app.js|buildPilotageInternalReuseHistoryChartConfig(...)|Prépare le graphe historique de réemploi interne.|Vue Pilotage|/api/monetary-indicators/pilotage-reuse-yearly|Visualiser l’évolution de la redépense interne.|Très utile|
|Pilotage|static/js/app.js|renderPilotageInternalReuseHistoryChart(...)|Rend le graphe de réemploi interne.|Vue Pilotage|Chart.js|Afficher la trajectoire annuelle.|Très utile|
|Pilotage|static/js/app.js|catalogue `PILOTAGE_INDICATOR_HELP`|Base texte de lecture pour KPI de pilotage.|Clic aide|valeurs pilotage|Mettre la formule et le sens à portée de main.|Très utile|
|Stats spécifiques|static/js/app.js|buildDevicePrivateAccountsInsightHtml(stats)|Construit un bloc dépliant sur les comptes particuliers de dispositif.|Stats globales si données présentes|stats device accounts|Traiter un cas spécialisé sans le mettre au centre du récit.|Très utile|
|Network|static/js/app.js|appState.network|État du network : seuil, recherche, cy instance, nœud sélectionné, données raw/enriched.|Vue Network|/api/network|Mémoire interactive du graphe.|Très utile|
|Network|static/js/app.js|renderNetworkGraph(...)|Rendu Cytoscape du graphe.|Après fetch network|/api/network|Transforme le JSON réseau en interaction visuelle.|Très utile|
|Network|static/js/app.js|bindNetworkSearchOutsideClick()|Ferme probablement certains résultats/autocomplete au clic extérieur.|Init UI network|DOM|Comportement d’interface plus propre.|Contexte|
|Thème|static/js/app.js|initThemeToggle()|Initialise le bouton de thème.|Boot application|local/UI state|Basculer clair/sombre.|Contexte|
|Sidebar|static/js/app.js|initSidebarCollapse()|Initialise le repli de la sidebar.|Boot application|DOM|Récupérer de la place pour les vues denses.|Contexte|
|Utilitaires|static/js/app.js|apiGet(url)|Fetch GET JSON standardisé avec gestion d’erreur.|Presque toutes les vues|Endpoints internes|Un point de passage commun pour lire l’API.|Essentiel|
|Utilitaires|static/js/app.js|apiPostJson(url, payload)|Fetch POST JSON standardisé.|Info markdown, tickets, actions|Endpoints POST|Un point de passage commun pour écrire.|Très utile|
|Utilitaires|static/js/app.js|setTitle(title)|Met à jour le titre principal de la vue.|À chaque rendu de vue|DOM|Clarifie immédiatement l’écran actif.|Contexte|
|Utilitaires|static/js/app.js|escapeHtml(text)|Échappe des chaînes injectées dans des templates HTML.|Rendu dynamique de labels|données JSON|Empêcher qu’un label devienne du HTML exécuté.|Essentiel|
|Utilitaires|static/js/app.js|euro(value) / formatters `format...`|Formatent montants, ratios, entiers et libellés.|Affichage KPI/graphiques|—|Affichage cohérent en français.|Contexte|
