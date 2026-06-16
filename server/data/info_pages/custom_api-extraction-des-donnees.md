# Écrans ↔ API

|Écran / composant|Fonction frontend|Endpoint / source|Méthode|Ce que ça ramène|Période filtrée ?|Rôle UX|Remarque utile au dev|
|---|---|---|---|---|---|---|---|
|Filtre global de période|initPeriodFilter()|/api/period-bounds|GET|Dates min/max disponibles en base.|Non|Évite des périodes impossibles.|Initialise les bornes des datepickers.|
|Stats globales|renderStatsView()|/api/stats|GET|KPI agrégés de synthèse.|Oui|Affiche les chiffres macro.|Payload allégé côté backend depuis OPT001.|
|Stats globales|renderStatsView()|/api/stats_charts|GET|Séries agrégées pour graphiques.|Oui|Alimente courbes et répartitions.|Calculs lourds backend, le front rend seulement.|
|Network global|renderNetworkView()|/api/network|GET|Nœuds/arêtes réseau.|Oui selon route|Rendu Cytoscape.|Payload mesuré ~37,8 KB sur 2026 et ~151,8 KB historique dans l’audit récent.|
|Liste pros|renderProsView()|/api/pros|GET|Liste / synthèse professionnels selon période.|Oui|Table et points d’entrée vers les fiches.|Utilisé par le front historique.|
|Fiche pro|renderProDetail(...)|/api/pro/<num_professionnel>|GET|Détail principal d’un professionnel.|Oui|Construit la fiche détaillée.|La ref a été normalisée pour les entrées depuis Network.|
|Cartographie pros|renderCartographyView()|/api/professionals-map|GET|Pros géolocalisés avec informations carto.|Selon route|Points sur MapLibre/deck.gl.|Vue historisée dans la refonte carto/territoires.|
|Territoires|renderTerritoriesView()|/api/territories/zip|GET|Agrégats d’activité territoriale par code postal.|Oui|Tableaux / cartes territoriales.|À rattacher à la future Cartographie des clusters selon la refonte.|
|Pilotage monétaire|renderMonetaryPilotageView()|/api/monetary-indicators/pilotage-summary|GET|Synthèse croisée flux Cyclos / stocks Odoo.|Oui|KPI de pilotage.|Fondamental pour les cartes de synthèse.|
|Pilotage monétaire|renderMonetaryPilotageView()|/api/monetary-indicators/pilotage-timeseries|GET|Séries temporelles de pilotage.|Oui|Graphes de pilotage.|Référencé dans le chargement du frontend.|
|Pilotage monétaire|renderMonetaryPilotageView()|/api/monetary-indicators/pilotage-reuse-yearly|GET|Historique annuel du réemploi interne.|Non ou annuel|Graphe de réemploi.|Utilisé par MULT004 front.|
|Pilotage monétaire|renderMonetaryPilotageView()|/api/monetary-indicators/pilotage-lm3-yearly|GET|Historique annuel du LM3 estimé.|Non ou annuel|Graphe LM3.|Permet la lecture temporelle du multiplicateur d’injection.|
|Pilotage monétaire|renderMonetaryPilotageView()|/api/monetary-indicators/pilotage-lm3-chains|GET|Chaînes LM3 détaillées, avec limite.|Oui + limit|Exploration des chaînes.|Référencé côté front avec `limit=50`.|
|Pilotage détention|renderMonetaryPilotageView()|/api/monetary-indicators/pilotage-holdings-summary|GET|Synthèse de détention particuliers/pros.|Oui|KPI de stock et détention.|Affichage coordonné avec la période pilote.|
|Pilotage détention|renderMonetaryPilotageView()|/api/monetary-indicators/pilotage-holdings-timeseries|GET|Séries de détention et dormance.|Oui|Graphes de stocks/parts/dormance.|Couverture dépendante des historiques de soldes.|
|Soldes particuliers|Composants de détention / futurs écrans U|/api/individual-balances/distribution|GET|Distribution des soldes particuliers à une date.|Date|Graphes/distributions.|Route visible dans l’audit POSTCLUSTER001.|
|Soldes particuliers|Composants de détention / futurs écrans U|/api/individual-balances/period-summary|GET|Synthèse de soldes particuliers sur période.|Oui|KPI de détention.|Route visible dans l’audit POSTCLUSTER001.|
|Circulation pros|renderProfessionalCirculationPanel()|/api/professionals/circulation-timeseries|GET|Timeseries mensuelle U→P, P→P, P→U, sorties P→T.|Oui|Graphe circulation.|Ajouté avec PROVIEW004.|
|Bassin de paiement pro|renderProfessionalCirculationPanel() / map renderer|/api/professionals/consumption-map|GET|Routes agrégées code postal -> pro, couverture, sources/destinations.|Oui|Carte de bassins de consommation.|Rendu via canvas dédié, extrait progressivement.|
|Info & méthodologie|renderInfoView()|/api/info-content|GET|Markdown courant.|Non|Lecture de la méthodologie.|Rendu via marked + DOMPurify.|
|Info & méthodologie|renderInfoView()|/api/info-content|POST|Nouveau Markdown.|Non|Édition in-app.|Permet la mise à jour sans éditer directement le fichier.|
|Tickets|renderTicketsView()|/api/tickets|GET|Liste filtrée de tickets.|Filtres, pas période|Suivi des retours.|Filtres dans `appState.tickets.filters`.|
|Ticket détail|renderTicketDetail(slug)|/api/tickets/<slug>|GET|Ticket + messages.|Non|Lecture d’un retour.|Affichage markdown possible dans les messages.|
|Ticket création|renderTicketsView()|/api/tickets|POST|Nouveau ticket.|Non|Création de retour.|Présent dans la brique tickets.|
|Ticket réponse|renderTicketDetail(slug)|/api/tickets/<slug>/messages|POST|Nouveau message dans un ticket.|Non|Discussion / suivi.|Présent dans la brique tickets.|
|Rechargement données|action dédiée dans UI selon route legacy|/api/reload|POST|Déclenchement d’une sync récente.|Non|Action de maintenance depuis l’UI.|À lire avec précaution / sync auth selon état actuel.|
