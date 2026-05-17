const content = document.getElementById("content");
const pageTitle = document.getElementById("pageTitle");
const reloadButton = document.getElementById("reloadButton");

const appState = {
  currentView: "stats",

  periodBounds: {
    min: null,
    max: null
  },

  analysisPeriod: {
    preset: "all",
    start: null,
    end: null
  },

  periodRefreshInProgress: false,

  // Préparation de l'analyse comparative : non exploitée pour l'instant,
  // mais l'état est déjà distinct de la période principale.
  comparisonPeriod: null,

  statsCache: {},
  dailyChartMetric: "count",
  dailyChartHiddenDatasets: {},

  prosSearch: "",
  prosSearchDebounce: null,
  prosSortBy: "Total Reçu",
  prosSortDir: "desc",
  prosData: [],


  detailSortBy: "Date",
  detailSortDir: "desc",
  detailPage: 1,
  detailPageSize: 50,
  detailMode: "all",
  detailData: null,
  currentPro: null,
  proTab: "data",

  charts: {
    activity: null,
    balance: null,
    globalDailyCount: null,
    globalWeeklyAvg: null,
    globalHourly: null,
    globalWeekday: null,
    globalCumulative: null,
    monetaryStockHistory: null,
    pilotageRotation: null,
    pilotageFlowRhythm: null,
    pilotageRetention: null,
    pilotageInternalReuseHistory: null,
    pilotageLm3History: null,
    pilotageHoldingsStockShare: null,
    pilotageHoldingsMassComposition: null,
    pilotageHoldingsMobilization: null,
    pilotageHoldingsDormancy: null
  },

  network: {
    minEdgeWeight: 500,
    includeOperators: false,
    searchTerm: "",
    cy: null,
    selectedNodeId: null,
    hoveredNodeId: null,
    rawData: null,
    enrichedData: null
  },

  cartography: {
    data: null,
    map: null,
    overlay: null
  },

  territories: {
    data: null
  },

  sectors: {
    data: null
  },

  monetaryIndicators: {
    periodSummary: null,
    daily: null
  },

      info: {
    pages: null,
    activePage: null,
    markdown: null,
    searchIndex: null
  },

  tickets: {
    filters: {
      q: "",
      category: "",
      status: "open",
      sort: "last_activity"
    },
    createFormOpen: false,
    lastList: null,
    currentSlug: null,
    currentDetail: null
  }
};



function configureGlobalChartPerformanceDefaults() {
  if (!window.Chart || !window.Chart.defaults) {
    return;
  }

  // MLCFlux affiche surtout des tableaux de bord analytiques.
  // Les animations d'entrée coûtent cher sur les longues séries
  // et n'apportent pas de valeur fonctionnelle ici.
  window.Chart.defaults.animation = false;
  window.Chart.defaults.animations = {};
}

configureGlobalChartPerformanceDefaults();

function destroyCartographyMap() {
  const cartography = appState.cartography;

  if (cartography.map && cartography.overlay) {
    try {
      cartography.map.removeControl(cartography.overlay);
    } catch (_err) {
      // Le contrôle a pu être déjà détaché lors d'un changement de vue.
    }
  }

  if (cartography.map) {
    try {
      cartography.map.remove();
    } catch (_err) {
      // La carte a pu être déjà détruite avec son conteneur.
    }
  }

  cartography.map = null;
  cartography.overlay = null;
}

function formatCartographyLocation(professional) {
  const city = String(professional.cyclos_city || professional.city || "").trim();
  const zip = String(professional.cyclos_zip || professional.zip || "").trim();

  if (city && zip) return `${city} (${zip})`;
  return city || zip || "Localisation confirmée";
}

function buildCartographyTooltip(professional) {
  const title = `${professional.professional_ref} — ${professional.odoo_name}`;
  const industry = professional.industry_name || "Secteur non renseigné";
  const activity = professional.detailed_activity || "";
  const location = formatCartographyLocation(professional);

  const score = Number(professional.activity_score || 0);
  const lorenzReliefScore = Number(professional.lorenz_relief_score || 0);
  const flowRank = Number(professional.flow_rank || 0);
  const totalFlowShare = Number(professional.total_flow_share || 0);
  const receivedVolume = Number(professional.received_volume || 0);
  const emittedVolume = Number(professional.emitted_volume || 0);
  const totalFlowVolume = Number(professional.total_flow_volume || 0);
  const receivedCount = Number(professional.received_count || 0);
  const emittedCount = Number(professional.emitted_count || 0);

  return {
    html: `
      <div class="cartography-tooltip">
        <div class="cartography-tooltip-title">${escapeHtml(title)}</div>
        <div class="cartography-tooltip-line">${escapeHtml(industry)}</div>
        ${activity ? `<div class="cartography-tooltip-line">${escapeHtml(activity)}</div>` : ""}
        <div class="cartography-tooltip-location">${escapeHtml(location)}</div>

        <div class="cartography-tooltip-hint">
          <strong>Indice d’activité composite :</strong> ${score.toLocaleString("fr-FR", {
            minimumFractionDigits: 3,
            maximumFractionDigits: 3
          })}
        </div>

        <div class="cartography-tooltip-line">
          <strong>Volume brassé :</strong>
          ${totalFlowVolume.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} G
          ${flowRank ? `· rang ${flowRank}` : ""}
        </div>

        <div class="cartography-tooltip-line">
          Part du volume brassé :
          ${(totalFlowShare * 100).toLocaleString("fr-FR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
          })} %
          · relief Lorenz ${lorenzReliefScore.toLocaleString("fr-FR", {
            minimumFractionDigits: 3,
            maximumFractionDigits: 3
          })}
        </div>

        <div class="cartography-tooltip-line">
          Reçu : ${receivedVolume.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} G
          · ${receivedCount.toLocaleString("fr-FR")} transaction${receivedCount > 1 ? "s" : ""}
        </div>

        <div class="cartography-tooltip-line">
          Émis : ${emittedVolume.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} G
          · ${emittedCount.toLocaleString("fr-FR")} transaction${emittedCount > 1 ? "s" : ""}
        </div>

        <div class="cartography-tooltip-hint">Cliquer pour ouvrir la fiche</div>
      </div>
    `,
    style: {
      backgroundColor: "rgba(17, 24, 39, 0.96)",
      color: "#ffffff",
      borderRadius: "12px",
      padding: "10px 12px",
      maxWidth: "380px",
      fontSize: "13px",
      lineHeight: "1.45"
    }
  };
}

function fitCartographyMapToProfessionals(map, professionals) {
  if (!map || !window.maplibregl || !professionals.length) return;

  const bounds = new window.maplibregl.LngLatBounds();
  let validCount = 0;

  professionals.forEach(professional => {
    const longitude = Number(professional.longitude);
    const latitude = Number(professional.latitude);

    if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
      return;
    }

    bounds.extend([longitude, latitude]);
    validCount += 1;
  });

  if (!validCount) return;

  map.fitBounds(bounds, {
    padding: 64,
    maxZoom: 13,
    duration: 700
  });
}



function getCartographyActivityColor(activityScore) {
  const score = Math.max(0, Math.min(1, Number(activityScore || 0)));

  // Palette froide, progressive et semi-transparente :
  // le relief reste lisible sans donner un rendu trop saturé.
  if (score < 0.25) return [56, 189, 248, 78];
  if (score < 0.50) return [59, 130, 246, 108];
  if (score < 0.75) return [99, 102, 241, 138];
  return [168, 85, 247, 178];
}


function addCartographyPixelOffsets(professionals) {
  const groups = new Map();

  professionals.forEach(professional => {
    const latitude = Number(professional.latitude);
    const longitude = Number(professional.longitude);

    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      professional.pixelOffset = [0, 0];
      return;
    }

    // Arrondi suffisamment fin pour capter les coordonnées effectivement identiques
    // issues de la géolocalisation Cyclos, sans regrouper abusivement des adresses proches.
    const key = `${latitude.toFixed(6)}|${longitude.toFixed(6)}`;

    if (!groups.has(key)) {
      groups.set(key, []);
    }

    groups.get(key).push(professional);
  });

  groups.forEach(group => {
    if (group.length === 1) {
      group[0].pixelOffset = [0, 0];
      return;
    }

    const radius = group.length === 2 ? 14 : 18;

    group.forEach((professional, index) => {
      const angle = (-Math.PI / 2) + ((2 * Math.PI * index) / group.length);

      professional.pixelOffset = [
        Math.round(Math.cos(angle) * radius),
        Math.round(Math.sin(angle) * radius)
      ];
    });
  });

  return professionals;
}


function initializeProfessionalsMap(professionals, options = {}) {
  const containerId = options.containerId || "professionalsMap";
  const fitButtonId = options.fitButtonId || "cartographyFitBtn";
  const mapStateKey = options.mapStateKey || "map";
  const overlayStateKey = options.overlayStateKey || "overlay";
  const mapNode = document.getElementById(containerId);
  if (!mapNode) return;

  if (!professionals.length) {
    mapNode.innerHTML = `
      <div class="cartography-map-empty">
        Aucun professionnel confirmé à afficher.
      </div>
    `;
    return;
  }

  if (
    !window.maplibregl ||
    !window.deck ||
    !window.deck.MapboxOverlay ||
    !window.deck.IconLayer ||
    !window.deck.ColumnLayer
  ) {
    mapNode.innerHTML = `
      <div class="cartography-map-empty">
        Les bibliothèques cartographiques ne sont pas disponibles.
      </div>
    `;
    return;
  }

  const map = new window.maplibregl.Map({
    container: containerId,
    style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    center: [4.8357, 45.7640],
    zoom: 9,
    pitch: 52,
    bearing: -12
  });

  // Empêche la carte de capturer le scroll de page.
  map.scrollZoom.disable();

  map.addControl(new window.maplibregl.NavigationControl(), "top-right");

  const { MapboxOverlay, IconLayer, ColumnLayer } = window.deck;
  const displayProfessionals = addCartographyPixelOffsets(
    professionals.map(professional => ({ ...professional }))
  );

  const reliefProfessionals = displayProfessionals.filter(professional =>
    Number(professional.activity_score || 0) > 0
  );

  const professionalPointIcon = {
    url: "/static/img/cartography-professional-point.svg",
    width: 36,
    height: 36,
    anchorX: 18,
    anchorY: 18
  };

  const activityColumnsLayer = new ColumnLayer({
    id: "professional-activity-columns",
    data: reliefProfessionals,
    pickable: true,
    autoHighlight: true,
    extruded: true,
    diskResolution: 36,
    radius: 115,
    coverage: 0.92,
    radiusUnits: "meters",
    elevationScale: 8500,
    flatShading: false,
    material: {
      ambient: 0.58,
      diffuse: 0.52,
      shininess: 18,
      specularColor: [0.12, 0.12, 0.16]
    },
    getPosition: professional => [
      Number(professional.longitude),
      Number(professional.latitude)
    ],
    getElevation: professional => Number(professional.lorenz_relief_score || 0),
    getFillColor: professional => getCartographyActivityColor(professional.lorenz_relief_score),
    highlightColor: [15, 23, 42, 180],
    onClick: ({ object }) => {
      if (object && object.professional_ref) {
        renderProDetail(object.professional_ref);
      }
    }
  });

  const professionalMarkersLayer = new IconLayer({
    id: "confirmed-professionals",
    data: displayProfessionals,
    pickable: true,
    autoHighlight: true,
    getPosition: professional => [
      Number(professional.longitude),
      Number(professional.latitude)
    ],
    getIcon: () => professionalPointIcon,
    getSize: 20,
    sizeUnits: "pixels",
    getPixelOffset: professional => professional.pixelOffset || [0, 0],
    highlightColor: [15, 23, 42, 180],
    onClick: ({ object }) => {
      if (object && object.professional_ref) {
        renderProDetail(object.professional_ref);
      }
    }
  });

  const overlay = new MapboxOverlay({
    interleaved: false,
    layers: [activityColumnsLayer, professionalMarkersLayer],
    getTooltip: ({ object }) => object ? buildCartographyTooltip(object) : null
  });

  map.once("load", () => {
    map.addControl(overlay);
    fitCartographyMapToProfessionals(map, professionals);
  });

  const fitButton = document.getElementById(fitButtonId);
  if (fitButton) {
    fitButton.addEventListener("click", () => {
      fitCartographyMapToProfessionals(map, professionals);
    });
  }

  appState.cartography[mapStateKey] = map;
  appState.cartography[overlayStateKey] = overlay;

  return map;
}


function formatTerritoryPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return percent(Number(value) * 100);
}

function buildTerritoryRankingHtml(territories) {
  const topTerritories = territories.slice(0, 10);
  const maxReceivedVolume = Math.max(
    ...topTerritories.map(territory => Number(territory.received_volume || 0)),
    0
  );

  if (!topTerritories.length || maxReceivedVolume <= 0) {
    return `<div class="territory-empty-state">Aucune activité territoriale sur la période.</div>`;
  }

  return `
    <div class="territory-ranking-list">
      ${topTerritories.map(territory => {
        const width = maxReceivedVolume > 0
          ? (Number(territory.received_volume || 0) / maxReceivedVolume) * 100
          : 0;

        const label = [
          territory.zip_code,
          territory.city_label
        ].filter(Boolean).join(" — ");

        return `
          <div class="territory-ranking-row">
            <div class="territory-ranking-label">
              ${escapeHtml(label || territory.zip_code)}
            </div>
            <div class="territory-ranking-bar-track">
              <div class="territory-ranking-bar" style="width: ${width.toFixed(1)}%;"></div>
            </div>
            <div class="territory-ranking-value">
              ${euro(territory.received_volume || 0)}
            </div>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function buildTerritoriesTableHtml(territories) {
  if (!territories.length) {
    return `<div class="territory-empty-state">Aucun territoire exploitable sur la période.</div>`;
  }

  return `
    <div class="territory-table-wrap">
      <table class="territory-table">
        <thead>
          <tr>
            <th>Code postal</th>
            <th>Ville(s)</th>
            <th>Pros</th>
            <th>Pros actifs</th>
            <th>Gonettes reçues</th>
            <th>Gonettes émises</th>
            <th>Réutilisation</th>
            <th>Part du reçu</th>
          </tr>
        </thead>
        <tbody>
          ${territories.map(territory => `
            <tr>
              <td><strong>${escapeHtml(territory.zip_code || "—")}</strong></td>
              <td>${escapeHtml(territory.city_label || "—")}</td>
              <td>${Number(territory.professional_count || 0).toLocaleString("fr-FR")}</td>
              <td>${Number(territory.active_professional_count || 0).toLocaleString("fr-FR")}</td>
              <td>${euro(territory.received_volume || 0)}</td>
              <td>${euro(territory.emitted_volume || 0)}</td>
              <td>${formatTerritoryPercent(territory.reuse_rate)}</td>
              <td>${formatTerritoryPercent(territory.received_volume_share)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}


function formatSectorPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return percent(Number(value) * 100);
}

function buildSectorRankingHtml(sectors) {
  const topSectors = sectors.slice(0, 12);
  const maxReceivedVolume = Math.max(
    ...topSectors.map(sector => Number(sector.received_volume || 0)),
    0
  );

  if (!topSectors.length || maxReceivedVolume <= 0) {
    return `<div class="sector-empty-state">Aucune activité sectorielle sur la période.</div>`;
  }

  return `
    <div class="sector-ranking-list">
      ${topSectors.map(sector => {
        const width = maxReceivedVolume > 0
          ? (Number(sector.received_volume || 0) / maxReceivedVolume) * 100
          : 0;

        return `
          <div class="sector-ranking-row">
            <div class="sector-ranking-label">
              ${escapeHtml(sector.sector_name || "Secteur non renseigné")}
            </div>
            <div class="sector-ranking-bar-track">
              <div class="sector-ranking-bar" style="width: ${width.toFixed(1)}%;"></div>
            </div>
            <div class="sector-ranking-value">
              ${euro(sector.received_volume || 0)}
            </div>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function buildSectorReceiptsMixHtml(sectors) {
  const topSectors = sectors
    .filter(sector => Number(sector.received_volume || 0) > 0)
    .slice(0, 12);

  if (!topSectors.length) {
    return `<div class="sector-empty-state">Aucune ventilation des recettes sur la période.</div>`;
  }

  return `
    <div class="sector-mix-list">
      ${topSectors.map(sector => {
        const c2b = Number(sector.c2b_received_share || 0) * 100;
        const b2b = Number(sector.b2b_received_share || 0) * 100;
        const other = Number(sector.other_received_share || 0) * 100;

        return `
          <div class="sector-mix-row">
            <div class="sector-mix-label">
              ${escapeHtml(sector.sector_name || "Secteur non renseigné")}
            </div>

            <div class="sector-mix-bar" title="C2B ${c2b.toFixed(1)} % · B2B ${b2b.toFixed(1)} % · autres ${other.toFixed(1)} %">
              <span class="sector-mix-c2b" style="width: ${c2b.toFixed(2)}%;"></span>
              <span class="sector-mix-b2b" style="width: ${b2b.toFixed(2)}%;"></span>
              <span class="sector-mix-other" style="width: ${other.toFixed(2)}%;"></span>
            </div>

            <div class="sector-mix-meta">
              C2B ${c2b.toFixed(0)} %
              · B2B ${b2b.toFixed(0)} %
            </div>
          </div>
        `;
      }).join("")}
    </div>

    <div class="sector-mix-legend">
      <span><i class="sector-legend-c2b"></i> Particuliers → pros</span>
      <span><i class="sector-legend-b2b"></i> Pros → pros</span>
      <span><i class="sector-legend-other"></i> Autres flux</span>
    </div>
  `;
}

function buildSectorsTableHtml(sectors) {
  if (!sectors.length) {
    return `<div class="sector-empty-state">Aucun secteur exploitable sur la période.</div>`;
  }

  return `
    <div class="sector-table-wrap">
      <table class="sector-table">
        <thead>
          <tr>
            <th>Secteur</th>
            <th>Pros</th>
            <th>Pros actifs</th>
            <th>Gonettes reçues</th>
            <th>Gonettes émises</th>
            <th>Réutilisation</th>
            <th>Part du reçu</th>
            <th>C2B reçu</th>
            <th>B2B reçu</th>
          </tr>
        </thead>
        <tbody>
          ${sectors.map(sector => `
            <tr>
              <td><strong>${escapeHtml(sector.sector_name || "Secteur non renseigné")}</strong></td>
              <td>${Number(sector.professional_count || 0).toLocaleString("fr-FR")}</td>
              <td>${Number(sector.active_professional_count || 0).toLocaleString("fr-FR")}</td>
              <td>${euro(sector.received_volume || 0)}</td>
              <td>${euro(sector.emitted_volume || 0)}</td>
              <td>${formatSectorPercent(sector.reuse_rate)}</td>
              <td>${formatSectorPercent(sector.received_volume_share)}</td>
              <td>${formatSectorPercent(sector.c2b_received_share)}</td>
              <td>${formatSectorPercent(sector.b2b_received_share)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

async function renderSectorsView(forceReload = false) {
  const preserveVisibleView = shouldPreservePeriodRefreshView("sectors", forceReload);

  destroyCartographyMap();

  appState.currentView = "sectors";
  syncSidebarView("sectors");
  setTitle("Analyse sectorielle");

  if (!preserveVisibleView) {
    content.innerHTML = `<div class="card">Chargement de l’analyse sectorielle...</div>`;
  }

  if (!appState.sectors.data || forceReload) {
    appState.sectors.data = await apiGet(`/api/sectors/activity${getPeriodQueryParam()}`);
  }

  const data = appState.sectors.data || {};
  const summary = data.summary || {};
  const sectors = Array.isArray(data.sectors) ? data.sectors : [];

  content.innerHTML = `
    <section class="card sector-overview-card">
      <div class="sector-overview-header">
        <div>
          <div class="stat-label">Activité monétaire par secteur principal</div>
          <h2>${Number(summary.sector_count || 0).toLocaleString("fr-FR")} secteurs analysés</h2>
          <p>
            Cette vue répartit l’activité numérique des professionnels par secteur principal :
            volume reçu, volume réémis, réutilisation et origine des recettes.
          </p>
        </div>

        <div class="sector-kpis">
          <div class="sector-kpi">
            <strong>${Number(summary.professionals_with_sector || 0).toLocaleString("fr-FR")}</strong>
            <span>pros sectorisés</span>
          </div>
          <div class="sector-kpi">
            <strong>${Number(summary.active_professionals_with_sector || 0).toLocaleString("fr-FR")}</strong>
            <span>pros actifs sectorisés</span>
          </div>
          <div class="sector-kpi">
            <strong>${formatSectorPercent(summary.overall_reuse_rate)}</strong>
            <span>réutilisation globale</span>
          </div>
        </div>
      </div>

      <div class="sector-flow-grid">
        <div class="sector-flow-card">
          <span>Gonettes reçues</span>
          <strong>${euro(summary.total_received_volume || 0)}</strong>
        </div>
        <div class="sector-flow-card">
          <span>Gonettes émises</span>
          <strong>${euro(summary.total_emitted_volume || 0)}</strong>
        </div>
        <div class="sector-flow-card">
          <span>Volume total brassé</span>
          <strong>${euro(summary.total_flow_volume || 0)}</strong>
        </div>
      </div>

      <div class="sector-quality-note">
        ${Number(summary.professionals_without_sector || 0).toLocaleString("fr-FR")} professionnel(s)
        restent sans secteur principal renseigné.
        Sur les recettes sectorialisées :
        ${euro(summary.total_c2b_received_volume || 0)} proviennent des particuliers,
        ${euro(summary.total_b2b_received_volume || 0)} des autres professionnels.
      </div>
    </section>

    <section class="card sector-ranking-card">
      <div class="sector-section-heading">
        <h3>Principaux secteurs par gonettes reçues</h3>
      </div>
      ${buildSectorRankingHtml(sectors)}
    </section>

    <section class="card sector-mix-card">
      <div class="sector-section-heading">
        <h3>Origine des recettes : C2B / B2B</h3>
      </div>
      ${buildSectorReceiptsMixHtml(sectors)}
    </section>

    <section class="card sector-table-card">
      <div class="sector-section-heading">
        <h3>Détail par secteur</h3>
      </div>
      ${buildSectorsTableHtml(sectors)}
    </section>
  `;
}


async function renderTerritoriesView(forceReload = false) {
  const preserveVisibleView = shouldPreservePeriodRefreshView("territories", forceReload);

  destroyCartographyMap();

  appState.currentView = "territories";
  syncSidebarView("territories");
  setTitle("Analyse territoriale — codes postaux");

  if (!preserveVisibleView) {
    content.innerHTML = `<div class="card">Chargement de l’analyse territoriale...</div>`;
  }

  if (!appState.territories.data || forceReload) {
    appState.territories.data = await apiGet(`/api/territories/zip${getPeriodQueryParam()}`);
  }

  const data = appState.territories.data || {};
  const summary = data.summary || {};
  const territories = Array.isArray(data.territories) ? data.territories : [];

  content.innerHTML = `
    <section class="card territory-overview-card">
      <div class="territory-overview-header">
        <div>
          <div class="stat-label">Activité monétaire territorialisée</div>
          <h2>${Number(summary.territory_count || 0).toLocaleString("fr-FR")} codes postaux analysés</h2>
          <p>
            Cette vue ventile l’activité numérique des professionnels par code postal :
            gonettes reçues, gonettes réémises et taux de réutilisation territorial.
          </p>
        </div>

        <div class="territory-kpis">
          <div class="territory-kpi">
            <strong>${Number(summary.territorialized_professional_count || 0).toLocaleString("fr-FR")}</strong>
            <span>pros rattachés à un CP</span>
          </div>
          <div class="territory-kpi">
            <strong>${Number(summary.territorialized_active_professional_count || 0).toLocaleString("fr-FR")}</strong>
            <span>pros actifs</span>
          </div>
          <div class="territory-kpi">
            <strong>${formatTerritoryPercent(summary.overall_reuse_rate)}</strong>
            <span>réutilisation globale</span>
          </div>
        </div>
      </div>

      <div class="territory-flow-grid">
        <div class="territory-flow-card">
          <span>Gonettes reçues territorialisées</span>
          <strong>${euro(summary.territorialized_received_volume || 0)}</strong>
        </div>
        <div class="territory-flow-card">
          <span>Gonettes émises territorialisées</span>
          <strong>${euro(summary.territorialized_emitted_volume || 0)}</strong>
        </div>
        <div class="territory-flow-card">
          <span>Volume total brassé</span>
          <strong>${euro(summary.territorialized_total_flow_volume || 0)}</strong>
        </div>
      </div>

      <div class="territory-quality-note">
        Couverture :
        ${formatTerritoryPercent(summary.received_volume_coverage)} du volume reçu
        et ${formatTerritoryPercent(summary.emitted_volume_coverage)} du volume émis
        sont rattachés à un code postal.
        ${Number(summary.professionals_without_zip || 0).toLocaleString("fr-FR")} professionnel(s)
        enrichi(s) restent sans code postal exploitable.
      </div>
    </section>

    <section class="card territory-ranking-card">
      <div class="territory-section-heading">
        <h3>Principaux territoires par gonettes reçues</h3>
      </div>
      ${buildTerritoryRankingHtml(territories)}
    </section>

    <section class="card territory-table-card">
      <div class="territory-section-heading">
        <h3>Détail par code postal</h3>
      </div>
      ${buildTerritoriesTableHtml(territories)}
    </section>
  `;
}


async function renderCartographyView(forceReload = false) {
  const preserveVisibleView = shouldPreservePeriodRefreshView("cartography", forceReload);

  if (!preserveVisibleView) {
    destroyCartographyMap();
  }

  appState.currentView = "cartography";
  syncSidebarView("cartography");
  setTitle("Cartographie des professionnels");

  if (!preserveVisibleView) {
    content.innerHTML = `<div class="card">Chargement de la cartographie...</div>`;
  }

  if (!appState.cartography.data || forceReload) {
    appState.cartography.data = await apiGet(`/api/professionals-map${getPeriodQueryParam()}`);
  }

  const data = appState.cartography.data || {};
  const summary = data.summary || {};
  const professionals = Array.isArray(data.professionals) ? data.professionals : [];

  if (preserveVisibleView) {
    destroyCartographyMap();
  }

  content.innerHTML = `
    <section class="card cartography-overview-card">
      <div class="cartography-overview-header">
        <div>
          <div class="stat-label">Référentiel géographique confirmé</div>
          <h2>${summary.cartographiable_count ?? professionals.length} professionnels affichés</h2>
          <p>
            La carte montre les professionnels dont la position Odoo est confirmée
            par Cyclos avec un écart inférieur ou égal à 1 km.
            Le relief 3D représente la concentration du volume monétaire brassé
            sur la période sélectionnée.
          </p>
        </div>

        <div class="cartography-kpis">
          <div class="cartography-kpi">
            <strong>${summary.total_enriched ?? 0}</strong>
            <span>pros enrichis</span>
          </div>
          <div class="cartography-kpi">
            <strong>${summary.confirmed ?? 0}</strong>
            <span>confirmés</span>
          </div>
          <div class="cartography-kpi">
            <strong>${summary.mismatch ?? 0}</strong>
            <span>divergences</span>
          </div>
        </div>
      </div>

      <div class="cartography-quality-note">
        Non affichés :
        ${summary.no_odoo_coordinates ?? 0} sans coordonnées Odoo,
        ${summary.no_cyclos_coordinates ?? 0} sans coordonnées Cyclos,
        ${summary.no_cyclos_address ?? 0} sans adresse Cyclos.
      </div>
    </section>

    <section class="card cartography-map-card">
      <div class="cartography-map-toolbar">
        <div>
          <strong>${professionals.length}</strong> points confirmés · relief d’activité monétaire.
        </div>
        <button id="cartographyFitBtn" class="secondary-btn" type="button">
          Recentrer
        </button>
      </div>

      <div id="professionalsMap" class="cartography-map"></div>
    </section>
  `;

  initializeProfessionalsMap(professionals);
}


function buildNetworkApiUrl() {
  const periodQuery = getPeriodQueryParam();
  const includeOperators = Boolean(appState.network.includeOperators);

  if (!includeOperators) {
    return `/api/network${periodQuery}`;
  }

  const connector = periodQuery ? "&" : "?";
  return `/api/network${periodQuery}${connector}include_operators=1`;
}


function buildProfessionalNetworkPanelLoadingHtml() {
  return `
    <section class="card professional-analysis-roadmap-card">
      <div class="professional-analysis-section-heading">
        <div class="stat-label">Réseau interprofessionnel</div>
        <h3>Chargement de l’atlas relationnel…</h3>
        <p>
          Les relations P→P sont recalculées pour la période et le périmètre actuellement sélectionnés.
        </p>
      </div>
    </section>
  `;
}

function buildProfessionalNetworkPanelErrorHtml() {
  return `
    <section class="card professional-analysis-roadmap-card">
      <div class="professional-analysis-section-heading">
        <div class="stat-label">Réseau interprofessionnel</div>
        <h3>Le graphe relationnel n’est pas disponible</h3>
        <p>
          Les données réseau n’ont pas pu être chargées pour cette période.
          Les autres onglets restent utilisables.
        </p>
      </div>
    </section>
  `;
}

function buildProfessionalNetworkPanelHtml() {
  return `
    <section class="card network-atlas-hero">
      <div class="network-atlas-hero-main">
        <div class="stat-label">Réseau interprofessionnel · flux P→P</div>
        <h2>Atlas relationnel de la circulation entre professionnels</h2>
        <p>
          Ce graphe représente les relations monétaires <strong>professionnel → professionnel</strong>
          observées sur la période sélectionnée. Chaque nœud correspond à un professionnel relié
          au moins une fois à un autre professionnel ; chaque lien cumule le volume des paiements
          orientés entre deux acteurs.
        </p>

        <div class="network-atlas-method-note">
          <strong>Périmètre actuel.</strong>
          Cette première lecture porte sur le cœur <strong>P→P</strong> du réseau.
          Les comptes opérateurs <strong>P0000 / P9999</strong> sont
          <strong>exclus par défaut</strong> afin de ne pas confondre l’infrastructure associative
          avec le tissu d’échanges interprofessionnels. Ils peuvent être réintégrés via l’option
          d’exploration ci-dessous.
        </div>
      </div>

      <div class="network-atlas-kpi-grid">
        <article class="network-atlas-kpi">
          <span>Acteurs visibles</span>
          <strong id="networkVisibleNodeCount">—</strong>
          <small>Professionnels conservés après seuil.</small>
        </article>

        <article class="network-atlas-kpi">
          <span>Relations visibles</span>
          <strong id="networkVisibleEdgeCount">—</strong>
          <small>Liens P→P au-dessus du seuil.</small>
        </article>

        <article class="network-atlas-kpi">
          <span>Volume relationnel visible</span>
          <strong id="networkVisibleVolume">—</strong>
          <small>Somme des liens actuellement affichés.</small>
        </article>

        <article class="network-atlas-kpi">
          <span>Seuil de relation</span>
          <strong id="networkVisibleThreshold">—</strong>
          <small>Filtre appliqué au volume cumulé.</small>
        </article>
      </div>
    </section>

    <section class="card network-atlas-workbench">
      <div class="network-atlas-workbench-header">
        <div>
          <div class="stat-label">Exploration navigable</div>
          <h3>Filtrer, chercher, isoler un voisinage</h3>
          <p>
            Ajuste le seuil pour faire émerger les relations structurantes, recherche un acteur,
            puis clique sur un nœud pour isoler son voisinage visible et lire ses flux entrants
            et sortants.
          </p>
        </div>
      </div>

      <div class="network-toolbar network-atlas-toolbar">
        <div class="network-search-box">
          <input
            id="networkSearch"
            type="text"
            placeholder="Rechercher un professionnel : P0512, Biocoop, Melting..."
            value="${escapeHtml(appState.network.searchTerm)}"
          />
          <div id="networkSearchPreview" class="network-search-preview hidden"></div>
        </div>

        <div class="network-slider-group">
          <label for="networkThreshold">
            Seuil minimal des relations :
            <strong id="networkThresholdValue">${appState.network.minEdgeWeight} €</strong>
          </label>
          <input
            id="networkThreshold"
            type="range"
            min="0"
            max="5000"
            step="100"
            value="${appState.network.minEdgeWeight}"
          />
          <small>Les liens dont le volume cumulé est inférieur au seuil sont masqués.</small>
        </div>

        <div class="network-actions">
          <button id="networkFitBtn" class="secondary-btn" type="button">Recentrer</button>
          <button id="networkZoomInBtn" class="secondary-btn" type="button">Zoom +</button>
          <button id="networkZoomOutBtn" class="secondary-btn" type="button">Zoom -</button>
        </div>
      </div>

      <label class="network-operator-toggle" for="networkIncludeOperators">
        <input
          id="networkIncludeOperators"
          type="checkbox"
          ${appState.network.includeOperators ? "checked" : ""}
        />
        <span>
          <strong>Inclure les comptes opérateurs P0000 / P9999</strong>
          <small>
            Désactivé par défaut pour lire le réseau interprofessionnel hors infrastructure Gonette.
          </small>
        </span>
      </label>

      <div class="network-atlas-legend">
        <span><span class="legend-dot legend-dot-blue"></span> Taille du nœud : volume relationnel cumulé</span>
        <span><span class="legend-dot legend-dot-dark"></span> Acteur sélectionné</span>
        <span><span class="legend-line legend-line-red"></span> Relations du voisinage isolé</span>
      </div>

      <div class="network-layout network-atlas-layout">
        <div class="network-main network-atlas-main">
          <div class="network-graph-shell">
            <div id="networkGraph"></div>
            <div id="networkFloatingLabel" class="network-floating-label hidden"></div>
          </div>
        </div>

        <aside id="networkSidePanel" class="network-sidepanel">
          <div class="network-sidepanel-empty">
            <strong>Sélectionner un professionnel</strong>
            <span>
              Clique sur un nœud pour isoler son voisinage visible, lire son volume relationnel
              et ouvrir sa fiche détaillée.
            </span>
          </div>
        </aside>
      </div>
    </section>
  `;
}

async function renderProfessionalNetworkPanel(forceReload = false) {
  const panel = document.getElementById("professionalNetworkPanel");
  if (!panel) {
    return;
  }

  const periodKey = [
    getPeriodQueryParam() || "__no_period__",
    `operators=${appState.network.includeOperators ? "1" : "0"}`
  ].join("::");

  const alreadyHydrated = (
    panel.dataset.professionalNetworkHydrated === "true"
    && panel.dataset.professionalNetworkPeriodKey === periodKey
  );

  if (alreadyHydrated && !forceReload) {
    window.requestAnimationFrame(() => {
      const graphNode = document.getElementById("networkGraph");
      const cy = appState.network.cy;

      if (!graphNode || !cy) {
        return;
      }

      const cyContainer = cy.container();
      if (!cyContainer || cyContainer !== graphNode) {
        return;
      }

      cy.resize();

      if (!appState.network.selectedNodeId) {
        cy.fit(cy.elements(":visible"), 60);
      }

      updateNetworkFloatingLabel();
    });

    return;
  }

  panel.dataset.professionalNetworkHydrated = "false";
  panel.dataset.professionalNetworkPeriodKey = periodKey;
  panel.innerHTML = buildProfessionalNetworkPanelLoadingHtml();

  try {
    if (appState.network.cy) {
      appState.network.cy.destroy();
      appState.network.cy = null;
    }

    const data = await apiGet(buildNetworkApiUrl());
    appState.network.rawData = data;
    appState.network.enrichedData = enrichNetworkData(data);

    panel.innerHTML = buildProfessionalNetworkPanelHtml();
    panel.dataset.professionalNetworkHydrated = "true";

    renderNetworkGraph(data);
    bindNetworkControls();
    updateNetworkOverviewMetrics();
  } catch (error) {
    console.warn(
      "Réseau interprofessionnel indisponible dans la vue Professionnels & particuliers.",
      error
    );

    panel.innerHTML = buildProfessionalNetworkPanelErrorHtml();
    panel.dataset.professionalNetworkHydrated = "false";
  }
}

function getNetworkSearchMatches(limit = 8) {
  const cy = appState.network.cy;
  if (!cy) return [];

  const q = normalizeText(appState.network.searchTerm);
  if (!q) return [];

  const matches = cy.nodes()
    .map(n => {
      const label = String(n.data("label") || n.id() || "");
      const id = String(n.id() || "");
      const haystack = normalizeText(`${id} ${label}`);

      let score = null;

      if (normalizeText(id) === q) score = 100;
      else if (normalizeText(label) === q) score = 95;
      else if (normalizeText(id).startsWith(q)) score = 90;
      else if (normalizeText(label).startsWith(q)) score = 80;
      else if (haystack.includes(q)) score = 60;

      if (score === null) return null;

      return { id, label, score };
    })
    .filter(Boolean)
    .sort((a, b) => b.score - a.score || a.label.localeCompare(b.label, "fr"))
    .slice(0, limit);

  return matches;
}

function renderNetworkSearchPreview(forceOpen = false) {
  const preview = document.getElementById("networkSearchPreview");
  const searchBox = document.querySelector(".network-search-box");
  const searchInput = document.getElementById("networkSearch");

  if (!preview || !searchBox || !searchInput) return;

  const matches = getNetworkSearchMatches(10);
  const q = normalizeText(appState.network.searchTerm);
  const isSearchActive = document.activeElement === searchInput;

  if (!q || matches.length === 0) {
    preview.classList.add("hidden");
    preview.innerHTML = "";
    searchBox.classList.remove("preview-open");
    return;
  }

  preview.innerHTML = matches.map(item => `
    <button
      class="network-search-item"
      type="button"
      data-node-id="${escapeHtml(item.id)}"
    >
      <span class="network-search-id">${escapeHtml(item.id)}</span>
      <span class="network-search-label">${escapeHtml(item.label)}</span>
    </button>
  `).join("");

  if (forceOpen || isSearchActive) {
    preview.classList.remove("hidden");
    searchBox.classList.add("preview-open");
  } else {
    preview.classList.add("hidden");
    searchBox.classList.remove("preview-open");
  }
}

function selectNetworkSearchResult(nodeId) {
  appState.network.searchTerm = nodeId;

  const input = document.getElementById("networkSearch");
  const preview = document.getElementById("networkSearchPreview");
  const searchBox = document.querySelector(".network-search-box");

  if (input) input.value = nodeId;
  if (preview) preview.classList.add("hidden");
  if (searchBox) searchBox.classList.remove("preview-open");

  focusNetworkNode(nodeId);
}

function bindNetworkSearchOutsideClick() {
  document.addEventListener("click", (e) => {
    const preview = document.getElementById("networkSearchPreview");
    const searchBox = document.querySelector(".network-search-box");

    if (!preview || !searchBox) return;

    if (!searchBox.contains(e.target)) {
      preview.classList.add("hidden");
      searchBox.classList.remove("preview-open");
    }
  });
}

function bindNetworkControls() {
  const searchInput = document.getElementById("networkSearch");
  const thresholdInput = document.getElementById("networkThreshold");
  const thresholdValue = document.getElementById("networkThresholdValue");
  const fitBtn = document.getElementById("networkFitBtn");
  const zoomInBtn = document.getElementById("networkZoomInBtn");
  const zoomOutBtn = document.getElementById("networkZoomOutBtn");
  const searchPreview = document.getElementById("networkSearchPreview");
  const includeOperatorsInput = document.getElementById("networkIncludeOperators");

  if (searchPreview && !searchPreview.dataset.bound) {
    searchPreview.addEventListener("click", (e) => {
      const btn = e.target.closest(".network-search-item");
      if (!btn) return;

      const nodeId = btn.dataset.nodeId;
      if (!nodeId) return;

      selectNetworkSearchResult(nodeId);
    });

    searchPreview.dataset.bound = "true";
  }

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      appState.network.searchTerm = e.target.value;
      applyNetworkSearch();
      renderNetworkSearchPreview(true);
    });

    searchInput.addEventListener("focus", () => {
      renderNetworkSearchPreview(true);
    });

    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        const preview = document.getElementById("networkSearchPreview");
        const searchBox = document.querySelector(".network-search-box");
        if (preview) preview.classList.add("hidden");
        if (searchBox) searchBox.classList.remove("preview-open");
      }
    });
}

  if (includeOperatorsInput) {
    includeOperatorsInput.addEventListener("change", (e) => {
      appState.network.includeOperators = Boolean(e.target.checked);
      appState.network.selectedNodeId = null;
      appState.network.hoveredNodeId = null;
      void renderProfessionalNetworkPanel(true);
    });
  }

  if (thresholdInput) {
    thresholdInput.addEventListener("input", (e) => {
      appState.network.minEdgeWeight = Number(e.target.value || 0);
      thresholdValue.textContent = `${appState.network.minEdgeWeight} €`;
      updateNetworkGraphVisibility();
    });
  }

  if (fitBtn) {
    fitBtn.addEventListener("click", () => {
      if (appState.network.cy) {
        appState.network.cy.fit(undefined, 40);
      }
    });
  }

  if (zoomOutBtn) {
    zoomOutBtn.addEventListener("click", () => {
      if (appState.network.cy) {
        appState.network.cy.zoom({
          level: appState.network.cy.zoom() * 0.85,
          renderedPosition: {
            x: appState.network.cy.width() / 2,
            y: appState.network.cy.height() / 2
          }
        });
      }
    });
  }
}

function enrichNetworkData(data) {
  const degreeMap = new Map();

  data.nodes.forEach(n => {
    degreeMap.set(n.data.id, { degree: 0, volume: 0 });
  });

  data.edges.forEach(e => {
    const src = e.data.source;
    const dst = e.data.target;
    const w = Number(e.data.weight || 0);

    if (degreeMap.has(src)) {
      degreeMap.get(src).degree += 1;
      degreeMap.get(src).volume += w;
    }
    if (degreeMap.has(dst)) {
      degreeMap.get(dst).degree += 1;
      degreeMap.get(dst).volume += w;
    }
  });

  data.nodes = data.nodes.map(n => {
    const stats = degreeMap.get(n.data.id) || { degree: 0, volume: 0 };
    return {
      data: {
        ...n.data,
        degree: stats.degree,
        volume: stats.volume
      }
    };
  });

  return data;
}

function getFilteredNetworkElements(data, minWeight) {
  const filteredEdges = data.edges.filter(
    e => Number(e.data.weight || 0) >= minWeight
  );

  const keptNodeIds = new Set();
  filteredEdges.forEach(e => {
    keptNodeIds.add(e.data.source);
    keptNodeIds.add(e.data.target);
  });

  const filteredNodes = data.nodes.filter(n => keptNodeIds.has(n.data.id));

  return {
    filteredNodes,
    filteredEdges,
    keptNodeIds
  };
}

function computeNetworkVisibleSummary(
  data = appState.network.enrichedData,
  minWeight = appState.network.minEdgeWeight || 0
) {
  if (!data) {
    return {
      visibleNodeCount: 0,
      visibleEdgeCount: 0,
      visibleVolume: 0,
      minWeight
    };
  }

  const { filteredNodes, filteredEdges } = getFilteredNetworkElements(data, minWeight);

  const visibleVolume = filteredEdges.reduce(
    (sum, edge) => sum + Number(edge?.data?.weight || 0),
    0
  );

  return {
    visibleNodeCount: filteredNodes.length,
    visibleEdgeCount: filteredEdges.length,
    visibleVolume,
    minWeight
  };
}

function updateNetworkOverviewMetrics() {
  const summary = computeNetworkVisibleSummary();

  const nodeCount = document.getElementById("networkVisibleNodeCount");
  const edgeCount = document.getElementById("networkVisibleEdgeCount");
  const volume = document.getElementById("networkVisibleVolume");
  const threshold = document.getElementById("networkVisibleThreshold");

  if (nodeCount) {
    nodeCount.textContent = Number(summary.visibleNodeCount || 0).toLocaleString("fr-FR");
  }

  if (edgeCount) {
    edgeCount.textContent = Number(summary.visibleEdgeCount || 0).toLocaleString("fr-FR");
  }

  if (volume) {
    volume.textContent = euro(summary.visibleVolume || 0);
  }

  if (threshold) {
    threshold.textContent = euro(summary.minWeight || 0);
  }
}


function updateNetworkGraphVisibility() {
  const cy = appState.network.cy;
  const data = appState.network.enrichedData;

  if (!cy || !data) return;

  const minWeight = appState.network.minEdgeWeight || 0;
  const { keptNodeIds } = getFilteredNetworkElements(data, minWeight);

  cy.batch(() => {
    cy.edges().forEach(edge => {
      const weight = Number(edge.data("weight") || 0);
      if (weight >= minWeight) {
        edge.style("display", "element");
      } else {
        edge.style("display", "none");
      }
    });

    cy.nodes().forEach(node => {
      if (keptNodeIds.has(node.id())) {
        node.style("display", "element");
      } else {
        node.style("display", "none");
      }
    });
  });

  const selectedNodeId = appState.network.selectedNodeId;
  if (selectedNodeId) {
    const selectedNode = cy.getElementById(selectedNodeId);
    if (!selectedNode || selectedNode.empty() || selectedNode.style("display") === "none") {
      appState.network.selectedNodeId = null;
      appState.network.hoveredNodeId = null;
      renderNetworkSidePanel(null);
      hideNetworkFloatingLabel();
      cy.elements().removeClass("faded highlighted selected-node search-match");
    } else {
      focusNetworkNode(selectedNodeId, { fit: false });
    }
  } else {
    cy.elements().removeClass("faded highlighted selected-node");
    applyNetworkSearch();
  }

  updateNetworkOverviewMetrics();
  renderNetworkSearchPreview();
}

function applyNetworkSearch() {
  const cy = appState.network.cy;
  if (!cy) return;

  cy.nodes().removeClass("search-match");

  const q = normalizeText(appState.network.searchTerm || "");
  if (!q) {
    renderNetworkSearchPreview();
    return;
  }

  cy.nodes().forEach(node => {
    const label = normalizeText(node.data("label") || "");
    const id = normalizeText(node.id() || "");

    if (label.includes(q) || id.includes(q)) {
      node.addClass("search-match");
    }
  });

  renderNetworkSearchPreview();
}


function getNetworkNodeRoleProfile(node) {
  const incoming = Number(node?.data("incoming_volume") || 0);
  const outgoing = Number(node?.data("outgoing_volume") || 0);
  const total = incoming + outgoing;

  if (total <= 0) {
    return {
      key: "neutral",
      label: "Profil indéterminé",
      text: "Aucun volume relationnel P→P exploitable n’est disponible pour cet acteur."
    };
  }

  const net = incoming - outgoing;
  const imbalance = Math.abs(net) / total;

  if (net > 0 && imbalance >= 0.20) {
    return {
      key: "receiver",
      label: "Récepteur net",
      text: "Dans le réseau P→P de la période, cet acteur reçoit nettement plus qu’il ne réémet."
    };
  }

  if (net < 0 && imbalance >= 0.20) {
    return {
      key: "emitter",
      label: "Redistributeur net",
      text: "Dans le réseau P→P de la période, cet acteur réémet nettement plus qu’il ne reçoit."
    };
  }

  return {
    key: "balanced",
    label: "Pivot relativement équilibré",
    text: "Les volumes P→P reçus et émis restent relativement proches sur la période."
  };
}

function getVisibleNetworkRelations(node) {
  const incoming = [];
  const outgoing = [];

  if (!node) {
    return { incoming, outgoing };
  }

  node.connectedEdges().forEach(edge => {
    if (edge.style("display") === "none") {
      return;
    }

    const weight = Number(edge.data("weight") || 0);
    const transactionCount = Number(edge.data("transaction_count") || 0);
    const averageAmount = Number(edge.data("average_amount") || 0);

    if (edge.target().id() === node.id()) {
      const sourceNode = edge.source();
      incoming.push({
        actorId: sourceNode.id(),
        actorLabel: sourceNode.data("label") || sourceNode.id(),
        weight,
        transactionCount,
        averageAmount
      });
    }

    if (edge.source().id() === node.id()) {
      const targetNode = edge.target();
      outgoing.push({
        actorId: targetNode.id(),
        actorLabel: targetNode.data("label") || targetNode.id(),
        weight,
        transactionCount,
        averageAmount
      });
    }
  });

  incoming.sort((a, b) => b.weight - a.weight);
  outgoing.sort((a, b) => b.weight - a.weight);

  return {
    incoming: incoming.slice(0, 4),
    outgoing: outgoing.slice(0, 4)
  };
}

function renderNetworkRelationGroup(title, items, emptyText) {
  if (!items.length) {
    return `
      <div class="network-relation-group">
        <h4>${escapeHtml(title)}</h4>
        <div class="network-relation-empty">${escapeHtml(emptyText)}</div>
      </div>
    `;
  }

  return `
    <div class="network-relation-group">
      <h4>${escapeHtml(title)}</h4>
      <div class="network-relation-list">
        ${items.map(item => `
          <button
            type="button"
            class="network-relation-item"
            onclick="focusNetworkNode('${escapeHtml(item.actorId)}')"
          >
            <span class="network-relation-label">${escapeHtml(item.actorLabel)}</span>
            <strong>${euro(item.weight || 0)}</strong>
            <small>
              ${Number(item.transactionCount || 0).toLocaleString("fr-FR")} tx
              · moyenne ${euro(item.averageAmount || 0)}
            </small>
          </button>
        `).join("")}
      </div>
    </div>
  `;
}

function renderNetworkSidePanel(node) {
  const panel = document.getElementById("networkSidePanel");
  if (!panel) return;

  if (!node) {
    panel.innerHTML = `
      <div class="network-sidepanel-empty">
        <strong>Sélectionner un professionnel</strong>
        <span>
          Clique sur un nœud pour isoler son voisinage visible, lire son rôle apparent
          dans le réseau P→P et ouvrir sa fiche détaillée.
        </span>
      </div>
    `;
    return;
  }

  const label = node.data("label") || node.id();
  const profile = getNetworkNodeRoleProfile(node);
  const visibleRelations = getVisibleNetworkRelations(node);

  let visibleRelationCount = 0;
  let visibleVolume = 0;
  let incomingVisibleVolume = 0;
  let outgoingVisibleVolume = 0;

  node.connectedEdges().forEach(edge => {
    if (edge.style("display") === "none") {
      return;
    }

    const weight = Number(edge.data("weight") || 0);
    visibleRelationCount += 1;
    visibleVolume += weight;

    if (edge.target().id() === node.id()) {
      incomingVisibleVolume += weight;
    }

    if (edge.source().id() === node.id()) {
      outgoingVisibleVolume += weight;
    }
  });

  const incomingPeriodVolume = Number(node.data("incoming_volume") || 0);
  const outgoingPeriodVolume = Number(node.data("outgoing_volume") || 0);
  const netBalance = Number(node.data("net_relation_balance") || 0);
  const netBalanceLabel = `${netBalance > 0 ? "+" : ""}${euro(netBalance || 0)}`;

  const neighborCount = Number(node.data("neighbor_count") || 0);
  const inboundRelations = Number(node.data("inbound_relation_count") || 0);
  const outboundRelations = Number(node.data("outbound_relation_count") || 0);

  panel.innerHTML = `
    <div class="network-sidepanel-card">
      <div class="stat-label">Acteur sélectionné</div>
      <h3>${escapeHtml(label)}</h3>
      <p class="network-sidepanel-ref">${escapeHtml(node.id())}</p>

      <div class="network-role-chip network-role-chip-${escapeHtml(profile.key)}">
        ${escapeHtml(profile.label)}
      </div>

      <p class="network-role-reading">${escapeHtml(profile.text)}</p>

      <div class="network-sidepanel-metric-grid">
        <div class="network-sidepanel-metric">
          <span>Relations visibles</span>
          <strong>${Number(visibleRelationCount || 0).toLocaleString("fr-FR")}</strong>
        </div>

        <div class="network-sidepanel-metric">
          <span>Volume visible</span>
          <strong>${euro(visibleVolume || 0)}</strong>
        </div>
      </div>

      <div class="network-sidepanel-period-card">
        <div class="network-sidepanel-period-title">
          Profil P→P sur toute la période
        </div>

        <div class="network-sidepanel-period-grid">
          <div>
            <span>Voisins distincts</span>
            <strong>${neighborCount.toLocaleString("fr-FR")}</strong>
          </div>
          <div>
            <span>Liens entrants</span>
            <strong>${inboundRelations.toLocaleString("fr-FR")}</strong>
          </div>
          <div>
            <span>Liens sortants</span>
            <strong>${outboundRelations.toLocaleString("fr-FR")}</strong>
          </div>
          <div>
            <span>Solde relationnel net</span>
            <strong>${netBalanceLabel}</strong>
          </div>
        </div>
      </div>

      <div class="network-sidepanel-directional">
        <div class="network-sidepanel-direction">
          <span>Flux P→P reçus</span>
          <strong>${euro(incomingPeriodVolume || 0)}</strong>
        </div>

        <div class="network-sidepanel-direction">
          <span>Flux P→P émis</span>
          <strong>${euro(outgoingPeriodVolume || 0)}</strong>
        </div>

        <div class="network-sidepanel-direction network-sidepanel-direction-muted">
          <span>Reçu visible au seuil</span>
          <strong>${euro(incomingVisibleVolume || 0)}</strong>
        </div>

        <div class="network-sidepanel-direction network-sidepanel-direction-muted">
          <span>Émis visible au seuil</span>
          <strong>${euro(outgoingVisibleVolume || 0)}</strong>
        </div>
      </div>

      <div class="network-sidepanel-relations">
        ${renderNetworkRelationGroup(
          "Principales entrées visibles",
          visibleRelations.incoming,
          "Aucune relation entrante visible à ce seuil."
        )}

        ${renderNetworkRelationGroup(
          "Principales sorties visibles",
          visibleRelations.outgoing,
          "Aucune relation sortante visible à ce seuil."
        )}
      </div>

      <p class="network-sidepanel-reading">
        Les relations visibles dépendent du seuil appliqué au graphe.
        Les volumes de profil P→P portent, eux, sur l’ensemble des relations de la période.
      </p>

      <div class="network-sidepanel-actions">
        <button class="primary-btn" onclick="renderProDetail('${escapeHtml(node.id())}')">
          Ouvrir la fiche pro
        </button>
      </div>
    </div>
  `;
}

function focusNetworkNode(nodeId, options = {}) {
  const cy = appState.network.cy;
  if (!cy) return;

  const {
    fit = true,
    padding = 80,
    duration = 350
  } = options;

  const node = cy.getElementById(nodeId);
  if (!node || node.empty()) {
    appState.network.selectedNodeId = null;
    appState.network.hoveredNodeId = null;
    renderNetworkSidePanel(null);
    hideNetworkFloatingLabel();
    applyNetworkSearch();
    return;
  }

  cy.elements().addClass("faded");
  cy.edges().removeClass("highlighted");
  cy.nodes().removeClass("selected-node search-match");

  node.removeClass("faded");
  node.addClass("selected-node");

  const neighborhood = node.closedNeighborhood();
  neighborhood.removeClass("faded");

  node.connectedEdges().addClass("highlighted");

  appState.network.selectedNodeId = node.id();
  appState.network.hoveredNodeId = null;

  renderNetworkSidePanel(node);
  applyNetworkSearch();
  updateNetworkFloatingLabel();

  if (fit) {
    cy.animate({
      fit: {
        eles: neighborhood,
        padding
      },
      duration,
      complete: () => updateNetworkFloatingLabel()
    });
  }
}

function hideNetworkFloatingLabel() {
  const el = document.getElementById("networkFloatingLabel");
  if (!el) return;

  el.classList.add("hidden");
  el.innerHTML = "";
}

function updateNetworkFloatingLabel() {
  const cy = appState.network.cy;
  const el = document.getElementById("networkFloatingLabel");

  if (!cy || !el) return;

  const nodeId = appState.network.hoveredNodeId || appState.network.selectedNodeId;
  if (!nodeId) {
    hideNetworkFloatingLabel();
    return;
  }

  const node = cy.getElementById(nodeId);
  if (!node || node.empty()) {
    hideNetworkFloatingLabel();
    return;
  }

  const pos = node.renderedPosition();
  const label = node.data("label") || node.id();

  el.innerHTML = `
    <div class="network-floating-label-code">${escapeHtml(node.id())}</div>
    <div class="network-floating-label-name">${escapeHtml(label)}</div>
  `;

  el.style.left = `${pos.x}px`;
  el.style.top = `${pos.y - 20}px`;
  el.classList.remove("hidden");
}

function bindNetworkFloatingLabel(cy) {
  if (!cy) return;

  const refresh = () => updateNetworkFloatingLabel();
  cy.on("pan zoom render resize", refresh);
}

function renderNetworkGraph(data) {
  const container = document.getElementById("networkGraph");
  if (!container) return;

  if (appState.network.cy) {
    const currentContainer = appState.network.cy.container();

    if (!currentContainer || currentContainer !== container || !document.body.contains(currentContainer)) {
      appState.network.cy.destroy();
      appState.network.cy = null;
    }
  }

  if (!appState.network.enrichedData) {
    appState.network.enrichedData = enrichNetworkData(data);
  }

  const enriched = appState.network.enrichedData;
  const minWeight = appState.network.minEdgeWeight || 0;
  const { filteredNodes, filteredEdges } = getFilteredNetworkElements(enriched, minWeight);

  const selectedNodeId = appState.network.selectedNodeId;

  if (!appState.network.cy) {
    const cy = cytoscape({
      container,
      elements: [
        ...enriched.nodes,
        ...enriched.edges
      ],
      style: [
        {
          selector: "node",
          style: {
            "label": "",
            "background-color": "mapData(volume, 0, 60000, #bfdbfe, #1d4ed8)",
            "width": "mapData(volume, 0, 60000, 18, 68)",
            "height": "mapData(volume, 0, 60000, 18, 68)",
            "border-width": 3,
            "border-color": "#eff6ff",
            "overlay-padding": 12,
            "overlay-opacity": 0,
            "z-index": 10
          }
        },
        {
          selector: "edge",
          style: {
            "width": "mapData(weight, 0, 60000, 1.1, 8)",
            "line-color": "#94a3b8",
            "target-arrow-color": "#94a3b8",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.72,
            "curve-style": "bezier",
            "control-point-step-size": 28,
            "opacity": 0.30
          }
        },
        {
          selector: ".faded",
          style: {
            "opacity": 0.045
          }
        },
        {
          selector: ".highlighted",
          style: {
            "line-color": "#f97316",
            "target-arrow-color": "#f97316",
            "opacity": 0.98,
            "z-index": 30
          }
        },
        {
          selector: ".selected-node",
          style: {
            "background-color": "#0f172a",
            "border-color": "#f97316",
            "border-width": 5
          }
        },
        {
          selector: ".search-match",
          style: {
            "border-color": "#eab308",
            "border-width": 5
          }
        }
      ],
      layout: {
        name: "cose",
        animate: false,
        fit: true,
        padding: 72,
        nodeRepulsion: 12000,
        idealEdgeLength: 108,
        edgeElasticity: 100,
        nestingFactor: 1.18,
        gravity: 0.42,
        numIter: 1200
      },
      wheelSensitivity: 0.14
    });

    appState.network.cy = cy;

    cy.on("tap", "node", evt => {
      focusNetworkNode(evt.target.id());
    });

    cy.on("tap", evt => {
      if (evt.target === cy) {
        appState.network.selectedNodeId = null;
        appState.network.hoveredNodeId = null;
        cy.elements().removeClass("faded highlighted selected-node");
        renderNetworkSidePanel(null);
        hideNetworkFloatingLabel();
        applyNetworkSearch();
      }
    });

    cy.on("mouseover", "node", evt => {
      appState.network.hoveredNodeId = evt.target.id();
      updateNetworkFloatingLabel();
    });

    cy.on("mouseout", "node", () => {
      appState.network.hoveredNodeId = null;
      updateNetworkFloatingLabel();
    });

    bindNetworkFloatingLabel(cy);
  }

  updateNetworkGraphVisibility();

  const cy = appState.network.cy;

  if (
    selectedNodeId &&
    filteredNodes.some(n => n.data.id === selectedNodeId)
  ) {
    focusNetworkNode(selectedNodeId, { fit: false });
  } else if (!selectedNodeId && filteredNodes.length > 0) {
    cy.fit(cy.elements(':visible'), 60);
  }
}

async function apiGet(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Erreur API ${res.status}`);
  }
  return await res.json();
}

async function apiPost(url) {
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    throw new Error(`Erreur API ${res.status}`);
  }
  return await res.json();
}

async function apiPostJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(data.error || `Erreur API ${res.status}`);
  }

  return data;
}

function euro(value) {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0
  }).format(Number(value || 0));
}

function percent(value) {
  return new Intl.NumberFormat("fr-FR", {
    style: "percent",
    maximumFractionDigits: 1
  }).format(Number(value || 0) / 100);
}

function setTitle(title) {
  pageTitle.innerHTML = `<h1>${title}</h1>`;
}

function formatProfessionalPageTitle(numProf, fullname) {
  const code = String(numProf || "").trim();
  const rawFullname = String(fullname || "").trim();

  if (!rawFullname || rawFullname === code) {
    return escapeHtml(code);
  }

  const prefix = `${code} - `;
  const name = rawFullname.startsWith(prefix)
    ? rawFullname.slice(prefix.length).trim()
    : rawFullname;

  return `${escapeHtml(code)} — ${escapeHtml(name)}`;
}

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function plainTextFromHtml(value) {
  const html = String(value || "").trim();
  if (!html) return "";

  const doc = new DOMParser().parseFromString(html, "text/html");
  const text = doc && doc.body ? doc.body.textContent : "";

  return String(text || "")
    .replace(/\s+/g, " ")
    .trim();
}

function formatProfessionalLocation(enrichment) {
  const city = String((enrichment && enrichment.city) || "").trim();
  const zip = String((enrichment && enrichment.zip) || "").trim();

  if (city && zip) return `${city} (${zip})`;
  return city || zip || "";
}

function sortIndicator(column) {
  if (appState.prosSortBy !== column) return "";
  return appState.prosSortDir === "asc" ? " ▲" : " ▼";
}

function sortableHeader(label, columnKey) {
  return `<button class="table-sort-btn" onclick="toggleProsSort('${escapeHtml(columnKey)}')">${label}${sortIndicator(columnKey)}</button>`;
}

function detailSortIndicator(column) {
  if (appState.detailSortBy !== column) return "";
  return appState.detailSortDir === "asc" ? " ▲" : " ▼";
}

function detailSortableHeader(label, columnKey) {
  return `<button class="table-sort-btn" onclick="toggleDetailSort('${escapeHtml(columnKey)}')">${label}${detailSortIndicator(columnKey)}</button>`;
}

function toggleDetailSort(column) {
  if (appState.detailSortBy === column) {
    appState.detailSortDir = appState.detailSortDir === "asc" ? "desc" : "asc";
  } else {
    appState.detailSortBy = column;
    appState.detailSortDir = column === "Date" ? "desc" : "asc";
  }

  appState.detailPage = 1;
  drawDetailSection();
}

function changeDetailTransactionPage(delta) {
  const currentPage = Number(appState.detailPage || 1);
  appState.detailPage = Math.max(1, currentPage + delta);
  drawDetailSection();
}

function drawDetailSection() {
  const detailContainer = document.getElementById("detailSection");
  if (!detailContainer || !appState.detailData || !appState.currentPro) return;

  const tx = appState.detailData.transactions || [];
  detailContainer.innerHTML = buildDetailSection(
    appState.currentPro,
    tx,
    appState.detailMode
  );
}

function sortRows(rows, mapping = null) {
  const sorted = [...rows];
  const key = appState.detailSortBy;

  sorted.sort((a, b) => {
    let av = mapping ? mapping(a, key) : a[key];
    let bv = mapping ? mapping(b, key) : b[key];

    if (key === "Date") {
      const ad = new Date(av.split("-").reverse().join("-"));
      const bd = new Date(bv.split("-").reverse().join("-"));
      return appState.detailSortDir === "asc" ? ad - bd : bd - ad;
    }

    const aNum = Number(String(av).replace(/[^\d.-]/g, ""));
    const bNum = Number(String(bv).replace(/[^\d.-]/g, ""));
    const bothNumeric = !Number.isNaN(aNum) && !Number.isNaN(bNum);

    if (bothNumeric) {
      return appState.detailSortDir === "asc" ? aNum - bNum : bNum - aNum;
    }

    av = String(av ?? "").toLowerCase();
    bv = String(bv ?? "").toLowerCase();

    if (av < bv) return appState.detailSortDir === "asc" ? -1 : 1;
    if (av > bv) return appState.detailSortDir === "asc" ? 1 : -1;
    return 0;
  });

  return sorted;
}

function getSortedAndFilteredPros() {
  let rows = [...appState.prosData];

  if (appState.prosSearch.trim()) {
    const q = appState.prosSearch.trim().toLowerCase();
    rows = rows.filter(row =>
      String(row.Professionnel || "").toLowerCase().includes(q)
    );
  }

  rows.sort((a, b) => {
    const key = appState.prosSortBy;
    let av = a[key];
    let bv = b[key];

    const aNum = Number(av);
    const bNum = Number(bv);
    const bothNumeric = !Number.isNaN(aNum) && !Number.isNaN(bNum);

    if (bothNumeric) {
      av = aNum;
      bv = bNum;
      return appState.prosSortDir === "asc" ? av - bv : bv - av;
    }

    av = String(av ?? "").toLowerCase();
    bv = String(bv ?? "").toLowerCase();

    if (av < bv) return appState.prosSortDir === "asc" ? -1 : 1;
    if (av > bv) return appState.prosSortDir === "asc" ? 1 : -1;
    return 0;
  });

  return rows;
}

function isPro(value) {
  return String(value || "").trim().startsWith("P");
}

function isUser(value) {
  return String(value || "").trim().startsWith("U");
}

function renderActorLink(value) {
  const text = String(value || "").trim();
  if (!text) return "";

  const matchPro = text.match(/P\d{4}/);
  const matchUser = text.match(/U\d{4}/);

  if (matchPro) {
    const code = matchPro[0];
    return `<button class="linkish" onclick="renderProDetail('${escapeHtml(code)}')">${escapeHtml(text)}</button>`;
  }

  if (matchUser) {
    const code = matchUser[0];
    return `<button class="linkish" onclick="renderUserDetail('${escapeHtml(code)}')">${escapeHtml(text)}</button>`;
  }

  return escapeHtml(text);
}

function isConversion(value) {
  return String(value || "").toLowerCase().includes("conversion");
}


function parseFrDate(str) {
  const value = String(str || "").trim();
  if (!value) return new Date("invalid");

  const datePart = value.split(" ")[0];

  if (datePart.includes("-")) {
    const parts = datePart.split("-");

    if (parts[0].length === 4) {
      const [yyyy, mm, dd] = parts;
      return new Date(Number(yyyy), Number(mm) - 1, Number(dd));
    }

    const [dd, mm, yyyy] = parts;
    return new Date(Number(yyyy), Number(mm) - 1, Number(dd));
  }

  if (datePart.includes("/")) {
    const [dd, mm, yyyy] = datePart.split("/");
    return new Date(Number(yyyy), Number(mm) - 1, Number(dd));
  }

  return new Date(value);
}

function formatFrDate(date) {
  const dd = String(date.getDate()).padStart(2, "0");
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const yyyy = date.getFullYear();
  return `${dd}-${mm}-${yyyy}`;
}

function toIsoDayFromFrDate(str) {
  const d = parseFrDate(str);
  if (Number.isNaN(d.getTime())) return null;
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function getWeekStartFromIso(isoDate) {
  const d = new Date(`${isoDate}T00:00:00`);
  const day = d.getDay(); // 0 = dimanche
  const diff = d.getDate() - (day === 0 ? 6 : day - 1);
  d.setDate(diff);

  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function destroyGlobalStatsCharts() {
  const keys = [
    "globalDailyCount",
    "globalWeeklyAvg",
    "globalHourly",
    "globalWeekday",
    "globalCumulative",
    "circuitMonthlyFlows",
    "circuitInflowDestinations",
    "circuitCumulativeFlows",
    "circuitNetGap",
    "operationsMonthlyFamilies",
    "operationsMonthlyOperatorProfiles",
    "operationsStructuralFlowDistribution",
    "monetaryStockHistory"
  ];

  keys.forEach(key => {
    if (appState.charts[key]) {
      appState.charts[key].destroy();
      appState.charts[key] = null;
    }
  });
}

function buildGlobalChartsData(transactions) {
  const validTx = (transactions || [])
    .map(row => {
      const rawDate = String(row.Date || "");
      const isoDate = toIsoDayFromFrDate(rawDate);
      const amount = Number(row["Montant"] || 0);

      return {
        rawDate,
        isoDate,
        amount,
        from: String(row["Réalisé par"] || ""),
        to: String(row["Vers"] || "")
      };
    })
      .filter(row => row.isoDate && !Number.isNaN(row.amount));

  const dailyCounts = {};
  validTx.forEach(row => {
    dailyCounts[row.isoDate] = (dailyCounts[row.isoDate] || 0) + 1;
  });
  const sortedDates = Object.keys(dailyCounts).sort();
  const transactionCounts = sortedDates.map(d => dailyCounts[d]);

  const weeklyData = {};
  validTx.forEach(row => {
    const weekStart = getWeekStartFromIso(row.isoDate);
    if (!weeklyData[weekStart]) {
      weeklyData[weekStart] = { sum: 0, count: 0 };
    }
    weeklyData[weekStart].sum += row.amount;
    weeklyData[weekStart].count += 1;
  });
  const sortedWeeks = Object.keys(weeklyData).sort();
  const weeklyAvg = sortedWeeks.map(week => weeklyData[week].sum / weeklyData[week].count);

  const hourlyLabels = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, "0")}h`);
  const hourlyValues = Array(24).fill(0);

  const weekdayLabels = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];
  const weekdayValues = Array(7).fill(0);

  validTx.forEach(row => {
    const source = String(row.rawDate || "");
    const parts = source.split(" ");
      if (parts.length > 1 && parts[1].includes(":")) {
      const hour = Number(parts[1].split(":")[0]);
      if (!Number.isNaN(hour) && hour >= 0 && hour <= 23) {
        hourlyValues[hour] += 1;
      }
    }

    const d = new Date(`${row.isoDate}T00:00:00`);
    const jsDay = d.getDay(); // 0 dimanche
    const mondayFirstIndex = jsDay === 0 ? 6 : jsDay - 1;
    weekdayValues[mondayFirstIndex] += 1;
  });

  const sortedTx = [...validTx].sort((a, b) => a.isoDate.localeCompare(b.isoDate));
  let cumulativeSum = 0;
  const cumulativeDates = [];
  const cumulativeVolume = [];

  sortedTx.forEach(row => {
    cumulativeSum += row.amount;
    cumulativeDates.push(row.isoDate);
    cumulativeVolume.push(cumulativeSum);
  });

  return {
    sortedDates,
    transactionCounts,
    sortedWeeks,
    weeklyAvg,
    hourlyLabels,
    hourlyValues,
    weekdayLabels,
    weekdayValues,
    cumulativeDates,
    cumulativeVolume
  };
}

function renderGlobalStatsCharts(transactions) {
  const chartsHost = document.getElementById("globalStatsCharts");
  if (!chartsHost) return;

  destroyGlobalStatsCharts();

  if (!transactions || transactions.length === 0) {
    chartsHost.innerHTML = `
      <div class="card">
        <h3>Graphiques globaux</h3>
        <p>Aucune transaction disponible.</p>
      </div>
    `;
    return;
  }

  const data = buildGlobalChartsData(transactions);

  chartsHost.innerHTML = `
    <div class="card">
      <h3>Transactions par jour — circulation et opérations techniques</h3>
      <canvas id="globalDailyCountChart" height="90"></canvas>
    </div>

    <div class="card">
      <h3>Montant moyen par semaine</h3>
      <canvas id="globalWeeklyAvgChart" height="90"></canvas>
    </div>

    <div class="card">
      <h3>Paiements économiques par heure</h3>
      <canvas id="globalHourlyChart" height="90"></canvas>
    </div>

    <div class="card">
      <h3>Paiements économiques par jour de semaine</h3>
      <canvas id="globalWeekdayChart" height="90"></canvas>
    </div>

    <div class="card">
      <h3>Volume cumulé de l’activité économique</h3>
      <canvas id="globalCumulativeChart" height="90"></canvas>
    </div>
  `;

  const dailyCtx = document.getElementById("globalDailyCountChart");
  const weeklyCtx = document.getElementById("globalWeeklyAvgChart");
  const hourlyCtx = document.getElementById("globalHourlyChart");
  const weekdayCtx = document.getElementById("globalWeekdayChart");
  const cumulativeCtx = document.getElementById("globalCumulativeChart");

  if (!dailyCtx || !weeklyCtx || !hourlyCtx || !weekdayCtx || !cumulativeCtx) return;

  appState.charts.globalDailyCount = new Chart(dailyCtx, {
    type: "line",
    data: {
      labels: data.sortedDates,
      datasets: [{
        label: "Transactions",
        data: data.transactionCounts,
        fill: true,
        tension: 0.25
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: "top" }
      },
      scales: {
        x: {
          ticks: { maxRotation: 45, minRotation: 0 }
        },
        y: {
          beginAtZero: true
        }
      }
    }
  });

  appState.charts.globalWeeklyAvg = new Chart(weeklyCtx, {
    type: "line",
    data: {
      labels: data.sortedWeeks,
      datasets: [{
        label: "Montant moyen hebdomadaire",
        data: data.weeklyAvg,
        fill: true,
        tension: 0.25
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: "top" },
        tooltip: {
          callbacks: {
            label: function(context) {
              return `${context.dataset.label}: ${euro(context.raw)}`;
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { maxRotation: 45, minRotation: 0 }
        },
        y: {
          beginAtZero: true
        }
      }
    }
  });

  appState.charts.globalHourly = new Chart(hourlyCtx, {
    type: "bar",
    data: {
      labels: data.hourlyLabels,
      datasets: [{
        label: "Transactions par heure",
        data: data.hourlyValues
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: "top" }
      },
      scales: {
        y: {
          beginAtZero: true
        }
      }
    }
  });

  appState.charts.globalWeekday = new Chart(weekdayCtx, {
    type: "bar",
    data: {
      labels: data.weekdayLabels,
      datasets: [{
        label: "Transactions par jour",
        data: data.weekdayValues
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: "top" }
      },
      scales: {
        y: {
          beginAtZero: true
        }
      }
    }
  });

  appState.charts.globalCumulative = new Chart(cumulativeCtx, {
    type: "line",
    data: {
      labels: data.cumulativeDates,
      datasets: [{
        label: "Volume cumulé de l’activité économique",
        data: data.cumulativeVolume,
        fill: true,
        tension: 0.2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: "top" },
        tooltip: {
          callbacks: {
            label: function(context) {
              return `${context.dataset.label}: ${euro(context.raw)}`;
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { maxRotation: 45, minRotation: 0 }
        },
        y: {
          beginAtZero: true
        }
      }
    }
  });
}

function uniqueSortedDates(rows) {
  const unique = [...new Set(rows.map(r => String(r.Date)))];
  unique.sort((a, b) => parseFrDate(a) - parseFrDate(b));
  return unique;
}

function getPeriodBounds(rows) {
  const dates = uniqueSortedDates(rows);
  return {
    dates,
    min: dates[0] || null,
    max: dates[dates.length - 1] || null
  };
}

function getFilteredTransactionsByPeriod(rows) {
  // Le filtrage temporel est désormais global et appliqué côté API
  // depuis le volet latéral. Les transactions reçues ici sont déjà
  // bornées à la période active.
  return rows;
}

function computeStatsFromTransactions(allTx, numProf) {
  const tx = getFilteredTransactionsByPeriod(allTx);

  const received = tx.filter(row =>
    String(row["Vers"] || "").includes(numProf) &&
    !isConversion(row["Réalisé par"])
  );

  const particuliersPayeurs = tx.filter(row =>
    String(row["Vers"] || "").includes(numProf) &&
    isUser(row["Réalisé par"]) &&
    !isConversion(row["Réalisé par"])
  );

  const professionnelsPayeurs = tx.filter(row =>
    String(row["Vers"] || "").includes(numProf) &&
    isPro(row["Réalisé par"]) &&
    !isConversion(row["Réalisé par"])
  );

  const emisVersPro = tx.filter(row =>
    String(row["Réalisé par"] || "").includes(numProf) &&
    isPro(row["Vers"])
  );

  const emisVersParticuliers = tx.filter(row =>
    String(row["Réalisé par"] || "").includes(numProf) &&
    isUser(row["Vers"])
  );

  const reconverti = tx.filter(row =>
    String(row["Réalisé par"] || "").includes(numProf) &&
    isConversion(row["Vers"])
  );

  const converti = tx.filter(row =>
    String(row["Vers"] || "").includes(numProf) &&
    isConversion(row["Réalisé par"])
  );

  const montantRecuParticuliers = particuliersPayeurs.reduce(
    (s, r) => s + Number(r["Montant"] || 0),
    0
  );

  const montantRecuProfessionnels = professionnelsPayeurs.reduce(
    (s, r) => s + Number(r["Montant"] || 0),
    0
  );

  const montantTotalRecu = received.reduce(
    (s, r) => s + Number(r["Montant"] || 0),
    0
  );

  const montantEmisVersPro = emisVersPro.reduce(
    (s, r) => s + Number(r["Montant"] || 0),
    0
  );

  const montantEmisVersParticuliers = emisVersParticuliers.reduce(
    (s, r) => s + Number(r["Montant"] || 0),
    0
  );

  const montantReconverti = reconverti.reduce(
    (s, r) => s + Number(r["Montant"] || 0),
    0
  );

  const montantConverti = converti.reduce(
    (s, r) => s + Number(r["Montant"] || 0),
    0
  );

  const totalMontantEmisSansReconversion =
    montantEmisVersPro + montantEmisVersParticuliers;

  const baseReutilisation = montantTotalRecu + montantConverti;
  const tauxReutilisation = baseReutilisation > 0
    ? (totalMontantEmisSansReconversion / baseReutilisation) * 100
    : 0;

  const bounds = getPeriodBounds(tx);

  return {
    tx,
    periode_debut: bounds.min || "-",
    periode_fin: bounds.max || "-",
    nb_transactions_recues: received.length,

    // Répartition des montants reçus
    montant_recu_particuliers: montantRecuParticuliers,
    montant_recu_professionnels: montantRecuProfessionnels,
    montant_total_recu: montantTotalRecu,

    // Clé historique conservée pour compatibilité pendant la refonte UI
    somme_transactions_recues: montantTotalRecu,

    nb_particuliers: new Set(particuliersPayeurs.map(r => r["Réalisé par"])).size,
    nb_professionnels: new Set(professionnelsPayeurs.map(r => r["Réalisé par"])).size,

    montant_emis_vers_pro: montantEmisVersPro,
    montant_emis_vers_particuliers: montantEmisVersParticuliers,
    montant_reconverti: montantReconverti,
    montant_converti: montantConverti,
    total_montant_emis_sans_reconversion: totalMontantEmisSansReconversion,
    taux_reutilisation: tauxReutilisation
  };
}

function transactionTable(rows) {
  const sortedRows = sortRows(rows);

  const body = sortedRows.map(row => `
    <tr>
      <td>${escapeHtml(row.Date)}</td>
      <td>${renderActorLink(row["Réalisé par"])}</td>
      <td>${renderActorLink(row["Vers"])}</td>
      <td class="num">${euro(row["Montant"])}</td>
    </tr>
  `).join("");

  return `
    <table>
      <thead>
        <tr>
          <th>${detailSortableHeader("Date", "Date")}</th>
          <th>${detailSortableHeader("Réalisé par", "Réalisé par")}</th>
          <th>${detailSortableHeader("Vers", "Vers")}</th>
          <th class="num">${detailSortableHeader("Montant", "Montant")}</th>
        </tr>
      </thead>
      <tbody>
        ${body || `<tr><td colspan="4">Aucune ligne</td></tr>`}
      </tbody>
    </table>
  `;
}

function paginatedTransactionTable(rows) {
  const sortedRows = sortRows(rows);
  const totalRows = sortedRows.length;
  const pageSize = Number(appState.detailPageSize || 50);
  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));

  const requestedPage = Number(appState.detailPage || 1);
  const currentPage = Math.min(Math.max(requestedPage, 1), totalPages);
  appState.detailPage = currentPage;

  const startIndex = (currentPage - 1) * pageSize;
  const pageRows = sortedRows.slice(startIndex, startIndex + pageSize);

  const startDisplay = totalRows ? startIndex + 1 : 0;
  const endDisplay = totalRows ? Math.min(startIndex + pageRows.length, totalRows) : 0;

  const body = pageRows.map(row => `
    <tr>
      <td>${escapeHtml(row.Date)}</td>
      <td>${renderActorLink(row["Réalisé par"])}</td>
      <td>${renderActorLink(row["Vers"])}</td>
      <td class="num">${euro(row["Montant"])}</td>
    </tr>
  `).join("");

  const pagination = totalRows ? `
    <div class="detail-pagination">
      <div class="detail-pagination-meta">
        Transactions ${startDisplay}–${endDisplay} sur ${totalRows}
      </div>

      ${totalPages > 1 ? `
        <div class="detail-pagination-controls">
          <button
            class="secondary-btn"
            type="button"
            onclick="changeDetailTransactionPage(-1)"
            ${currentPage <= 1 ? "disabled" : ""}
          >
            ← Précédent
          </button>

          <span class="detail-pagination-page">Page ${currentPage} / ${totalPages}</span>

          <button
            class="secondary-btn"
            type="button"
            onclick="changeDetailTransactionPage(1)"
            ${currentPage >= totalPages ? "disabled" : ""}
          >
            Suivant →
          </button>
        </div>
      ` : ""}
    </div>
  ` : "";

  return `
    <table>
      <thead>
        <tr>
          <th>${detailSortableHeader("Date", "Date")}</th>
          <th>${detailSortableHeader("Réalisé par", "Réalisé par")}</th>
          <th>${detailSortableHeader("Vers", "Vers")}</th>
          <th class="num">${detailSortableHeader("Montant", "Montant")}</th>
        </tr>
      </thead>
      <tbody>
        ${body || `<tr><td colspan="4">Aucune ligne</td></tr>`}
      </tbody>
    </table>
    ${pagination}
  `;
}

function aggregateTable(rows, keyField, label) {
  const map = new Map();

  rows.forEach(row => {
    const key = String(row[keyField] || "").trim();
    const current = map.get(key) || { Libelle: key, Count: 0, Total: 0 };
    current.Count += 1;
    current.Total += Number(row["Montant"] || 0);
    map.set(key, current);
  });

  const aggregated = [...map.values()];

  const sortedRows = sortRows(aggregated, (row, key) => {
    if (key === "Libelle") return row.Libelle;
    if (key === "Count") return row.Count;
    if (key === "Total") return row.Total;
    return row[key];
  });

  const body = sortedRows.map(item => `
    <tr>
      <td>${renderActorLink(item.Libelle)}</td>
      <td class="num">${item.Count}</td>
      <td class="num">${euro(item.Total)}</td>
    </tr>
  `).join("");

  return `
    <table>
      <thead>
        <tr>
          <th>${detailSortableHeader(label, "Libelle")}</th>
          <th class="num">${detailSortableHeader("Nb opérations", "Count")}</th>
          <th class="num">${detailSortableHeader("Montant total", "Total")}</th>
        </tr>
      </thead>
      <tbody>
        ${body || `<tr><td colspan="3">Aucune ligne</td></tr>`}
      </tbody>
    </table>
  `;
}

function buildDetailSection(numProf, allTx, mode) {
  const filteredTx = getFilteredTransactionsByPeriod(allTx);
  
  let title = "Transactions";
  let html = "";

  if (mode === "recues") {
    const rows = filteredTx.filter(row =>
      String(row["Vers"] || "").includes(numProf) &&
      !isConversion(row["Réalisé par"])
    );
    title = `Transactions reçues (${rows.length})`;
    html = paginatedTransactionTable(rows);
  }

  if (mode === "somme_recue") {
    const rows = filteredTx.filter(row =>
      String(row["Vers"] || "").includes(numProf) &&
      !isConversion(row["Réalisé par"])
    );
    title = "Acheteurs / payeurs";
    html = aggregateTable(rows, "Réalisé par", "Acheteur");
  }

  if (mode === "payeurs_particuliers") {
    const rows = filteredTx.filter(row =>
      String(row["Vers"] || "").includes(numProf) &&
      isUser(row["Réalisé par"]) &&
      !isConversion(row["Réalisé par"])
    );
    title = "Particuliers payeurs";
    html = aggregateTable(rows, "Réalisé par", "Particulier");
  }

  if (mode === "payeurs_professionnels") {
    const rows = filteredTx.filter(row =>
      String(row["Vers"] || "").includes(numProf) &&
      isPro(row["Réalisé par"]) &&
      !isConversion(row["Réalisé par"])
    );
    title = "Professionnels payeurs";
    html = aggregateTable(rows, "Réalisé par", "Professionnel");
  }

  if (mode === "emis_pro") {
    const rows = filteredTx.filter(row =>
      String(row["Réalisé par"] || "").includes(numProf) &&
      isPro(row["Vers"])
    );
    title = "Vendeurs professionnels";
    html = aggregateTable(rows, "Vers", "Vendeur pro");
  }

  if (mode === "emis_particuliers") {
    const rows = filteredTx.filter(row =>
      String(row["Réalisé par"] || "").includes(numProf) &&
      isUser(row["Vers"])
    );
    title = "Destinataires particuliers";
    html = aggregateTable(rows, "Vers", "Particulier");
  }

  if (mode === "emis_total") {
    const rows = filteredTx.filter(row =>
      String(row["Réalisé par"] || "").includes(numProf) &&
      (
        isPro(row["Vers"]) ||
        isUser(row["Vers"])
      )
    );
    title = "Destinataires des émissions hors reconversion";
    html = aggregateTable(rows, "Vers", "Destinataire");
  }

  if (mode === "reconverti") {
    const rows = filteredTx.filter(row =>
      String(row["Réalisé par"] || "").includes(numProf) &&
      isConversion(row["Vers"])
    );
    title = "Opérations de reconversion";
    html = paginatedTransactionTable(rows);
  }

  if (mode === "converti") {
    const rows = filteredTx.filter(row =>
      String(row["Vers"] || "").includes(numProf) &&
      isConversion(row["Réalisé par"])
    );
    title = "Opérations de conversion reçues";
    html = paginatedTransactionTable(rows);
  }

  if (mode === "all") {
    title = `Toutes les transactions (${filteredTx.length})`;
    html = paginatedTransactionTable(filteredTx);
  }

  return `
    <div class="card">
      <div class="detail-section-header">
        <h3 class="detail-section-title">${title}</h3>

        <div class="detail-section-actions">
          <div class="detail-filter-badge">
            <span class="detail-filter-label">Filtre actif</span>
            <span class="detail-filter-value">${escapeHtml(getDetailModeLabel(mode))}</span>
          </div>

          <button class="secondary-btn detail-show-all-btn" onclick="renderProDetail('${escapeHtml(numProf)}', 'all')">Tout voir</button>
        </div>
      </div>

      ${html}
    </div>
  `;
}
  
const PERIOD_AUTO_APPLY_DELAY_MS = 260;
let periodAutoApplyTimer = null;

function initSidebarCollapse() {
  const collapseBtn = document.getElementById("sidebarCollapseBtn");
  const body = document.body;

  if (!collapseBtn || !body) {
    return;
  }

  const storageKey = "mlcflux_sidebar_collapsed";
  const stored = localStorage.getItem(storageKey);
  const isCollapsed = stored === "1";

  body.classList.toggle("sidebar-collapsed", isCollapsed);
  collapseBtn.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
  collapseBtn.title = isCollapsed
    ? "Déplier le volet latéral"
    : "Replier le volet latéral";

  if (collapseBtn.dataset.bound === "true") {
    return;
  }

  collapseBtn.addEventListener("click", () => {
    const nextCollapsed = !body.classList.contains("sidebar-collapsed");

    body.classList.toggle("sidebar-collapsed", nextCollapsed);
    collapseBtn.setAttribute("aria-expanded", nextCollapsed ? "false" : "true");
    collapseBtn.title = nextCollapsed
      ? "Déplier le volet latéral"
      : "Replier le volet latéral";

    localStorage.setItem(storageKey, nextCollapsed ? "1" : "0");
  });

  collapseBtn.dataset.bound = "true";
}

function scheduleAnalysisPeriodApply(delay = PERIOD_AUTO_APPLY_DELAY_MS) {
  window.clearTimeout(periodAutoApplyTimer);

  periodAutoApplyTimer = window.setTimeout(async () => {
    await applyAnalysisPeriod();
  }, delay);
}


function getPeriodQueryParam() {
  const params = new URLSearchParams();

  if (appState.analysisPeriod.start) {
    params.set("start", appState.analysisPeriod.start);
  }

  if (appState.analysisPeriod.end) {
    params.set("end", appState.analysisPeriod.end);
  }

  const query = params.toString();
  return query ? `?${query}` : "";
}

function getPeriodCacheKey() {
  const { preset, start, end } = appState.analysisPeriod;
  return `${preset || "custom"}|${start || "none"}|${end || "none"}`;
}

function shiftIsoDate(dateString, days) {
  if (!dateString) return null;

  const date = new Date(`${dateString}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return null;

  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function clampDateToBounds(dateString) {
  if (!dateString) return dateString;

  const { min, max } = appState.periodBounds;

  if (min && dateString < min) return min;
  if (max && dateString > max) return max;

  return dateString;
}

function formatIsoDateForSidebar(dateString) {
  if (!dateString) return "-";

  const [year, month, day] = String(dateString).split("-");
  if (!year || !month || !day) return dateString;

  return `${day}/${month}/${year}`;
}

function setCustomPeriodFieldsExpanded(expanded) {
  const customFields = document.getElementById("customPeriodFields");
  const activeSummary = document.getElementById("periodActiveSummary");
  const isExpanded = Boolean(expanded);

  if (customFields) {
    customFields.classList.toggle("hidden", !isExpanded);
  }

  if (activeSummary) {
    activeSummary.setAttribute("aria-expanded", isExpanded ? "true" : "false");
  }
}

function toggleCustomPeriodFields(preset) {
  setCustomPeriodFieldsExpanded(preset === "custom");
}

function getPresetPeriod(preset) {
  const { min, max } = appState.periodBounds;

  if (!min || !max) {
    return { start: null, end: null };
  }

  if (preset === "last30") {
    return {
      start: clampDateToBounds(shiftIsoDate(max, -29)),
      end: max
    };
  }

  if (preset === "last90") {
    return {
      start: clampDateToBounds(shiftIsoDate(max, -89)),
      end: max
    };
  }

  const fixedYearMatch = /^year(\d{4})$/.exec(preset || "");
  if (fixedYearMatch) {
    const year = fixedYearMatch[1];
    return {
      start: clampDateToBounds(`${year}-01-01`),
      end: clampDateToBounds(`${year}-12-31`)
    };
  }

  if (preset === "currentYear") {
    const yearStart = `${max.slice(0, 4)}-01-01`;
    return {
      start: clampDateToBounds(yearStart),
      end: max
    };
  }

  return {
    start: min,
    end: max
  };
}

function updatePeriodHint(text = null) {
  const hint = document.getElementById("periodFilterHint");
  if (!hint) return;

  if (text) {
    hint.textContent = text;
    return;
  }

  const { start, end } = appState.analysisPeriod;

  if (start && end) {
    hint.textContent = `${formatIsoDateForSidebar(start)} → ${formatIsoDateForSidebar(end)}`;
  } else {
    hint.textContent = "Aucune période disponible.";
  }
}

function syncPeriodInputsFromValues(preset, start, end) {
  const presetEl = document.getElementById("periodPreset");
  const startEl = document.getElementById("periodStart");
  const endEl = document.getElementById("periodEnd");

  if (!presetEl || !startEl || !endEl) return;

  presetEl.value = preset || "custom";
  startEl.value = start || "";
  endEl.value = end || "";

  if (appState.periodBounds.min) {
    startEl.min = appState.periodBounds.min;
    endEl.min = appState.periodBounds.min;
  }

  if (appState.periodBounds.max) {
    startEl.max = appState.periodBounds.max;
    endEl.max = appState.periodBounds.max;
  }

}

function updatePeriodDraftFromPreset(preset) {
  if (preset === "custom") {
    setCustomPeriodFieldsExpanded(true);
    return;
  }

  const { start, end } = getPresetPeriod(preset);
  syncPeriodInputsFromValues(preset, start, end);
  setCustomPeriodFieldsExpanded(false);
}

function markPeriodAsCustom() {
  const presetEl = document.getElementById("periodPreset");
  if (presetEl) {
    presetEl.value = "custom";
  }

  setCustomPeriodFieldsExpanded(true);
}

async function reloadCurrentViewForPeriod() {
  const scrollPositionBeforeRefresh = captureViewportScrollPosition();

  const useSoftPeriodRefresh = (
    appState.currentView !== "info"
  );

  if (useSoftPeriodRefresh) {
    beginPeriodRefreshFeedback();
  }

  try {

  const activeStatsTab = document.querySelector("[data-stats-tab].tab-btn-active")?.dataset.statsTab || null;
  const activePilotageTab = document.querySelector("[data-pilotage-tab].tab-btn-active")?.dataset.pilotageTab || null;

  appState.statsCache = {};
  appState.prosData = [];
  appState.detailData = null;

  if (appState.currentView === "pro-detail" && appState.currentPro) {
    await renderProDetail(appState.currentPro, appState.detailMode);
    return;
  }

  appState.currentPro = null;

  if (appState.currentView === "stats") {
    await renderStatsView(true);

    if (activeStatsTab) {
      const restoreButton = document.querySelector(`[data-stats-tab="${activeStatsTab}"]`);
      if (restoreButton) {
        restoreButton.click();
      }
    }
  } else if (appState.currentView === "monetary-pilotage") {
    await renderMonetaryPilotageView(true);

    if (activePilotageTab) {
      const restoreButton = document.querySelector(`[data-pilotage-tab="${activePilotageTab}"]`);
      if (restoreButton) {
        restoreButton.click();
      }
    }
  } else if (appState.currentView === "pros") {
    await renderProsView(true);
  } else if (appState.currentView === "network") {
    appState.professionalsViewTab = "network";
    await renderProsView(true);
  } else if (appState.currentView === "cartography") {
    await renderCartographyView(true);
  } else if (appState.currentView === "territories") {
    await renderTerritoriesView(true);
  } else if (appState.currentView === "sectors") {
    await renderSectorsView(true);
  } else if (appState.currentView === "info") {
    await renderInfoView(false);
  } else {
    await renderStatsView(true);
  }

  } finally {
    restoreViewportScrollPosition(scrollPositionBeforeRefresh);

    if (useSoftPeriodRefresh) {
      endPeriodRefreshFeedback();
    }
  }
}

function captureViewportScrollPosition() {
  return {
    x: window.scrollX || window.pageXOffset || 0,
    y: window.scrollY || window.pageYOffset || 0
  };
}

function restoreViewportScrollPosition(position) {
  if (!position) return;

  const targetX = Number(position.x || 0);
  const targetY = Number(position.y || 0);

  // Après un remplacement de DOM, le navigateur peut recalculer la hauteur
  // de la page sur plusieurs frames. On restaure donc la position deux fois :
  // une première fois après le rendu immédiat, une seconde après stabilisation.
  window.requestAnimationFrame(() => {
    window.scrollTo({
      left: targetX,
      top: targetY,
      behavior: "auto"
    });

    window.requestAnimationFrame(() => {
      window.scrollTo({
        left: targetX,
        top: targetY,
        behavior: "auto"
      });
    });
  });
}

function beginPeriodRefreshFeedback(
  message = "Mise à jour de la période et des indicateurs…"
) {
  appState.periodRefreshInProgress = true;
  document.body.classList.add("period-refreshing");

  let indicator = document.getElementById("periodRefreshIndicator");

  if (!indicator) {
    indicator = document.createElement("div");
    indicator.id = "periodRefreshIndicator";
    indicator.className = "period-refresh-indicator";
    indicator.setAttribute("role", "status");
    indicator.setAttribute("aria-live", "polite");
    document.body.appendChild(indicator);
  }

  indicator.hidden = false;
  indicator.innerHTML = `
    <span class="period-refresh-indicator-dot" aria-hidden="true"></span>
    <span data-period-refresh-message></span>
  `;

  const messageNode = indicator.querySelector("[data-period-refresh-message]");
  if (messageNode) {
    messageNode.textContent = message;
  }
}

function endPeriodRefreshFeedback() {
  appState.periodRefreshInProgress = false;
  document.body.classList.remove("period-refreshing");

  const indicator = document.getElementById("periodRefreshIndicator");
  if (indicator) {
    indicator.hidden = true;
  }
}

function shouldPreservePeriodRefreshView(viewName, _forceReload = false) {
  return Boolean(
    appState.periodRefreshInProgress
    && appState.currentView === viewName
    && content?.childElementCount > 0
  );
}


function waitForNextBrowserPaint() {
  return new Promise((resolve) => {
    window.requestAnimationFrame(() => resolve());
  });
}

const PROGRESSIVE_VIEW_SHELLS = {
  stats: {
    pageTitle: "Statistiques globales",
    eyebrow: "Lecture globale des flux",
    heading: "Les principaux indicateurs se mettent en place.",
    description:
      "La structure de l’analyse est affichée immédiatement. Les données de la période sélectionnée arrivent ensuite : indicateurs, répartitions et graphiques.",
    sections: [
      "Activité économique",
      "Alimentations et sorties du circuit",
      "Opérations associatives / techniques",
      "Comptes particuliers de dispositif"
    ]
  },

  "monetary-pilotage": {
    pageTitle: "Pilotage monétaire",
    eyebrow: "Analyse croisée Odoo × Cyclos",
    heading: "Les repères du pilotage monétaire apparaissent d’abord.",
    description:
      "Les cadres de lecture sont prêts. Les stocks, flux, ratios de réemploi et séries historiques sont calculés puis injectés dans un second temps.",
    sections: [
      "Synthèse monétaire",
      "Circulation et réemploi",
      "Détention et ancrage",
      "Séries historiques"
    ]
  },

  pros: {
    pageTitle: "Professionnels & particuliers",
    eyebrow: "Utilisateurs de la Gonette",
    heading: "La vue des communautés d’usage s’ouvre immédiatement.",
    description:
      "Les espaces de lecture sont disponibles dès l’entrée dans la page. Les synthèses, flux, réseau interprofessionnel, cartographies de clusters et classements sont ensuite hydratés.",
    sections: [
      "Vue d’ensemble U / P",
      "Circulation et multiplicateur",
      "Réseau interprofessionnel",
      "Cartographie des clusters",
      "Classements et détails"
    ]
  },

  sectors: {
    pageTitle: "Analyse sectorielle",
    eyebrow: "Activité par grands secteurs",
    heading: "La lecture sectorielle est déjà en place.",
    description:
      "Les familles d’analyse sont affichées avant le calcul des volumes, des ratios de réemploi et des répartitions par secteur.",
    sections: [
      "Vue d’ensemble",
      "Secteurs actifs",
      "Réutilisation",
      "Tableau détaillé"
    ]
  },

  territories: {
    pageTitle: "Analyse territoriale — codes postaux",
    eyebrow: "Géographie de l’activité",
    heading: "Le cadre territorial est prêt.",
    description:
      "Les principaux blocs de lecture apparaissent immédiatement. Les données par code postal et les indicateurs associés sont chargés ensuite.",
    sections: [
      "Synthèse territoriale",
      "Répartition des volumes",
      "Réemploi local",
      "Tableau des territoires"
    ]
  },

  cartography: {
    pageTitle: "Cartographie des professionnels",
    eyebrow: "Implantation et activité",
    heading: "La cartographie prépare ses données.",
    description:
      "La page existe déjà visuellement ; les professionnels géolocalisés, leurs métriques et la carte interactive arrivent ensuite.",
    sections: [
      "Carte des professionnels",
      "Repères d’activité",
      "Filtres",
      "Lecture géographique"
    ]
  }
};

function renderProgressiveViewShell(viewKey) {
  const shell = PROGRESSIVE_VIEW_SHELLS[viewKey];
  if (!shell) return false;

  appState.currentView = viewKey;
  syncSidebarView(viewKey);
  setTitle(shell.pageTitle);

  const sectionCards = shell.sections.map((section) => `
    <article class="progressive-shell-card">
      <div class="progressive-shell-card-line progressive-shell-card-line-short"></div>
      <strong>${section}</strong>
      <div class="progressive-shell-card-line"></div>
      <div class="progressive-shell-card-line progressive-shell-card-line-medium"></div>
    </article>
  `).join("");

  content.innerHTML = `
    <section class="card progressive-shell-overview">
      <div class="stat-label">${shell.eyebrow}</div>
      <h2>${shell.heading}</h2>
      <p>${shell.description}</p>
    </section>

    <section class="progressive-shell-grid">
      ${sectionCards}
    </section>
  `;

  return true;
}

async function runProgressiveViewHydration({
  viewKey,
  hydrate,
  message = "Chargement des données…"
}) {
  const shellRendered = renderProgressiveViewShell(viewKey);

  if (shellRendered) {
    await waitForNextBrowserPaint();

    beginPeriodRefreshFeedback(message);
    try {
      await hydrate();
    } finally {
      endPeriodRefreshFeedback();
    }

    return;
  }

  await hydrate();
}

async function openViewProgressively(viewKey) {
  if (viewKey === "stats") {
    await runProgressiveViewHydration({
      viewKey,
      hydrate: () => renderStatsView(false),
      message: "Chargement des statistiques de la période…"
    });
    return;
  }

  if (viewKey === "monetary-pilotage") {
    await runProgressiveViewHydration({
      viewKey,
      hydrate: () => renderMonetaryPilotageView(false),
      message: "Chargement du pilotage monétaire…"
    });
    return;
  }

  if (viewKey === "pros") {
    await runProgressiveViewHydration({
      viewKey,
      hydrate: () => renderProsView(false),
      message: "Chargement de la vue Professionnels & particuliers…"
    });
    return;
  }

  if (viewKey === "cartography") {
    await runProgressiveViewHydration({
      viewKey,
      hydrate: () => renderCartographyView(false),
      message: "Chargement de la cartographie…"
    });
    return;
  }

  if (viewKey === "territories") {
    await runProgressiveViewHydration({
      viewKey,
      hydrate: () => renderTerritoriesView(false),
      message: "Chargement de l’analyse territoriale…"
    });
    return;
  }

  if (viewKey === "sectors") {
    await runProgressiveViewHydration({
      viewKey,
      hydrate: () => renderSectorsView(false),
      message: "Chargement de l’analyse sectorielle…"
    });
    return;
  }

  if (viewKey === "network") {
    appState.professionalsViewTab = "network";
    await runProgressiveViewHydration({
      viewKey: "pros",
      hydrate: () => renderProsView(false),
      message: "Chargement du réseau interprofessionnel…"
    });
    return;
  }

  if (viewKey === "tickets") {
    await renderTicketsView();
    return;
  }

  if (viewKey === "info") {
    await renderInfoView();
  }
}



async function applyAnalysisPeriod() {
  const presetEl = document.getElementById("periodPreset");
  const startEl = document.getElementById("periodStart");
  const endEl = document.getElementById("periodEnd");

  if (!presetEl || !startEl || !endEl) return;

  const start = startEl.value || appState.periodBounds.min;
  const end = endEl.value || appState.periodBounds.max;

  if (!start || !end) {
    alert("Aucune période exploitable n’est disponible.");
    return;
  }

  if (start > end) {
    alert("La date de début doit être antérieure ou égale à la date de fin.");
    return;
  }

  appState.analysisPeriod = {
    preset: presetEl.value || "custom",
    start,
    end
  };

  syncPeriodInputsFromValues(appState.analysisPeriod.preset, start, end);
  updatePeriodHint();

  await reloadCurrentViewForPeriod();
}

async function resetAnalysisPeriod() {
  const { start, end } = getPresetPeriod("all");

  appState.analysisPeriod = {
    preset: "all",
    start,
    end
  };

  syncPeriodInputsFromValues("all", start, end);
  updatePeriodHint();

  await reloadCurrentViewForPeriod();
}

async function initPeriodFilter() {
  const presetEl = document.getElementById("periodPreset");
  const startEl = document.getElementById("periodStart");
  const endEl = document.getElementById("periodEnd");
  const activeSummary = document.getElementById("periodActiveSummary");

  if (!presetEl || !startEl || !endEl || !activeSummary) return;

  try {
    const bounds = await apiGet("/api/period-bounds");

    appState.periodBounds = {
      min: bounds?.min_date || null,
      max: bounds?.max_date || null
    };

    const { start, end } = getPresetPeriod("currentYear");

    appState.analysisPeriod = {
      preset: "currentYear",
      start,
      end
    };

    syncPeriodInputsFromValues("currentYear", start, end);
    updatePeriodHint();
  } catch (err) {
    console.error("Impossible de charger les bornes temporelles :", err);
    updatePeriodHint("Impossible de charger la période disponible.");
  }

  if (presetEl.dataset.bound === "true") return;

  presetEl.addEventListener("change", async (event) => {
    const preset = event.target.value;
    updatePeriodDraftFromPreset(preset);

    if (preset !== "custom") {
      await applyAnalysisPeriod();
    }
  });

  activeSummary.addEventListener("click", () => {
    const isExpanded = activeSummary.getAttribute("aria-expanded") === "true";

    if (isExpanded) {
      setCustomPeriodFieldsExpanded(false);
      return;
    }

    presetEl.value = "custom";
    setCustomPeriodFieldsExpanded(true);
    startEl.focus();
  });

  startEl.addEventListener("change", () => {
    markPeriodAsCustom();
    scheduleAnalysisPeriodApply();
  });

  endEl.addEventListener("change", () => {
    markPeriodAsCustom();
    scheduleAnalysisPeriodApply();
  });

  presetEl.dataset.bound = "true";
}


function slugifyInfoHeadingText(text) {
  return String(text || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9à-öø-ÿ_-]/g, "");
}

function decorateInfoMarkdownHeadings(container) {
  if (!container) {
    return;
  }

  const usedIds = new Map();

  container.querySelectorAll("h1, h2, h3, h4, h5, h6").forEach((heading) => {
    const baseId = slugifyInfoHeadingText(heading.textContent);

    if (!baseId) {
      return;
    }

    const occurrence = usedIds.get(baseId) || 0;
    const uniqueId = occurrence === 0
      ? baseId
      : `${baseId}-${occurrence + 1}`;

    usedIds.set(baseId, occurrence + 1);
    heading.id = uniqueId;
  });
}

function renderInfoMarkdownToc(reader) {
  const toc = document.getElementById("infoMarkdownToc");
  const tocCard = document.getElementById("infoMarkdownTocCard");

  if (!toc || !tocCard || !reader) {
    return;
  }

  const headings = Array.from(reader.querySelectorAll("h1[id], h2[id], h3[id]"))
    .filter((heading) => String(heading.textContent || "").trim());

  if (headings.length === 0) {
    tocCard.classList.add("is-empty");
    toc.innerHTML = `
      <p class="info-toc-empty">
        Aucun titre détecté dans la fiche.
      </p>
    `;
    return;
  }

  tocCard.classList.remove("is-empty");

  const items = headings.map((heading) => {
    const rawLevel = Number(String(heading.tagName || "H1").slice(1));
    const level = Math.min(Math.max(rawLevel || 1, 1), 3);
    const label = String(heading.textContent || "").trim();
    const href = `#${encodeURIComponent(heading.id)}`;

    return `
      <li class="info-toc-item info-toc-level-${level}">
        <a href="${href}">${escapeHtml(label)}</a>
      </li>
    `;
  }).join("");

  toc.innerHTML = `
    <ul class="info-toc-list">
      ${items}
    </ul>
  `;
}


function renderInfoMarkdown(markdown) {
  const source = String(markdown || "").replace(/^[\u200B\u200C\u200D\u200E\u200F\uFEFF]/, "");

  if (
    !window.marked
    || typeof window.marked.parse !== "function"
    || !window.DOMPurify
    || typeof window.DOMPurify.sanitize !== "function"
  ) {
    return `<pre class="info-markdown-fallback">${escapeHtml(source)}</pre>`;
  }

  const rawHtml = window.marked.parse(source, {
    gfm: true,
    breaks: false
  });

  return window.DOMPurify.sanitize(rawHtml, {
    USE_PROFILES: { html: true }
  });
}

function setInfoFeedback(message, isError = false) {
  const feedback = document.getElementById("infoFeedback");
  if (!feedback) return;

  feedback.textContent = message || "";
  feedback.classList.toggle("hidden", !message);
  feedback.classList.toggle("is-error", Boolean(isError));
  feedback.classList.toggle("is-success", Boolean(message) && !isError);
}

function renderInfoPageCards(pages, activePageSlug) {
  const safePages = Array.isArray(pages) ? pages : [];

  if (safePages.length === 0) {
    return `
      <p class="info-page-grid-empty">
        Aucune fiche de documentation disponible.
      </p>
    `;
  }

  return safePages.map((page) => {
    const slug = String(page?.slug || "");
    const title = String(page?.title || "Fiche sans titre");
    const kicker = String(page?.kicker || "Documentation");
    const summary = String(page?.summary || "");
    const isActive = slug && slug === activePageSlug;

    return `
      <button
        class="card info-page-card ${isActive ? "is-active" : ""}"
        type="button"
        data-info-page-slug="${escapeHtml(slug)}"
        aria-pressed="${isActive ? "true" : "false"}"
      >
        <span class="info-page-card-kicker">${escapeHtml(kicker)}</span>
        <strong class="info-page-card-title">${escapeHtml(title)}</strong>
        <span class="info-page-card-summary">${escapeHtml(summary)}</span>
      </button>
    `;
  }).join("");
}

function getActiveInfoPage() {
  const pages = Array.isArray(appState.info.pages) ? appState.info.pages : [];
  return pages.find((page) => page?.slug === appState.info.activePage) || null;
}

function renderInfoActivePageMeta(page) {
  const kicker = String(page?.kicker || "Documentation");
  const title = String(page?.title || "Fiche de documentation");
  const summary = String(page?.summary || "");

  return `
    <div class="info-active-page-copy">
      <p class="info-view-kicker">${escapeHtml(kicker)}</p>
      <h3>${escapeHtml(title)}</h3>
      <p class="info-active-page-summary">${escapeHtml(summary)}</p>
    </div>
  `;
}

function normalizeInfoDocumentationSearchText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/→/g, " vers ")
    .replace(/[^\w]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function stripInfoMarkdownForSearch(markdown) {
  return String(markdown || "")
    .replace(/```[\s\S]*?```/g, (block) => block.replace(/```/g, " "))
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^>\s?/gm, "")
    .replace(/[*_`~]/g, "")
    .replace(/\[(.*?)\]\((.*?)\)/g, "$1")
    .replace(/\|/g, " ")
    .replace(/-{3,}/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function extractInfoSearchSections(markdown) {
  const lines = String(markdown || "").split(/\r?\n/);
  const sections = [];
  const usedIds = new Map();

  let current = {
    heading: "",
    level: 0,
    body: []
  };

  const pushCurrent = () => {
    const heading = String(current.heading || "").trim();

    if (!heading) {
      return;
    }

    const baseId = slugifyInfoHeadingText(heading);
    const occurrence = usedIds.get(baseId) || 0;
    const anchorId = occurrence === 0
      ? baseId
      : `${baseId}-${occurrence + 1}`;

    usedIds.set(baseId, occurrence + 1);

    const bodyMarkdown = current.body.join("\n");
    const bodyText = stripInfoMarkdownForSearch(bodyMarkdown);

    sections.push({
      heading,
      level: current.level,
      anchorId,
      bodyText,
      searchableText: normalizeInfoDocumentationSearchText(
        `${heading} ${bodyText}`
      )
    });
  };

  lines.forEach((line) => {
    const match = line.match(/^(#{1,3})\s+(.+?)\s*$/);

    if (match) {
      pushCurrent();

      current = {
        heading: match[2],
        level: match[1].length,
        body: []
      };
      return;
    }

    current.body.push(line);
  });

  pushCurrent();

  return sections;
}

function prepareInfoSearchIndex(items) {
  const safeItems = Array.isArray(items) ? items : [];

  return safeItems.map((item) => {
    const page = item?.page || {};
    const markdown = String(item?.markdown || "");
    const title = String(page?.title || "");
    const kicker = String(page?.kicker || "");
    const summary = String(page?.summary || "");
    const plainText = stripInfoMarkdownForSearch(markdown);

    return {
      page,
      markdown,
      pageSearchText: normalizeInfoDocumentationSearchText(
        `${title} ${kicker} ${summary} ${plainText}`
      ),
      sections: extractInfoSearchSections(markdown)
    };
  });
}

async function ensureInfoSearchIndex() {
  if (Array.isArray(appState.info.searchIndex)) {
    return appState.info.searchIndex;
  }

  const data = await apiGet("/api/info-search-index");
  appState.info.searchIndex = prepareInfoSearchIndex(data.items || []);
  return appState.info.searchIndex;
}

function infoSearchAllTokensMatch(searchableText, tokens) {
  return tokens.every((token) => searchableText.includes(token));
}

function buildInfoSearchSnippet(text, tokens) {
  const source = String(text || "").replace(/\s+/g, " ").trim();

  if (!source) {
    return "";
  }

  const normalized = normalizeInfoDocumentationSearchText(source);
  let firstMatchIndex = -1;

  for (const token of tokens) {
    const index = normalized.indexOf(token);
    if (index !== -1 && (firstMatchIndex === -1 || index < firstMatchIndex)) {
      firstMatchIndex = index;
    }
  }

  if (firstMatchIndex === -1) {
    return source.length > 190
      ? `${source.slice(0, 187).trim()}…`
      : source;
  }

  const start = Math.max(0, firstMatchIndex - 55);
  const end = Math.min(source.length, firstMatchIndex + 135);
  const prefix = start > 0 ? "…" : "";
  const suffix = end < source.length ? "…" : "";

  return `${prefix}${source.slice(start, end).trim()}${suffix}`;
}

function scoreInfoSearchCandidate({
  tokens,
  page,
  section = null
}) {
  const titleText = normalizeInfoDocumentationSearchText(page?.title || "");
  const kickerText = normalizeInfoDocumentationSearchText(page?.kicker || "");
  const summaryText = normalizeInfoDocumentationSearchText(page?.summary || "");
  const sectionHeadingText = normalizeInfoDocumentationSearchText(section?.heading || "");
  const sectionBodyText = normalizeInfoDocumentationSearchText(section?.bodyText || "");

  let score = 0;

  tokens.forEach((token) => {
    if (sectionHeadingText.includes(token)) score += 14;
    if (titleText.includes(token)) score += 12;
    if (kickerText.includes(token)) score += 8;
    if (summaryText.includes(token)) score += 6;
    if (sectionBodyText.includes(token)) score += 3;
  });

  if (section && section.level === 1) score += 1;

  return score;
}

function searchInfoDocumentation(query) {
  const normalizedQuery = normalizeInfoDocumentationSearchText(query);
  const tokens = normalizedQuery
    .split(" ")
    .map((token) => token.trim())
    .filter((token) => token.length >= 1);

  if (tokens.length === 0) {
    return [];
  }

  const index = Array.isArray(appState.info.searchIndex)
    ? appState.info.searchIndex
    : [];

  const results = [];

  index.forEach((item) => {
    const page = item.page || {};

    item.sections.forEach((section) => {
      if (!infoSearchAllTokensMatch(section.searchableText, tokens)) {
        return;
      }

      results.push({
        kind: "section",
        pageSlug: page.slug,
        pageTitle: page.title,
        pageKicker: page.kicker,
        sectionHeading: section.heading,
        anchorId: section.anchorId,
        score: scoreInfoSearchCandidate({
          tokens,
          page,
          section
        }),
        snippet: buildInfoSearchSnippet(section.bodyText, tokens)
      });
    });

    const titleSummaryText = normalizeInfoDocumentationSearchText(
      `${page.title || ""} ${page.kicker || ""} ${page.summary || ""}`
    );

    if (infoSearchAllTokensMatch(titleSummaryText, tokens)) {
      results.push({
        kind: "page",
        pageSlug: page.slug,
        pageTitle: page.title,
        pageKicker: page.kicker,
        sectionHeading: "",
        anchorId: "",
        score: scoreInfoSearchCandidate({
          tokens,
          page
        }) + 4,
        snippet: String(page.summary || "")
      });
    }
  });

  const deduped = new Map();

  results.forEach((result) => {
    const key = `${result.pageSlug}::${result.anchorId || "__page__"}`;
    const existing = deduped.get(key);

    if (!existing || result.score > existing.score) {
      deduped.set(key, result);
    }
  });

  return Array.from(deduped.values())
    .sort((a, b) => b.score - a.score)
    .slice(0, 12);
}

function renderInfoSearchResults(results, query) {
  const container = document.getElementById("infoSearchResults");

  if (!container) {
    return;
  }

  const trimmedQuery = String(query || "").trim();

  if (!trimmedQuery) {
    container.classList.add("hidden");
    container.innerHTML = "";
    return;
  }

  if (!Array.isArray(results) || results.length === 0) {
    container.classList.remove("hidden");
    container.innerHTML = `
      <div class="info-search-empty">
        Aucun résultat documentaire trouvé pour
        <strong>${escapeHtml(trimmedQuery)}</strong>.
      </div>
    `;
    return;
  }

  container.classList.remove("hidden");
  container.innerHTML = `
    <div class="info-search-results-header">
      ${results.length} résultat${results.length > 1 ? "s" : ""} pertinent${results.length > 1 ? "s" : ""}
    </div>
    <div class="info-search-results-list">
      ${results.map((result) => {
        const label = result.kind === "section"
          ? result.sectionHeading
          : result.pageTitle;

        const path = result.kind === "section"
          ? `${result.pageTitle} → ${result.sectionHeading}`
          : result.pageTitle;

        return `
          <button
            class="info-search-result-item"
            type="button"
            data-info-search-page="${escapeHtml(result.pageSlug || "")}"
            data-info-search-anchor="${escapeHtml(result.anchorId || "")}"
          >
            <span class="info-search-result-kicker">
              ${escapeHtml(result.pageKicker || "Documentation")}
            </span>
            <strong class="info-search-result-title">
              ${escapeHtml(label || result.pageTitle || "Résultat documentaire")}
            </strong>
            <span class="info-search-result-path">
              ${escapeHtml(path || "")}
            </span>
            ${result.snippet ? `
              <span class="info-search-result-snippet">
                ${escapeHtml(result.snippet)}
              </span>
            ` : ""}
          </button>
        `;
      }).join("")}
    </div>
  `;
}

function highlightInfoSearchTarget(target) {
  if (!target) {
    return;
  }

  target.classList.add("info-search-target-highlight");

  window.setTimeout(() => {
    target.classList.remove("info-search-target-highlight");
  }, 2200);
}

function bindInfoSearch() {
  const input = document.getElementById("infoDocumentationSearch");
  const clearButton = document.getElementById("infoDocumentationSearchClear");
  const resultsContainer = document.getElementById("infoSearchResults");

  if (!input || !clearButton || !resultsContainer) {
    return;
  }

  const refreshSearch = async () => {
    const query = input.value || "";

    if (!query.trim()) {
      renderInfoSearchResults([], "");
      return;
    }

    resultsContainer.classList.remove("hidden");
    resultsContainer.innerHTML = `
      <div class="info-search-loading">
        Recherche dans la documentation…
      </div>
    `;

    await ensureInfoSearchIndex();

    const results = searchInfoDocumentation(query);
    renderInfoSearchResults(results, query);
  };

  input.addEventListener("input", refreshSearch);

  clearButton.addEventListener("click", () => {
    input.value = "";
    renderInfoSearchResults([], "");
    input.focus();
  });

  resultsContainer.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-info-search-page]");

    if (!button) {
      return;
    }

    const pageSlug = String(button.dataset.infoSearchPage || "").trim();
    const anchorId = String(button.dataset.infoSearchAnchor || "").trim();

    if (!pageSlug) {
      return;
    }

    appState.info.activePage = pageSlug;
    appState.info.markdown = null;

    await renderInfoView(true, pageSlug);

    if (anchorId) {
      window.setTimeout(() => {
        const target = document.getElementById(anchorId);

        if (target) {
          target.scrollIntoView({
            behavior: "smooth",
            block: "start"
          });

          highlightInfoSearchTarget(target);
        }
      }, 80);
    }
  });

  ensureInfoSearchIndex().catch((err) => {
    console.warn("Index de recherche Info indisponible :", err);
  });
}

function bindInfoPageCards() {
  document.querySelectorAll("[data-info-page-slug]").forEach((button) => {
    button.addEventListener("click", async () => {
      const slug = String(button.dataset.infoPageSlug || "").trim();

      if (!slug || slug === appState.info.activePage) {
        return;
      }

      appState.info.activePage = slug;
      appState.info.markdown = null;
      await renderInfoView(true, slug);
    });
  });
}

function bindInfoPageCreator() {
  const createButton = document.getElementById("infoCreatePageButton");
  const form = document.getElementById("infoPageCreatorForm");
  const panel = document.getElementById("infoPageCreatorPanel");
  const cancelButton = document.getElementById("infoCancelCreatePageButton");
  const submitButton = document.getElementById("infoSubmitCreatePageButton");
  const titleInput = document.getElementById("infoNewPageTitle");
  const kickerInput = document.getElementById("infoNewPageKicker");
  const summaryInput = document.getElementById("infoNewPageSummary");

  if (
    !createButton
    || !form
    || !panel
    || !cancelButton
    || !submitButton
    || !titleInput
    || !kickerInput
    || !summaryInput
  ) {
    return;
  }

  const openCreator = () => {
    panel.classList.remove("hidden");
    createButton.classList.add("hidden");
    titleInput.focus();
    setInfoFeedback("");
  };

  const closeCreator = () => {
    panel.classList.add("hidden");
    createButton.classList.remove("hidden");
    form.reset();
  };

  createButton.addEventListener("click", openCreator);

  cancelButton.addEventListener("click", () => {
    closeCreator();
    setInfoFeedback("Création de carte annulée.");
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const title = titleInput.value.trim();
    const kicker = kickerInput.value.trim();
    const summary = summaryInput.value.trim();

    if (!title) {
      setInfoFeedback("Le titre de la nouvelle carte est obligatoire.", true);
      titleInput.focus();
      return;
    }

    try {
      submitButton.disabled = true;
      cancelButton.disabled = true;
      submitButton.textContent = "Création...";

      const result = await apiPostJson("/api/info-pages", {
        title,
        kicker,
        summary
      });

      appState.info.pages = Array.isArray(result.pages) ? result.pages : null;
      appState.info.activePage = result.page?.slug || null;
      appState.info.markdown = result.markdown || null;

      await renderInfoView(true, appState.info.activePage);
      setInfoFeedback(result.message || "Nouvelle carte créée.");
    } catch (err) {
      setInfoFeedback(`Erreur : ${err.message}`, true);
    } finally {
      submitButton.disabled = false;
      cancelButton.disabled = false;
      submitButton.textContent = "Créer la carte";
    }
  });
}

function bindInfoEditor() {
  const editButton = document.getElementById("infoEditButton");
  const reader = document.getElementById("infoMarkdownReader");
  const editor = document.getElementById("infoMarkdownEditor");
  const textarea = document.getElementById("infoMarkdownTextarea");
  const preview = document.getElementById("infoMarkdownPreview");
  const titleInput = document.getElementById("infoEditPageTitle");
  const kickerInput = document.getElementById("infoEditPageKicker");
  const summaryInput = document.getElementById("infoEditPageSummary");
  const saveButton = document.getElementById("infoSaveButton");
  const cancelButton = document.getElementById("infoCancelButton");

  if (
    !editButton
    || !reader
    || !editor
    || !textarea
    || !preview
    || !titleInput
    || !kickerInput
    || !summaryInput
    || !saveButton
    || !cancelButton
  ) {
    return;
  }

  const refreshPreview = () => {
    preview.innerHTML = renderInfoMarkdown(textarea.value);
    decorateInfoMarkdownHeadings(preview);
  };

  const openEditor = () => {
    const activePage = getActiveInfoPage();

    titleInput.value = activePage?.title || "";
    kickerInput.value = activePage?.kicker || "";
    summaryInput.value = activePage?.summary || "";

    textarea.value = appState.info.markdown || "";
    refreshPreview();

    reader.classList.add("hidden");
    editor.classList.remove("hidden");
    editButton.classList.add("hidden");
    textarea.focus();
    setInfoFeedback("");
  };

  const closeEditor = () => {
    editor.classList.add("hidden");
    reader.classList.remove("hidden");
    editButton.classList.remove("hidden");
  };

  editButton.addEventListener("click", openEditor);

  cancelButton.addEventListener("click", () => {
    closeEditor();
    setInfoFeedback("Modification annulée.");
  });

  textarea.addEventListener("input", refreshPreview);

  saveButton.addEventListener("click", async () => {
    try {
      saveButton.disabled = true;
      cancelButton.disabled = true;
      saveButton.textContent = "Enregistrement...";

      const markdown = textarea.value;
      const metadataResult = await apiPostJson(
        `/api/info-pages/${encodeURIComponent(appState.info.activePage)}/metadata`,
        {
          title: titleInput.value.trim(),
          kicker: kickerInput.value.trim(),
          summary: summaryInput.value.trim()
        }
      );

      const result = await apiPostJson("/api/info-content", {
        page: appState.info.activePage,
        markdown
      });

      appState.info.pages = Array.isArray(metadataResult.pages)
        ? metadataResult.pages
        : appState.info.pages;
      appState.info.markdown = markdown;

      const updatedPage = getActiveInfoPage();
      const cards = document.getElementById("infoPageCards");
      const activeMetaHost = document.querySelector(".info-active-page-header .info-active-page-copy");

      if (cards) {
        cards.innerHTML = renderInfoPageCards(appState.info.pages, appState.info.activePage);
        bindInfoPageCards();
      }

      if (activeMetaHost && updatedPage) {
        activeMetaHost.outerHTML = renderInfoActivePageMeta(updatedPage);
      }

      appState.info.searchIndex = null;

      reader.innerHTML = renderInfoMarkdown(markdown);
      decorateInfoMarkdownHeadings(reader);
      renderInfoMarkdownToc(reader);

      closeEditor();
      setInfoFeedback(
        metadataResult.message
        || result.message
        || "Fiche enregistrée."
      );
    } catch (err) {
      setInfoFeedback(`Erreur : ${err.message}`, true);
    } finally {
      saveButton.disabled = false;
      cancelButton.disabled = false;
      saveButton.textContent = "Enregistrer";
    }
  });
}

async function renderInfoView(forceReload = false, requestedPageSlug = null) {
  appState.currentView = "info";
  syncSidebarView("info");
  destroyCartographyMap();
  setTitle("Info & méthodologie");

  content.innerHTML = `
    <section class="card">
      <h2>Info & méthodologie</h2>
      <p>Chargement de la documentation…</p>
    </section>
  `;

  try {
    const requestedSlug = String(
      requestedPageSlug || appState.info.activePage || ""
    ).trim();

    const mustReload = (
      forceReload
      || !Array.isArray(appState.info.pages)
      || appState.info.markdown === null
      || (requestedSlug && requestedSlug !== appState.info.activePage)
    );

    if (mustReload) {
      const endpoint = requestedSlug
        ? `/api/info-content?page=${encodeURIComponent(requestedSlug)}`
        : "/api/info-content";

      const data = await apiGet(endpoint);

      appState.info.pages = Array.isArray(data.pages) ? data.pages : [];
      appState.info.activePage = data.page?.slug
        || appState.info.pages[0]?.slug
        || null;
      appState.info.markdown = data.markdown || "";
    }

    const activePage = getActiveInfoPage();

    content.innerHTML = `
      <section class="card info-view-card">
        <div class="info-view-header">
          <div>
            <p class="info-view-kicker">Documentation modulaire</p>
            <h2>Info & méthodologie</h2>
            <p class="info-view-intro">
              La documentation est organisée en plusieurs fiches Markdown.
              Chaque carte ouvre un contenu thématique éditable directement depuis MLCFlux.
            </p>
          </div>

          <div class="info-view-actions">
            <a
              class="secondary-btn"
              href="https://github.com/kxsb/mlc_flux"
              target="_blank"
              rel="noopener noreferrer"
            >
              Voir le dépôt GitHub
            </a>

            <button id="infoCreatePageButton" class="secondary-btn" type="button">
              Créer une carte Markdown
            </button>
          </div>
        </div>

        <section class="card info-search-panel">
          <div class="info-search-header">
            <div>
              <p class="info-view-kicker">Recherche documentaire</p>
              <h3>Retrouver rapidement une formule, une notion ou un périmètre</h3>
            </div>
          </div>

          <div class="info-search-controls">
            <input
              id="infoDocumentationSearch"
              class="info-documentation-search-input"
              type="search"
              autocomplete="off"
              placeholder="Ex. LM3, U → P, fonds de garantie, comptes opérateurs, dormance…"
              aria-label="Rechercher dans la documentation Info et méthodologie"
            >
            <button
              id="infoDocumentationSearchClear"
              class="secondary-btn"
              type="button"
            >
              Effacer
            </button>
          </div>

          <div
            id="infoSearchResults"
            class="info-search-results hidden"
            aria-live="polite"
          ></div>
        </section>

        <div id="infoFeedback" class="info-feedback hidden"></div>

        <section id="infoPageCreatorPanel" class="card info-page-creator hidden">
          <form id="infoPageCreatorForm" class="info-page-creator-form">
            <div class="info-page-creator-header">
              <div>
                <p class="info-view-kicker">Nouvelle fiche</p>
                <h3>Créer une carte Markdown</h3>
              </div>
            </div>

            <div class="info-page-creator-grid">
              <div class="info-page-creator-field">
                <label for="infoNewPageTitle">Titre de la carte</label>
                <input
                  id="infoNewPageTitle"
                  type="text"
                  maxlength="140"
                  placeholder="Ex. Fonctions clés — onglets 1 & 2"
                  required
                >
              </div>

              <div class="info-page-creator-field">
                <label for="infoNewPageKicker">Petit repère</label>
                <input
                  id="infoNewPageKicker"
                  type="text"
                  maxlength="80"
                  placeholder="Ex. Antisèche technique"
                >
              </div>

              <div class="info-page-creator-field info-page-creator-field-wide">
                <label for="infoNewPageSummary">Résumé affiché sur la carte</label>
                <textarea
                  id="infoNewPageSummary"
                  maxlength="600"
                  placeholder="Ex. Tableau de référence des principales fonctions, endpoints et périmètres analytiques."
                ></textarea>
              </div>
            </div>

            <div class="info-page-creator-actions">
              <button id="infoSubmitCreatePageButton" class="primary-btn" type="submit">
                Créer la carte
              </button>
              <button id="infoCancelCreatePageButton" class="secondary-btn" type="button">
                Annuler
              </button>
            </div>
          </form>
        </section>

        <div class="info-page-grid" id="infoPageCards">
          ${renderInfoPageCards(appState.info.pages, appState.info.activePage)}
        </div>

        <section class="card info-active-page-card">
          <div class="info-active-page-header">
            ${renderInfoActivePageMeta(activePage)}
            <button id="infoEditButton" class="primary-btn" type="button">
              Modifier cette fiche
            </button>
          </div>

          <details id="infoMarkdownTocCard" class="info-toc-card" open>
            <summary class="info-toc-summary">
              Sommaire de la fiche
            </summary>
            <nav id="infoMarkdownToc" class="info-toc-nav" aria-label="Sommaire de la fiche">
              <p class="info-toc-empty">Chargement du sommaire…</p>
            </nav>
          </details>

          <div id="infoMarkdownReader" class="markdown-body info-markdown-reader">
            <p>Chargement de la documentation…</p>
          </div>

          <div id="infoMarkdownEditor" class="info-editor hidden">
            <section class="info-card-metadata-editor">
              <div class="info-card-metadata-editor-header">
                <p class="info-view-kicker">Métadonnées de la carte</p>
                <h4>Titre, sous-titre et résumé</h4>
              </div>

              <div class="info-card-metadata-grid">
                <div class="info-page-creator-field">
                  <label for="infoEditPageTitle">Titre de la carte</label>
                  <input
                    id="infoEditPageTitle"
                    type="text"
                    maxlength="140"
                  >
                </div>

                <div class="info-page-creator-field">
                  <label for="infoEditPageKicker">Sous-titre / repère</label>
                  <input
                    id="infoEditPageKicker"
                    type="text"
                    maxlength="80"
                  >
                </div>

                <div class="info-page-creator-field info-page-creator-field-wide">
                  <label for="infoEditPageSummary">Résumé affiché sur la carte</label>
                  <textarea
                    id="infoEditPageSummary"
                    maxlength="600"
                  ></textarea>
                </div>
              </div>
            </section>

            <div class="info-editor-grid">
              <div class="info-editor-column">
                <label class="info-editor-label" for="infoMarkdownTextarea">Markdown</label>
                <textarea
                  id="infoMarkdownTextarea"
                  class="info-markdown-textarea"
                  spellcheck="true"
                ></textarea>
              </div>

              <div class="info-editor-column">
                <div class="info-editor-label">Aperçu</div>
                <div
                  id="infoMarkdownPreview"
                  class="markdown-body info-markdown-preview"
                ></div>
              </div>
            </div>

            <div class="info-editor-actions">
              <button id="infoSaveButton" class="primary-btn" type="button">
                Enregistrer
              </button>
              <button id="infoCancelButton" class="secondary-btn" type="button">
                Annuler
              </button>
            </div>
          </div>
        </section>
      </section>
    `;

    const reader = document.getElementById("infoMarkdownReader");
    if (reader) {
      reader.innerHTML = renderInfoMarkdown(appState.info.markdown || "");
      decorateInfoMarkdownHeadings(reader);
      renderInfoMarkdownToc(reader);
    }

    bindInfoSearch();
    bindInfoPageCards();
    bindInfoPageCreator();
    bindInfoEditor();
  } catch (err) {
    content.innerHTML = `
      <section class="card">
        <h2>Info & méthodologie</h2>
        <p>Impossible de charger la documentation : ${escapeHtml(err.message)}</p>
      </section>
    `;
  }
}


function formatTicketDate(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return escapeHtml(String(value));
  }

  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

function ticketReplyCountLabel(messageCount) {
  const replies = Math.max(0, Number(messageCount || 0) - 1);
  return `${replies} réponse${replies > 1 ? "s" : ""}`;
}

function getTicketsQueryString() {
  const filters = appState.tickets.filters;
  const params = new URLSearchParams();

  if (filters.q) {
    params.set("q", filters.q);
  }

  if (filters.category) {
    params.set("category", filters.category);
  }

  if (filters.status) {
    params.set("status", filters.status);
  }

  if (filters.sort) {
    params.set("sort", filters.sort);
  }

  params.set("limit", "100");

  return `?${params.toString()}`;
}

function renderTicketSelectOptions(options, selectedValue, emptyLabel) {
  const entries = Object.entries(options || {});
  const emptyOption = emptyLabel
    ? `<option value="">${escapeHtml(emptyLabel)}</option>`
    : "";

  return emptyOption + entries.map(([value, label]) => `
    <option value="${escapeHtml(value)}" ${value === selectedValue ? "selected" : ""}>
      ${escapeHtml(label)}
    </option>
  `).join("");
}

function renderTicketStatusOptions(selectedValue, statuses) {
  const options = [
    `<option value="open" ${selectedValue === "open" ? "selected" : ""}>Tickets ouverts</option>`,
    `<option value="" ${selectedValue === "" ? "selected" : ""}>Tous les statuts</option>`
  ];

  Object.entries(statuses || {}).forEach(([value, label]) => {
    options.push(`
      <option value="${escapeHtml(value)}" ${value === selectedValue ? "selected" : ""}>
        ${escapeHtml(label)}
      </option>
    `);
  });

  return options.join("");
}

function renderTicketSortOptions(selectedValue) {
  const options = [
    ["last_activity", "Dernière activité"],
    ["newest", "Plus récents"],
    ["oldest", "Plus anciens"]
  ];

  return options.map(([value, label]) => `
    <option value="${value}" ${value === selectedValue ? "selected" : ""}>
      ${label}
    </option>
  `).join("");
}

function renderTicketBadge(ticket) {
  return `
    <span class="ticket-badge ticket-category-badge">
      ${escapeHtml(ticket.category_label || ticket.category || "Ticket")}
    </span>
    <span class="ticket-badge ticket-status-badge ticket-status-${escapeHtml(ticket.status || "new")}">
      ${escapeHtml(ticket.status_label || ticket.status || "Nouveau")}
    </span>
  `;
}

function renderTicketTeamBadge(ticket) {
  if (!Number(ticket.team_reply_count || 0)) {
    return "";
  }

  return `
    <span class="ticket-badge ticket-team-indicator">
      Réponse de l’équipe MLCFlux
    </span>
  `;
}

function renderTicketCards(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return `
      <section class="ticket-empty-state">
        <h3>Aucun ticket ne correspond à ces filtres.</h3>
        <p>
          Vous pouvez ajuster la recherche, afficher tous les statuts,
          ou ouvrir un nouveau ticket.
        </p>
      </section>
    `;
  }

  return items.map((ticket) => `
    <article class="ticket-list-card">
      <div class="ticket-card-badges">
        ${renderTicketBadge(ticket)}
        ${renderTicketTeamBadge(ticket)}
      </div>

      <button
        type="button"
        class="ticket-card-title"
        data-ticket-open="${escapeHtml(ticket.slug)}"
      >
        <span>${escapeHtml(ticket.public_ref || "")}</span>
        ${escapeHtml(ticket.title || "Ticket sans titre")}
      </button>

      <p class="ticket-card-excerpt">
        ${escapeHtml(ticket.opening_excerpt || "Aucun aperçu disponible.")}
      </p>

      <div class="ticket-card-meta">
        <span>Ouvert par <strong>${escapeHtml(ticket.author_name || "Anonyme")}</strong></span>
        <span>${ticketReplyCountLabel(ticket.message_count)}</span>
        <span>Dernière activité : ${formatTicketDate(ticket.last_activity_at)}</span>
      </div>

      <div class="ticket-card-actions">
        <button
          type="button"
          class="secondary-btn"
          data-ticket-open="${escapeHtml(ticket.slug)}"
        >
          Voir le fil
        </button>
      </div>
    </article>
  `).join("");
}

function setTicketCreateFeedback(message, isError = false) {
  const feedback = document.getElementById("ticketCreateFeedback");
  if (!feedback) return;

  feedback.textContent = message || "";
  feedback.classList.toggle("hidden", !message);
  feedback.classList.toggle("is-error", Boolean(isError));
  feedback.classList.toggle("is-success", Boolean(message) && !isError);
}

function setTicketDetailFeedback(message, isError = false) {
  const feedback = document.getElementById("ticketDetailFeedback");
  if (!feedback) return;

  feedback.textContent = message || "";
  feedback.classList.toggle("hidden", !message);
  feedback.classList.toggle("is-error", Boolean(isError));
  feedback.classList.toggle("is-success", Boolean(message) && !isError);
}

function renderTicketsViewMarkup(data) {
  const filters = appState.tickets.filters;
  const total = data?.pagination?.total ?? 0;
  const returned = data?.pagination?.returned ?? 0;
  const createHiddenClass = appState.tickets.createFormOpen ? "" : "hidden";

  return `
    <div class="tickets-view">
      <section class="card tickets-hero-card">
        <div class="tickets-hero-header">
          <div>
            <p class="tickets-kicker">Retours publics</p>
            <h2>Tickets & discussions</h2>
            <p class="tickets-intro">
              Signalez un bug, posez une question, suggérez une amélioration
              ou contribuez à un ticket existant.
            </p>
          </div>

          <button id="ticketCreateToggle" class="primary-btn" type="button">
            ${appState.tickets.createFormOpen ? "Fermer le formulaire" : "Ouvrir un ticket"}
          </button>
        </div>

        <div class="tickets-public-notice">
          <strong>Les tickets et les réponses sont publics.</strong>
          N’indiquez pas d’informations personnelles, confidentielles ou sensibles.
        </div>
      </section>

      <section id="ticketCreatePanel" class="card ticket-create-card ${createHiddenClass}">
        <div class="ticket-section-header">
          <div>
            <p class="tickets-kicker">Nouveau ticket</p>
            <h3>Déposer un retour</h3>
          </div>
        </div>

        <div id="ticketCreateFeedback" class="ticket-feedback hidden"></div>

        <form id="ticketCreateForm" class="ticket-form">
          <div class="ticket-form-grid">
            <div class="ticket-form-field">
              <label for="ticketCreateName">Nom ou pseudo *</label>
              <input id="ticketCreateName" name="author_name" type="text" maxlength="120" required />
            </div>

            <div class="ticket-form-field">
              <label for="ticketCreateEmail">Adresse email — facultative</label>
              <input id="ticketCreateEmail" name="author_email" type="email" maxlength="254" />
              <small>Elle n’est jamais affichée publiquement.</small>
            </div>

            <div class="ticket-form-field">
              <label for="ticketCreateCategory">Catégorie *</label>
              <select id="ticketCreateCategory" name="category" required>
                ${renderTicketSelectOptions(data.available_categories, "", "Choisir une catégorie")}
              </select>
            </div>

            <div class="ticket-form-field ticket-form-field-wide">
              <label for="ticketCreateTitle">Titre *</label>
              <input
                id="ticketCreateTitle"
                name="title"
                type="text"
                maxlength="180"
                placeholder="Résumez votre demande en une phrase"
                required
              />
            </div>

            <div class="ticket-form-field ticket-form-field-full">
              <label for="ticketCreateBody">Description *</label>
              <textarea
                id="ticketCreateBody"
                name="body_markdown"
                maxlength="20000"
                placeholder="Décrivez le problème, la question ou la suggestion…"
                required
              ></textarea>
            </div>
          </div>

          <div class="ticket-form-actions">
            <button id="ticketCreateSubmit" class="primary-btn" type="submit">
              Publier le ticket
            </button>
            <button id="ticketCreateCancel" class="secondary-btn" type="button">
              Annuler
            </button>
          </div>
        </form>
      </section>

      <section class="card ticket-filter-card">
        <div class="ticket-filter-header">
          <div>
            <p class="tickets-kicker">Explorer</p>
            <h3>Tickets publiés</h3>
          </div>
          <div class="ticket-results-count">
            ${returned} affiché${returned > 1 ? "s" : ""} · ${total} résultat${total > 1 ? "s" : ""}
          </div>
        </div>

        <form id="ticketFiltersForm" class="ticket-filters-form">
          <div class="ticket-filters-grid">
            <div class="ticket-form-field ticket-search-field">
              <label for="ticketFilterSearch">Recherche</label>
              <input
                id="ticketFilterSearch"
                type="search"
                value="${escapeHtml(filters.q)}"
                placeholder="Rechercher dans les titres ou messages…"
              />
            </div>

            <div class="ticket-form-field">
              <label for="ticketFilterCategory">Catégorie</label>
              <select id="ticketFilterCategory">
                ${renderTicketSelectOptions(data.available_categories, filters.category, "Toutes les catégories")}
              </select>
            </div>

            <div class="ticket-form-field">
              <label for="ticketFilterStatus">Statut</label>
              <select id="ticketFilterStatus">
                ${renderTicketStatusOptions(filters.status, data.available_statuses)}
              </select>
            </div>

            <div class="ticket-form-field">
              <label for="ticketFilterSort">Tri</label>
              <select id="ticketFilterSort">
                ${renderTicketSortOptions(filters.sort)}
              </select>
            </div>
          </div>

          <div class="ticket-filter-actions">
            <button class="primary-btn" type="submit">Appliquer</button>
            <button id="ticketFiltersReset" class="secondary-btn" type="button">Réinitialiser</button>
          </div>
        </form>
      </section>

      <section class="ticket-list-grid">
        ${renderTicketCards(data.items)}
      </section>
    </div>
  `;
}

function bindTicketsViewInteractions() {
  const toggleButton = document.getElementById("ticketCreateToggle");
  const createPanel = document.getElementById("ticketCreatePanel");
  const cancelButton = document.getElementById("ticketCreateCancel");
  const createForm = document.getElementById("ticketCreateForm");
  const filtersForm = document.getElementById("ticketFiltersForm");
  const resetFiltersButton = document.getElementById("ticketFiltersReset");

  if (toggleButton && createPanel) {
    toggleButton.addEventListener("click", () => {
      appState.tickets.createFormOpen = !appState.tickets.createFormOpen;
      createPanel.classList.toggle("hidden", !appState.tickets.createFormOpen);
      toggleButton.textContent = appState.tickets.createFormOpen
        ? "Fermer le formulaire"
        : "Ouvrir un ticket";

      if (appState.tickets.createFormOpen) {
        document.getElementById("ticketCreateName")?.focus();
      }
    });
  }

  if (cancelButton && createPanel && toggleButton) {
    cancelButton.addEventListener("click", () => {
      appState.tickets.createFormOpen = false;
      createPanel.classList.add("hidden");
      toggleButton.textContent = "Ouvrir un ticket";
      createForm?.reset();
      setTicketCreateFeedback("");
    });
  }

  if (createForm) {
    createForm.addEventListener("submit", async (event) => {
      event.preventDefault();

      const submitButton = document.getElementById("ticketCreateSubmit");
      const payload = {
        author_name: document.getElementById("ticketCreateName")?.value || "",
        author_email: document.getElementById("ticketCreateEmail")?.value || "",
        category: document.getElementById("ticketCreateCategory")?.value || "",
        title: document.getElementById("ticketCreateTitle")?.value || "",
        body_markdown: document.getElementById("ticketCreateBody")?.value || "",
        source_page: "/tickets"
      };

      try {
        if (submitButton) {
          submitButton.disabled = true;
          submitButton.textContent = "Publication...";
        }

        setTicketCreateFeedback("");
        const result = await apiPostJson("/api/tickets", payload);

        appState.tickets.createFormOpen = false;
        await renderTicketDetail(
          result.ticket.slug,
          "Ticket publié. La discussion est désormais visible publiquement."
        );
      } catch (err) {
        setTicketCreateFeedback(`Erreur : ${err.message}`, true);
      } finally {
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = "Publier le ticket";
        }
      }
    });
  }

  if (filtersForm) {
    filtersForm.addEventListener("submit", async (event) => {
      event.preventDefault();

      appState.tickets.filters.q = document.getElementById("ticketFilterSearch")?.value.trim() || "";
      appState.tickets.filters.category = document.getElementById("ticketFilterCategory")?.value || "";
      appState.tickets.filters.status = document.getElementById("ticketFilterStatus")?.value || "";
      appState.tickets.filters.sort = document.getElementById("ticketFilterSort")?.value || "last_activity";

      await renderTicketsView(true);
    });
  }

  if (resetFiltersButton) {
    resetFiltersButton.addEventListener("click", async () => {
      appState.tickets.filters = {
        q: "",
        category: "",
        status: "open",
        sort: "last_activity"
      };

      await renderTicketsView(true);
    });
  }

  document.querySelectorAll("[data-ticket-open]").forEach((button) => {
    button.addEventListener("click", async () => {
      const slug = button.dataset.ticketOpen;
      if (slug) {
        await renderTicketDetail(slug);
      }
    });
  });
}

async function renderTicketsView(forceReload = false) {
  destroyCartographyMap();
  appState.currentView = "tickets";
  syncSidebarView("tickets");
  setTitle("Tickets & retours");
  appState.tickets.currentSlug = null;
  appState.tickets.currentDetail = null;

  content.innerHTML = `<div class="card">Chargement des tickets…</div>`;

  try {
    const data = await apiGet(`/api/tickets${getTicketsQueryString()}`);
    appState.tickets.lastList = data;

    content.innerHTML = renderTicketsViewMarkup(data);
    bindTicketsViewInteractions();
  } catch (err) {
    content.innerHTML = `
      <section class="card">
        <h2>Tickets & retours</h2>
        <p>Impossible de charger les tickets : ${escapeHtml(err.message)}</p>
      </section>
    `;
  }
}

function renderTicketOfficialAnswer(messages) {
  const officialMessage = Array.isArray(messages)
    ? messages.find((message) => message.is_official_answer)
    : null;

  if (!officialMessage) {
    return "";
  }

  return `
    <section class="ticket-official-answer">
      <div class="ticket-official-answer-header">
        Réponse officielle — Équipe MLCFlux
      </div>
      <div class="markdown-body ticket-message-markdown">
        ${renderInfoMarkdown(officialMessage.body_markdown || "")}
      </div>
    </section>
  `;
}

function renderTicketMessages(messages) {
  if (!Array.isArray(messages) || messages.length === 0) {
    return `
      <div class="ticket-empty-state">
        <p>Aucun message public pour ce ticket.</p>
      </div>
    `;
  }

  return messages.map((message) => `
    <article class="ticket-message ${message.is_team_response ? "is-team-response" : ""}">
      <div class="ticket-message-header">
        <div class="ticket-message-author">
          <strong>${escapeHtml(message.author_name || "Anonyme")}</strong>
          ${message.is_team_response ? '<span class="ticket-team-badge">Équipe MLCFlux</span>' : ""}
          ${message.is_official_answer ? '<span class="ticket-official-mini-badge">Réponse officielle</span>' : ""}
        </div>
        <time>${formatTicketDate(message.created_at)}</time>
      </div>

      <div class="markdown-body ticket-message-markdown">
        ${renderInfoMarkdown(message.body_markdown || "")}
      </div>
    </article>
  `).join("");
}

function renderTicketDetailMarkup(data) {
  const ticket = data.ticket;
  const messages = data.messages || [];
  const isClosed = ticket.status === "closed";

  return `
    <div class="ticket-detail-view">
      <div class="topbar">
        <button id="ticketBackToList" class="secondary-btn" type="button">
          ← Retour aux tickets
        </button>
      </div>

      <section class="card ticket-detail-header-card">
        <div class="ticket-detail-badges">
          ${renderTicketBadge(ticket)}
          ${renderTicketTeamBadge(ticket)}
        </div>

        <h2>
          <span>${escapeHtml(ticket.public_ref || "")}</span>
          ${escapeHtml(ticket.title || "Ticket sans titre")}
        </h2>

        <div class="ticket-detail-meta">
          <span>Ouvert par <strong>${escapeHtml(ticket.author_name || "Anonyme")}</strong></span>
          <span>Créé le ${formatTicketDate(ticket.created_at)}</span>
          <span>${ticketReplyCountLabel(ticket.message_count)}</span>
          <span>Dernière activité : ${formatTicketDate(ticket.last_activity_at)}</span>
        </div>

        ${ticket.source_page ? `
          <div class="ticket-detail-context">
            Contexte d’origine : <code>${escapeHtml(ticket.source_page)}</code>
          </div>
        ` : ""}
      </section>

      <div id="ticketDetailFeedback" class="ticket-feedback hidden"></div>

      ${renderTicketOfficialAnswer(messages)}

      <section class="ticket-thread">
        ${renderTicketMessages(messages)}
      </section>

      <section class="card ticket-reply-card">
        <div class="ticket-section-header">
          <div>
            <p class="tickets-kicker">Contribuer</p>
            <h3>${isClosed ? "Ticket clos" : "Répondre à ce ticket"}</h3>
          </div>
        </div>

        ${isClosed ? `
          <p class="ticket-closed-note">
            Ce ticket est clos et ne peut plus recevoir de nouvelle réponse publique.
          </p>
        ` : `
          <p class="ticket-reply-intro">
            Votre réponse sera visible publiquement. Merci de rester dans le sujet du ticket.
          </p>

          <form id="ticketReplyForm" class="ticket-form">
            <div class="ticket-form-grid">
              <div class="ticket-form-field">
                <label for="ticketReplyName">Nom ou pseudo *</label>
                <input id="ticketReplyName" type="text" maxlength="120" required />
              </div>

              <div class="ticket-form-field">
                <label for="ticketReplyEmail">Adresse email *</label>
                <input id="ticketReplyEmail" type="email" maxlength="254" required />
                <small>Elle n’est jamais affichée publiquement.</small>
              </div>

              <div class="ticket-form-field ticket-form-field-full">
                <label for="ticketReplyBody">Message *</label>
                <textarea
                  id="ticketReplyBody"
                  maxlength="20000"
                  placeholder="Ajoutez votre précision, votre question ou votre contribution…"
                  required
                ></textarea>
              </div>
            </div>

            <div class="ticket-form-actions">
              <button id="ticketReplySubmit" class="primary-btn" type="submit">
                Publier la réponse
              </button>
            </div>
          </form>
        `}
      </section>
    </div>
  `;
}

function bindTicketDetailInteractions(slug) {
  const backButton = document.getElementById("ticketBackToList");
  const replyForm = document.getElementById("ticketReplyForm");

  if (backButton) {
    backButton.addEventListener("click", async () => {
      await renderTicketsView(true);
    });
  }

  if (replyForm) {
    replyForm.addEventListener("submit", async (event) => {
      event.preventDefault();

      const submitButton = document.getElementById("ticketReplySubmit");
      const payload = {
        author_name: document.getElementById("ticketReplyName")?.value || "",
        author_email: document.getElementById("ticketReplyEmail")?.value || "",
        body_markdown: document.getElementById("ticketReplyBody")?.value || ""
      };

      try {
        if (submitButton) {
          submitButton.disabled = true;
          submitButton.textContent = "Publication...";
        }

        setTicketDetailFeedback("");
        await apiPostJson(
          `/api/tickets/${encodeURIComponent(slug)}/messages`,
          payload
        );

        await renderTicketDetail(slug, "Réponse publiée.");
      } catch (err) {
        setTicketDetailFeedback(`Erreur : ${err.message}`, true);
      } finally {
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = "Publier la réponse";
        }
      }
    });
  }
}

async function renderTicketDetail(slug, feedbackMessage = "") {
  destroyCartographyMap();
  appState.currentView = "tickets";
  syncSidebarView("tickets");
  setTitle("Ticket");
  appState.tickets.currentSlug = slug;

  content.innerHTML = `<div class="card">Chargement du ticket…</div>`;

  try {
    const data = await apiGet(`/api/tickets/${encodeURIComponent(slug)}`);
    appState.tickets.currentDetail = data;

    setTitle(data.ticket?.title || "Ticket");
    content.innerHTML = renderTicketDetailMarkup(data);
    bindTicketDetailInteractions(slug);

    if (feedbackMessage) {
      setTicketDetailFeedback(feedbackMessage);
    }
  } catch (err) {
    content.innerHTML = `
      <section class="card">
        <h2>Ticket introuvable</h2>
        <p>Impossible de charger ce ticket : ${escapeHtml(err.message)}</p>
        <button id="ticketBackToList" class="secondary-btn" type="button">
          ← Retour aux tickets
        </button>
      </section>
    `;

    document.getElementById("ticketBackToList")?.addEventListener("click", async () => {
      await renderTicketsView(true);
    });
  }
}


function buildDevicePrivateAccountsInsightHtml(stats) {
  const integerFr = (value) => Number(value || 0).toLocaleString("fr-FR", {
    maximumFractionDigits: 0
  });

  const percentageFr = (value) => Number(value || 0).toLocaleString("fr-FR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2
  });

  const totalTransactions = Number(stats?.nb_transactions_device_private_accounts || 0);

  if (!totalTransactions) {
    return "";
  }

  const activeAccounts = Number(stats?.nb_device_private_accounts_active || 0);
  const totalVolume = Number(stats?.volume_device_private_accounts || 0);
  const activityTransactions = Number(stats?.nb_transactions_device_private_activity || 0);
  const activityVolume = Number(stats?.volume_device_private_activity || 0);
  const operationsTransactions = Number(stats?.nb_transactions_device_private_operations || 0);
  const operationsVolume = Number(stats?.volume_device_private_operations || 0);
  const shareTransactions = Number(stats?.share_device_private_activity_transactions_pct || 0);
  const shareVolume = Number(stats?.share_device_private_activity_volume_pct || 0);

  return `
    <details class="card device-private-accounts-disclosure">
      <summary class="device-private-accounts-disclosure-summary">
        <span class="device-private-accounts-disclosure-kicker">Zoom complémentaire</span>
        <strong>Des comptes particuliers liés à un dispositif ponctuel</strong>
        <span class="device-private-accounts-disclosure-hint">Déplier</span>
      </summary>

      <div class="device-private-accounts-disclosure-body">
        <section class="device-private-accounts-overview">
      <div class="device-private-accounts-header">
        <p class="device-private-accounts-intro">
          Sur cette période, MLCFlux repère des comptes particuliers associés à un usage spécifique ou temporaire.
          Ils participent bien à l’activité économique lorsqu’ils paient des professionnels,
          mais leur logique n’est pas tout à fait celle des particuliers ordinaires.
          Ce focus permet donc de les lire à part, sans les confondre avec la dynamique générale.
        </p>
      </div>

      <details class="device-private-accounts-helper">
        <summary>Comment lire ce focus&nbsp;?</summary>
        <div class="device-private-accounts-helper-content">
          <p>
            Ces comptes apparaissent lorsqu’un événement, un projet ou un dispositif particulier
            mobilise ponctuellement la Gonette numérique. Ils peuvent provoquer un pic de transactions
            sur une période donnée, sans traduire à eux seuls une évolution durable des usages ordinaires.
          </p>
          <p>
            Les paiements vers les professionnels restent comptés dans l’activité économique.
            Les mouvements périphériques — par exemple des opérations liées à la clôture ou au fonctionnement du dispositif —
            sont isolés dans la dernière carte.
          </p>
        </div>
      </details>

      <div class="activity-flow-grid device-private-accounts-grid">
        <article class="activity-flow-card device-private-accounts-card">
          <div class="activity-flow-heading">
            <span class="activity-flow-code">UD</span>
            <h4>Qui est concerné&nbsp;?</h4>
          </div>
          <p class="activity-flow-description">
            Les comptes de dispositif effectivement actifs sur la période sélectionnée.
          </p>
          <div class="activity-flow-metrics">
            <div class="activity-flow-metric">
              <span class="activity-flow-metric-label">Comptes actifs</span>
              <strong>${integerFr(activeAccounts)}</strong>
            </div>
            <div class="activity-flow-metric">
              <span class="activity-flow-metric-label">Transactions</span>
              <strong>${integerFr(totalTransactions)}</strong>
            </div>
            <div class="activity-flow-metric">
              <span class="activity-flow-metric-label">Volume</span>
              <strong>${euro(totalVolume)}</strong>
            </div>
          </div>
        </article>

        <article class="activity-flow-card device-private-accounts-card">
          <div class="activity-flow-heading">
            <span class="activity-flow-code">UD→éco</span>
            <h4>Ce qui nourrit l’activité</h4>
          </div>
          <p class="activity-flow-description">
            Les transactions de ces comptes réellement intégrées à l’activité économique centrale.
          </p>
          <div class="activity-flow-metrics">
            <div class="activity-flow-metric">
              <span class="activity-flow-metric-label">Transactions d’activité</span>
              <strong>${integerFr(activityTransactions)}</strong>
            </div>
            <div class="activity-flow-metric">
              <span class="activity-flow-metric-label">Volume d’activité</span>
              <strong>${euro(activityVolume)}</strong>
            </div>
          </div>
        </article>

        <article class="activity-flow-card device-private-accounts-card">
          <div class="activity-flow-heading">
            <span class="activity-flow-code">Part</span>
            <h4>Leur poids sur la période</h4>
          </div>
          <p class="activity-flow-description">
            La place de ces comptes dans l’ensemble de l’activité économique retenue.
          </p>
          <div class="activity-flow-metrics">
            <div class="activity-flow-metric">
              <span class="activity-flow-metric-label">Part des transactions</span>
              <strong>${percentageFr(shareTransactions)} %</strong>
            </div>
            <div class="activity-flow-metric">
              <span class="activity-flow-metric-label">Part du volume</span>
              <strong>${percentageFr(shareVolume)} %</strong>
            </div>
          </div>
        </article>

        <article class="activity-flow-card device-private-accounts-card">
          <div class="activity-flow-heading">
            <span class="activity-flow-code">Hors éco</span>
            <h4>Mouvements périphériques</h4>
          </div>
          <p class="activity-flow-description">
            Les opérations impliquant ces comptes mais non retenues comme paiements économiques centraux.
          </p>
          <div class="activity-flow-metrics">
            <div class="activity-flow-metric">
              <span class="activity-flow-metric-label">Transactions</span>
              <strong>${integerFr(operationsTransactions)}</strong>
            </div>
            <div class="activity-flow-metric">
              <span class="activity-flow-metric-label">Volume</span>
              <strong>${euro(operationsVolume)}</strong>
            </div>
          </div>
        </article>
      </div>
        </section>
      </div>
    </details>
  `;
}

function mountDevicePrivateAccountsInsight(stats) {
  const html = buildDevicePrivateAccountsInsightHtml(stats);

  document.getElementById("devicePrivateAccountsInsightMount")?.remove();

  if (!html) {
    return;
  }

  const statsPanels = [...document.querySelectorAll(".stats-tab-panel")];

  const activityPanel = statsPanels.find((panel) => {
    const text = String(panel.textContent || "");
    return text.includes("Activité économique");
  });

  const fallbackPanel =
    document.querySelector('[data-stats-panel="activity"]')
    || document.querySelector('[data-stats-tab-panel="activity"]')
    || activityPanel;

  const targetPanel = activityPanel || fallbackPanel;

  if (!targetPanel) {
    console.warn("Bloc comptes particuliers de dispositif : panneau activité introuvable.");
    return;
  }

  const mount = document.createElement("div");
  mount.id = "devicePrivateAccountsInsightMount";
  mount.innerHTML = html;

  // Le bloc est volontairement placé tout en bas de l’onglet Activité économique :
  // il constitue un zoom spécifique, pas un indicateur structurant de premier niveau.
  targetPanel.appendChild(mount);
}

async function renderStatsView(forceReload = false) {
  const preserveVisibleView = shouldPreservePeriodRefreshView("stats", forceReload);

  destroyCartographyMap();
  appState.currentView = "stats";
  syncSidebarView("stats");
  setTitle("Statistiques globales");

  const cacheKey = getPeriodCacheKey();

  if (!forceReload && appState.statsCache[cacheKey]) {
    const cached = appState.statsCache[cacheKey];
    renderStatsCardsAndCharts(cached.stats, cached.charts);
    return;
  }

  if (!preserveVisibleView) {
    content.innerHTML = `<div class="card">Chargement...</div>`;
  }

  const [stats, charts] = await Promise.all([
    apiGet(`/api/stats${getPeriodQueryParam()}`),
    apiGet(`/api/stats_charts${getPeriodQueryParam()}`)
  ]);

  appState.statsCache[cacheKey] = { stats, charts };
  renderStatsCardsAndCharts(stats, charts);
}

function renderStatsCardsAndCharts(stats, charts) {
  const integerFr = (value) => Number(value || 0).toLocaleString("fr-FR", {
    maximumFractionDigits: 0
  });

  const decimalFr = (value, digits = 2) => Number(value || 0).toLocaleString("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });

  const fluxActivite = stats.flux_activite || {};
  const flowDefinitions = [
    {
      key: "U→P",
      title: "Particuliers → professionnels",
      description: "Paiements des particuliers vers les professionnels du réseau."
    },
    {
      key: "P→P",
      title: "Professionnels → professionnels",
      description: "Circulation interprofessionnelle de la Gonette numérique."
    },
    {
      key: "P→U",
      title: "Professionnels → particuliers",
      description: "Paiements ou reversements des professionnels vers des particuliers."
    },
    {
      key: "U→U",
      title: "Particuliers → particuliers",
      description: "Transferts économiques ou monétaires entre particuliers."
    }
  ];

  const activityFlowsHtml = flowDefinitions.map((definition) => {
    const flow = fluxActivite[definition.key] || {};
    return `
      <article class="activity-flow-card">
        <div class="activity-flow-heading">
          <span class="activity-flow-code">${definition.key}</span>
          <h4>${definition.title}</h4>
        </div>
        <p class="activity-flow-description">${definition.description}</p>
        <div class="activity-flow-metrics">
          <div class="activity-flow-metric">
            <span class="activity-flow-metric-label">Transactions</span>
            <strong>${integerFr(flow.nb_transactions)}</strong>
          </div>
          <div class="activity-flow-metric">
            <span class="activity-flow-metric-label">Volume</span>
            <strong>${euro(flow.volume_total || 0)}</strong>
          </div>
          <div class="activity-flow-metric">
            <span class="activity-flow-metric-label">Montant moyen</span>
            <strong>${euro(flow.montant_moyen || 0)}</strong>
          </div>
        </div>
      </article>
    `;
  }).join("");


  const circuitInflowDestinations = stats.circuit_inflow_destinations || {};
  const circuitInflowDefinitions = [
    {
      key: "T→U",
      title: "Vers les particuliers",
      description: "Alimentations numériques adressées à des comptes particuliers."
    },
    {
      key: "T→P",
      title: "Vers les professionnels",
      description: "Alimentations numériques adressées à des comptes professionnels."
    },
    {
      key: "T→T",
      title: "Résiduel technique",
      description: "Cas très marginaux d’alimentation technique interne."
    }
  ];

  const circuitInflowDestinationsHtml = circuitInflowDefinitions.map((definition) => {
    const flow = circuitInflowDestinations[definition.key] || {};
    return `
      <article class="activity-flow-card">
        <div class="activity-flow-heading">
          <span class="activity-flow-code">${definition.key}</span>
          <h4>${definition.title}</h4>
        </div>
        <p class="activity-flow-description">${definition.description}</p>
        <div class="activity-flow-metrics">
          <div class="activity-flow-metric">
            <span class="activity-flow-metric-label">Opérations</span>
            <strong>${integerFr(flow.nb_transactions)}</strong>
          </div>
          <div class="activity-flow-metric">
            <span class="activity-flow-metric-label">Volume</span>
            <strong>${euro(flow.volume_total || 0)}</strong>
          </div>
          <div class="activity-flow-metric">
            <span class="activity-flow-metric-label">Montant moyen</span>
            <strong>${euro(flow.montant_moyen || 0)}</strong>
          </div>
        </div>
      </article>
    `;
  }).join("");

  const operationsOperatorProfiles = stats.operations_operator_profiles || {};
  const operationsOperatorProfileDefinitions = [
    {
      key: "P0000_involved",
      code: "P0000",
      title: "Compte opérateur historique",
      description: "Opérations impliquant le compte P0000."
    },
    {
      key: "P9999_involved",
      code: "P9999",
      title: "Compte de collecte mensualisée",
      description: "Opérations impliquant le compte P9999."
    },
    {
      key: "P0000_P9999_bridge",
      code: "P0000 ↔ P9999",
      title: "Flux entre comptes opérateurs",
      description: "Opérations reliant directement P0000 et P9999."
    }
  ];

  const operationsOperatorProfilesHtml = operationsOperatorProfileDefinitions.map((definition) => {
    const profile = operationsOperatorProfiles[definition.key] || {};
    return `
      <article class="activity-flow-card">
        <div class="activity-flow-heading">
          <span class="activity-flow-code">${definition.code}</span>
          <h4>${definition.title}</h4>
        </div>
        <p class="activity-flow-description">${definition.description}</p>
        <div class="activity-flow-metrics">
          <div class="activity-flow-metric">
            <span class="activity-flow-metric-label">Opérations</span>
            <strong>${integerFr(profile.nb_transactions || 0)}</strong>
          </div>
          <div class="activity-flow-metric">
            <span class="activity-flow-metric-label">Volume</span>
            <strong>${euro(profile.volume_total || 0)}</strong>
          </div>
          <div class="activity-flow-metric">
            <span class="activity-flow-metric-label">Montant moyen</span>
            <strong>${euro(profile.montant_moyen || 0)}</strong>
          </div>
        </div>
      </article>
    `;
  }).join("");

  content.innerHTML = `
    <nav class="pro-tabs stats-tabs" aria-label="Sections des statistiques globales">
      <button
        class="tab-btn tab-btn-active"
        type="button"
        data-stats-tab="activity"
        aria-selected="true"
      >
        Activité économique
      </button>
      <button
        class="tab-btn"
        type="button"
        data-stats-tab="circuit"
        aria-selected="false"
      >
        Alimentation / sorties
      </button>
      <button
        class="tab-btn"
        type="button"
        data-stats-tab="operations"
        aria-selected="false"
      >
        Opérations associatives / techniques
      </button>
      <button
        class="tab-btn"
        type="button"
        data-stats-tab="monetary"
        aria-selected="false"
      >
        Masse monétaire &amp; garanties
      </button>
    </nav>

    <section class="stats-tab-panel" data-stats-panel="activity">
      <div class="grid activity-kpi-grid">
        <div class="card stat-card-static">
          <div class="stat-label">Transactions économiques</div>
          <div class="stat-value">${integerFr(stats.nb_transactions_activite_economique)}</div>
          <div class="stat-subtext">Périmètre structurel de l’activité</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Volume d’activité</div>
          <div class="stat-value">${euro(stats.volume_activite_economique || 0)}</div>
          <div class="stat-subtext">${euro(stats.volume_moyen_par_jour || 0)} par jour en moyenne</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Montant moyen par transaction</div>
          <div class="stat-value">${euro(stats.montant_moyen_activite || 0)}</div>
          <div class="stat-subtext">Sur l’ensemble de l’activité retenue</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Transactions moyennes par jour</div>
          <div class="stat-value">${decimalFr(stats.moyenne_transactions_par_jour || 0)}</div>
          <div class="stat-subtext">${integerFr(stats.nb_jours_periode_activite || 0)} jours calendaires</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Acteurs impliqués</div>
          <div class="stat-value">${integerFr(stats.nb_acteurs_activite || 0)}</div>
          <div class="stat-subtext">
            ${integerFr(stats.nb_acteurs_particuliers || 0)} particuliers ·
            ${integerFr(stats.nb_acteurs_professionnels || 0)} professionnels
          </div>
        </div>
      </div>

      <div id="globalStatsOverviewCharts"></div>

      <section class="card activity-flow-overview">
        <div class="activity-flow-overview-header">
          <h3>Principaux flux de l’activité économique</h3>
          <p>
            Les quatre flux structurants entre particuliers et professionnels.
            Les flux atypiques restent inclus dans le total d’activité mais seront documentés séparément.
          </p>
        </div>
        <div class="activity-flow-grid">
          ${activityFlowsHtml}
        </div>
      </section>

      <div id="activityStatsCharts"></div>
    </section>

    <section class="stats-tab-panel hidden" data-stats-panel="circuit">
      <div class="grid circuit-kpi-grid">
        <div class="card stat-card-static">
          <div class="stat-label">Opérations d’alimentation</div>
          <div class="stat-value">${integerFr(stats.nb_alimentations_circuit || 0)}</div>
          <div class="stat-subtext">${euro(stats.montant_moyen_alimentation || 0)} par opération en moyenne</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Volume alimenté</div>
          <div class="stat-value">${euro(stats.volume_alimente_circuit || 0)}</div>
          <div class="stat-subtext">Entrées de Gonettes numériques sur la période</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Opérations de sortie</div>
          <div class="stat-value">${integerFr(stats.nb_sorties_circuit || 0)}</div>
          <div class="stat-subtext">${euro(stats.montant_moyen_sortie || 0)} par opération en moyenne</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Volume sorti</div>
          <div class="stat-value">${euro(stats.volume_sorti_circuit || 0)}</div>
          <div class="stat-subtext">Reconversions / sorties professionnelles</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Écart net entrées – sorties</div>
          <div class="stat-value">${euro(stats.ecart_net_circuit || 0)}</div>
          <div class="stat-subtext">Indicateur de flux sur la période, pas un stock de monnaie</div>
        </div>
      </div>

      <section class="card activity-flow-overview">
        <div class="activity-flow-overview-header">
          <h3>Destinataires des alimentations</h3>
          <p>
            Répartition structurelle des entrées de Gonettes numériques :
            vers les particuliers, vers les professionnels, et résidu technique marginal.
          </p>
        </div>
        <div class="activity-flow-grid">
          ${circuitInflowDestinationsHtml}
        </div>
      </section>

      <div id="circuitStatsCharts"></div>
    </section>

    <section class="stats-tab-panel hidden" data-stats-panel="operations">
      <div class="grid operations-kpi-grid">
        <div class="card stat-card-static">
          <div class="stat-label">Opérations associatives / techniques</div>
          <div class="stat-value">${integerFr(stats.nb_operations_assoc_tech || 0)}</div>
          <div class="stat-subtext">Tous les mouvements hors activité économique centrale</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Volume associé</div>
          <div class="stat-value">${euro(stats.volume_operations_assoc_tech || 0)}</div>
          <div class="stat-subtext">${euro(stats.montant_moyen_operations_assoc_tech || 0)} par opération en moyenne</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Comptes opérateurs</div>
          <div class="stat-value">${integerFr(stats.nb_operations_operator_accounts || 0)}</div>
          <div class="stat-subtext">${euro(stats.volume_operations_operator_accounts || 0)} de mouvements impliquant P0000 / P9999</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Particuliers → comptes techniques</div>
          <div class="stat-value">${integerFr(stats.nb_operations_user_to_technical_accounts || 0)}</div>
          <div class="stat-subtext">${euro(stats.volume_operations_user_to_technical_accounts || 0)} sur la période</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Montant moyen U→compte technique</div>
          <div class="stat-value">${euro(stats.montant_moyen_user_to_technical_accounts || 0)}</div>
          <div class="stat-subtext">Bloc structurel à lire comme opérations de gestion / correction</div>
        </div>
      </div>

      <section class="card activity-flow-overview">
        <div class="activity-flow-overview-header">
          <h3>Comptes opérateurs P0000 et P9999</h3>
          <p>
            Ces comptes concentrent les flux associatifs ou techniques exclus de l’activité économique centrale.
            Ils sont présentés séparément car leur rôle et leur structure de transactions diffèrent nettement.
          </p>
        </div>
        <div class="activity-flow-grid">
          ${operationsOperatorProfilesHtml}
        </div>
      </section>

      <section class="card activity-flow-overview operations-technical-flow-overview">
        <div class="activity-flow-overview-header">
          <h3>Flux particuliers vers comptes techniques</h3>
          <p>
            Cette famille regroupe structurellement les flux <strong>U→T</strong>.
            L’audit des libellés montre qu’il s’agit très majoritairement d’annulations,
            avoirs, clôtures ou corrections, mais la classification affichée ici ne dépend pas des libellés libres.
          </p>
        </div>

        <div class="activity-flow-grid operations-technical-flow-grid">
          <article class="activity-flow-card">
            <div class="activity-flow-heading">
              <span class="activity-flow-code">U→T</span>
              <h4>Particuliers vers compte technique</h4>
            </div>
            <p class="activity-flow-description">
              Mouvements sortant d’un compte particulier vers l’acteur technique.
              Ce bloc doit être lu à part de l’activité économique.
            </p>
            <div class="activity-flow-metrics">
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Opérations</span>
                <strong>${integerFr(stats.nb_operations_user_to_technical_accounts || 0)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Volume</span>
                <strong>${euro(stats.volume_operations_user_to_technical_accounts || 0)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Montant moyen</span>
                <strong>${euro(stats.montant_moyen_user_to_technical_accounts || 0)}</strong>
              </div>
            </div>
          </article>
        </div>
      </section>

      <div id="operationsStatsCharts"></div>
    </section>

    <section class="stats-tab-panel hidden" data-stats-panel="monetary">
      <div id="monetaryIndicatorsTab">
        <div class="card">
          Chargement des indicateurs de masse monétaire et de garanties...
        </div>
      </div>
    </section>
  `;
  mountDevicePrivateAccountsInsight(stats);

  bindStatsTabs();
  renderGlobalStatsChartsFromSeries(charts);
  renderMonetaryIndicatorsTab();
}

function bindStatsTabs() {
  const buttons = Array.from(document.querySelectorAll("[data-stats-tab]"));
  const panels = Array.from(document.querySelectorAll("[data-stats-panel]"));

  if (!buttons.length || !panels.length) {
    return;
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextTab = button.dataset.statsTab;

      buttons.forEach((candidate) => {
        const isActive = candidate === button;
        candidate.classList.toggle("tab-btn-active", isActive);
        candidate.setAttribute("aria-selected", isActive ? "true" : "false");
      });

      panels.forEach((panel) => {
        panel.classList.toggle("hidden", panel.dataset.statsPanel !== nextTab);
      });
    });
  });
}

function percentFr(value, digits = 1) {
  return `${Number(value || 0).toLocaleString("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })} %`;
}

function formatAccountingAmount(value, suffix = "", signed = false) {
  const amount = Number(value || 0);
  const sign = signed && amount > 0 ? "+" : "";

  const formatted = amount.toLocaleString("fr-FR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });

  return `${sign}${formatted}${suffix ? ` ${suffix}` : ""}`;
}

function gonettes(value) {
  return formatAccountingAmount(value, "G");
}

function accountingEuros(value) {
  return formatAccountingAmount(value, "€");
}

function signedAccountingGap(value) {
  return formatAccountingAmount(value, "", true);
}

function monetaryCoverageRate(guaranteeValue, circulationValue) {
  const circulation = Number(circulationValue || 0);
  const guarantee = Number(guaranteeValue || 0);

  if (!circulation) {
    return null;
  }

  return (guarantee / circulation) * 100;
}

function formatCoverageRate(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return percentFr(value, 1);
}

function monetaryDelta(currentValue, previousValue) {
  const current = Number(currentValue || 0);
  const previous = Number(previousValue || 0);

  return current - previous;
}

function monetaryDeltaRate(currentValue, previousValue) {
  const previous = Number(previousValue || 0);

  if (!previous) {
    return null;
  }

  return (monetaryDelta(currentValue, previousValue) / previous) * 100;
}

function formatSignedGonetteDelta(value) {
  const amount = Number(value || 0);
  const sign = amount > 0 ? "+" : "";
  return `${sign}${gonettes(amount)}`;
}

function formatSignedRate(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  const amount = Number(value);
  const sign = amount > 0 ? "+" : "";

  return `${sign}${percentFr(amount, 1)}`;
}

function formatIsoDateFr(value) {
  const raw = String(value || "");
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);

  if (!match) {
    return raw || "—";
  }

  const [, year, month, day] = match;
  return `${day}/${month}/${year}`;
}

function buildMonetaryEffectivePeriodNotice(requestedPeriod, effectivePeriod) {
  if (!requestedPeriod || !effectivePeriod) {
    return "";
  }

  const isClipped =
    requestedPeriod.start !== effectivePeriod.start ||
    requestedPeriod.end !== effectivePeriod.end;

  if (!isClipped) {
    return "";
  }

  return `
    <div class="monetary-period-warning">
      <strong>Périmètre comptable disponible :</strong>
      les stocks Odoo commencent au
      <strong>${formatIsoDateFr(effectivePeriod.start)}</strong>,
      tandis que le filtre global demandé remonte au
      <strong>${formatIsoDateFr(requestedPeriod.start)}</strong>.
    </div>
  `;
}

function buildMonetarySyntheticOpeningNotice(openingSnapshot) {
  if (!openingSnapshot?.is_synthetic) {
    return "";
  }

  return `
    <div class="monetary-period-note">
      Les stocks Odoo quotidiens commencent au <strong>01/01/2024</strong>.
      Le stock antérieur à cette date n’est pas instruit dans MLCFlux :
      les indicateurs de variation de stock restent donc non disponibles
      lorsque la période démarre avant cette borne.
    </div>
  `;
}

function buildIsoDayRange(startIso, endIso) {
  if (!startIso || !endIso) {
    return [];
  }

  const start = new Date(`${startIso}T00:00:00Z`);
  const end = new Date(`${endIso}T00:00:00Z`);

  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) {
    return [];
  }

  const days = [];
  const current = new Date(start);

  while (current <= end) {
    days.push(current.toISOString().slice(0, 10));
    current.setUTCDate(current.getUTCDate() + 1);
  }

  return days;
}

function buildMonetaryChartItems(dailyPayload) {
  const rawItems = Array.isArray(dailyPayload?.items) ? dailyPayload.items : [];
  const requestedPeriod = dailyPayload?.requested_period || null;
  const effectivePeriod = dailyPayload?.effective_period || null;

  const start =
    requestedPeriod?.start ||
    effectivePeriod?.start ||
    rawItems[0]?.snapshot_date ||
    null;

  const end =
    requestedPeriod?.end ||
    effectivePeriod?.end ||
    rawItems[rawItems.length - 1]?.snapshot_date ||
    null;

  const dateRange = buildIsoDayRange(start, end);

  if (!dateRange.length) {
    return rawItems;
  }

  const itemsByDate = new Map(
    rawItems.map((item) => [item.snapshot_date, item])
  );

  return dateRange.map((snapshotDate) => {
    const existing = itemsByDate.get(snapshotDate);

    if (existing) {
      return existing;
    }

    return {
      snapshot_date: snapshotDate,
      gonettes_total_circulation: null,
      gonettes_num_circulation: null,
      gonettes_paper_circulation: null,
      is_missing_monetary_snapshot: true
    };
  });
}

function monetaryChartValue(item, key) {
  const value = item?.[key];

  if (value === null || value === undefined || value === "") {
    return null;
  }

  return Number(value);
}

function formatMonetarySnapshotLabel(item) {
  if (!item) {
    return "Aucune année disponible";
  }

  const currentYear = new Date().getFullYear();

  if (Number(item.year) === currentYear) {
    return `${item.year} · valeur provisoire à date`;
  }

  return `${item.year} · exercice annuel stocké`;
}

function buildMonetaryYearlyRows(items) {
  return items.map((item) => `
    <tr>
      <td><strong>${item.year}</strong></td>
      <td>${gonettes(item.gonettes_total_circulation || 0)}</td>
      <td>${gonettes(item.gonettes_num_circulation || 0)}</td>
      <td>${gonettes(item.gonettes_paper_circulation || 0)}</td>
      <td>${accountingEuros(item.fonds_garantie_num || 0)}</td>
      <td>${accountingEuros(item.fonds_garantie_paper || 0)}</td>
    </tr>
  `).join("");
}

async function renderMonetaryIndicatorsTab() {
  const host = document.getElementById("monetaryIndicatorsTab");
  if (!host) {
    return;
  }

  try {
    const periodQuery = getPeriodQueryParam();

    const [summary, dailyPayload] = await Promise.all([
      apiGet(`/api/monetary-indicators/period-summary${periodQuery}`),
      apiGet(`/api/monetary-indicators/daily${periodQuery}`)
    ]);

    const dailyItems = Array.isArray(dailyPayload?.items) ? dailyPayload.items : [];
    const opening = summary?.opening_snapshot || null;
    const closing = summary?.closing_snapshot || null;
    const metrics = summary?.period_metrics || null;
    const effectivePeriod = summary?.effective_period || null;
    const requestedPeriod = summary?.requested_period || null;

    appState.monetaryIndicators.periodSummary = summary;
    appState.monetaryIndicators.daily = dailyItems;

    if (!effectivePeriod || !closing || !metrics) {
      host.innerHTML = `
        <div class="card monetary-empty-card">
          <h3>Masse monétaire &amp; garanties</h3>
          <p>Aucune donnée monétaire Odoo n’est disponible sur la période sélectionnée.</p>
        </div>
      `;
      return;
    }

    const total = Number(closing.gonettes_total_circulation || 0);
    const numeric = Number(closing.gonettes_num_circulation || 0);
    const paper = Number(closing.gonettes_paper_circulation || 0);

    const numericShare = total > 0 ? (numeric / total) * 100 : 0;
    const paperShare = total > 0 ? (paper / total) * 100 : 0;

    const numericCoverageRate = monetaryCoverageRate(
      closing.fonds_garantie_num,
      closing.gonettes_num_circulation
    );

    const paperCoverageRate = monetaryCoverageRate(
      closing.fonds_garantie_paper,
      closing.gonettes_paper_circulation
    );

    const effectiveStartLabel = formatIsoDateFr(effectivePeriod.start);
    const effectiveEndLabel = formatIsoDateFr(effectivePeriod.end);
    const requestedStartLabel = formatIsoDateFr(requestedPeriod?.start || effectivePeriod.start);
    const requestedEndLabel = formatIsoDateFr(requestedPeriod?.end || effectivePeriod.end);
    const openingDateLabel = opening ? formatIsoDateFr(opening.snapshot_date) : "—";
    const closingDateLabel = formatIsoDateFr(closing.snapshot_date);

    const dayCountLabel = Number(metrics.day_count || 0).toLocaleString("fr-FR");
    const chartItems = buildMonetaryChartItems(dailyPayload);

    host.innerHTML = `
      <section class="card monetary-intro-card">
        <div class="activity-flow-overview-header">
          <h3>Masse monétaire &amp; garanties</h3>
          <p>
            Cet onglet distingue deux lectures complémentaires :
            les <strong>stocks comptables observés à une date</strong>
            et les <strong>dynamiques calculées sur la période sélectionnée</strong>.
          </p>
        </div>

        <div class="monetary-reference-line">
          Période monétaire analysée :
          <strong>${effectiveStartLabel} → ${effectiveEndLabel}</strong>
        </div>

        ${buildMonetaryEffectivePeriodNotice(requestedPeriod, effectivePeriod)}
        ${buildMonetarySyntheticOpeningNotice(opening)}
      </section>

      <section class="card monetary-stock-section">
        <div class="activity-flow-overview-header">
          <h3>Stock monétaire à la date de clôture</h3>
          <p>
            Les cartes ci-dessous sont des <strong>photographies comptables</strong>
            au <strong>${closingDateLabel}</strong>, dernier jour disponible de la période monétaire retenue.
          </p>
        </div>
      </section>

      <div class="grid monetary-kpi-grid">
        <div class="card stat-card-static">
          <div class="stat-label">Masse totale de clôture</div>
          <div class="stat-value">${gonettes(total)}</div>
          <div class="stat-subtext">Stock numérique + papier au ${closingDateLabel}</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Masse numérique de clôture</div>
          <div class="stat-value">${gonettes(numeric)}</div>
          <div class="stat-subtext">${percentFr(numericShare)} de la masse monétaire à cette date</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Masse papier de clôture</div>
          <div class="stat-value">${gonettes(paper)}</div>
          <div class="stat-subtext">${percentFr(paperShare)} de la masse monétaire à cette date</div>
        </div>
      </div>

      <section class="card monetary-period-dynamics-card">
        <div class="activity-flow-overview-header">
          <h3>Dynamique sur la période sélectionnée</h3>
          <p>
            Ces indicateurs décrivent la trajectoire de la masse monétaire entre
            <strong>${effectiveStartLabel}</strong> et <strong>${effectiveEndLabel}</strong>.
          </p>
        </div>

        <div class="activity-flow-grid monetary-period-grid">
          <article class="activity-flow-card">
            <div class="activity-flow-heading">
              <span class="activity-flow-code">Ouverture</span>
              <h4>Stock total d’ouverture</h4>
            </div>
            <p class="activity-flow-description">
              ${
                opening?.is_synthetic
                  ? "Stock antérieur non instruit dans MLCFlux avant le premier snapshot Odoo disponible."
                  : `Stock total observé la veille du début de période, soit le ${openingDateLabel}.`
              }
            </p>
            <div class="activity-flow-metrics">
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Masse totale</span>
                <strong>${
                  opening?.is_synthetic
                    ? "—"
                    : formatNullableGonettes(opening?.gonettes_total_circulation)
                }</strong>
              </div>
            </div>
          </article>

          <article class="activity-flow-card">
            <div class="activity-flow-heading">
              <span class="activity-flow-code">Moyenne</span>
              <h4>Masse totale moyenne</h4>
            </div>
            <p class="activity-flow-description">
              Moyenne quotidienne de la masse totale sur la période monétaire effective.
            </p>
            <div class="activity-flow-metrics">
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Masse moyenne</span>
                <strong>${gonettes(metrics.average_gonettes_total_circulation || 0)}</strong>
              </div>
            </div>
          </article>

          <article class="activity-flow-card">
            <div class="activity-flow-heading">
              <span class="activity-flow-code">Clôture</span>
              <h4>Stock total de clôture</h4>
            </div>
            <p class="activity-flow-description">
              Stock total observé au dernier jour disponible, soit le ${closingDateLabel}.
            </p>
            <div class="activity-flow-metrics">
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Masse totale</span>
                <strong>${gonettes(closing.gonettes_total_circulation || 0)}</strong>
              </div>
            </div>
          </article>

          <article class="activity-flow-card">
            <div class="activity-flow-heading">
              <span class="activity-flow-code">Durée</span>
              <h4>Jours couverts</h4>
            </div>
            <p class="activity-flow-description">
              Nombre de snapshots quotidiens effectivement mobilisés dans le calcul.
            </p>
            <div class="activity-flow-metrics">
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Snapshots</span>
                <strong>${dayCountLabel} jours</strong>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="card monetary-evolution-card">
        <div class="activity-flow-overview-header">
          <h3>Variation des stocks sur la période</h3>
          <p>
            Différence entre le stock d’ouverture et le stock de clôture.
            Ces variations portent bien sur la période sélectionnée, et non sur une simple photographie de clôture.
          </p>
        </div>

        <div class="activity-flow-grid monetary-evolution-grid">
          <article class="activity-flow-card">
            <div class="activity-flow-heading">
              <span class="activity-flow-code">Total</span>
              <h4>Masse totale</h4>
            </div>
            <p class="activity-flow-description">
              Évolution du stock global de Gonettes en circulation.
            </p>
            <div class="activity-flow-metrics">
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Variation</span>
                <strong>${formatSignedGonetteDelta(metrics.variation_gonettes_total_circulation)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Taux</span>
                <strong>${formatSignedRate(metrics.variation_rate_gonettes_total_circulation)}</strong>
              </div>
            </div>
          </article>

          <article class="activity-flow-card">
            <div class="activity-flow-heading">
              <span class="activity-flow-code">Num.</span>
              <h4>Masse numérique</h4>
            </div>
            <p class="activity-flow-description">
              Évolution du compartiment numérique au cours de la période.
            </p>
            <div class="activity-flow-metrics">
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Variation</span>
                <strong>${formatSignedGonetteDelta(metrics.variation_gonettes_num_circulation)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Taux</span>
                <strong>${formatSignedRate(metrics.variation_rate_gonettes_num_circulation)}</strong>
              </div>
            </div>
          </article>

          <article class="activity-flow-card">
            <div class="activity-flow-heading">
              <span class="activity-flow-code">Pap.</span>
              <h4>Masse papier</h4>
            </div>
            <p class="activity-flow-description">
              Évolution du compartiment papier au cours de la période.
            </p>
            <div class="activity-flow-metrics">
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Variation</span>
                <strong>${formatSignedGonetteDelta(metrics.variation_gonettes_paper_circulation)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Taux</span>
                <strong>${formatSignedRate(metrics.variation_rate_gonettes_paper_circulation)}</strong>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="card activity-flow-overview monetary-guarantee-overview">
        <div class="activity-flow-overview-header">
          <h3>Couverture et fonds de garantie à la date de clôture</h3>
          <p>
            Ces indicateurs décrivent l’état observé au <strong>${closingDateLabel}</strong>.
            Les écarts sont calculés comme différence entre le fonds associé
            et la masse monétaire correspondante ; leur interprétation métier doit rester prudente.
          </p>
        </div>

        <div class="activity-flow-grid monetary-guarantee-grid">
          <article class="activity-flow-card">
            <div class="activity-flow-heading">
              <span class="activity-flow-code">Num.</span>
              <h4>Garantie numérique</h4>
            </div>
            <p class="activity-flow-description">
              Fonds de garantie associé à la circulation numérique à la clôture.
            </p>
            <div class="activity-flow-metrics">
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Fonds de garantie</span>
                <strong>${accountingEuros(closing.fonds_garantie_num || 0)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Masse numérique</span>
                <strong>${gonettes(closing.gonettes_num_circulation || 0)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Écart</span>
                <strong class="monetary-delta">${signedAccountingGap(closing.ecart_num || 0)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">
                  Taux de couverture
                  <span
                    class="inline-helper"
                    title="Rapport entre le fonds de garantie numérique et la masse numérique en circulation. 100 % signifie un fonds équivalent au stock numérique affiché."
                    aria-label="Aide : taux de couverture numérique"
                  >?</span>
                </span>
                <strong>${formatCoverageRate(numericCoverageRate)}</strong>
              </div>
            </div>
          </article>

          <article class="activity-flow-card">
            <div class="activity-flow-heading">
              <span class="activity-flow-code">Pap.</span>
              <h4>Garantie papier</h4>
            </div>
            <p class="activity-flow-description">
              Fonds de garantie associé à la circulation papier à la clôture.
            </p>
            <div class="activity-flow-metrics">
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Fonds de garantie</span>
                <strong>${accountingEuros(closing.fonds_garantie_paper || 0)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Masse papier</span>
                <strong>${gonettes(closing.gonettes_paper_circulation || 0)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Écart</span>
                <strong class="monetary-delta">${signedAccountingGap(closing.ecart_paper || 0)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">
                  Taux de couverture
                  <span
                    class="inline-helper"
                    title="Rapport entre le fonds de garantie papier et la masse papier en circulation. Cet indicateur doit être interprété avec prudence et validé au regard des règles comptables de La Gonette."
                    aria-label="Aide : taux de couverture papier"
                  >?</span>
                </span>
                <strong>${formatCoverageRate(paperCoverageRate)}</strong>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="stats-chart-section monetary-chart-section">
        <div class="stats-section-header">
          <h3>Évolution quotidienne des stocks monétaires</h3>
          <p>
            L’axe temporel suit la <strong>période demandée dans le filtre latéral</strong>
            <strong>${requestedStartLabel} → ${requestedEndLabel}</strong>.
            Les courbes ne sont tracées que lorsque MLCFlux dispose d’un snapshot Odoo journalier.
          </p>
        </div>

        <div class="stats-chart-grid">
          <div class="card stats-chart-card stats-chart-card-full monetary-chart-card">
            <div class="stats-chart-card-header">
              <div class="stats-chart-title-group">
                <h3>Masse totale, numérique et papier</h3>
                <p>
                  Lecture quotidienne des stocks comptables.
                  Les portions vides signalent l’absence de données monétaires journalières disponibles.
                </p>
              </div>
            </div>

            <canvas id="monetaryStockHistoryChart" height="110"></canvas>
          </div>
        </div>
      </section>

      <section class="card monetary-method-card">
        <div class="activity-flow-overview-header">
          <h3>Point méthodologique</h3>
          <p>
            Les onglets 1 à 3 analysent les <strong>flux numériques Cyclos</strong>.
            Cet onglet analyse des <strong>stocks comptables Odoo</strong> :
            une valeur de stock vaut à une date précise, tandis qu’une moyenne ou une variation
            porte sur la période sélectionnée.
          </p>
        </div>
      </section>
    `;

    renderMonetaryStockHistoryChart(chartItems);
  } catch (error) {
    console.error("Erreur lors du chargement des indicateurs monétaires Odoo :", error);

    host.innerHTML = `
      <div class="card monetary-empty-card">
        <h3>Masse monétaire &amp; garanties</h3>
        <p>Le chargement des indicateurs comptables a échoué.</p>
      </div>
    `;
  }
}

function buildMonetaryStockHistoryChartConfig(items) {
  const labels = items.map((item) => formatIsoDateFr(item.snapshot_date));
  const totalValues = items.map((item) => monetaryChartValue(item, "gonettes_total_circulation"));
  const numericValues = items.map((item) => monetaryChartValue(item, "gonettes_num_circulation"));
  const paperValues = items.map((item) => monetaryChartValue(item, "gonettes_paper_circulation"));

  const pointRadius = items.length <= 120 ? 2 : 0;

  return {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Masse totale",
          data: totalValues,
          tension: 0.18,
          pointRadius,
          pointHoverRadius: 4,
          borderWidth: 3,
          spanGaps: false
        },
        {
          label: "Masse numérique",
          data: numericValues,
          tension: 0.18,
          pointRadius,
          pointHoverRadius: 4,
          borderWidth: 2,
          spanGaps: false
        },
        {
          label: "Masse papier",
          data: paperValues,
          tension: 0.18,
          pointRadius,
          pointHoverRadius: 4,
          borderWidth: 2,
          spanGaps: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          position: "top"
        },
        tooltip: {
          callbacks: {
            label(context) {
              const label = context.dataset.label || "";
              const value = Number(context.raw || 0);
              return `${label} : ${gonettes(value)}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: {
            display: false
          },
          ticks: {
            autoSkip: true,
            maxTicksLimit: 12
          }
        },
        y: {
          beginAtZero: true,
          ticks: {
            callback(value) {
              return gonettes(value);
            }
          }
        }
      }
    }
  };
}

function renderMonetaryStockHistoryChart(items) {
  const canvas = document.getElementById("monetaryStockHistoryChart");
  if (!canvas || !Array.isArray(items) || !items.length) {
    return;
  }

  if (appState.charts.monetaryStockHistory) {
    appState.charts.monetaryStockHistory.destroy();
    appState.charts.monetaryStockHistory = null;
  }

  appState.charts.monetaryStockHistory = new Chart(
    canvas,
    buildMonetaryStockHistoryChartConfig(items)
  );
}


function formatPilotagePercent(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return percentFr(Number(value) * 100, digits);
}

function formatPilotageSignedPercent(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  const numericValue = Number(value);
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${percentFr(numericValue * 100, digits)}`;
}

function formatPilotageMultiple(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${Number(value).toLocaleString("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })}×`;
}

function formatPilotageDays(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${Number(value).toLocaleString("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })} jours`;
}

function formatPilotageThirtyDayPeriods(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${Number(value).toLocaleString("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })} mois`;
}

function formatPilotageGonetteYield(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${Number(value).toLocaleString("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })} G`;
}

function formatPilotageTxPer1000G(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${Number(value).toLocaleString("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })} tx`;
}

function formatPilotageSignedGonettes(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  const numericValue = Number(value);
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${gonettes(numericValue)}`;
}

function formatNullableGonettes(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return gonettes(value);
}


function getPilotageDaysInMonth(monthKey) {
  const [year, month] = String(monthKey || "").split("-");
  const y = Number(year);
  const m = Number(month);

  if (!y || !m || Number.isNaN(y) || Number.isNaN(m)) {
    return null;
  }

  return new Date(y, m, 0).getDate();
}

function isPilotagePartialMonth(item) {
  const totalDays = getPilotageDaysInMonth(item?.month_key);
  const coveredDays = Number(item?.day_count || 0);

  if (!totalDays || !coveredDays) {
    return false;
  }

  return coveredDays < totalDays;
}

function formatPilotageMonthLabel(itemOrMonthKey) {
  const item = typeof itemOrMonthKey === "object"
    ? itemOrMonthKey
    : { month_key: itemOrMonthKey };

  const monthKey = item?.month_key;
  const [year, month] = String(monthKey || "").split("-");
  const monthIndex = Number(month) - 1;

  if (!year || Number.isNaN(monthIndex) || monthIndex < 0 || monthIndex > 11) {
    return monthKey || "";
  }

  const date = new Date(Number(year), monthIndex, 1);
  const label = date.toLocaleDateString("fr-FR", {
    month: "short",
    year: "numeric"
  });

  return isPilotagePartialMonth(item) ? `${label}*` : label;
}

function getPilotageMonthKeyFromIsoDate(isoDate) {
  const match = String(isoDate || "").match(/^(\d{4})-(\d{2})-/);

  if (!match) {
    return null;
  }

  return `${match[1]}-${match[2]}`;
}

function isPilotageChartGap(item) {
  return Boolean(item?.__pilotage_chart_gap__);
}

function buildPilotageMonthlyChartSeries(items = [], requestedPeriod = null) {
  const sourceItems = Array.isArray(items) ? items : [];
  const startMonthKey = getPilotageMonthKeyFromIsoDate(requestedPeriod?.start);
  const endMonthKey = getPilotageMonthKeyFromIsoDate(requestedPeriod?.end);

  if (!startMonthKey || !endMonthKey) {
    return sourceItems;
  }

  const [startYear, startMonth] = startMonthKey.split("-").map(Number);
  const [endYear, endMonth] = endMonthKey.split("-").map(Number);

  if (
    !startYear || !startMonth || !endYear || !endMonth ||
    Number.isNaN(startYear) || Number.isNaN(startMonth) ||
    Number.isNaN(endYear) || Number.isNaN(endMonth)
  ) {
    return sourceItems;
  }

  const startDate = new Date(startYear, startMonth - 1, 1);
  const endDate = new Date(endYear, endMonth - 1, 1);

  if (startDate > endDate) {
    return sourceItems;
  }

  const itemsByMonth = new Map(
    sourceItems
      .filter((item) => item?.month_key)
      .map((item) => [item.month_key, item])
  );

  const chartItems = [];
  const cursor = new Date(startDate);

  while (cursor <= endDate) {
    const monthKey = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}`;
    const existingItem = itemsByMonth.get(monthKey);

    chartItems.push(existingItem || {
      month_key: monthKey,
      day_count: 0,
      aligned_day_count: 0,
      __pilotage_chart_gap__: true
    });

    cursor.setMonth(cursor.getMonth() + 1);
  }

  return chartItems;
}

function formatPilotageChartG(value) {
  const numericValue = Number(value || 0);
  return `${numericValue.toLocaleString("fr-FR", {
    maximumFractionDigits: 0
  })} G`;
}

function formatPilotageChartPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${Number(value).toLocaleString("fr-FR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 1
  })} %`;
}

function formatPilotageChartMultiple(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${Number(value).toLocaleString("fr-FR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}×`;
}

function isPilotageReusePartialYear(item) {
  const year = Number(item?.year);
  const periodStart = String(item?.period_start || "");
  const periodEnd = String(item?.period_end || "");

  if (!year || !periodStart || !periodEnd) {
    return false;
  }

  return (
    periodStart !== `${year}-01-01`
    || periodEnd !== `${year}-12-31`
  );
}

function formatPilotageReuseYearLabel(item) {
  if (!item?.year) {
    return "—";
  }

  return isPilotageReusePartialYear(item)
    ? `${item.year}*`
    : String(item.year);
}

function isPilotageLm3PartialYear(item) {
  const year = Number(item?.year);
  const periodStart = String(item?.period_start || "");
  const periodEnd = String(item?.period_end || "");

  if (!year || !periodStart || !periodEnd) {
    return false;
  }

  return (
    periodStart !== `${year}-01-01`
    || periodEnd !== `${year}-12-31`
  );
}

function formatPilotageLm3YearLabel(item) {
  if (!item?.year) {
    return "—";
  }

  return isPilotageLm3PartialYear(item)
    ? `${item.year}*`
    : String(item.year);
}

function buildPilotageLm3YearlyFootnote(items) {
  const partialYears = (items || []).filter(isPilotageLm3PartialYear);

  if (!partialYears.length) {
    return "";
  }

  return `
    <p class="pilotage-chart-footnote pilotage-lm3-footnote">
      <strong>* Année partielle.</strong>
      Le LM3 est calculé année par année. La première année disponible
      et l’année en cours peuvent ne pas couvrir douze mois complets ;
      leur comparaison avec les années pleines doit rester prudente.
    </p>
  `;
}

function buildPilotageReuseYearlyFootnote(items) {
  const partialYears = (items || []).filter(isPilotageReusePartialYear);

  if (!partialYears.length) {
    return "";
  }

  return `
    <p class="pilotage-chart-footnote pilotage-reuse-footnote">
      <strong>* Année partielle.</strong>
      La première année disponible et l’année en cours peuvent ne pas couvrir
      douze mois complets. Les comparaisons historiques restent utiles,
      mais doivent être interprétées avec cette prudence.
    </p>
  `;
}

function buildPilotagePartialMonthNote(items) {
  const partialMonths = (items || []).filter(isPilotagePartialMonth);

  if (!partialMonths.length) {
    return "";
  }

  return `
    <p class="pilotage-chart-footnote">
      <strong>* Mois partiel.</strong>
      Les flux mensuels sont ramenés en <strong>équivalent 30 jours</strong>
      lorsque c’est nécessaire. Les ratios annualisés restent indicatifs
      sur les périodes courtes ou incomplètes.
    </p>
  `;
}

function destroyMonetaryPilotageCharts() {
  const chartKeys = [
    "pilotageRotation",
    "pilotageFlowRhythm",
    "pilotageRetention",
    "pilotageInternalReuseHistory",
    "pilotageLm3History",
    "pilotageHoldingsStockShare",
    "pilotageHoldingsMassComposition",
    "pilotageHoldingsMobilization",
    "pilotageHoldingsDormancy"
  ];

  chartKeys.forEach((key) => {
    if (appState.charts[key]) {
      appState.charts[key].destroy();
      appState.charts[key] = null;
    }
  });
}

function buildPilotageRotationChartConfig(items, summary) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const labels = items.map((item) => formatPilotageMonthLabel(item));
  const periodReference = Number(
    summary?.pilotage_metrics?.circulation
      ?.annualized_economic_activity_intensity_indicative
  );

  const datasets = [
    {
      type: "line",
      label: "Rotation annualisée",
      data: items.map((item) => (
        item.annualized_economic_activity_intensity_indicative ?? null
      )),
      tension: 0.28,
      pointRadius: 4,
      pointHoverRadius: 6
    }
  ];

  if (!Number.isNaN(periodReference)) {
    datasets.push({
      type: "line",
      label: "Référence de la période",
      data: items.map((item) => (
        isPilotageChartGap(item) ? null : periodReference
      )),
      borderDash: [6, 5],
      pointRadius: 0,
      pointHoverRadius: 0
    });
  }

  return {
    type: "line",
    data: {
      labels,
      datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: true
        },
        tooltip: {
          callbacks: {
            label(context) {
              const label = context.dataset.label || "";
              return `${label} : ${formatPilotageChartMultiple(context.raw)} / an`;
            },
            afterTitle(context) {
              const index = context?.[0]?.dataIndex;
              const item = items[index];

              if (!item || !isPilotagePartialMonth(item)) {
                return "";
              }

              return `Mois partiel : ${item.day_count} jour(s) couvert(s)`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: "Rotation annualisée (× / an)"
          },
          ticks: {
            callback(value) {
              return formatPilotageChartMultiple(value);
            }
          }
        }
      }
    }
  };
}

function buildPilotageFlowRhythmChartConfig(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const labels = items.map((item) => formatPilotageMonthLabel(item));

  const inflowEquivalent30d = items.map((item) => {
    const dayCount = Number(item.day_count || 0);
    if (!dayCount) return null;
    return Number(item.inflow_volume || 0) / dayCount * 30;
  });

  const outflowEquivalent30d = items.map((item) => {
    const dayCount = Number(item.day_count || 0);
    if (!dayCount) return null;
    return -Number(item.outflow_volume || 0) / dayCount * 30;
  });

  return {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Alimentations — équiv. 30 jours",
          data: inflowEquivalent30d
        },
        {
          label: "Sorties — équiv. 30 jours",
          data: outflowEquivalent30d
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: true
        },
        tooltip: {
          callbacks: {
            label(context) {
              const label = context.dataset.label || "";
              const value = Math.abs(Number(context.raw || 0));
              return `${label} : ${formatPilotageChartG(value)}`;
            },
            afterTitle(context) {
              const index = context?.[0]?.dataIndex;
              const item = items[index];

              if (!item || !isPilotagePartialMonth(item)) {
                return "";
              }

              return `Mois partiel : ${item.day_count} jour(s) couvert(s)`;
            }
          }
        }
      },
      scales: {
        y: {
          title: {
            display: true,
            text: "Rythme mensuel — équivalent 30 jours (G)"
          },
          ticks: {
            callback(value) {
              return formatPilotageChartG(value);
            }
          }
        }
      }
    }
  };
}

function buildPilotageRetentionChartConfig(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const labels = items.map((item) => formatPilotageMonthLabel(item));

  return {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Rétention nette des alimentations",
          data: items.map((item) => (
            item.net_inflow_retention_rate === null ||
            item.net_inflow_retention_rate === undefined
              ? null
              : item.net_inflow_retention_rate * 100
          ))
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            label(context) {
              return `Rétention nette : ${formatPilotageChartPercent(context.raw)}`;
            },
            afterTitle(context) {
              const index = context?.[0]?.dataIndex;
              const item = items[index];

              if (!item || !isPilotagePartialMonth(item)) {
                return "";
              }

              return `Mois partiel : ${item.day_count} jour(s) couvert(s)`;
            }
          }
        }
      },
      scales: {
        y: {
          title: {
            display: true,
            text: "Rétention nette (%)"
          },
          ticks: {
            callback(value) {
              return formatPilotageChartPercent(value);
            }
          }
        }
      }
    }
  };
}

function buildPilotageInternalReuseHistoryChartConfig(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const labels = items.map((item) => formatPilotageReuseYearLabel(item));

  return {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Réemploi interne — réseau global",
          data: items.map((item) => {
            const value = item?.global?.weighted_internal_reuse_propensity;
            return value === null || value === undefined ? null : value * 100;
          }),
          yAxisID: "reuseRate",
          tension: 0.28,
          pointRadius: 4,
          pointHoverRadius: 6
        },
        {
          label: "Réemploi interne — professionnels",
          data: items.map((item) => {
            const value = item?.professionals?.weighted_internal_reuse_propensity;
            return value === null || value === undefined ? null : value * 100;
          }),
          yAxisID: "reuseRate",
          tension: 0.28,
          pointRadius: 4,
          pointHoverRadius: 6
        },
        {
          label: "Multiplicateur estimé — réseau global",
          data: items.map((item) => (
            item?.global?.internal_multiplier_estimated ?? null
          )),
          yAxisID: "multiplier",
          tension: 0.28,
          pointRadius: 4,
          pointHoverRadius: 6,
          borderDash: [6, 4]
        },
        {
          label: "Multiplicateur estimé — professionnels",
          data: items.map((item) => (
            item?.professionals?.internal_multiplier_estimated ?? null
          )),
          yAxisID: "multiplier",
          tension: 0.28,
          pointRadius: 4,
          pointHoverRadius: 6,
          borderDash: [3, 4]
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: true
        },
        tooltip: {
          callbacks: {
            label(context) {
              const label = context.dataset.label || "";
              const axis = context.dataset.yAxisID;

              if (axis === "reuseRate") {
                return `${label} : ${formatPilotageChartPercent(context.raw)}`;
              }

              return `${label} : ${formatPilotageChartMultiple(context.raw)}`;
            },
            afterTitle(context) {
              const index = context?.[0]?.dataIndex;
              const item = items[index];

              if (!item || !isPilotageReusePartialYear(item)) {
                return "";
              }

              return `Année partielle : ${item.period_start} → ${item.period_end}`;
            }
          }
        }
      },
      scales: {
        reuseRate: {
          type: "linear",
          position: "left",
          beginAtZero: true,
          title: {
            display: true,
            text: "Réemploi interne pondéré (%)"
          },
          ticks: {
            callback(value) {
              return formatPilotageChartPercent(value);
            }
          }
        },
        multiplier: {
          type: "linear",
          position: "right",
          beginAtZero: false,
          title: {
            display: true,
            text: "Multiplicateur estimé (×)"
          },
          ticks: {
            callback(value) {
              return formatPilotageChartMultiple(value);
            }
          },
          grid: {
            drawOnChartArea: false
          }
        }
      }
    }
  };
}

function buildPilotageLm3HistoryChartConfig(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const labels = items.map((item) => formatPilotageLm3YearLabel(item));

  return {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Dépense initiale",
          data: items.map(() => 1),
          stack: "lm3"
        },
        {
          label: "Gain de vague 2",
          data: items.map((item) => item?.wave_2 ?? null),
          stack: "lm3"
        },
        {
          label: "Gain de vague 3",
          data: items.map((item) => item?.wave_3 ?? null),
          stack: "lm3"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: true
        },
        tooltip: {
          callbacks: {
            label(context) {
              const label = context.dataset.label || "";
              return `${label} : ${formatPilotageChartMultiple(context.raw)}`;
            },
            footer(context) {
              const index = context?.[0]?.dataIndex;
              const item = items[index];

              if (!item) {
                return "";
              }

              return `LM3 estimé : ${formatPilotageChartMultiple(item.lm3_estimated)}`;
            },
            afterTitle(context) {
              const index = context?.[0]?.dataIndex;
              const item = items[index];

              if (!item || !isPilotageLm3PartialYear(item)) {
                return "";
              }

              return "Année partielle";
            }
          }
        }
      },
      scales: {
        x: {
          stacked: true
        },
        y: {
          stacked: true,
          beginAtZero: true,
          title: {
            display: true,
            text: "LM3 estimé (×)"
          },
          ticks: {
            callback(value) {
              return formatPilotageChartMultiple(value);
            }
          }
        }
      }
    }
  };
}

function renderPilotageLm3HistoryChart(items) {
  const canvas = document.getElementById("pilotageLm3HistoryChart");
  const config = buildPilotageLm3HistoryChartConfig(items);

  if (!canvas || !config) {
    return;
  }

  appState.charts.pilotageLm3History = new Chart(canvas, config);
}


function renderPilotageInternalReuseHistoryChart(items) {
  const canvas = document.getElementById("pilotageInternalReuseHistoryChart");
  const config = buildPilotageInternalReuseHistoryChartConfig(items);

  if (!canvas || !config) {
    return;
  }

  appState.charts.pilotageInternalReuseHistory = new Chart(canvas, config);
}


function renderPilotageRotationChart(items, summary) {
  const canvas = document.getElementById("pilotageRotationChart");
  const config = buildPilotageRotationChartConfig(items, summary);

  if (!canvas || !config) {
    return;
  }

  appState.charts.pilotageRotation = new Chart(canvas, config);
}


function renderPilotageFlowRhythmChart(items) {
  const canvas = document.getElementById("pilotageFlowRhythmChart");
  const config = buildPilotageFlowRhythmChartConfig(items);

  if (!canvas || !config) {
    return;
  }

  appState.charts.pilotageFlowRhythm = new Chart(canvas, config);
}


function renderPilotageRetentionChart(items) {
  const canvas = document.getElementById("pilotageRetentionChart");
  const config = buildPilotageRetentionChartConfig(items);

  if (!canvas || !config) {
    return;
  }

  appState.charts.pilotageRetention = new Chart(canvas, config);
}


function getPilotageHoldingsDormancyBucket(buckets, bucketKey) {
  return (Array.isArray(buckets) ? buckets : []).find((bucket) => bucket.key === bucketKey) || {
    key: bucketKey,
    label: bucketKey,
    user_count: 0,
    positive_user_stock: 0,
    stock_share_of_positive_user_stock: null
  };
}

function formatPilotageInteger(value) {
  return Number(value || 0).toLocaleString("fr-FR", {
    maximumFractionDigits: 0
  });
}

function isPilotageHoldingsPartialMonth(item) {
  const totalDays = getPilotageDaysInMonth(item?.month_key);
  const alignedDays = Number(item?.aligned_day_count || 0);

  return Boolean(totalDays && alignedDays > 0 && alignedDays < totalDays);
}

function formatPilotageHoldingsMonthLabel(item) {
  return formatPilotageMonthLabel({
    ...item,
    day_count: Number(item?.aligned_day_count || 0)
  });
}

function buildPilotageHoldingsPartialMonthNote(items) {
  const partialMonths = (items || []).filter(isPilotageHoldingsPartialMonth);

  if (!partialMonths.length) {
    return "";
  }

  return `
    <p class="pilotage-chart-footnote">
      * Certains mois sont partiels : les moyennes portent uniquement sur les jours
      communs effectivement disponibles entre soldes particuliers, soldes professionnels et stocks Odoo.
    </p>
  `;
}

function getPilotageHoldingsDormancyStock(item, bucketKey) {
  if (isPilotageChartGap(item)) {
    return null;
  }

  const bucket = getPilotageHoldingsDormancyBucket(
    item?.dormancy?.buckets || [],
    bucketKey
  );

  return Number(bucket?.positive_user_stock || 0);
}

function buildPilotageHoldingsStockShareChartConfig(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const labels = items.map((item) => formatPilotageHoldingsMonthLabel(item));

  return {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Stock particulier moyen",
          data: items.map((item) => item.average_positive_user_stock ?? null),
          yAxisID: "yStock",
          tension: 0.28,
          pointRadius: 4,
          pointHoverRadius: 6
        },
        {
          label: "Stock professionnels du réseau moyen",
          data: items.map((item) => item.average_positive_professional_network_stock ?? null),
          yAxisID: "yStock",
          tension: 0.28,
          pointRadius: 4,
          pointHoverRadius: 6
        },
        {
          label: "Stock comptes entreprise Gonette moyen",
          data: items.map((item) => item.average_positive_gonette_business_accounts_stock ?? null),
          yAxisID: "yStock",
          tension: 0.28,
          pointRadius: 4,
          pointHoverRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: true
        },
        tooltip: {
          callbacks: {
            label(context) {
                const label = context.dataset.label || "";
                return `${label} : ${formatPilotageChartG(context.raw)}`;
              },
            afterTitle(context) {
              const index = context?.[0]?.dataIndex;
              const item = items[index];

              if (!item || !isPilotageHoldingsPartialMonth(item)) {
                return "";
              }

              return `Mois partiel : ${item.aligned_day_count} jour(s) aligné(s)`;
            }
          }
        }
      },
      scales: {
        yStock: {
          beginAtZero: true,
          position: "left",
          title: {
            display: true,
            text: "Stock particulier moyen (G)"
          }
        }
      }
    }
  };
}


function buildPilotageHoldingsMassCompositionChartConfig(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const labels = items.map((item) => formatPilotageHoldingsMonthLabel(item));

  const sharePercent = (value) => (
    value === null || value === undefined
      ? null
      : Number(value || 0) * 100
  );

  const residualSharePercent = (item) => {
    const userShare = sharePercent(item.average_user_stock_share_of_numeric_mass);
    const professionalShare = sharePercent(
      item.average_professional_network_stock_share_of_numeric_mass
    );
    const gonetteShare = sharePercent(
      item.average_gonette_business_accounts_stock_share_of_numeric_mass
    );

    if (
      userShare === null &&
      professionalShare === null &&
      gonetteShare === null
    ) {
      return null;
    }

    return Math.max(
      0,
      100 -
      Number(userShare || 0) -
      Number(professionalShare || 0) -
      Number(gonetteShare || 0)
    );
  };

  return {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Particuliers",
          data: items.map((item) => sharePercent(
            item.average_user_stock_share_of_numeric_mass
          )),
          stack: "massComposition"
        },
        {
          label: "Professionnels du réseau",
          data: items.map((item) => sharePercent(
            item.average_professional_network_stock_share_of_numeric_mass
          )),
          stack: "massComposition"
        },
        {
          label: "Comptes entreprise Gonette",
          data: items.map((item) => sharePercent(
            item.average_gonette_business_accounts_stock_share_of_numeric_mass
          )),
          stack: "massComposition"
        },
        {
          label: "Reste non encore ventilé",
          data: items.map((item) => residualSharePercent(item)),
          stack: "massComposition"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: true
        },
        tooltip: {
          callbacks: {
            label(context) {
              const label = context.dataset.label || "";
              return `${label} : ${formatPilotageChartPercent(context.raw)}`;
            },
            afterTitle(context) {
              const index = context?.[0]?.dataIndex;
              const item = items[index];

              if (!item || !isPilotageHoldingsPartialMonth(item)) {
                return "";
              }

              return `Mois partiel : ${item.aligned_day_count} jour(s) aligné(s)`;
            }
          }
        }
      },
      scales: {
        x: {
          stacked: true
        },
        y: {
          stacked: true,
          beginAtZero: true,
          max: 100,
          title: {
            display: true,
            text: "Part de la masse numérique moyenne (%)"
          },
          ticks: {
            callback(value) {
              return formatPilotageChartPercent(value);
            }
          }
        }
      }
    }
  };
}

function buildPilotageHoldingsMobilizationChartConfig(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const labels = items.map((item) => formatPilotageHoldingsMonthLabel(item));
  const mobilizationValues = items.map((item) => (
    item.economic_up_volume_per_100_g_average_user_stock ?? null
  ));

  return {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Dépenses U→P / 100 G détenues",
          data: mobilizationValues,
          tension: 0.28,
          pointRadius: 4,
          pointHoverRadius: 6,
          fill: false,
          spanGaps: false
        },
        {
          label: "Repère 100 G / 100 G",
          data: items.map((item) => (
            isPilotageChartGap(item) ? null : 100
          )),
          tension: 0,
          pointRadius: 0,
          pointHoverRadius: 0,
          borderDash: [6, 5],
          borderWidth: 1.5,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: true,
          position: "bottom"
        },
        tooltip: {
          callbacks: {
            label(context) {
              if (context.dataset?.label === "Repère 100 G / 100 G") {
                return "Repère : 100 G vers les pros pour 100 G détenues";
              }

              return `Intensité : ${formatPilotageGonetteYield(context.raw)} vers les pros pour 100 G détenues`;
            },
            afterTitle(context) {
              const index = context?.[0]?.dataIndex;
              const item = items[index];

              if (!item || !isPilotageHoldingsPartialMonth(item)) {
                return "";
              }

              return `Mois partiel : ${item.aligned_day_count} jour(s) aligné(s)`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: "G U→P pour 100 G détenues"
          }
        }
      }
    }
  };
}

function buildPilotageHoldingsDormancyChartConfig(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const labels = items.map((item) => formatPilotageHoldingsMonthLabel(item));

  return {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Actif ≤ 30 j",
          data: items.map((item) => getPilotageHoldingsDormancyStock(item, "active_30"))
        },
        {
          label: "Dormant 31–90 j",
          data: items.map((item) => getPilotageHoldingsDormancyStock(item, "dormant_31_90"))
        },
        {
          label: "Dormant 91–180 j",
          data: items.map((item) => getPilotageHoldingsDormancyStock(item, "dormant_91_180"))
        },
        {
          label: "Dormant > 180 j",
          data: items.map((item) => getPilotageHoldingsDormancyStock(item, "dormant_gt_180"))
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: true
        },
        tooltip: {
          callbacks: {
            label(context) {
              const label = context.dataset.label || "";
              return `${label} : ${formatPilotageChartG(context.raw)}`;
            },
            afterTitle(context) {
              const index = context?.[0]?.dataIndex;
              const item = items[index];

              if (!item || !isPilotageHoldingsPartialMonth(item)) {
                return "";
              }

              return `Mois partiel : ${item.aligned_day_count} jour(s) aligné(s)`;
            }
          }
        }
      },
      scales: {
        x: {
          stacked: true
        },
        y: {
          stacked: true,
          beginAtZero: true,
          title: {
            display: true,
            text: "Stock particulier positif à la clôture (G)"
          }
        }
      }
    }
  };
}

function renderPilotageHoldingsStockShareChart(items) {
  const canvas = document.getElementById("pilotageHoldingsStockShareChart");
  const config = buildPilotageHoldingsStockShareChartConfig(items);

  if (!canvas || !config) {
    return;
  }

  appState.charts.pilotageHoldingsStockShare = new Chart(canvas, config);
}

function renderPilotageHoldingsMassCompositionChart(items) {
  const canvas = document.getElementById("pilotageHoldingsMassCompositionChart");
  const config = buildPilotageHoldingsMassCompositionChartConfig(items);

  if (!canvas || !config) {
    return;
  }

  appState.charts.pilotageHoldingsMassComposition = new Chart(canvas, config);
}

function renderPilotageHoldingsMobilizationChart(items) {
  const canvas = document.getElementById("pilotageHoldingsMobilizationChart");
  const config = buildPilotageHoldingsMobilizationChartConfig(items);

  if (!canvas || !config) {
    return;
  }

  appState.charts.pilotageHoldingsMobilization = new Chart(canvas, config);
}

function renderPilotageHoldingsDormancyChart(items) {
  const canvas = document.getElementById("pilotageHoldingsDormancyChart");
  const config = buildPilotageHoldingsDormancyChartConfig(items);

  if (!canvas || !config) {
    return;
  }

  appState.charts.pilotageHoldingsDormancy = new Chart(canvas, config);
}


function renderMonetaryPilotageCharts(
  items,
  summary,
  reuseYearlyItems = [],
  lm3YearlyItems = [],
  holdingsItems = [],
  holdingsSummary = null
) {
  destroyMonetaryPilotageCharts();

  const pilotageChartPayload = {
    pilotageItems: items,
    pilotageSummary: summary,
    pilotageReuseYearlyItems: reuseYearlyItems,
    pilotageLm3YearlyItems: lm3YearlyItems,
    pilotageHoldingsItems: holdingsItems,
    pilotageHoldingsSummary: holdingsSummary
  };

  if (Array.isArray(reuseYearlyItems) && reuseYearlyItems.length > 0) {
    renderPilotageInternalReuseHistoryChart(reuseYearlyItems);
  }

  if (Array.isArray(lm3YearlyItems) && lm3YearlyItems.length > 0) {
    renderPilotageLm3HistoryChart(lm3YearlyItems);
  }

  if (Array.isArray(items) && items.length > 0) {
    renderPilotageRotationChart(items, summary);
    renderPilotageFlowRhythmChart(items);
    renderPilotageRetentionChart(items);
  }

  if (Array.isArray(holdingsItems) && holdingsItems.length > 0) {
    renderPilotageHoldingsStockShareChart(holdingsItems);
    renderPilotageHoldingsMassCompositionChart(holdingsItems);
    renderPilotageHoldingsMobilizationChart(holdingsItems);
    renderPilotageHoldingsDormancyChart(holdingsItems);
  }

  bindStatsChartTools(pilotageChartPayload);
}

function formatPilotageLm3ChainExample(example = {}) {
  const conversionDate = formatIsoDateFr(example.conversion_date);
  const p1ToP2Date = formatIsoDateFr(example.p1_to_p2_date);
  const p2ToP3Date = formatIsoDateFr(example.p2_to_p3_date);

  return `
    <div class="pilotage-lm3-chain-example">
      <span>
        <strong>Alim.</strong>
        ${conversionDate}
        · ${gonettes(example.conversion_amount || 0)}
      </span>
      <span class="pilotage-lm3-chain-example-arrow">→</span>
      <span>
        <strong>P1→P2</strong>
        ${p1ToP2Date}
        · ${gonettes(example.p1_to_p2_amount || 0)}
      </span>
      <span class="pilotage-lm3-chain-example-arrow">→</span>
      <span>
        <strong>P2→P3</strong>
        ${p2ToP3Date}
        · ${gonettes(example.p2_to_p3_amount || 0)}
      </span>
    </div>
  `;
}

function buildPilotageLm3ChainsTable(data = {}, page = 1) {
  const items = Array.isArray(data?.items) ? data.items : [];

  if (!items.length) {
    return `
      <div class="pilotage-lm3-chains-empty">
        Aucune chaîne de circulation compatible jusqu’au 3ᵉ niveau
        n’a été trouvée sur cette période.
      </div>
    `;
  }

  const pageSize = 5;
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const safePage = Math.min(Math.max(Number(page) || 1, 1), totalPages);
  const startIndex = (safePage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, items.length);
  const visibleItems = items.slice(startIndex, endIndex);

  const rows = visibleItems.map((item) => `
    <tr>
      <td class="pilotage-lm3-chain-path-cell">
        <div class="pilotage-lm3-chain-path">
          <span>${escapeHtml(item.p1 || "—")}</span>
          <span class="pilotage-lm3-chain-arrow">→</span>
          <span>${escapeHtml(item.p2 || "—")}</span>
          <span class="pilotage-lm3-chain-arrow">→</span>
          <span>${escapeHtml(item.p3 || "—")}</span>
        </div>
      </td>
      <td>${Number(item.configuration_count || 0).toLocaleString("fr-FR")}</td>
      <td>${Number(item.p1_to_p2_transaction_count || 0).toLocaleString("fr-FR")}</td>
      <td>${Number(item.p2_to_p3_transaction_count || 0).toLocaleString("fr-FR")}</td>
      <td>${formatPilotageLm3ChainExample(item.first_example || {})}</td>
    </tr>
  `).join("");

  const pagination = totalPages > 1
    ? `
      <nav class="pilotage-lm3-chains-pagination" aria-label="Pagination des chaînes LM3">
        <button
          type="button"
          class="pilotage-lm3-page-button"
          data-lm3-chains-page="${safePage - 1}"
          ${safePage <= 1 ? "disabled" : ""}
        >
          ← Précédent
        </button>

        <span class="pilotage-lm3-page-status">
          Page <strong>${safePage}</strong> / ${totalPages}
          · triplets ${startIndex + 1}–${endIndex} sur ${items.length}
        </span>

        <button
          type="button"
          class="pilotage-lm3-page-button"
          data-lm3-chains-page="${safePage + 1}"
          ${safePage >= totalPages ? "disabled" : ""}
        >
          Suivant →
        </button>
      </nav>
    `
    : "";

  return `
    <div class="pilotage-lm3-chains-summary-grid">
      <article>
        <span>Paiements P1→P2 compatibles</span>
        <strong>${Number(data.candidate_p1_to_p2_count || 0).toLocaleString("fr-FR")}</strong>
      </article>
      <article>
        <span>Configurations temporelles P1→P2→P3</span>
        <strong>${Number(data.observed_configuration_count || 0).toLocaleString("fr-FR")}</strong>
      </article>
      <article>
        <span>Triplets distincts observés</span>
        <strong>${Number(data.distinct_triplet_count || 0).toLocaleString("fr-FR")}</strong>
      </article>
    </div>

    <div class="pilotage-lm3-chains-table-wrap">
      <table class="pilotage-lm3-chains-table">
        <thead>
          <tr>
            <th>Chaîne observée</th>
            <th>Config. temporelles</th>
            <th>Tx P1→P2</th>
            <th>Tx P2→P3</th>
            <th>Premier exemple daté</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    </div>

    ${pagination}

    <p class="pilotage-lm3-chains-note">
      Les lignes sont triées par <strong>nombre de configurations temporelles compatibles</strong>.
      Une même transaction aval peut apparaître dans plusieurs configurations si plusieurs
      paiements P1→P2 antérieurs existent. Le tableau illustre donc la
      <strong>profondeur de circulation observée</strong>, sans attribuer unité par unité
      les mêmes Gonettes à chaque maillon.
    </p>
  `;
}
function bindPilotageLm3ChainsDetails() {
  const details = document.querySelector("[data-lm3-chains-details]");
  const body = document.querySelector("[data-lm3-chains-body]");

  if (!details || !body) {
    return;
  }

  details.addEventListener("toggle", async () => {
    if (!details.open || details.dataset.loaded === "1") {
      return;
    }

    body.innerHTML = `
      <div class="pilotage-lm3-chains-loading">
        Chargement des chaînes de circulation observées...
      </div>
    `;

    try {
      const query = getPeriodQueryParam();
      const separator = query ? "&" : "?";
      const data = await apiGet(
        `/api/monetary-indicators/pilotage-lm3-chains${query}${separator}limit=50`
      );

      details._lm3ChainsData = data;
      details._lm3ChainsPage = 1;

      body.innerHTML = buildPilotageLm3ChainsTable(data, 1);
      details.dataset.loaded = "1";
    } catch (error) {
      console.error("Erreur lors du chargement des chaînes LM3 :", error);
      body.innerHTML = `
        <div class="pilotage-lm3-chains-empty">
          Impossible de charger les chaînes observées pour cette période.
        </div>
      `;
    }
  });

  body.addEventListener("click", (event) => {
    const button = event.target.closest("[data-lm3-chains-page]");
    if (!button || button.disabled) {
      return;
    }

    const data = details._lm3ChainsData;
    if (!data) {
      return;
    }

    const requestedPage = Number(button.dataset.lm3ChainsPage || 1);
    details._lm3ChainsPage = requestedPage;
    body.innerHTML = buildPilotageLm3ChainsTable(data, requestedPage);
  });
}
function buildPilotageResidualCaution(data) {
  const effectiveStart = data?.effective_period?.start;
  const firstMonetaryDay = data?.bounds?.min_date;

  if (!effectiveStart || !firstMonetaryDay || effectiveStart !== firstMonetaryDay) {
    return "";
  }

  return `
    <div class="pilotage-warning-card">
      <strong>Rapprochement stock ↔ flux non interprétable sur cette période :</strong>
      la période commence au premier jour disponible des stocks Odoo quotidiens.
      Le stock antérieur n’étant pas instruit dans MLCFlux,
      la variation de stock numérique et le résiduel de rapprochement
      ne sont pas calculés.
    </div>
  `;
}


const PILOTAGE_INDICATOR_HELP = {
  lm3Estimated: {
    title: "LM3 estimé",
    summary: "Le LM3 mesure la capacité de propagation des Gonettes nouvellement injectées sur trois vagues successives d’échanges.",
    usefulness: "Il renseigne ce que produit une alimentation lorsqu’elle ne s’arrête pas à une première dépense, mais continue à générer des recettes chez d’autres acteurs du réseau.",
    reading: [
      "Un LM3 de 1,301× signifie qu’une Gonette injectée puis dépensée génère, selon le modèle, 1,301 G de recettes cumulées après trois vagues.",
      "Ce chiffre doit être lu comme une estimation de propagation, non comme un traçage exact de chaque Gonette."
    ],
    crossReading: [
      "À comparer au « Multiplicateur interne estimé » pour distinguer fonctionnement moyen du réseau et propagation spécifique des injections.",
      "À croiser avec les gains de vague 2 et 3 afin de comprendre où l’effet se construit ou s’essouffle.",
      "À rapprocher du volume d’alimentations : la quantité injectée et la profondeur de propagation sont deux dimensions distinctes."
    ],
    pilotage: [
      "Un LM3 qui progresse indique que les nouvelles Gonettes s’enracinent mieux dans le réseau.",
      "Un LM3 qui recule peut inviter à examiner les circuits de redépense des acteurs alimentés."
    ],
    perimeter: [
      "Calcul annuel dérivé des alimentations et des paiements économiques internes."
    ],
    formulas: [
      "LM3 = 1 + vague 2 + vague 3."
    ],
    sources: [
      "pilotage-lm3-yearly.items[].lm3_estimated"
    ]
  },

  lm3Wave2: {
    title: "Gain de vague 2",
    summary: "Cette composante du LM3 mesure le supplément de recettes généré par les acteurs directement atteints par la dépense initiale.",
    usefulness: "Elle indique si les Gonettes injectées déclenchent rapidement une première boucle de redépense.",
    reading: [
      "Plus le gain de vague 2 est élevé, plus les premiers receveurs redépensent fortement dans le réseau.",
      "C’est souvent la composante principale de l’effet LM3."
    ],
    crossReading: [
      "À comparer à la vague 3 : l’écart entre les deux renseigne la profondeur ou l’essoufflement de la propagation.",
      "À lire avec le réemploi professionnel, car les premiers receveurs sont souvent au cœur économique du réseau."
    ],
    pilotage: [
      "Une vague 2 faible peut indiquer que les injections atteignent des acteurs qui redépensent peu."
    ],
    perimeter: [
      "Calcul pondéré à partir des acteurs P2 atteints par les dépenses de P1."
    ],
    formulas: [
      "Gain de vague 2 = somme des poids P2 × propension de réemploi P2."
    ],
    sources: [
      "pilotage-lm3-yearly.items[].wave_2",
      "pilotage-lm3-yearly.items[].p2_effective_propensity"
    ]
  },

  lm3Wave3: {
    title: "Gain de vague 3",
    summary: "Cette composante mesure la propagation supplémentaire du LM3 au troisième niveau de circulation.",
    usefulness: "Elle renseigne la profondeur réelle des chaînes de redépense : le circuit s’arrête-t-il vite ou parvient-il à générer une nouvelle couche de recettes ?",
    reading: [
      "Une vague 3 significative montre que les recettes de vague 2 se diffusent encore au-delà du premier réemploi.",
      "Une vague 3 faible signale une propagation plus courte ou des acteurs P2 moins capables de redépenser."
    ],
    crossReading: [
      "À comparer directement à la vague 2.",
      "À lire avec le nombre d’acteurs P3 atteints, qui renseigne la diffusion du troisième niveau."
    ],
    pilotage: [
      "Cet indicateur peut aider à cibler les points où les chaînes économiques s’interrompent."
    ],
    perimeter: [
      "Calcul pondéré à partir des acteurs P3 atteints par la propagation des dépenses de P2."
    ],
    formulas: [
      "Gain de vague 3 = somme des poids P3 × propension de réemploi P3."
    ],
    sources: [
      "pilotage-lm3-yearly.items[].wave_3",
      "pilotage-lm3-yearly.items[].p3_effective_propensity"
    ]
  },

  lm3P3Actors: {
    title: "Acteurs atteints au 3ᵉ niveau",
    summary: "Cette donnée compte les acteurs P3 atteints par la propagation des Gonettes injectées après deux niveaux de redépense.",
    usefulness: "Elle donne une lecture de profondeur et de diffusion : combien d’acteurs restent atteints lorsque l’on suit la circulation jusqu’au troisième cercle ?",
    reading: [
      "Un nombre élevé traduit une propagation plus diffuse au troisième niveau.",
      "Un nombre plus faible peut signaler une concentration ou une perte de profondeur dans les chaînes de circulation."
    ],
    crossReading: [
      "À lire avec le gain de vague 3 : un grand nombre d’acteurs P3 n’implique pas automatiquement un fort volume propagé.",
      "À comparer d’une année sur l’autre pour repérer un élargissement ou un resserrement des circuits d’injection."
    ],
    pilotage: [
      "Cette mesure deviendra particulièrement utile lorsqu’on analysera des dispositifs d’injection spécifiques."
    ],
    perimeter: [
      "Nombre d’acteurs P3 distincts atteints dans la construction annuelle du LM3."
    ],
    formulas: [
      "P3 = acteurs recevant la propagation pondérée issue de P2."
    ],
    sources: [
      "pilotage-lm3-yearly.items[].p3_actor_count"
    ]
  },

  internalMultiplierGlobal: {
    title: "Multiplicateur interne estimé",
    summary: "Cet indicateur exprime la capacité moyenne de recirculation du réseau dérivée de la propension pondérée de réemploi interne.",
    usefulness: "Il donne une lecture synthétique de l’effet cumulatif potentiel de la redépense interne : plus les recettes sont réemployées dans le réseau, plus le multiplicateur estimé augmente.",
    reading: [
      "Une valeur de 1,33× signifie que la propension de réemploi observée correspond à une capacité moyenne de recirculation supérieure au simple passage unique d’une recette.",
      "Cet indicateur est dérivé d’un comportement moyen de réseau ; il ne suit pas encore une injection particulière Gonette par Gonette."
    ],
    crossReading: [
      "À croiser avec la « Propension pondérée de réemploi » qui est la variable source du calcul.",
      "À rapprocher du graphe historique annuel pour voir si la valeur actuelle s’inscrit dans une progression ou un recul.",
      "À lire avec la rotation économique annualisée : le multiplicateur renseigne la qualité de redépense, la rotation renseigne l’intensité d’activité par masse disponible."
    ],
    pilotage: [
      "Une hausse durable peut signaler une amélioration de la densité des débouchés internes.",
      "Une baisse peut inviter à examiner le réemploi professionnel, les chaînes P→P ou les sorties du circuit."
    ],
    perimeter: [
      "Calculé sur les transactions d’activité économique MLCFlux.",
      "Il s’agit d’un multiplicateur interne estimé de fonctionnement moyen, distinct du futur LM3 d’injection."
    ],
    formulas: [
      "k = 1 / (1 - c), où c est la propension pondérée de réemploi interne."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.internal_reuse.global.internal_multiplier_estimated"
    ]
  },

  internalReusePropensityGlobal: {
    title: "Propension pondérée de réemploi interne",
    summary: "Cet indicateur mesure la part des recettes économiques internes qui est redépensée dans le réseau, après bornage acteur par acteur.",
    usefulness: "C’est la brique fondamentale du multiplicateur interne. Elle renseigne directement la capacité des acteurs receveurs à transformer leurs recettes en nouvelles dépenses économiques Gonette.",
    reading: [
      "Une valeur de 24,9 % signifie qu’en pondération par les recettes, environ un quart des volumes reçus est réemployé dans le périmètre économique interne.",
      "Le bornage à 100 % évite de surévaluer les acteurs qui dépensent sur la période un stock acquis avant celle-ci."
    ],
    crossReading: [
      "À croiser avec le « Multiplicateur interne estimé », qui en est la traduction multiplicative.",
      "À comparer au « Réemploi interne professionnel » pour identifier la contribution spécifique du cœur économique du réseau.",
      "À suivre dans le graphe historique annuel afin de distinguer un état ponctuel d’une tendance structurelle."
    ],
    pilotage: [
      "Une progression de ce ratio peut signaler que le réseau gagne en débouchés internes.",
      "Une stagnation ou un recul peut nourrir une réflexion sur l’animation des chaînes de redépense et les besoins d’intermédiation entre pros."
    ],
    perimeter: [
      "Calcul fondé sur les recettes et dépenses des transactions d’activité économique retenues dans MLCFlux."
    ],
    formulas: [
      "c = somme(min(recettes, dépenses) par acteur) / somme(recettes)."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.internal_reuse.global.weighted_internal_reuse_propensity",
      "pilotage-summary.pilotage_metrics.internal_reuse.global.reused_capped_volume",
      "pilotage-summary.pilotage_metrics.internal_reuse.global.received_volume"
    ]
  },

  internalReusePropensityProfessionals: {
    title: "Réemploi interne professionnel",
    summary: "Cet indicateur mesure la part pondérée des recettes économiques reçues par les professionnels qui est redépensée dans le réseau.",
    usefulness: "C’est probablement l’un des signaux les plus stratégiques pour piloter une monnaie locale : il renseigne la capacité des professionnels à trouver des débouchés de réemploi internes.",
    reading: [
      "Une valeur plus élevée indique que les pros réinjectent une part plus importante de leurs recettes Gonette dans l’économie du réseau.",
      "Une valeur plus faible peut refléter un manque de fournisseurs, une concentration des débouchés, ou une préférence accrue pour la reconversion."
    ],
    crossReading: [
      "À croiser avec le « Multiplicateur professionnel estimé ».",
      "À rapprocher des volumes P→P et des vues sectorielles / territoriales du réseau.",
      "À lire avec les sorties du circuit : un réemploi professionnel faible peut coexister avec une pression de reconversion plus forte."
    ],
    pilotage: [
      "Cet indicateur peut soutenir des stratégies concrètes d’animation B2B : cartographie des besoins, mise en relation, campagnes ciblées.",
      "Une baisse durable mérite d’être documentée avec les secteurs les plus récepteurs et les plus redépensiers."
    ],
    perimeter: [
      "Même méthode que le réemploi global, restreinte aux professionnels receveurs."
    ],
    formulas: [
      "Réemploi professionnel = somme des réemplois bornés des pros / somme des recettes économiques reçues par les pros."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.internal_reuse.professionals.weighted_internal_reuse_propensity"
    ]
  },

  internalMultiplierProfessionals: {
    title: "Multiplicateur professionnel estimé",
    summary: "Cet indicateur traduit le réemploi interne professionnel en capacité moyenne de recirculation estimée.",
    usefulness: "Il synthétise la contribution du réemploi professionnel à l’effet multiplicateur interne du réseau. C’est une lecture plus économique que le seul pourcentage de redépense.",
    reading: [
      "Le multiplicateur professionnel augmente à mesure que la propension de réemploi des pros s’élève.",
      "Il est particulièrement intéressant à suivre dans le temps, car les professionnels structurent l’essentiel des recettes économiques du réseau."
    ],
    crossReading: [
      "À lire avec le « Réemploi interne professionnel », sa variable source.",
      "À comparer au multiplicateur global : leur proximité ou leur divergence raconte le poids relatif des acteurs professionnels dans la recirculation.",
      "À rapprocher du graphe annuel pour identifier les périodes de renforcement ou d’affaiblissement du cœur économique."
    ],
    pilotage: [
      "Une hausse indique que les professionnels deviennent collectivement plus aptes à faire circuler leurs recettes en Gonette.",
      "Une baisse peut inviter à regarder les reconversions, la densité des fournisseurs internes ou les secteurs où le réemploi se contracte."
    ],
    perimeter: [
      "Calcul dérivé du réemploi pondéré des seuls professionnels receveurs."
    ],
    formulas: [
      "k_pro = 1 / (1 - c_pro)."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.internal_reuse.professionals.internal_multiplier_estimated"
    ]
  },

  annualizedRotation: {
    title: "Rotation économique annualisée",
    summary: "Cet indicateur synthétise, à l’échelle de la période, l’intensité de circulation de la Gonette numérique rapportée à la masse disponible.",
    usefulness: "Il sert à savoir si la masse numérique présente dans le système produit réellement de l’activité économique. C’est un indicateur de vitalité circulatoire, plus exigeant qu’un simple volume de transactions.",
    reading: [
      "Une valeur plus élevée signale davantage d’activité économique générée par unité de masse numérique moyenne.",
      "Une valeur plus faible peut traduire un ralentissement de l’usage, mais aussi une hausse récente de la masse plus rapide que l’activité.",
      "L’annualisation permet de comparer des périodes de durées différentes, mais elle reste indicative sur les périodes courtes."
    ],
    crossReading: [
      "À croiser avec la « Masse numérique moyenne » et l’« Activité économique » dans les grandeurs de référence.",
      "À rapprocher du graphe « Rotation économique annualisée » pour voir si la moyenne de période masque des inflexions mensuelles.",
      "À lire avec la « Rétention nette des alimentations » : garder davantage de Gonettes dans le circuit est d’autant plus intéressant si elles circulent effectivement."
    ],
    pilotage: [
      "Si la rotation baisse durablement, vérifier si l’activité ralentit, si la masse s’accumule, ou si les nouveaux volumes injectés trouvent mal leurs débouchés.",
      "À terme, cet indicateur devra être rapproché de la masse active / dormante."
    ],
    perimeter: [
      "Basé sur l’activité économique numérique retenue dans MLCFlux et sur la masse numérique moyenne issue des stocks Odoo.",
      "Ne mesure pas directement un multiplicateur économique complet ni un impact territorial."
    ],
    formulas: [
      "Rotation de période = activité économique / masse numérique moyenne.",
      "Rotation annualisée indicative = rotation de période rapportée à une année."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.circulation",
      "pilotage-summary.flow_reference",
      "pilotage-summary.monetary_reference"
    ]
  },

  netInflowRetention: {
    title: "Rétention nette des alimentations",
    summary: "Cet indicateur mesure la part nette des Gonettes nouvellement alimentées qui reste dans le circuit une fois les sorties observées retranchées.",
    usefulness: "Il renseigne sur la capacité apparente du circuit à conserver les volumes qui entrent. C’est utile pour distinguer une alimentation qui consolide réellement le système d’une alimentation vite neutralisée par des sorties.",
    reading: [
      "Une valeur positive signifie que les alimentations sont supérieures aux sorties.",
      "Une valeur proche de zéro indique que les entrées sont presque compensées par les sorties.",
      "Une valeur négative indique que les sorties dépassent les entrées sur la période."
    ],
    crossReading: [
      "À croiser avec les volumes « Alimentations » et « Sorties » dans les grandeurs de référence.",
      "À rapprocher du graphe « Rythme des alimentations et des sorties » pour comprendre les mois qui tirent le ratio vers le haut ou vers le bas.",
      "À lire avec la rotation économique : une bonne rétention n’est réellement convaincante que si ce qui reste continue de circuler."
    ],
    pilotage: [
      "Si la rétention se dégrade, identifier si cela vient d’une baisse des entrées, d’une hausse des sorties, ou d’un effet combiné.",
      "Si elle s’améliore fortement, vérifier aussi que la masse ne devient pas plus dormante."
    ],
    perimeter: [
      "Ratio construit uniquement à partir des alimentations et sorties numériques identifiées dans Cyclos.",
      "Ne dit pas à lui seul si les Gonettes conservées sont activement redépensées."
    ],
    formulas: [
      "Rétention nette = (alimentations − sorties) / alimentations × 100."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.retention_and_yield",
      "pilotage-summary.flow_reference"
    ]
  },

  economicActivityPerOutflow: {
    title: "Activité générée pour 1 G sorti",
    summary: "Cet indicateur rapporte l’activité économique observée au volume de Gonettes sorties du circuit.",
    usefulness: "Il donne une mesure de rendement circulatoire avant sortie : combien d’activité économique le circuit a-t-il généré pour chaque Gonette finalement reconvertie ou sortie ?",
    reading: [
      "Une valeur élevée signifie que les sorties sont faibles relativement à l’activité générée.",
      "Une valeur plus basse signale que les reconversions prennent davantage de poids au regard de l’activité économique.",
      "Cet indicateur n’établit pas une causalité individuelle entre une Gonette qui circule et une Gonette qui sort."
    ],
    crossReading: [
      "À lire avec le volume de « Sorties » et les « Sorties quotidiennes moyennes ».",
      "À rapprocher de la rotation économique : un bon rendement avant sortie est plus robuste si l’intensité circulatoire reste elle aussi élevée.",
      "À comparer à « Activité générée pour 1 G alimenté » afin de distinguer rendement des entrées et rendement avant sortie."
    ],
    pilotage: [
      "Une baisse progressive peut inviter à examiner si les sorties professionnelles s’accélèrent ou si l’activité économique ne suit plus.",
      "Utile pour suivre la capacité du circuit à produire de l’activité avant reconversion."
    ],
    perimeter: [
      "Fondé sur l’activité économique numérique retenue et sur les sorties identifiées dans Cyclos.",
      "À interpréter avec prudence lorsque le volume de sorties est très faible."
    ],
    formulas: [
      "Activité pour 1 G sorti = volume d’activité économique / volume de sorties."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.retention_and_yield",
      "pilotage-summary.flow_reference"
    ]
  },

  apparentReconversionCoverage: {
    title: "Couverture apparente des reconversions",
    summary: "Cet indicateur exprime combien de jours ou de mois de sorties moyennes le fonds de garantie numérique moyen représenterait au rythme observé.",
    usefulness: "Il fournit une lecture de robustesse apparente face au rythme courant des reconversions. Ce n’est pas un ratio prudentiel réglementaire, mais un repère de pilotage utile pour mettre les sorties en perspective.",
    reading: [
      "Une couverture plus longue signifie que les sorties observées sont faibles relativement au fonds de garantie moyen.",
      "Une couverture plus courte signale une pression de sortie plus forte au regard du stock de garantie.",
      "La valeur dépend à la fois du fonds moyen et du rythme des reconversions."
    ],
    crossReading: [
      "À croiser avec les « Sorties quotidiennes moyennes » et la « Couverture moyenne du stock numérique ».",
      "À lire avec le graphe « Rythme des alimentations et des sorties » : un pic de sorties peut réduire ce ratio.",
      "À replacer dans le contexte de la période : un mois exceptionnel n’a pas la même signification qu’une tendance durable."
    ],
    pilotage: [
      "Si la couverture se contracte nettement, regarder si cela vient d’une accélération des sorties, d’une baisse du fonds de garantie, ou des deux.",
      "Bon indicateur d’alerte douce, mais jamais un verdict isolé."
    ],
    perimeter: [
      "Fondé sur le fonds de garantie numérique moyen Odoo et les sorties numériques identifiées dans Cyclos.",
      "Doit rester interprété comme une approximation de pilotage, pas comme une mesure juridique ou bancaire de solvabilité."
    ],
    formulas: [
      "Sorties quotidiennes moyennes = volume de sorties / jours couverts.",
      "Couverture apparente en jours = fonds de garantie numérique moyen / sorties quotidiennes moyennes."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.reconversion_coverage_proxy",
      "pilotage-summary.monetary_reference",
      "pilotage-summary.flow_reference"
    ]
  },

  economicActivityVolume: {
    title: "Activité économique",
    summary: "Cette grandeur de référence correspond au volume total des paiements économiques numériques retenus dans le périmètre d’analyse.",
    usefulness: "Elle donne l’échelle brute de l’activité observée. C’est le numérateur de plusieurs ratios de pilotage et la base de lecture de la dynamique économique du réseau.",
    reading: [
      "Une hausse indique que davantage de Gonettes ont été échangées dans le périmètre économique retenu.",
      "Une baisse peut traduire un ralentissement de l’usage, mais doit être interprétée avec la durée de période et la masse disponible."
    ],
    crossReading: [
      "À croiser avec la « Masse numérique moyenne » pour comprendre la rotation.",
      "À lire avec les « Transactions économiques pour 1 000 G » pour distinguer volume total et densité d’usage.",
      "À comparer dans le temps avec les secteurs, territoires ou professionnels actifs."
    ],
    pilotage: [
      "Un volume d’activité en hausse est plus significatif s’il ne dépend pas seulement d’un petit nombre de gros flux.",
      "Ce chiffre gagne beaucoup à être interprété avec les vues Territoires, Secteurs et Activité des professionnels."
    ],
    perimeter: [
      "Même périmètre d’activité économique que les analyses de Statistiques globales.",
      "Ne comprend pas les opérations associatives / techniques exclues de l’activité économique centrale."
    ],
    formulas: [
      "Activité économique = somme des montants des transactions économiques retenues."
    ],
    sources: [
      "pilotage-summary.flow_reference.economic_activity_volume",
      "pilotage-summary.flow_reference.economic_activity_transaction_count"
    ]
  },

  averageNumericMass: {
    title: "Masse numérique moyenne",
    summary: "Cette grandeur correspond au stock moyen de Gonettes numériques en circulation sur les jours couverts par la période monétaire effective.",
    usefulness: "Elle donne l’échelle monétaire du système. Sans elle, on peut mesurer des volumes de flux, mais pas leur intensité par rapport à la quantité de Gonettes réellement disponible.",
    reading: [
      "Une masse moyenne plus élevée signifie qu’un stock numérique plus important est présent dans le circuit.",
      "Une hausse de masse n’implique pas automatiquement plus d’activité : encore faut-il que cette masse circule.",
      "Le nombre de jours couverts permet d’apprécier la robustesse de la moyenne."
    ],
    crossReading: [
      "À croiser avec l’« Activité économique » pour lire la rotation économique.",
      "À rapprocher des pressions d’alimentation et de sortie, qui rapportent les flux à cette masse.",
      "À terme, à comparer à la masse active / dormante et à la distribution des soldes."
    ],
    pilotage: [
      "Une masse qui augmente plus vite que l’activité peut signaler une phase d’accumulation ou une montée en charge encore peu transformée en circulation.",
      "C’est l’un des pivots les plus importants de l’analyse monétaire MLCFlux."
    ],
    perimeter: [
      "Calculée à partir des stocks quotidiens Odoo disponibles.",
      "Peut être limitée par le périmètre monétaire effectif affiché en tête de page."
    ],
    formulas: [
      "Masse numérique moyenne = moyenne des stocks numériques quotidiens sur la période effective."
    ],
    sources: [
      "pilotage-summary.monetary_reference.average_numeric_mass",
      "pilotage-summary.monetary_reference.day_count"
    ]
  },

  inflowVolume: {
    title: "Alimentations",
    summary: "Cette grandeur regroupe les entrées de Gonettes numériques dans le circuit sur la période analysée.",
    usefulness: "Elle permet de mesurer la capacité du système à être approvisionné en monnaie numérique. C’est le flux d’entrée qui alimente ensuite la circulation, la rétention ou l’accumulation.",
    reading: [
      "Une hausse signifie que davantage de Gonettes ont été injectées dans le circuit.",
      "Une alimentation forte peut correspondre à une dynamique positive, à une campagne spécifique ou à un événement ponctuel."
    ],
    crossReading: [
      "À croiser avec les « Sorties » et la « Rétention nette des alimentations ».",
      "À lire avec la « Pression d’alimentation », qui rapporte ces entrées à la masse moyenne.",
      "À comparer au graphe mensuel d’alimentations et sorties pour distinguer tendance et ponctualité."
    ],
    pilotage: [
      "Une campagne d’alimentation est d’autant plus intéressante si elle soutient ensuite l’activité et la rétention.",
      "Un pic d’entrées sans hausse ultérieure de circulation mérite d’être interrogé."
    ],
    perimeter: [
      "Alimentations numériques identifiées dans les flux Cyclos retenus par le backend de pilotage."
    ],
    formulas: [
      "Alimentations = somme des volumes d’entrée du circuit sur la période."
    ],
    sources: [
      "pilotage-summary.flow_reference.inflow_volume",
      "pilotage-summary.flow_reference.inflow_transaction_count"
    ]
  },

  outflowVolume: {
    title: "Sorties",
    summary: "Cette grandeur regroupe les reconversions ou sorties numériques du circuit sur la période analysée.",
    usefulness: "Elle permet de mesurer la pression de retrait qui s’exerce sur le système. C’est un repère central pour lire la rétention, la robustesse et le rendement avant sortie.",
    reading: [
      "Une hausse des sorties peut traduire davantage de reconversions professionnelles ou des tensions de réemploi.",
      "Une sortie élevée n’est pas mécaniquement problématique : elle doit être interprétée au regard de l’activité, des entrées et du contexte."
    ],
    crossReading: [
      "À croiser avec les « Alimentations » et le ratio « Sorties / alimentations ».",
      "À rapprocher des « Sorties quotidiennes moyennes » et de la « Couverture apparente des reconversions ».",
      "À lire avec « Activité générée pour 1 G sorti »."
    ],
    pilotage: [
      "Une hausse persistante des sorties peut inviter à examiner les capacités de réemploi des professionnels et les chaînes de recirculation.",
      "Cet indicateur peut devenir très précieux dans le suivi des politiques d’animation du réseau."
    ],
    perimeter: [
      "Sorties numériques identifiées dans les flux Cyclos retenus par le backend de pilotage."
    ],
    formulas: [
      "Sorties = somme des volumes de sortie du circuit sur la période."
    ],
    sources: [
      "pilotage-summary.flow_reference.outflow_volume",
      "pilotage-summary.flow_reference.outflow_transaction_count"
    ]
  },

  averageNumericGuaranteeFund: {
    title: "Fonds de garantie numérique moyen",
    summary: "Cette grandeur correspond au niveau moyen du fonds de garantie numérique observé sur la période.",
    usefulness: "Elle fournit l’assise comptable mise en regard des stocks numériques et du rythme des reconversions. Elle est essentielle pour produire des ratios de couverture interprétables.",
    reading: [
      "Une valeur élevée augmente mécaniquement les ratios de couverture, toutes choses égales par ailleurs.",
      "Elle doit être lue avec prudence comme une donnée de rapprochement comptable et de pilotage, pas isolément."
    ],
    crossReading: [
      "À croiser avec la « Masse numérique moyenne » pour lire la couverture moyenne du stock numérique.",
      "À rapprocher des « Sorties quotidiennes moyennes » et de la « Couverture apparente des reconversions ».",
      "À suivre dans le temps avec les données de stocks monétaires issues d’Odoo."
    ],
    pilotage: [
      "Une variation du fonds mérite d’être commentée au regard de la masse numérique et de la dynamique des reconversions.",
      "C’est un bon point d’entrée pour articuler analyse monétaire et lecture comptable."
    ],
    perimeter: [
      "Donnée moyenne issue des stocks quotidiens Odoo disponibles."
    ],
    formulas: [
      "Fonds de garantie numérique moyen = moyenne quotidienne du fonds observé sur la période."
    ],
    sources: [
      "pilotage-summary.monetary_reference.average_numeric_guarantee_fund"
    ]
  },

  transactionsPer1000G: {
    title: "Transactions économiques pour 1 000 G",
    summary: "Cet indicateur rapporte le nombre de paiements économiques à la masse numérique moyenne.",
    usefulness: "Il mesure une densité d’usage : non pas combien de Gonettes circulent en volume, mais combien d’opérations économiques sont produites relativement à la masse disponible.",
    reading: [
      "Une valeur élevée signifie qu’une même masse monétaire soutient de nombreux paiements.",
      "Une valeur faible peut indiquer une activité concentrée sur peu de transactions ou une moindre fréquence d’usage."
    ],
    crossReading: [
      "À lire avec la rotation économique annualisée : l’un renseigne sur le nombre d’actes, l’autre sur le volume d’activité.",
      "À comparer à l’« Activité économique » pour éviter de confondre fréquence et volume.",
      "À terme, utile à articuler avec le nombre d’utilisateurs actifs et de professionnels actifs."
    ],
    pilotage: [
      "Si ce ratio baisse alors que l’activité reste stable, cela peut signaler une concentration de l’activité sur moins de paiements plus élevés.",
      "S’il augmente, cela peut indiquer une diffusion plus large de l’usage."
    ],
    perimeter: [
      "Paiements économiques numériques retenus dans le périmètre de circulation.",
      "Masse numérique moyenne calculée sur la période monétaire effective."
    ],
    formulas: [
      "Transactions pour 1 000 G = nombre de transactions économiques / masse numérique moyenne × 1 000."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.circulation.transaction_intensity_per_1000_g"
    ]
  },

  economicActivityPerInflow: {
    title: "Activité générée pour 1 G alimenté",
    summary: "Cet indicateur rapporte l’activité économique observée au volume de Gonettes nouvellement alimentées.",
    usefulness: "Il donne une lecture de rendement apparent des entrées : à quel niveau d’activité économique correspond chaque Gonette injectée dans le circuit sur la période ?",
    reading: [
      "Une valeur élevée signifie que l’activité économique représente un volume important relativement aux alimentations.",
      "Une valeur faible peut apparaître si les entrées augmentent fortement sans produire encore une activité proportionnelle."
    ],
    crossReading: [
      "À croiser avec les « Alimentations » et la « Rétention nette des alimentations ».",
      "À comparer à « Activité générée pour 1 G sorti » pour distinguer logique d’injection et logique de sortie.",
      "À lire avec la rotation économique pour replacer ce rendement dans l’intensité globale de circulation."
    ],
    pilotage: [
      "Utile pour suivre si les politiques d’alimentation sont accompagnées d’une mise en circulation effective.",
      "Un recul de ce ratio peut inviter à examiner l’usage aval des Gonettes nouvellement injectées."
    ],
    perimeter: [
      "Activité économique numérique de période rapportée aux alimentations numériques de la même période.",
      "Ne mesure pas directement un multiplicateur causal d’une injection donnée."
    ],
    formulas: [
      "Activité pour 1 G alimenté = volume d’activité économique / volume d’alimentations."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.retention_and_yield.economic_activity_per_inflow"
    ]
  },

  outflowInflowRatio: {
    title: "Sorties / alimentations",
    summary: "Cet indicateur compare le volume sorti du circuit au volume alimenté pendant la même période.",
    usefulness: "Il donne un repère immédiat sur le degré de compensation des entrées par les sorties. C’est l’un des indicateurs les plus lisibles pour qualifier la rétention.",
    reading: [
      "Un ratio de 100 % signifie que les sorties égalent les alimentations.",
      "En dessous de 100 %, les entrées restent supérieures aux sorties.",
      "Au-dessus de 100 %, les sorties dépassent les entrées."
    ],
    crossReading: [
      "À lire avec la « Rétention nette des alimentations », qui exprime la même dynamique sous un autre angle.",
      "À rapprocher des volumes bruts « Alimentations » et « Sorties ».",
      "À replacer dans la chronologie mensuelle du graphe alimentations / sorties."
    ],
    pilotage: [
      "Une hausse durable peut signaler une érosion du flux net entrant.",
      "Un ratio bas n’est pas automatiquement positif si la rotation économique s’affaisse en parallèle."
    ],
    perimeter: [
      "Basé uniquement sur les volumes d’entrées et de sorties numériques retenus."
    ],
    formulas: [
      "Sorties / alimentations = volume de sorties / volume d’alimentations × 100."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.entry_exit_pressure.outflow_inflow_ratio"
    ]
  },

  inflowPressure: {
    title: "Pression d’alimentation",
    summary: "Cet indicateur rapporte le volume d’alimentations à la masse numérique moyenne disponible.",
    usefulness: "Il permet de mesurer l’intensité du renouvellement externe du circuit : quelle part de la masse moyenne est représentée par les nouvelles entrées ?",
    reading: [
      "Une valeur élevée signifie que les alimentations représentent un volume important relativement à la masse moyenne.",
      "Une valeur faible indique que le système dépend moins d’apports nouveaux sur la période."
    ],
    crossReading: [
      "À croiser avec les « Alimentations » et la « Masse numérique moyenne ».",
      "À comparer à la « Pression de sortie » pour lire l’équilibre entre renouvellement et évaporation.",
      "À rapprocher de la rotation économique pour distinguer injection et circulation."
    ],
    pilotage: [
      "Une forte pression d’alimentation peut traduire un effort d’activation ou un effet de campagne.",
      "La question suivante est : ces volumes entrés alimentent-ils durablement l’activité ou restent-ils peu mobilisés ?"
    ],
    perimeter: [
      "Rapport entre les alimentations numériques Cyclos et la masse numérique moyenne Odoo."
    ],
    formulas: [
      "Pression d’alimentation = volume d’alimentations / masse numérique moyenne."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.entry_exit_pressure.inflow_pressure"
    ]
  },

  outflowPressure: {
    title: "Pression de sortie",
    summary: "Cet indicateur rapporte le volume de sorties à la masse numérique moyenne disponible.",
    usefulness: "Il renseigne sur l’intensité de la pression de reconversion relativement à l’échelle du circuit numérique.",
    reading: [
      "Une valeur élevée signifie que les sorties représentent une part importante de la masse moyenne.",
      "Une valeur faible indique une pression de reconversion plus limitée relativement au stock monétaire."
    ],
    crossReading: [
      "À croiser avec les « Sorties » et les « Sorties quotidiennes moyennes ».",
      "À comparer à la « Pression d’alimentation » pour lire l’équilibre dynamique du circuit.",
      "À rapprocher de la « Couverture apparente des reconversions »."
    ],
    pilotage: [
      "Une hausse de pression de sortie peut justifier d’examiner les secteurs ou profils professionnels qui reconvertissent davantage.",
      "À terme, cet indicateur pourra être mis en relation avec la densité de débouchés de réemploi."
    ],
    perimeter: [
      "Rapport entre les sorties numériques Cyclos et la masse numérique moyenne Odoo."
    ],
    formulas: [
      "Pression de sortie = volume de sorties / masse numérique moyenne."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.entry_exit_pressure.outflow_pressure"
    ]
  },

  netFlowPressure: {
    title: "Flux net relatif à la masse moyenne",
    summary: "Cet indicateur rapporte le solde net alimentations moins sorties à la masse numérique moyenne.",
    usefulness: "Il donne une mesure synthétique de l’expansion ou de la contraction nette des flux du circuit, pondérée par sa taille monétaire moyenne.",
    reading: [
      "Une valeur positive signifie que les entrées nettes l’emportent.",
      "Une valeur négative signifie que les sorties nettes dominent.",
      "Plus l’amplitude est forte, plus le déséquilibre de flux est significatif au regard de la masse moyenne."
    ],
    crossReading: [
      "À lire avec les volumes « Alimentations » et « Sorties ».",
      "À rapprocher du diagnostic avancé stock ↔ flux : flux net et variation de stock ne coïncident pas nécessairement.",
      "À comparer à la rétention nette pour distinguer ratio d’entrées et poids du solde dans la masse."
    ],
    pilotage: [
      "Un flux net très positif peut traduire une phase d’expansion ; il faut ensuite vérifier sa transformation en activité.",
      "Un flux net négatif durable mérite une lecture attentive de la pression de sortie."
    ],
    perimeter: [
      "Construit à partir des entrées et sorties numériques Cyclos, rapportées à la masse moyenne Odoo."
    ],
    formulas: [
      "Flux net relatif = (alimentations − sorties) / masse numérique moyenne × 100."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.entry_exit_pressure.net_flow_pressure",
      "pilotage-summary.flow_reference.net_cyclos_flow"
    ]
  },

  averageNumericGuaranteeCoverage: {
    title: "Couverture moyenne du stock numérique",
    summary: "Cet indicateur rapporte le fonds de garantie numérique moyen à la masse numérique moyenne.",
    usefulness: "Il offre une lecture de cohérence apparente entre le stock monétaire numérique et son fonds de garantie associé. C’est un repère comptable important pour interpréter les autres ratios de robustesse.",
    reading: [
      "Une valeur proche de 100 % indique une proximité entre garantie numérique moyenne et masse numérique moyenne.",
      "Une valeur supérieure ou inférieure doit être interprétée avec les règles comptables et le périmètre des données mobilisées."
    ],
    crossReading: [
      "À croiser avec la « Masse numérique moyenne » et le « Fonds de garantie numérique moyen ».",
      "À rapprocher de la « Couverture apparente des reconversions » pour distinguer couverture du stock et couverture d’un rythme de sorties.",
      "À lire avec le diagnostic stock ↔ flux si des écarts de périmètre apparaissent."
    ],
    pilotage: [
      "Cet indicateur sert moins à conclure qu’à repérer des besoins de vérification ou de commentaire méthodologique.",
      "Il est particulièrement utile dans un outil croisant données comptables et données transactionnelles."
    ],
    perimeter: [
      "Rapport entre deux moyennes quotidiennes issues d’Odoo : fonds de garantie numérique et masse numérique."
    ],
    formulas: [
      "Couverture moyenne = fonds de garantie numérique moyen / masse numérique moyenne × 100."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.guarantee_coverage.average_numeric_guarantee_coverage_rate"
    ]
  },

  averageDailyOutflow: {
    title: "Sorties quotidiennes moyennes",
    summary: "Cet indicateur exprime le rythme moyen journalier des sorties observées sur la période.",
    usefulness: "Il traduit les reconversions en cadence quotidienne, ce qui permet ensuite de construire la couverture apparente en jours ou en mois.",
    reading: [
      "Une hausse signifie que les sorties se produisent à un rythme moyen plus intense.",
      "Une baisse signifie que la pression de reconversion ralentit sur la période."
    ],
    crossReading: [
      "À croiser avec le volume brut de « Sorties » et la durée de la période.",
      "À rapprocher de la « Couverture apparente détaillée ».",
      "À lire avec le graphe mensuel d’alimentations et sorties afin de repérer d’éventuels pics."
    ],
    pilotage: [
      "Un rythme quotidien qui s’élève durablement peut appeler une lecture sectorielle ou professionnelle des reconversions.",
      "C’est un indicateur plus opérationnel que le volume total de sorties pris isolément."
    ],
    perimeter: [
      "Sorties numériques identifiées dans Cyclos, ramenées au nombre de jours couverts."
    ],
    formulas: [
      "Sorties quotidiennes moyennes = volume de sorties / nombre de jours couverts."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.reconversion_coverage_proxy.average_daily_outflow"
    ]
  },

  numericStockVariation: {
    title: "Variation du stock numérique",
    summary: "Cette donnée mesure l’évolution du stock numérique observé dans Odoo entre le début et la fin de la période effective.",
    usefulness: "Elle sert de point d’ancrage comptable pour comparer ce que les stocks Odoo racontent à ce que les flux Cyclos expliquent.",
    reading: [
      "Une variation positive indique une hausse du stock numérique entre l’ouverture et la clôture de période.",
      "Une variation négative indique une baisse.",
      "Elle peut être non calculable lorsque la période commence au premier jour disponible des stocks quotidiens."
    ],
    crossReading: [
      "À comparer directement au « Flux net Cyclos ».",
      "À lire avec le « Résiduel de rapprochement » qui mesure l’écart entre les deux.",
      "À rapprocher des alimentations, sorties et éventuels écarts de périmètre."
    ],
    pilotage: [
      "Si la variation de stock et le flux net divergent fortement, une analyse méthodologique devient nécessaire.",
      "C’est un indicateur de cohérence, pas un KPI d’activité."
    ],
    perimeter: [
      "Stocks numériques Odoo à l’ouverture et à la clôture de la période monétaire effective."
    ],
    formulas: [
      "Variation du stock numérique = stock numérique de clôture − stock numérique d’ouverture."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.stock_flow_reconciliation.numeric_stock_variation"
    ]
  },

  netCyclosFlow: {
    title: "Flux net Cyclos",
    summary: "Cette donnée correspond au solde des alimentations et sorties numériques identifiées dans Cyclos.",
    usefulness: "Elle permet d’estimer ce que les flux transactionnels devraient expliquer dans l’évolution du stock numérique, avant comparaison au stock réellement observé.",
    reading: [
      "Une valeur positive signifie que les alimentations dépassent les sorties.",
      "Une valeur négative signifie que les sorties dépassent les alimentations.",
      "Ce n’est pas automatiquement l’équivalent exact d’une variation de stock comptable."
    ],
    crossReading: [
      "À comparer à la « Variation du stock numérique ».",
      "À lire avec le « Résiduel de rapprochement ».",
      "À replacer dans les indicateurs d’entrées, sorties et rétention."
    ],
    pilotage: [
      "Ce chiffre est essentiel pour objectiver ce que les flux Cyclos expliquent réellement.",
      "Il évite de confondre dynamique transactionnelle et évolution comptable du stock."
    ],
    perimeter: [
      "Somme des alimentations moins les sorties numériques Cyclos retenues."
    ],
    formulas: [
      "Flux net Cyclos = alimentations − sorties."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.stock_flow_reconciliation.net_cyclos_flow"
    ]
  },

  holdingsAverageUserStock: {
    title: "Stock particulier moyen",
    summary: "Cet indicateur mesure le volume moyen de Gonettes numériques détenues par les particuliers avec un solde positif sur la période analysée.",
    usefulness: "Il donne une première lecture de la monnaie disponible côté usagers. Ce stock peut être immédiatement mobilisable, en attente de dépense, ou progressivement s’éloigner de l’activité : il doit donc être lu avec la dormance et les paiements U→P.",
    reading: [
      "Une valeur élevée signifie qu’un volume important de Gonettes numériques stationne chez les particuliers en moyenne sur la période.",
      "Une hausse de ce stock n’est pas automatiquement positive ou négative : elle peut traduire davantage de détention active, une alimentation récente, ou une accumulation moins dépensée.",
      "La part indiquée sous la valeur rapporte ce stock à la masse numérique moyenne Odoo."
    ],
    crossReading: [
      "À croiser avec la « Masse particulière active / dormante » pour distinguer stock vivant et stock éloigné de l’usage.",
      "À rapprocher de la « Mobilisation économique du stock particulier » pour voir si cette détention se transforme en paiements vers les pros.",
      "À lire avec les alimentations : une hausse du stock particulier peut suivre une augmentation des entrées dans le circuit."
    ],
    pilotage: [
      "Cet indicateur aide à repérer l’importance du réservoir de monnaie porté par les particuliers.",
      "Il devient particulièrement utile lorsqu’on cherche à comprendre si la croissance de la masse numérique améliore réellement l’usage ou alimente surtout une détention peu mobilisée."
    ],
    perimeter: [
      "Moyenne journalière des soldes positifs particuliers sur les jours alignés entre les soldes Cyclos et la masse numérique Odoo.",
      "Les soldes nuls ou négatifs ne contribuent pas au stock positif."
    ],
    formulas: [
      "Stock particulier moyen = moyenne quotidienne de la somme des soldes particuliers positifs.",
      "Part de masse = stock particulier moyen / masse numérique moyenne."
    ],
    sources: [
      "pilotage-holdings-summary.holdings_reference.average_positive_user_stock",
      "pilotage-holdings-summary.holdings_reference.average_user_stock_share_of_numeric_mass"
    ]
  },

  holdingsAverageProfessionalNetworkStock: {
    title: "Stock professionnels du réseau moyen",
    summary: "Cet indicateur mesure le volume moyen de Gonettes numériques détenues par les professionnels du réseau, hors comptes entreprise Gonette P0000 / P9999.",
    usefulness: "Il renseigne l’ancrage de la monnaie dans le tissu économique professionnel. Une monnaie locale bien implantée peut logiquement s’accumuler temporairement chez les pros, mais ce signal gagne à être lu avec leur capacité de réemploi interne.",
    reading: [
      "Une valeur élevée indique que les professionnels portent une part importante de la masse numérique moyenne.",
      "Cette détention peut refléter un réseau professionnel bien irrigué, mais elle ne prouve pas à elle seule que la monnaie recircule activement.",
      "La part affichée sous la valeur permet de comparer ce stock à l’ensemble de la masse numérique moyenne."
    ],
    crossReading: [
      "À croiser avec le réemploi interne professionnel et les flux P→P.",
      "À rapprocher des reconversions : un stock professionnel élevé n’a pas le même sens s’il s’accompagne d’une pression de sortie croissante.",
      "À lire avec le graphe de composition de la masse numérique pour suivre la place relative des pros dans le circuit."
    ],
    pilotage: [
      "Cet indicateur est central pour apprécier l’ancrage économique de la Gonette.",
      "Une hausse peut être encourageante si elle accompagne davantage de débouchés internes ; elle peut inviter à vigilance si elle signale une accumulation sans redépense."
    ],
    perimeter: [
      "Moyenne journalière des soldes professionnels positifs.",
      "Les comptes P0000 et P9999 sont exclus afin de distinguer le réseau professionnel ordinaire des comptes entreprise Gonette."
    ],
    formulas: [
      "Stock professionnels du réseau moyen = moyenne quotidienne de la somme des soldes professionnels positifs, hors P0000 / P9999.",
      "Part de masse = stock professionnels du réseau moyen / masse numérique moyenne."
    ],
    sources: [
      "pilotage-holdings-summary.holdings_reference.average_positive_professional_network_stock",
      "pilotage-holdings-summary.holdings_reference.average_professional_network_stock_share_of_numeric_mass"
    ]
  },

  holdingsAverageGonetteBusinessAccountsStock: {
    title: "Stock comptes entreprise Gonette",
    summary: "Cet indicateur isole le stock moyen porté par les comptes entreprise Gonette P0000 / P9999.",
    usefulness: "Ces comptes n’ont pas la même signification que les professionnels ordinaires du réseau. Les distinguer évite de mélanger détention économique diffuse et mouvements liés aux comptes opérateurs de la structure Gonette.",
    reading: [
      "La valeur affichée mesure le stock positif moyen porté par P0000 / P9999.",
      "Une hausse ou une baisse doit être interprétée comme un signal opérateur spécifique, pas comme une évolution directe de l’ancrage professionnel.",
      "La part indiquée sous la valeur rapporte ces comptes à la masse numérique moyenne."
    ],
    crossReading: [
      "À lire séparément du stock professionnel du réseau, justement pour éviter les confusions de périmètre.",
      "À rapprocher de l’onglet sur les opérations associatives / techniques lorsque l’on cherche à comprendre les mouvements impliquant les comptes opérateurs.",
      "À croiser avec la composition de la masse numérique pour voir si ces comptes prennent ou non davantage de place dans le stock total."
    ],
    pilotage: [
      "Cet indicateur sert surtout de garde-fou analytique : il empêche de surinterpréter comme « professionnel » un stock qui relève des comptes entreprise Gonette.",
      "Une variation forte de ce stock peut justifier un contrôle des opérations de structure ou des rythmes de régularisation."
    ],
    perimeter: [
      "Comptes retenus : P0000 et P9999.",
      "Moyenne journalière des soldes positifs de ces comptes sur les jours alignés."
    ],
    formulas: [
      "Stock comptes entreprise Gonette = moyenne quotidienne de la somme des soldes positifs P0000 / P9999.",
      "Part de masse = stock comptes entreprise Gonette / masse numérique moyenne."
    ],
    sources: [
      "pilotage-holdings-summary.holdings_reference.average_positive_gonette_business_accounts_stock",
      "pilotage-holdings-summary.holdings_reference.average_gonette_business_accounts_stock_share_of_numeric_mass"
    ]
  },

  holdingsActive30Stock: {
    title: "Stock actif ≤ 30 jours",
    summary: "Cette carte mesure le stock positif particulier détenu à la clôture par des comptes ayant connu une activité dans les 30 derniers jours.",
    usefulness: "Elle donne une photographie du stock encore proche de l’usage récent. C’est une manière simple d’estimer la part de détention qui reste, à court terme, reliée à une dynamique de circulation.",
    reading: [
      "La valeur en Gonettes correspond au stock détenu par les particuliers considérés comme actifs à la clôture.",
      "Le nombre de comptes mesure l’étendue du groupe concerné.",
      "Le pourcentage indique la part de ce stock actif dans l’ensemble du stock particulier positif de clôture."
    ],
    crossReading: [
      "À lire avec les catégories dormantes 31–90 j et > 90 j pour comprendre la structure complète du stock particulier.",
      "À rapprocher du graphe de dormance, qui montre l’évolution mensuelle de ces masses.",
      "À croiser avec la mobilisation vers les pros : un stock plus actif peut contribuer davantage aux paiements U→P, sans relation mécanique."
    ],
    pilotage: [
      "Une part active élevée suggère que la détention particulière reste largement connectée à un usage récent.",
      "Une baisse durable peut justifier d’examiner les leviers de relance des usagers ou la disponibilité des usages concrets."
    ],
    perimeter: [
      "Comptes particuliers à solde positif à la date de clôture.",
      "Activité récente définie par au moins une transaction impliquant le compte dans les 30 jours précédant la clôture."
    ],
    formulas: [
      "Stock actif ≤ 30 j = somme des soldes positifs des comptes particuliers dont la dernière activité date de 30 jours ou moins.",
      "Part active = stock actif ≤ 30 j / stock particulier positif total de clôture."
    ],
    sources: [
      "pilotage-holdings-summary.holdings_metrics.dormancy.buckets[active_30]"
    ]
  },

  holdingsDormant31To90Stock: {
    title: "Stock dormant 31–90 jours",
    summary: "Cette carte mesure le stock particulier positif porté à la clôture par des comptes sans activité depuis 31 à 90 jours.",
    usefulness: "Elle décrit une zone intermédiaire : la monnaie s’éloigne de l’usage récent, mais elle n’appartient pas encore à la dormance longue. C’est souvent une strate intéressante pour des actions de remobilisation précoce.",
    reading: [
      "La valeur en Gonettes mesure le stock concerné.",
      "Le nombre de comptes indique combien de porteurs se situent dans cette phase de décrochage modéré.",
      "Le pourcentage rapporte ce stock au total du stock particulier positif de clôture."
    ],
    crossReading: [
      "À comparer à la part active ≤ 30 j et au stock dormant > 90 j.",
      "À suivre avec le graphe de dormance pour repérer un glissement progressif du stock vers des durées d’inactivité plus longues.",
      "À mettre en regard des politiques de relance ou de communication vers les utilisateurs."
    ],
    pilotage: [
      "Une hausse de cette strate peut être un signal précoce d’essoufflement de l’usage particulier.",
      "Elle peut aider à cibler des interventions avant que la dormance ne devienne plus installée."
    ],
    perimeter: [
      "Comptes particuliers à solde positif à la clôture.",
      "Dernière activité située entre 31 et 90 jours avant la clôture."
    ],
    formulas: [
      "Stock dormant 31–90 j = somme des soldes positifs des comptes particuliers dont la dernière activité remonte à 31–90 jours.",
      "Part dormante 31–90 j = stock dormant 31–90 j / stock particulier positif total de clôture."
    ],
    sources: [
      "pilotage-holdings-summary.holdings_metrics.dormancy.buckets[dormant_31_90]"
    ]
  },

  holdingsDormantGt90Stock: {
    title: "Stock dormant > 90 jours",
    summary: "Cette carte agrège le stock particulier positif porté par des comptes sans activité depuis plus de 90 jours.",
    usefulness: "Elle matérialise la part du stock la plus éloignée de l’usage récent. C’est un indicateur important pour suivre les masses durablement stationnées chez les particuliers et évaluer l’ampleur d’un éventuel chantier de réactivation.",
    reading: [
      "La valeur en Gonettes additionne les strates 91–180 jours et > 180 jours.",
      "Le nombre de comptes affiché suit la même logique d’agrégation.",
      "Le pourcentage rapporte cette dormance longue au stock particulier positif de clôture."
    ],
    crossReading: [
      "À lire avec la réactivation des stocks dormants : un stock > 90 jours élevé prend un sens différent si une part significative revient ensuite en circulation.",
      "À rapprocher du stock actif ≤ 30 j pour suivre le contraste entre monnaie encore proche de l’usage et monnaie très éloignée.",
      "À croiser avec les stratégies de réengagement des sociétaires ou usagers."
    ],
    pilotage: [
      "Une hausse prolongée de ce stock peut révéler un affaiblissement de la mise en usage côté particuliers.",
      "Cet indicateur peut servir à mesurer l’enjeu potentiel de campagnes de remobilisation ciblées."
    ],
    perimeter: [
      "Comptes particuliers à solde positif à la clôture.",
      "Agrégation des strates de dormance 91–180 jours et > 180 jours."
    ],
    formulas: [
      "Stock dormant > 90 j = stock dormant 91–180 j + stock dormant > 180 j.",
      "Part dormante > 90 j = stock dormant > 90 j / stock particulier positif total de clôture."
    ],
    sources: [
      "pilotage-holdings-summary.holdings_metrics.dormancy.buckets[dormant_91_180]",
      "pilotage-holdings-summary.holdings_metrics.dormancy.buckets[dormant_gt_180]"
    ]
  },

  holdingsReactivatedUserCount: {
    title: "Comptes réactivés",
    summary: "Cette carte compte les particuliers qui détenaient un solde positif, étaient dormants depuis plus de 90 jours à l’ouverture de la période, puis ont enregistré au moins une transaction.",
    usefulness: "Elle permet de mesurer si un stock éloigné de l’usage peut effectivement revenir vers une activité observable. C’est un indicateur de remobilisation, pas seulement de présence de soldes.",
    reading: [
      "Le nombre affiché compte les comptes effectivement réactivés pendant la période.",
      "Le pourcentage les rapporte à l’ensemble des comptes dormants > 90 jours identifiés à l’ouverture.",
      "Une réactivation signifie ici retour à une activité quelconque, pas nécessairement un paiement vers un professionnel."
    ],
    crossReading: [
      "À lire avec le « Stock dormant porté par ces comptes » pour connaître le poids monétaire associé.",
      "À rapprocher des « Paiements U→P issus des comptes réactivés » pour savoir si la réactivation se traduit en circulation économique vers le réseau professionnel.",
      "À comparer avec le stock dormant > 90 jours à la clôture afin de distinguer réactivation partielle et renouvellement de la dormance."
    ],
    pilotage: [
      "Cet indicateur peut servir à évaluer l’efficacité de dispositifs de relance ou d’accompagnement des utilisateurs.",
      "Une faible réactivation malgré un stock dormant élevé peut signaler un gisement de monnaie encore peu remobilisé."
    ],
    perimeter: [
      "Population de départ : comptes particuliers à solde positif et dormants > 90 jours à l’ouverture de la période.",
      "Réactivation : au moins une transaction impliquant le compte pendant la période."
    ],
    formulas: [
      "Comptes réactivés = nombre de comptes dormants > 90 j à l’ouverture ayant enregistré au moins une transaction pendant la période.",
      "Taux de réactivation = comptes réactivés / comptes dormants > 90 j à l’ouverture."
    ],
    sources: [
      "pilotage-holdings-summary.holdings_metrics.reactivation.reactivated_user_count",
      "pilotage-holdings-summary.holdings_metrics.reactivation.reactivated_user_share_of_dormant_gt_90_opening_users"
    ]
  },

  holdingsReactivatedOpeningStock: {
    title: "Stock dormant porté par les comptes réactivés",
    summary: "Cette carte mesure le volume de Gonettes qui était détenu à l’ouverture par les comptes dormants > 90 jours ayant ensuite été réactivés.",
    usefulness: "Elle complète le simple nombre de comptes réactivés. Quelques comptes peuvent représenter un stock important ; inversement, un grand nombre de réactivations peut ne concerner qu’un volume monétaire limité.",
    reading: [
      "La valeur affichée porte sur le stock dormant d’ouverture associé aux comptes qui seront réactivés pendant la période.",
      "Le pourcentage le rapporte au stock dormant > 90 jours total identifié à l’ouverture.",
      "Cet indicateur mesure un potentiel remobilisé, pas le volume réellement dépensé ensuite."
    ],
    crossReading: [
      "À lire avec le nombre de comptes réactivés pour distinguer ampleur sociale et ampleur monétaire de la réactivation.",
      "À rapprocher des paiements U→P issus des comptes réactivés pour voir quelle part de ce stock revient effectivement vers les professionnels.",
      "À croiser avec la dormance longue totale."
    ],
    pilotage: [
      "Une part élevée signifie que les comptes réactivés représentaient une fraction importante du stock dormant initial.",
      "Une part faible peut indiquer que les réactivations concernent surtout de petits soldes ou qu’un stock important reste encore à remobiliser."
    ],
    perimeter: [
      "Stock mesuré à l’ouverture de la période.",
      "Comptes concernés : particuliers dormants > 90 jours à l’ouverture, puis réactivés au cours de la période."
    ],
    formulas: [
      "Stock dormant porté par les comptes réactivés = somme des soldes d’ouverture des comptes réactivés.",
      "Part de stock réactivé = stock d’ouverture de ces comptes / stock dormant > 90 j total à l’ouverture."
    ],
    sources: [
      "pilotage-holdings-summary.holdings_metrics.reactivation.reactivated_opening_stock",
      "pilotage-holdings-summary.holdings_metrics.reactivation.reactivated_stock_share_of_dormant_gt_90_opening_stock"
    ]
  },

  holdingsReactivatedEconomicUpVolume: {
    title: "Paiements U→P issus des comptes réactivés",
    summary: "Cette carte mesure le volume de paiements vers les professionnels réalisé, pendant la période, par les comptes particuliers réactivés.",
    usefulness: "Elle indique si la réactivation se traduit en circulation économique directement utile au réseau professionnel. C’est un pont entre remobilisation d’usagers et activité effective.",
    reading: [
      "La valeur en Gonettes correspond au volume des paiements U→P réalisés par les comptes réactivés.",
      "Le nombre de transactions précise l’intensité d’usage associée.",
      "Un compte peut être réactivé sans effectuer de paiement U→P ; cette carte se concentre uniquement sur les flux économiques vers les pros."
    ],
    crossReading: [
      "À lire avec le nombre de comptes réactivés : beaucoup de réactivations n’impliquent pas forcément beaucoup de paiements vers les pros.",
      "À rapprocher du stock dormant porté par ces comptes pour estimer la capacité de transformation d’un stock remobilisé en activité économique.",
      "À comparer au volume U→P global si l’on veut mesurer le poids relatif des réactivations dans l’activité des particuliers."
    ],
    pilotage: [
      "Cet indicateur permet de distinguer une réactivation simplement administrative ou ponctuelle d’une réactivation réellement contributive à la circulation économique.",
      "Il peut aider à objectiver l’impact de campagnes de relance orientées vers l’usage marchand."
    ],
    perimeter: [
      "Comptes particuliers identifiés comme réactivés sur la période.",
      "Flux retenus : paiements économiques U→P effectués par ces comptes pendant la période."
    ],
    formulas: [
      "Volume U→P des comptes réactivés = somme des paiements particuliers → professionnels réalisés par les comptes réactivés.",
      "Nombre de transactions = nombre de paiements U→P associés à ces comptes."
    ],
    sources: [
      "pilotage-holdings-summary.holdings_metrics.reactivation.economic_up_volume_from_reactivated_users",
      "pilotage-holdings-summary.holdings_metrics.reactivation.economic_up_transaction_count_from_reactivated_users"
    ]
  },

  stockFlowResidual: {
    title: "Résiduel de rapprochement",
    summary: "Cet indicateur mesure l’écart entre la variation du stock numérique Odoo et le flux net d’alimentations / sorties identifié dans Cyclos.",
    usefulness: "Il ne sert pas à juger l’activité économique, mais à vérifier la cohérence du rapprochement stocks ↔ flux. C’est un outil de rigueur analytique et de contrôle de périmètre.",
    reading: [
      "Un résiduel proche de zéro signifie que les deux lectures se rapprochent bien.",
      "Un résiduel important peut signaler des mouvements non couverts par le modèle simplifié, des différences de périmètre ou des éléments comptables à documenter.",
      "Il peut être non calculable sur certaines périodes."
    ],
    crossReading: [
      "À lire conjointement avec la « Variation du stock numérique » et le « Flux net Cyclos ».",
      "À rapprocher du message d’avertissement lorsque la période commence au premier jour disponible des stocks Odoo.",
      "À replacer dans la documentation méthodologique de la page, pas dans une lecture isolée."
    ],
    pilotage: [
      "Un résiduel durablement élevé est un signal d’audit ou de clarification méthodologique.",
      "C’est un garde-fou contre les interprétations trop rapides des ratios monétaires."
    ],
    perimeter: [
      "Rapprochement entre stocks numériques Odoo et flux numériques Cyclos sur la même période effective."
    ],
    formulas: [
      "Résiduel = variation du stock numérique − flux net Cyclos."
    ],
    sources: [
      "pilotage-summary.pilotage_metrics.stock_flow_reconciliation.residual"
    ]
  }
};

function buildPilotageSummaryReading({
  flow = {},
  reference = {},
  retentionYield = {},
  coverage = {}
} = {}) {
  const retentionValue = Number(retentionYield.net_inflow_retention_rate);
  const retentionSentence = Number.isFinite(retentionValue)
    ? retentionValue >= 0
      ? `Les alimentations dépassent les sorties, avec une rétention nette de <strong>${formatPilotagePercent(retentionValue)}</strong>.`
      : `Les sorties dépassent les alimentations, avec une rétention nette de <strong>${formatPilotagePercent(retentionValue)}</strong>.`
    : "La rétention nette des alimentations n’est pas disponible sur cette période.";

  return `
    <section class="card pilotage-reading-card">
      <div class="pilotage-section-heading">
        <h3>Lecture rapide de la période</h3>
      </div>

      <div class="pilotage-reading-copy">
        <p>
          La Gonette numérique a généré
          <strong>${gonettes(flow.economic_activity_volume || 0)}</strong>
          d’activité économique pour une masse numérique moyenne de
          <strong>${gonettes(reference.average_numeric_mass || 0)}</strong>.
        </p>

        <p>
          ${retentionSentence}
          Au rythme moyen des reconversions observées,
          le fonds de garantie numérique moyen représente une couverture apparente de
          <strong>${formatPilotageThirtyDayPeriods(coverage.apparent_reconversion_coverage_30_day_periods)}</strong>.
        </p>
      </div>
    </section>
  `;
}


function openPilotageIndicatorHelp(indicatorKey) {
  openStatsChartModal(buildPilotageIndicatorHelpHtml(indicatorKey), "help");
}

function bindPilotageIndicatorHelpButtons() {
  document.querySelectorAll("[data-pilotage-help]").forEach((card) => {
    const indicatorKey = card.dataset.pilotageHelp;

    if (!indicatorKey || !PILOTAGE_INDICATOR_HELP[indicatorKey]) {
      return;
    }

    card.classList.add("pilotage-help-enabled");

    if (!card.querySelector("[data-pilotage-indicator-help]")) {
      card.insertAdjacentHTML("afterbegin", `
        <button
          type="button"
          class="stats-chart-tool-btn pilotage-indicator-help-btn"
          data-pilotage-indicator-help="${indicatorKey}"
          aria-label="Afficher l’aide de lecture de cet indicateur"
          title="Aide à la lecture"
        >
          ?
        </button>
      `);
    }
  });

  document.querySelectorAll("[data-pilotage-indicator-help]").forEach((button) => {
    button.addEventListener("click", () => {
      openPilotageIndicatorHelp(button.dataset.pilotageIndicatorHelp);
    });
  });
}

function bindPilotageTabs() {
  const buttons = Array.from(document.querySelectorAll("[data-pilotage-tab]"));
  const panels = Array.from(document.querySelectorAll("[data-pilotage-panel]"));

  if (!buttons.length || !panels.length) {
    return;
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextTab = button.dataset.pilotageTab;

      buttons.forEach((candidate) => {
        const isActive = candidate === button;
        candidate.classList.toggle("tab-btn-active", isActive);
        candidate.setAttribute("aria-selected", isActive ? "true" : "false");
      });

      panels.forEach((panel) => {
        panel.classList.toggle("hidden", panel.dataset.pilotagePanel !== nextTab);
      });

      // Les graphiques Chart.js sont initialisés alors que certains onglets sont masqués.
      // On force leur recalcul de taille au moment où un onglet devient visible.
      window.requestAnimationFrame(() => {
        [
          "pilotageRotation",
          "pilotageFlowRhythm",
          "pilotageRetention",
          "pilotageInternalReuseHistory",
          "pilotageLm3History",
          "pilotageHoldingsStockShare",
          "pilotageHoldingsMassComposition",
          "pilotageHoldingsMobilization",
          "pilotageHoldingsDormancy"
        ].forEach((chartKey) => {
          const chart = appState.charts[chartKey];
          if (chart && typeof chart.resize === "function") {
            chart.resize();
          }
        });
      });
    });
  });
}

async function renderMonetaryPilotageView(forceReload = false) {
  const preserveVisibleView = shouldPreservePeriodRefreshView(
    "monetary-pilotage",
    forceReload
  );

  if (!preserveVisibleView) {
    destroyMonetaryPilotageCharts();
  }

  appState.currentView = "monetary-pilotage";
  syncSidebarView("monetary-pilotage");
  setTitle("Pilotage monétaire");

  if (!preserveVisibleView) {
    content.innerHTML = `<div class="card">Chargement du pilotage monétaire...</div>`;
  }

  try {
    const [
      data,
      timeseries,
      reuseYearly,
      lm3Yearly,
      holdingsSummary,
      holdingsTimeseries
    ] = await Promise.all([
      apiGet(`/api/monetary-indicators/pilotage-summary${getPeriodQueryParam()}`),
      apiGet(`/api/monetary-indicators/pilotage-timeseries${getPeriodQueryParam()}`),
      apiGet("/api/monetary-indicators/pilotage-reuse-yearly"),
      apiGet("/api/monetary-indicators/pilotage-lm3-yearly"),
      apiGet(`/api/monetary-indicators/pilotage-holdings-summary${getPeriodQueryParam()}`),
      apiGet(`/api/monetary-indicators/pilotage-holdings-timeseries${getPeriodQueryParam()}`)
    ]);

    const effectivePeriod = (
      data?.effective_period?.start && data?.effective_period?.end
        ? data.effective_period
        : null
    );
    const requestedPeriod = data?.requested_period || null;
    const flow = data?.flow_reference || {};
    const reference = data?.monetary_reference || {};
    const metrics = data?.pilotage_metrics || {};
    const pilotageSeries = timeseries?.items || [];
    const pilotageSeriesForCharts = buildPilotageMonthlyChartSeries(
      pilotageSeries,
      requestedPeriod
    );
    const pilotageReuseYearlySeries = reuseYearly?.items || [];
    const pilotageLm3YearlySeries = lm3Yearly?.items || [];

    const holdingsEffectivePeriod = holdingsSummary?.effective_period || null;
    const holdingsReference = holdingsSummary?.holdings_reference || {};
    const holdingsClosing = holdingsReference?.closing_snapshot || {};
    const holdingsFlow = holdingsSummary?.flow_reference || {};
    const holdingsMetrics = holdingsSummary?.holdings_metrics || {};
    const holdingsMobilization = holdingsMetrics?.mobilization || {};
    const holdingsDormancy = holdingsMetrics?.dormancy || {};
    const holdingsReactivation = holdingsMetrics?.reactivation || {};
    const holdingsSeries = holdingsTimeseries?.items || [];
    const holdingsSeriesForCharts = buildPilotageMonthlyChartSeries(
      holdingsSeries,
      requestedPeriod
    );

    const circulation = metrics.circulation || {};
    const entryExit = metrics.entry_exit_pressure || {};
    const retentionYield = metrics.retention_and_yield || {};
    const guaranteeCoverage = metrics.guarantee_coverage || {};
    const reconciliation = metrics.stock_flow_reconciliation || {};
    const coverage = metrics.reconversion_coverage_proxy || {};
    const internalReuse = metrics.internal_reuse || {};
    const internalReuseGlobal = internalReuse.global || {};
    const internalReuseProfessionals = internalReuse.professionals || {};
    const periodLm3 = metrics.lm3 || {};
    const pilotagePartialMonthNote = buildPilotagePartialMonthNote(pilotageSeries);
    const pilotageReuseYearlyFootnote = buildPilotageReuseYearlyFootnote(
      pilotageReuseYearlySeries
    );
    const pilotageLm3YearlyFootnote = buildPilotageLm3YearlyFootnote(
      pilotageLm3YearlySeries
    );

    const holdingsDormancyBuckets = holdingsDormancy?.buckets || [];
    const holdingsActive30Bucket = getPilotageHoldingsDormancyBucket(
      holdingsDormancyBuckets,
      "active_30"
    );
    const holdingsDormant31To90Bucket = getPilotageHoldingsDormancyBucket(
      holdingsDormancyBuckets,
      "dormant_31_90"
    );
    const holdingsDormant91To180Bucket = getPilotageHoldingsDormancyBucket(
      holdingsDormancyBuckets,
      "dormant_91_180"
    );
    const holdingsDormantGt180Bucket = getPilotageHoldingsDormancyBucket(
      holdingsDormancyBuckets,
      "dormant_gt_180"
    );

    const holdingsDormantGt90Stock =
      Number(holdingsDormant91To180Bucket.positive_user_stock || 0) +
      Number(holdingsDormantGt180Bucket.positive_user_stock || 0);

    const holdingsDormantGt90Share = Number(holdingsDormancy?.positive_user_stock || 0) > 0
      ? holdingsDormantGt90Stock / Number(holdingsDormancy.positive_user_stock || 0)
      : null;

    const holdingsPartialMonthNote = buildPilotageHoldingsPartialMonthNote(
      holdingsSeries
    );

    const displayedPilotagePeriod = effectivePeriod || requestedPeriod || {};
    const holdingsDisplayedPeriod = holdingsEffectivePeriod || displayedPilotagePeriod;

    const holdingsEffectiveStartLabel = formatIsoDateFr(
      holdingsDisplayedPeriod?.start
    );
    const holdingsEffectiveEndLabel = formatIsoDateFr(
      holdingsDisplayedPeriod?.end
    );

    const holdingsPeriodDiffersFromPilotage = (
      holdingsDisplayedPeriod?.start &&
      holdingsDisplayedPeriod?.end &&
      (
        holdingsDisplayedPeriod.start !== displayedPilotagePeriod?.start ||
        holdingsDisplayedPeriod.end !== displayedPilotagePeriod?.end
      )
    );

    const holdingsPeriodNotice = holdingsPeriodDiffersFromPilotage
      ? `
          <div class="pilotage-period-line">
            Période de détention effective :
            <strong>${holdingsEffectiveStartLabel} → ${holdingsEffectiveEndLabel}</strong>
          </div>
        `
      : "";

    const effectiveStartLabel = formatIsoDateFr(displayedPilotagePeriod.start);
    const effectiveEndLabel = formatIsoDateFr(displayedPilotagePeriod.end);

    const requestedStartLabel = formatIsoDateFr(
      requestedPeriod?.start || displayedPilotagePeriod.start
    );
    const requestedEndLabel = formatIsoDateFr(
      requestedPeriod?.end || displayedPilotagePeriod.end
    );

    const pilotagePeriodLabel = effectivePeriod
      ? "Période de pilotage effective"
      : "Période de pilotage demandée";

    const pilotagePeriodNotice = effectivePeriod
      ? buildMonetaryEffectivePeriodNotice(requestedPeriod, effectivePeriod)
      : `
        <div class="monetary-period-warning">
          <strong>Périmètre partiellement incomplet :</strong>
          les indicateurs reposant sur les stocks quotidiens Odoo
          peuvent être non renseignés ou incomplets sur cette période.
          Les lectures fondées sur les flux Cyclos restent affichées.
        </div>
      `;

    if (preserveVisibleView) {
      destroyMonetaryPilotageCharts();
    }

    content.innerHTML = `
      <section class="card pilotage-overview-card">
        <div class="pilotage-overview-header pilotage-overview-header-refined">
          <div>
            <div class="stat-label">Analyse croisée Odoo × Cyclos</div>
            <h2>La Gonette numérique circule. Mais que raconte vraiment son mouvement ?</h2>
            <p>
              Cette lecture croise les <strong>flux Cyclos</strong> et les <strong>stocks comptables Odoo</strong>
              pour distinguer ce qui <strong>entre</strong>, ce qui <strong>circule</strong>,
              ce qui <strong>s’ancre</strong> et ce qui reste <strong>à remobiliser</strong>.
            </p>
          </div>
        </div>
        ${pilotagePeriodNotice}
      </section>

      <nav class="stats-tabs pilotage-tabs" aria-label="Lectures du pilotage monétaire">
        <button
          class="tab-btn tab-btn-active"
          type="button"
          data-pilotage-tab="summary"
          aria-selected="true"
        >
          Synthèse
        </button>

        <button
          class="tab-btn"
          type="button"
          data-pilotage-tab="circulation"
          aria-selected="false"
        >
          Circulation &amp; rendement
        </button>

        <button
          class="tab-btn"
          type="button"
          data-pilotage-tab="flows"
          aria-selected="false"
        >
          Entrées, sorties &amp; garanties
        </button>

        <button
          class="tab-btn"
          type="button"
          data-pilotage-tab="holdings"
          aria-selected="false"
        >
          Détention &amp; ancrage
        </button>
      </nav>

      <section class="pilotage-tab-panel" data-pilotage-panel="summary">
        <section class="pilotage-primary-kpi-grid">
          <article class="card pilotage-primary-kpi-card" data-pilotage-help="annualizedRotation">
            <div class="stat-label">Rotation économique annualisée</div>
            <div class="pilotage-primary-value">
              ${formatPilotageMultiple(circulation.annualized_economic_activity_intensity_indicative)}
              <span>/ an</span>
            </div>
            <div class="stat-subtext">
              ${formatPilotageMultiple(circulation.economic_activity_intensity)}
              sur la période · activité économique / masse numérique moyenne
            </div>
          </article>

          <article class="card pilotage-primary-kpi-card" data-pilotage-help="netInflowRetention">
            <div class="stat-label">Rétention nette des alimentations</div>
            <div class="pilotage-primary-value">
              ${formatPilotagePercent(retentionYield.net_inflow_retention_rate)}
            </div>
            <div class="stat-subtext">
              Part nette des Gonettes alimentées qui restent dans le circuit sur la période
            </div>
          </article>

          <article class="card pilotage-primary-kpi-card" data-pilotage-help="economicActivityPerOutflow">
            <div class="stat-label">Activité générée pour 1 G sorti</div>
            <div class="pilotage-primary-value">
              ${formatPilotageGonetteYield(retentionYield.economic_activity_per_outflow)}
            </div>
            <div class="stat-subtext">
              Volume d’activité économique rapporté aux reconversions / sorties
            </div>
          </article>

          <article class="card pilotage-primary-kpi-card" data-pilotage-help="apparentReconversionCoverage">
            <div class="stat-label">Couverture apparente des reconversions</div>
            <div class="pilotage-primary-value">
              ${formatPilotageThirtyDayPeriods(coverage.apparent_reconversion_coverage_30_day_periods)}
            </div>
            <div class="stat-subtext">
              ${formatPilotageDays(coverage.apparent_reconversion_coverage_days)}
              au rythme moyen des sorties observées
            </div>
          </article>
        </section>

        ${buildPilotageSummaryReading({
          flow,
          reference,
          retentionYield,
          coverage
        })}

        <section class="card pilotage-context-card">
          <div class="pilotage-section-heading">
            <h3>Grandeurs de référence de la période</h3>
            <p>
              Ces valeurs servent de socle aux ratios de pilotage présentés dans les différents onglets.
            </p>
          </div>

          <div class="pilotage-context-grid">
            <article class="pilotage-context-item" data-pilotage-help="economicActivityVolume">
              <span>Activité économique</span>
              <strong>${gonettes(flow.economic_activity_volume || 0)}</strong>
              <small>${(flow.economic_activity_transaction_count || 0).toLocaleString("fr-FR")} transactions</small>
            </article>

            <article class="pilotage-context-item" data-pilotage-help="averageNumericMass">
              <span>Masse numérique moyenne</span>
              <strong>${gonettes(reference.average_numeric_mass || 0)}</strong>
              <small>${(reference.day_count || 0).toLocaleString("fr-FR")} jours couverts</small>
            </article>

            <article class="pilotage-context-item" data-pilotage-help="inflowVolume">
              <span>Alimentations</span>
              <strong>${gonettes(flow.inflow_volume || 0)}</strong>
              <small>${(flow.inflow_transaction_count || 0).toLocaleString("fr-FR")} opérations</small>
            </article>

            <article class="pilotage-context-item" data-pilotage-help="outflowVolume">
              <span>Sorties</span>
              <strong>${gonettes(flow.outflow_volume || 0)}</strong>
              <small>${(flow.outflow_transaction_count || 0).toLocaleString("fr-FR")} opérations</small>
            </article>

            <article class="pilotage-context-item" data-pilotage-help="averageNumericGuaranteeFund">
              <span>Fonds de garantie numérique moyen</span>
              <strong>${accountingEuros(reference.average_numeric_guarantee_fund || 0)}</strong>
              <small>moyenne quotidienne</small>
            </article>
          </div>
        </section>

        <aside class="pilotage-method-note">
          <strong>Point méthodologique.</strong>
          Ces KPI croisent les <strong>stocks quotidiens Odoo</strong>
          et les <strong>flux numériques Cyclos</strong> sur une même période effective.
          Les analyses de détention, de concentration et de masse active / dormante
          viendront enrichir cette lecture.
        </aside>
      </section>

      <section class="pilotage-tab-panel hidden" data-pilotage-panel="circulation">
        <section class="pilotage-circulation-sequence pilotage-circulation-sequence-core">
          <section class="pilotage-charts-stack">
            <article class="card stats-chart-card stats-chart-card-full pilotage-chart-card pilotage-circulation-lead-chart">
              ${buildStatsChartHeader({
                chartKey: "pilotageRotation",
                title: "Rotation économique annualisée",
                description: "Ce graphe mesure mois par mois l’intensité de circulation de la Gonette numérique : volume d’activité économique rapporté à la masse numérique moyenne, puis annualisé.",
                supportsMetricToggle: false
              })}

              <div class="pilotage-chart-frame">
                <canvas id="pilotageRotationChart"></canvas>
              </div>
            </article>

            ${pilotagePartialMonthNote}
          </section>

          <section class="card pilotage-section-card pilotage-circulation-quality-card">
            <div class="pilotage-section-heading">
              <div class="stat-label">Circulation effective</div>
              <h3>Qualité de circulation</h3>
              <p>
                Ces indicateurs complètent la rotation monétaire par une lecture de la densité d’usage
                et du volume d’activité généré par rapport aux entrées ou aux sorties.
              </p>
            </div>

            <div class="pilotage-metric-grid pilotage-quality-grid">
              <article class="pilotage-metric-card" data-pilotage-help="transactionsPer1000G">
                <span>Transactions économiques pour 1 000 G</span>
                <strong>${formatPilotageTxPer1000G(circulation.transaction_intensity_per_1000_g)}</strong>
                <small>Nombre de paiements économiques rapporté à la masse numérique moyenne</small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="economicActivityPerOutflow">
                <span>Activité générée pour 1 G sorti</span>
                <strong>${formatPilotageGonetteYield(retentionYield.economic_activity_per_outflow)}</strong>
                <small>Indicateur de rendement circulatoire avant sortie</small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="economicActivityPerInflow">
                <span>Activité générée pour 1 G alimenté</span>
                <strong>${formatPilotageGonetteYield(retentionYield.economic_activity_per_inflow)}</strong>
                <small>Rapport entre activité économique et volume d’entrées</small>
              </article>
            </div>
          </section>
        </section>

        <section class="pilotage-circulation-sequence pilotage-circulation-sequence-reuse">
          <section class="card pilotage-section-card pilotage-reuse-overview-card">
            <div class="pilotage-section-heading">
              <div class="stat-label">Réemploi interne &amp; effet multiplicateur</div>
              <h3>Capacité moyenne de recirculation économique du réseau</h3>
              <p>
                Ces indicateurs mesurent la part des recettes économiques qui est redépensée
                dans le réseau, puis en déduisent un <strong>multiplicateur interne estimé</strong>.
                Ils éclairent la qualité d’ancrage économique de la circulation Gonette,
                au-delà du seul volume d’activité.
              </p>
            </div>

            <div class="pilotage-metric-grid pilotage-reuse-grid">
              <article class="pilotage-metric-card pilotage-reuse-highlight-card" data-pilotage-help="internalMultiplierGlobal">
                <span>Multiplicateur interne estimé</span>
                <strong>${formatPilotageMultiple(internalReuseGlobal.internal_multiplier_estimated)}</strong>
                <small>Réseau global · dérivé de la propension pondérée de réemploi</small>
              </article>

              <article class="pilotage-metric-card pilotage-reuse-highlight-card" data-pilotage-help="internalReusePropensityGlobal">
                <span>Propension pondérée de réemploi</span>
                <strong>${formatPilotagePercent(internalReuseGlobal.weighted_internal_reuse_propensity)}</strong>
                <small>
                  ${gonettes(internalReuseGlobal.reused_capped_volume || 0)}
                  réemployés sur
                  ${gonettes(internalReuseGlobal.received_volume || 0)}
                  reçus
                </small>
              </article>

              <article class="pilotage-metric-card pilotage-reuse-professional-card" data-pilotage-help="internalReusePropensityProfessionals">
                <span>Réemploi interne professionnel</span>
                <strong>${formatPilotagePercent(internalReuseProfessionals.weighted_internal_reuse_propensity)}</strong>
                <small>Part pondérée des recettes pros réémises dans l’activité économique</small>
              </article>

              <article class="pilotage-metric-card pilotage-reuse-professional-card" data-pilotage-help="internalMultiplierProfessionals">
                <span>Multiplicateur professionnel estimé</span>
                <strong>${formatPilotageMultiple(internalReuseProfessionals.internal_multiplier_estimated)}</strong>
                <small>Capacité de recirculation associée au réemploi des professionnels</small>
              </article>
            </div>
          </section>

          <section class="pilotage-charts-stack">
            <article class="card stats-chart-card stats-chart-card-full pilotage-chart-card pilotage-reuse-history-card">
              ${buildStatsChartHeader({
                chartKey: "pilotageInternalReuseHistory",
                title: "Réemploi interne & multiplicateur estimé — trajectoire annuelle",
                description: "Cette série suit la capacité de recirculation économique du réseau depuis 2019 : propension pondérée de réemploi et multiplicateur interne estimé, pour le réseau global et les professionnels.",
                supportsMetricToggle: false
              })}

              <div class="pilotage-chart-frame pilotage-chart-frame-reuse-history">
                <canvas id="pilotageInternalReuseHistoryChart"></canvas>
              </div>
            </article>

            ${pilotageReuseYearlyFootnote}
          </section>
        </section>

        <section class="pilotage-circulation-sequence pilotage-circulation-sequence-lm3">
          <section class="card pilotage-section-card pilotage-lm3-overview-card">
            <div class="pilotage-section-heading">
              <div class="stat-label">Injection monétaire &amp; effet LM3</div>
              <h3>Propagation des Gonettes nouvellement injectées</h3>
              <p>
                Le <strong>LM3 estimé</strong> mesure les recettes cumulées générées
                par les Gonettes converties puis dépensées, en suivant trois vagues
                successives de circulation. Il complète le multiplicateur interne :
                l’un décrit la recirculation moyenne du réseau, l’autre la propagation
                spécifique des injections.
              </p>
            </div>

            <aside class="pilotage-lm3-period-note">
              <strong>Période active.</strong>
              Les KPI LM3 ci-dessous sont recalculés sur la
              <strong>période de pilotage active</strong>.
              Sur une fenêtre courte ou partielle, ils décrivent la propagation
              observée dans la période sélectionnée ; le graphe annuel offre
              le repère historique complémentaire.
            </aside>

            <div class="pilotage-metric-grid pilotage-lm3-grid">
              <article class="pilotage-metric-card pilotage-lm3-highlight-card" data-pilotage-help="lm3Estimated">
                <span>LM3 estimé sur la période</span>
                <strong>${formatPilotageMultiple(periodLm3.lm3_estimated)}</strong>
                <small>Recettes cumulées après trois vagues d’échanges</small>
              </article>

              <article class="pilotage-metric-card pilotage-lm3-wave-card" data-pilotage-help="lm3Wave2">
                <span>Gain de vague 2</span>
                <strong>+${formatPilotageMultiple(periodLm3.wave_2)}</strong>
                <small>Réemploi des premiers receveurs de l’injection</small>
              </article>

              <article class="pilotage-metric-card pilotage-lm3-wave-card" data-pilotage-help="lm3Wave3">
                <span>Gain de vague 3</span>
                <strong>+${formatPilotageMultiple(periodLm3.wave_3)}</strong>
                <small>Propagation supplémentaire au troisième niveau</small>
              </article>

              <article class="pilotage-metric-card pilotage-lm3-depth-card" data-pilotage-help="lm3P3Actors">
                <span>Acteurs atteints au 3ᵉ niveau</span>
                <strong>${Number(periodLm3.p3_actor_count || 0).toLocaleString("fr-FR")}</strong>
                <small>P3 · profondeur de diffusion de l’injection</small>
              </article>
            </div>
          </section>

          <details class="card pilotage-section-card pilotage-lm3-chains-details" data-lm3-chains-details>
            <summary class="pilotage-details-summary">
              <span class="pilotage-details-title">
                Chaînes de circulation observées jusqu’au 3ᵉ niveau
              </span>
              <span class="pilotage-details-cta">Afficher</span>
            </summary>

            <div class="pilotage-details-body pilotage-lm3-chains-body">
              <div class="pilotage-section-heading pilotage-details-intro">
                <p>
                  Ce tableau agrège des triplets <strong>P1 → P2 → P3</strong>
                  réellement compatibles avec la période sélectionnée :
                  P1 a été alimenté, puis a payé P2, puis P2 a payé P3 plus tard.
                </p>
              </div>

              <div data-lm3-chains-body>
                <div class="pilotage-lm3-chains-placeholder">
                  Ouvre cette section pour charger les chaînes observées.
                </div>
              </div>
            </div>
          </details>

          <section class="pilotage-charts-stack">
            <article class="card stats-chart-card stats-chart-card-full pilotage-chart-card pilotage-lm3-history-card">
              ${buildStatsChartHeader({
                chartKey: "pilotageLm3History",
                title: "LM3 estimé — profondeur de propagation des alimentations",
                description: "Ce graphe décompose le LM3 annuel en trois composantes : dépense initiale, gain de vague 2 et gain de vague 3. Il montre comment les Gonettes nouvellement injectées se propagent dans le réseau.",
                supportsMetricToggle: false
              })}

              <div class="pilotage-chart-frame pilotage-chart-frame-lm3-history">
                <canvas id="pilotageLm3HistoryChart"></canvas>
              </div>
            </article>

            ${pilotageLm3YearlyFootnote}
          </section>


        </section>
      </section>

      <section class="pilotage-tab-panel hidden" data-pilotage-panel="flows">
        <section class="pilotage-charts-stack">
          <article class="card stats-chart-card stats-chart-card-full pilotage-chart-card">
            ${buildStatsChartHeader({
              chartKey: "pilotageFlowRhythm",
              title: "Rythme des alimentations et des sorties",
              description: "Les entrées apparaissent au-dessus de zéro et les sorties en dessous. Les volumes sont ramenés en équivalent 30 jours afin de comparer les mois complets et les mois partiels.",
              supportsMetricToggle: false
            })}

            <div class="pilotage-chart-frame">
              <canvas id="pilotageFlowRhythmChart"></canvas>
            </div>
          </article>

          <article class="card stats-chart-card stats-chart-card-full pilotage-chart-card">
            ${buildStatsChartHeader({
              chartKey: "pilotageRetention",
              title: "Rétention nette des alimentations",
              description: "Chaque barre indique la part nette des Gonettes alimentées qui reste dans le circuit : positive lorsque les alimentations dépassent les sorties, négative lorsque les sorties excèdent les entrées.",
              supportsMetricToggle: false
            })}

            <div class="pilotage-chart-frame pilotage-chart-frame-compact">
              <canvas id="pilotageRetentionChart"></canvas>
            </div>
          </article>

          ${pilotagePartialMonthNote}
        </section>

        <section class="pilotage-dashboard-grid">
          <article class="card pilotage-section-card">
            <div class="pilotage-section-heading">
              <h3>Entrées, sorties et rétention</h3>
              <p>
                Cette lecture qualifie la capacité du circuit à conserver une partie des Gonettes nouvellement alimentées.
              </p>
            </div>

            <div class="pilotage-metric-grid">
              <article class="pilotage-metric-card" data-pilotage-help="outflowInflowRatio">
                <span>Sorties / alimentations</span>
                <strong>${formatPilotagePercent(entryExit.outflow_inflow_ratio)}</strong>
                <small>
                  ${gonettes(flow.outflow_volume || 0)}
                  sortis pour
                  ${gonettes(flow.inflow_volume || 0)}
                  alimentés
                </small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="inflowPressure">
                <span>Pression d’alimentation</span>
                <strong>${formatPilotageMultiple(entryExit.inflow_pressure)}</strong>
                <small>
                  ${formatPilotageMultiple(entryExit.annualized_inflow_pressure_indicative)}
                  / an, annualisé indicatif
                </small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="outflowPressure">
                <span>Pression de sortie</span>
                <strong>${formatPilotageMultiple(entryExit.outflow_pressure)}</strong>
                <small>
                  ${formatPilotageMultiple(entryExit.annualized_outflow_pressure_indicative)}
                  / an, annualisé indicatif
                </small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="netFlowPressure">
                <span>Flux net relatif à la masse moyenne</span>
                <strong>${formatPilotageSignedPercent(entryExit.net_flow_pressure)}</strong>
                <small>
                  Solde net :
                  ${formatPilotageSignedGonettes(flow.net_cyclos_flow || 0)}
                </small>
              </article>
            </div>
          </article>

          <article class="card pilotage-section-card">
            <div class="pilotage-section-heading">
              <h3>Garantie et robustesse</h3>
              <p>
                Ces indicateurs donnent une lecture prudente du rapport entre fonds de garantie, masse numérique et reconversions.
              </p>
            </div>

            <div class="pilotage-metric-grid pilotage-robustness-grid">
              <article class="pilotage-metric-card" data-pilotage-help="averageNumericGuaranteeCoverage">
                <span>Couverture moyenne du stock numérique</span>
                <strong>${formatPilotagePercent(guaranteeCoverage.average_numeric_guarantee_coverage_rate)}</strong>
                <small>
                  Fonds de garantie numérique moyen / masse numérique moyenne
                </small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="averageDailyOutflow">
                <span>Sorties quotidiennes moyennes</span>
                <strong>${gonettes(coverage.average_daily_outflow || 0)}</strong>
                <small>Reconversions / nombre de jours couverts</small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="apparentReconversionCoverage">
                <span>Couverture apparente détaillée</span>
                <strong>${formatPilotageDays(coverage.apparent_reconversion_coverage_days)}</strong>
                <small>
                  soit
                  ${formatPilotageThirtyDayPeriods(coverage.apparent_reconversion_coverage_30_day_periods)}
                  de sorties moyennes
                </small>
              </article>
            </div>
          </article>
        </section>

        <details class="card pilotage-section-card pilotage-reconciliation-section pilotage-details-card">
          <summary class="pilotage-details-summary">
            <span class="pilotage-details-title">
              Diagnostic avancé : rapprochement stock numérique ↔ flux Cyclos
            </span>
            <span class="pilotage-details-cta">Afficher</span>
          </summary>

          <div class="pilotage-details-body">
            <div class="pilotage-section-heading pilotage-details-intro">
              <p>
                Cette lecture compare l’évolution du stock numérique observée dans Odoo
                au solde net des alimentations et sorties identifiées dans Cyclos.
              </p>
            </div>

            ${buildPilotageResidualCaution(data)}

            <div class="pilotage-metric-grid pilotage-reconciliation-grid">
              <article class="pilotage-metric-card" data-pilotage-help="numericStockVariation">
                <span>Variation du stock numérique</span>
                <strong>${formatPilotageSignedGonettes(reconciliation.numeric_stock_variation)}</strong>
                <small>Évolution du stock Odoo sur la période</small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="netCyclosFlow">
                <span>Flux net Cyclos</span>
                <strong>${formatPilotageSignedGonettes(reconciliation.net_cyclos_flow)}</strong>
                <small>Alimentations − sorties observées</small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="stockFlowResidual">
                <span>Résiduel de rapprochement</span>
                <strong>${formatPilotageSignedGonettes(reconciliation.residual)}</strong>
                <small>Variation de stock − flux net Cyclos</small>
              </article>
            </div>
          </div>
        </details>
      </section>

      <section class="pilotage-tab-panel hidden" data-pilotage-panel="holdings">
        <section class="card pilotage-section-card pilotage-holdings-overview-card">
          <div class="pilotage-section-heading">
            <div class="stat-label">Détention &amp; ancrage</div>
            <h3>Où la Gonette numérique stationne-t-elle — et reste-t-elle disponible pour circuler ?</h3>
            <p>
              Une Gonette dépensée ne disparaît pas : elle change de main.
              Cet onglet suit où elle stationne — chez les <strong>particuliers</strong>,
              les <strong>professionnels du réseau</strong> ou les <strong>comptes entreprise Gonette</strong> —
              puis mesure ce qui reste <strong>mobilisable</strong>, <strong>dormant</strong> ou <strong>réactivé</strong>.
            </p>
          </div>

          ${holdingsPeriodNotice}

          <aside class="pilotage-holdings-monetary-reference-pill">
            <span>Repère comptable</span>
            <strong>${gonettes(holdingsReference.average_numeric_mass || 0)}</strong>
            <small>
              Masse numérique moyenne Odoo · référence des parts affichées ici
            </small>
          </aside>

          <div class="pilotage-holdings-story-step pilotage-holdings-story-step-opening">
            <span>1</span>
            <div>
              <h3>Où stationne la Gonette numérique ?</h3>
              <p>
                Ces trois familles de comptes donnent la première lecture de la détention numérique sur la période.
              </p>
            </div>
          </div>

          <div class="pilotage-metric-grid pilotage-holdings-category-grid">
            <article class="pilotage-metric-card pilotage-holdings-highlight-card pilotage-holdings-category-card pilotage-holdings-category-users" data-pilotage-help="holdingsAverageUserStock">
              <span>Stock particulier moyen</span>
              <strong>${gonettes(holdingsReference.average_positive_user_stock || 0)}</strong>
              <small>
                ${formatPilotagePercent(holdingsReference.average_user_stock_share_of_numeric_mass)}
                de la masse numérique moyenne
              </small>
            </article>

            <article class="pilotage-metric-card pilotage-holdings-highlight-card pilotage-holdings-category-card pilotage-holdings-category-professionals" data-pilotage-help="holdingsAverageProfessionalNetworkStock">
              <span>Stock professionnels du réseau moyen</span>
              <strong>${gonettes(holdingsReference.average_positive_professional_network_stock || 0)}</strong>
              <small>
                ${formatPilotagePercent(holdingsReference.average_professional_network_stock_share_of_numeric_mass)}
                de la masse numérique moyenne · hors P0000 / P9999
              </small>
            </article>

            <article class="pilotage-metric-card pilotage-holdings-highlight-card pilotage-holdings-category-card pilotage-holdings-category-gonette" data-pilotage-help="holdingsAverageGonetteBusinessAccountsStock">
              <span>Stock comptes entreprise Gonette</span>
              <strong>${gonettes(holdingsReference.average_positive_gonette_business_accounts_stock || 0)}</strong>
              <small>
                ${formatPilotagePercent(holdingsReference.average_gonette_business_accounts_stock_share_of_numeric_mass)}
                de la masse numérique moyenne · P0000 / P9999
              </small>
            </article>

          </div>

          <div class="pilotage-holdings-ownership-context">
              <span>À la clôture</span>
              <strong>${formatPilotageInteger(holdingsClosing.users_positive || 0)} particuliers à solde positif</strong>
              <small>${gonettes(holdingsClosing.positive_user_stock || 0)} détenues</small>
            </div>

            </section>

                  <section class="pilotage-charts-stack">
            <div class="pilotage-holdings-story-step">
              <span>2</span>
              <div>
                <h3>Comment cette détention se répartit-elle et évolue-t-elle ?</h3>
                <p>
                  La composition situe les grandes parts de masse ; les stocks moyens montrent ensuite
                  les volumes réellement détenus et leur déplacement dans le temps.
                </p>
              </div>
            </div>

<article class="card stats-chart-card stats-chart-card-full pilotage-chart-card">
            ${buildStatsChartHeader({
              chartKey: "pilotageHoldingsMassComposition",
              title: "Composition de la masse numérique par catégorie de détenteurs",
              description: "Les barres empilées montrent la part moyenne de la masse numérique portée par les particuliers, les professionnels du réseau, les comptes entreprise Gonette et le reste non encore ventilé.",
              supportsMetricToggle: false
            })}

            <div class="pilotage-chart-frame pilotage-chart-frame-compact">
              <canvas id="pilotageHoldingsMassCompositionChart"></canvas>
            </div>
          </article>

          

          <article class="card stats-chart-card stats-chart-card-full pilotage-chart-card">
            ${buildStatsChartHeader({
              chartKey: "pilotageHoldingsStockShare",
              title: "Stocks numériques moyens par catégorie de détenteurs",
              description: "Ce graphe compare, mois par mois, le stock positif moyen détenu par les particuliers, celui des professionnels du réseau et celui des comptes entreprise Gonette.",
              supportsMetricToggle: false
            })}

            <div class="pilotage-chart-frame">
              <canvas id="pilotageHoldingsStockShareChart"></canvas>
            </div>
          </article>

          

            <div class="pilotage-holdings-story-step">
              <span>3</span>
              <div>
                <h3>Quelle part du stock particulier reste proche de l’activité ?</h3>
                <p>
                  Une monnaie détenue n’est pas nécessairement immobilisée. Cette lecture distingue
                  ce qui reste lié à une activité récente de ce qui s’éloigne progressivement de l’usage.
                </p>
              </div>
            </div>

<article class="card stats-chart-card stats-chart-card-full pilotage-chart-card">
            ${buildStatsChartHeader({
              chartKey: "pilotageHoldingsDormancy",
              title: "Masse particulière active / dormante",
              description: "Les barres empilées répartissent le stock positif particulier à la clôture de chaque mois selon la date de dernière activité du compte.",
              supportsMetricToggle: false
            })}

            <div class="pilotage-chart-frame">
              <canvas id="pilotageHoldingsDormancyChart"></canvas>
            </div>
          </article>

            <article class="card pilotage-section-card pilotage-holdings-dormancy-card">
            <div class="pilotage-section-heading">
              <h3>Masse active / dormante à la clôture</h3>
              <p>
                La dormance est mesurée par l’absence de toute transaction impliquant le compte particulier.
                Elle ne signifie pas automatiquement qu’un solde est « perdu », mais qu’il s’éloigne de l’activité récente.
              </p>
            </div>

            <div class="pilotage-metric-grid pilotage-holdings-dormancy-grid">
              <article class="pilotage-metric-card" data-pilotage-help="holdingsActive30Stock">
                <span>Actif ≤ 30 j</span>
                <strong>${gonettes(holdingsActive30Bucket.positive_user_stock || 0)}</strong>
                <small>
                  ${formatPilotageInteger(holdingsActive30Bucket.user_count || 0)} comptes ·
                  ${formatPilotagePercent(holdingsActive30Bucket.stock_share_of_positive_user_stock)}
                </small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="holdingsDormant31To90Stock">
                <span>Dormant 31–90 j</span>
                <strong>${gonettes(holdingsDormant31To90Bucket.positive_user_stock || 0)}</strong>
                <small>
                  ${formatPilotageInteger(holdingsDormant31To90Bucket.user_count || 0)} comptes ·
                  ${formatPilotagePercent(holdingsDormant31To90Bucket.stock_share_of_positive_user_stock)}
                </small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="holdingsDormantGt90Stock">
                <span>Dormant > 90 j</span>
                <strong>${gonettes(holdingsDormantGt90Stock || 0)}</strong>
                <small>
                  ${formatPilotageInteger(
                    Number(holdingsDormant91To180Bucket.user_count || 0) +
                    Number(holdingsDormantGt180Bucket.user_count || 0)
                  )} comptes ·
                  ${formatPilotagePercent(holdingsDormantGt90Share)}
                </small>
              </article>
            </div>
          </article>


          

            <div class="pilotage-holdings-story-step">
              <span>4</span>
              <div>
                <h3>Cette détention revient-elle vers l’économie locale ?</h3>
                <p>
                  La mobilisation rapporte les paiements U→P au stock particulier moyen :
                  elle relie la monnaie détenue à sa capacité à revenir vers les professionnels.
                </p>
              </div>
            </div>

<article class="card stats-chart-card stats-chart-card-full pilotage-chart-card">
            ${buildStatsChartHeader({
              chartKey: "pilotageHoldingsMobilization",
              title: "Intensité de mobilisation du stock particulier",
              description: "Chaque point indique le volume mensuel U→P observé pour 100 G de stock particulier moyen. L’unité est exprimée en G / 100 G détenues, pas en pourcentage.",
              supportsMetricToggle: false
            })}

            <div class="pilotage-chart-frame pilotage-chart-frame-compact">
              <canvas id="pilotageHoldingsMobilizationChart"></canvas>
            </div>
          </article>

            <article class="card pilotage-section-card pilotage-holdings-reactivation-card">
            <div class="pilotage-section-heading">
              <h3>Réactivation des stocks dormants</h3>
              <p>
                Un compte réactivé détenait un solde positif et était dormant depuis plus de 90 jours
                à l’ouverture de la période, puis a enregistré au moins une transaction.
              </p>
            </div>

            <div class="pilotage-metric-grid pilotage-holdings-reactivation-grid">
              <article class="pilotage-metric-card" data-pilotage-help="holdingsReactivatedUserCount">
                <span>Comptes réactivés</span>
                <strong>${formatPilotageInteger(holdingsReactivation.reactivated_user_count || 0)}</strong>
                <small>
                  ${formatPilotagePercent(holdingsReactivation.reactivated_user_share_of_dormant_gt_90_opening_users)}
                  des comptes dormants &gt; 90 j identifiés à l’ouverture
                </small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="holdingsReactivatedOpeningStock">
                <span>Stock dormant porté par ces comptes</span>
                <strong>${gonettes(holdingsReactivation.reactivated_opening_stock || 0)}</strong>
                <small>
                  ${formatPilotagePercent(holdingsReactivation.reactivated_stock_share_of_dormant_gt_90_opening_stock)}
                  du stock dormant &gt; 90 j d’ouverture
                </small>
              </article>

              <article class="pilotage-metric-card" data-pilotage-help="holdingsReactivatedEconomicUpVolume">
                <span>Paiements U→P issus des comptes réactivés</span>
                <strong>${gonettes(holdingsReactivation.economic_up_volume_from_reactivated_users || 0)}</strong>
                <small>
                  ${formatPilotageInteger(holdingsReactivation.economic_up_transaction_count_from_reactivated_users || 0)}
                  transaction(s) économiques vers les pros
                </small>
              </article>
            </div>
          </article>


          

            ${holdingsPartialMonthNote}
          </section>      </section>
    `;

    bindPilotageIndicatorHelpButtons();
    bindPilotageTabs();
    bindPilotageLm3ChainsDetails();
    renderMonetaryPilotageCharts(
      pilotageSeriesForCharts,
      data,
      pilotageReuseYearlySeries,
      pilotageLm3YearlySeries,
      holdingsSeriesForCharts,
      holdingsSummary
    );
  } catch (error) {
    console.error("Erreur lors du chargement du pilotage monétaire :", error);

    if (preserveVisibleView) {
      destroyMonetaryPilotageCharts();
    }

    content.innerHTML = `
      <section class="card pilotage-empty-card">
        <h2>Pilotage monétaire</h2>
        <p>Le chargement des indicateurs de pilotage a échoué.</p>
      </section>
    `;
  }
}



function formatProfessionalSummaryInteger(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("fr-FR", {
    maximumFractionDigits: 0
  });
}

function formatProfessionalSummaryRatio(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${(Number(value) * 100).toLocaleString("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })} %`;
}

function formatProfessionalSummaryMultiple(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${Number(value).toLocaleString("fr-FR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })}×`;
}

function renderProfessionalSummaryKpiCard(label, value, subtext) {
  return `
    <article class="professional-summary-kpi-card">
      <div class="stat-label">${escapeHtml(label)}</div>
      <div class="professional-summary-kpi-value">${value}</div>
      <p>${escapeHtml(subtext)}</p>
    </article>
  `;
}

function renderProfessionalSummaryReferenceCard(label, value, subtext) {
  return `
    <article class="professional-summary-reference-card">
      <div class="stat-label">${escapeHtml(label)}</div>
      <strong>${value}</strong>
      <span>${escapeHtml(subtext)}</span>
    </article>
  `;
}

function renderProfessionalSummaryPanel(flowSummary, holdingsSummary, pilotageSummary) {
  const flowPayload = flowSummary || {};
  const counts = flowPayload.professional_counts || {};
  const flows = flowPayload.flows || {};
  const aggregates = flowPayload.aggregates || {};

  const up = flows.up || {};
  const pp = flows.pp || {};
  const pu = flows.pu || {};

  const professionalReuse = (
    pilotageSummary?.pilotage_metrics?.internal_reuse?.professionals
    || {}
  );

  const professionalReusePropensity = (
    professionalReuse.weighted_internal_reuse_propensity
  );

  const professionalMultiplierEstimated = (
    professionalReuse.internal_multiplier_estimated
  );

  const professionalReuseAvailable = (
    professionalReusePropensity !== null
    && professionalReusePropensity !== undefined
    && !Number.isNaN(Number(professionalReusePropensity))
  );

  const professionalMultiplierAvailable = (
    professionalMultiplierEstimated !== null
    && professionalMultiplierEstimated !== undefined
    && !Number.isNaN(Number(professionalMultiplierEstimated))
  );

  const holdingsEffectivePeriod = holdingsSummary?.effective_period || null;
  const holdingsReference = holdingsSummary?.holdings_reference || {};
  const holdingsAvailable = Boolean(
    holdingsEffectivePeriod
    && holdingsReference
    && holdingsReference.average_positive_professional_network_stock !== undefined
  );

  const averageProfessionalNetworkStock = holdingsAvailable
    ? holdingsReference.average_positive_professional_network_stock
    : null;

  const averageProfessionalNetworkStockShare = holdingsAvailable
    ? holdingsReference.average_professional_network_stock_share_of_numeric_mass
    : null;

  const userHoldingsAvailable = Boolean(
    holdingsEffectivePeriod
    && holdingsReference
    && holdingsReference.average_positive_user_stock !== undefined
  );

  const averageUserStock = userHoldingsAvailable
    ? holdingsReference.average_positive_user_stock
    : null;

  const averageUserStockShare = userHoldingsAvailable
    ? holdingsReference.average_user_stock_share_of_numeric_mass
    : null;

  const averageNumericMass = holdingsAvailable
    ? holdingsReference.average_numeric_mass
    : null;

  const stockReading = userHoldingsAvailable && holdingsAvailable
    ? `
      Sur les jours monétaires effectivement couverts, les
      <strong>particuliers</strong> détenaient en moyenne
      <strong>${euro(averageUserStock || 0)}</strong>,
      soit <strong>${formatProfessionalSummaryRatio(averageUserStockShare)}</strong>
      de la masse numérique moyenne. Les
      <strong>professionnels du réseau</strong> détenaient de leur côté
      <strong>${euro(averageProfessionalNetworkStock || 0)}</strong>,
      soit <strong>${formatProfessionalSummaryRatio(averageProfessionalNetworkStockShare)}</strong>.
    `
    : holdingsAvailable
      ? `
        Sur les jours monétaires effectivement couverts, les
        <strong>professionnels du réseau</strong> détenaient en moyenne
        <strong>${euro(averageProfessionalNetworkStock || 0)}</strong>,
        soit <strong>${formatProfessionalSummaryRatio(averageProfessionalNetworkStockShare)}</strong>
        de la masse numérique moyenne. Le stock particulier moyen n’est pas disponible
        sur cette période.
      `
      : userHoldingsAvailable
        ? `
          Sur les jours monétaires effectivement couverts, les
          <strong>particuliers</strong> détenaient en moyenne
          <strong>${euro(averageUserStock || 0)}</strong>,
          soit <strong>${formatProfessionalSummaryRatio(averageUserStockShare)}</strong>
          de la masse numérique moyenne. Le stock professionnel moyen n’est pas disponible
          sur cette période.
        `
        : `
          Les indicateurs de stock particulier et professionnel ne sont pas disponibles
          sur cette période. Les flux économiques restent, eux, pleinement lisibles
          sur l’historique transactionnel.
        `;

  return `
    <section class="professional-summary-shell">
      <div class="professional-summary-kpi-grid professional-summary-kpi-grid-balanced">
        ${renderProfessionalSummaryKpiCard(
          "Paiements particuliers → professionnels",
          euro(up.volume || 0),
          `${formatProfessionalSummaryInteger(up.count || 0)} paiement(s) U→P observé(s).`
        )}

        ${renderProfessionalSummaryKpiCard(
          "Part des recettes pros venant des particuliers",
          formatProfessionalSummaryRatio(aggregates.received_from_users_share),
          "Poids des paiements U→P dans les recettes professionnelles observées."
        )}

        ${renderProfessionalSummaryKpiCard(
          "Stock particulier moyen",
          userHoldingsAvailable ? euro(averageUserStock || 0) : "—",
          userHoldingsAvailable
            ? `${formatProfessionalSummaryRatio(averageUserStockShare)} de la masse numérique moyenne.`
            : "Disponible uniquement sur les périodes couvertes par les snapshots monétaires."
        )}

        ${renderProfessionalSummaryKpiCard(
          "Professionnels actifs",
          formatProfessionalSummaryInteger(counts.active || 0),
          "Professionnels impliqués dans l’activité économique centrale observée."
        )}

        ${renderProfessionalSummaryKpiCard(
          "Gonettes reçues par les pros",
          euro(aggregates.received_volume || 0),
          "Recettes reçues depuis les particuliers et les autres professionnels."
        )}

        ${renderProfessionalSummaryKpiCard(
          "Stock pros du réseau moyen",
          holdingsAvailable ? euro(averageProfessionalNetworkStock || 0) : "—",
          holdingsAvailable
            ? `${formatProfessionalSummaryRatio(averageProfessionalNetworkStockShare)} de la masse numérique moyenne.`
            : "Disponible uniquement sur les périodes couvertes par les snapshots monétaires."
        )}
      </div>

      <section class="card professional-summary-reading-card">
        <div class="professional-analysis-section-heading">
          <div class="stat-label">Lecture rapide de la période</div>
          <h3>Ce que la rencontre entre particuliers et professionnels révèle ici</h3>
        </div>

        <p>
          Sur la période, les particuliers ont réalisé
          <strong>${formatProfessionalSummaryInteger(up.count || 0)}</strong>
          paiement(s) vers les professionnels pour un volume de
          <strong>${euro(up.volume || 0)}</strong>.
          Ces flux <strong>U→P</strong> représentent
          <strong>${formatProfessionalSummaryRatio(aggregates.received_from_users_share)}</strong>
          des recettes professionnelles observées.
        </p>

        <p>
          Du côté du réseau professionnel,
          <strong>${formatProfessionalSummaryInteger(counts.active || 0)}</strong>
          professionnels ont participé à l’activité économique numérique retenue par MLCFlux.
          Ils ont reçu <strong>${euro(aggregates.received_volume || 0)}</strong>,
          puis réémis <strong>${euro(aggregates.emitted_volume || 0)}</strong>
          vers le réseau, soit une <strong>remise en circulation observée</strong> de
          <strong>${formatProfessionalSummaryRatio(aggregates.observed_reemission_rate)}</strong>.
          <strong>${formatProfessionalSummaryInteger(counts.involved_in_b2b || 0)}</strong>
          professionnels ont été impliqués dans au moins un flux interprofessionnel.
        </p>

        <p>${stockReading}</p>
      </section>

      <section class="card professional-summary-reuse-card">
        <div class="professional-analysis-section-heading">
          <div class="stat-label">Qualité de circulation professionnelle</div>
          <h3>Réémettre ne suffit pas : les recettes sont-elles réellement réemployées&nbsp;?</h3>
          <p>
            La remise en circulation observée rapporte les flux sortants des professionnels
            aux recettes reçues sur la période. Le réemploi interne professionnel adopte
            une lecture plus exigeante : il mesure la part pondérée des recettes professionnelles
            effectivement redépensée dans l’activité économique du réseau.
          </p>
        </div>

        <div class="professional-summary-reuse-grid">
          ${renderProfessionalSummaryKpiCard(
            "Remise en circulation observée",
            formatProfessionalSummaryRatio(aggregates.observed_reemission_rate),
            "Volumes économiquement réémis par les pros rapportés à leurs recettes économiques de la période."
          )}

          ${renderProfessionalSummaryKpiCard(
            "Réemploi interne professionnel",
            professionalReuseAvailable
              ? formatProfessionalSummaryRatio(professionalReusePropensity)
              : "—",
            professionalReuseAvailable
              ? "Part pondérée des recettes pros effectivement redépensée dans le réseau."
              : "Indicateur indisponible pour cette période."
          )}

          ${renderProfessionalSummaryKpiCard(
            "Multiplicateur professionnel estimé",
            professionalMultiplierAvailable
              ? formatProfessionalSummaryMultiple(professionalMultiplierEstimated)
              : "—",
            professionalMultiplierAvailable
              ? "Capacité de recirculation associée au réemploi interne des professionnels."
              : "Indicateur indisponible pour cette période."
          )}
        </div>

        <div class="professional-summary-reuse-note">
          <strong>Comment lire l’écart&nbsp;?</strong>
          La <strong>remise en circulation observée</strong> peut intégrer des dépenses
          financées par un stock accumulé avant la période. Le
          <strong>réemploi interne professionnel</strong> cherche plutôt à estimer,
          sur les recettes professionnelles effectivement observées,
          la fraction qui revient dans l’économie Gonette.
        </div>
      </section>

      <section class="card professional-summary-reference-block">
        <div class="professional-analysis-section-heading">
          <div class="stat-label">Grandeurs de référence</div>
          <h3>Recevoir, réémettre, détenir</h3>
          <p>
            Ces repères donnent une première lecture de l’usage professionnel :
            qui paie les pros, vers qui ils redépensent, et quelle masse numérique
            reste portée par le tissu professionnel lorsqu’elle est mesurable.
          </p>
        </div>

        <div class="professional-summary-reference-grid">
          ${renderProfessionalSummaryReferenceCard(
            "Particuliers → professionnels",
            euro(up.volume || 0),
            `${formatProfessionalSummaryInteger(up.count || 0)} paiement(s) U→P observé(s).`
          )}

          ${renderProfessionalSummaryReferenceCard(
            "Professionnels → professionnels",
            euro(pp.volume || 0),
            `${formatProfessionalSummaryInteger(pp.count || 0)} paiement(s) P→P observé(s).`
          )}

          ${renderProfessionalSummaryReferenceCard(
            "Professionnels → particuliers",
            euro(pu.volume || 0),
            `${formatProfessionalSummaryInteger(pu.count || 0)} flux P→U observé(s).`
          )}

          ${renderProfessionalSummaryReferenceCard(
            "Professionnels receveurs",
            formatProfessionalSummaryInteger(counts.receiving || 0),
            "Professionnels ayant reçu au moins un flux économique."
          )}

          ${renderProfessionalSummaryReferenceCard(
            "Professionnels émetteurs",
            formatProfessionalSummaryInteger(counts.emitting || 0),
            "Professionnels ayant réémis vers le réseau."
          )}

          ${renderProfessionalSummaryReferenceCard(
            "Masse numérique moyenne",
            holdingsAvailable ? euro(averageNumericMass || 0) : "—",
            holdingsAvailable
              ? "Repère comptable Odoo aligné avec les stocks professionnels."
              : "Non disponible sur cette période."
          )}
        </div>
      </section>

      <section class="professional-summary-method-note">
        <strong>Point méthodologique.</strong>
        Les flux présentés ici reposent sur l’<strong>activité économique centrale MLCFlux</strong> :
        les comptes techniques <strong>T_*</strong> en sont exclus, les particuliers de dispositif
        <strong>UD_*</strong> sont intégrés à la famille des particuliers, et les comptes opérateurs
        <strong>P0000 / P9999</strong> ne sont pas assimilés aux professionnels du réseau.
        Côté stock, la catégorie <strong>professionnels du réseau</strong> reprend exactement
        la définition du Pilotage monétaire : soldes professionnels positifs hors
        <strong>comptes entreprise Gonette P0000 / P9999</strong>.
      </section>
    </section>
  `;
}


function formatProfessionalCirculationMonthLabel(item) {
  const monthKey = String(item?.month_key || "").trim();
  const match = /^(\d{4})-(\d{2})$/.exec(monthKey);

  if (!match) {
    return monthKey || "—";
  }

  const year = match[1];
  const monthIndex = Number(match[2]) - 1;
  const monthLabels = [
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc."
  ];

  return `${monthLabels[monthIndex] || match[2]} ${year}`;
}


function isProfessionalReusePartialYear(item) {
  const year = Number(item?.year || 0);
  const start = String(item?.period_start || "");
  const end = String(item?.period_end || "");

  if (!year || !start || !end) {
    return false;
  }

  return (
    start !== `${year}-01-01`
    || end !== `${year}-12-31`
  );
}

function formatProfessionalReuseYearLabel(item) {
  if (!item?.year) {
    return "—";
  }

  return isProfessionalReusePartialYear(item)
    ? `${item.year}*`
    : String(item.year);
}


function buildProfessionalOutflowsComparisonChartConfig(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const labels = items.map((item) => formatProfessionalCirculationMonthLabel(item));

  return {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Volumes réémis économiquement",
          data: items.map((item) => Number(item?.aggregates?.emitted_volume || 0)),
          tension: 0.28,
          pointRadius: 2,
          borderWidth: 2
        },
        {
          label: "Sorties professionnelles du circuit",
          data: items.map((item) => Number(item?.flows?.pt_outflows?.volume || 0)),
          tension: 0.28,
          pointRadius: 2,
          borderWidth: 2,
          borderDash: [7, 5]
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          position: "bottom"
        },
        tooltip: {
          callbacks: {
            label(context) {
              const value = Number(context.parsed?.y ?? context.raw ?? 0);
              return `${context.dataset.label}: ${euro(value)}`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback(value) {
              return Number(value || 0).toLocaleString("fr-FR", {
                maximumFractionDigits: 0
              });
            }
          }
        }
      }
    }
  };
}

function getProfessionalChainFatePrimaryModel(chainFateSummary) {
  const payload = chainFateSummary || {};
  const primaryModelKey = payload.primary_model || "u_to_p_seeds_only";

  return payload?.models?.[primaryModelKey] || null;
}

function getProfessionalChainFateExtendedModel(chainFateSummary) {
  return chainFateSummary?.models?.u_to_p_plus_t_to_p_seeds || null;
}

function formatProfessionalChainFateDays(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${Number(value).toLocaleString("fr-FR", {
    maximumFractionDigits: 0
  })} j`;
}

function buildProfessionalChainFateDelayChartConfig(chainFateSummary) {
  const model = getProfessionalChainFatePrimaryModel(chainFateSummary);
  const buckets = model?.tracked_exit_to_t?.summary?.volume_by_delay_bucket || {};

  const bucketSpecs = [
    { key: "same_day", label: "Même jour" },
    { key: "d1_7", label: "1–7 j" },
    { key: "d8_30", label: "8–30 j" },
    { key: "d31_90", label: "31–90 j" },
    { key: "gt90", label: "> 90 j" }
  ];

  const values = bucketSpecs.map((item) => Number(buckets?.[item.key]?.volume || 0));

  if (!values.some((value) => value > 0)) {
    return null;
  }

  return {
    type: "bar",
    data: {
      labels: bucketSpecs.map((item) => item.label),
      datasets: [
        {
          label: "Volume sorti vers compte technique",
          data: values,
          borderWidth: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          position: "bottom"
        },
        tooltip: {
          callbacks: {
            label(context) {
              const value = Number(context.parsed?.y ?? context.raw ?? 0);
              const spec = bucketSpecs[context.dataIndex];
              const bucket = buckets?.[spec?.key] || {};
              const fragments = formatProfessionalSummaryInteger(bucket.fragment_count || 0);

              return `${context.dataset.label}: ${euro(value)} · ${fragments} fragment(s)`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback(value) {
              return Number(value || 0).toLocaleString("fr-FR", {
                maximumFractionDigits: 0
              });
            }
          }
        }
      }
    }
  };
}

function buildProfessionalChainFateDepthChartConfig(chainFateSummary) {
  const model = getProfessionalChainFatePrimaryModel(chainFateSummary);
  const buckets = model?.tracked_exit_to_t?.summary?.volume_by_depth_bucket || {};

  const bucketSpecs = [
    { key: "0", label: "0" },
    { key: "1", label: "1" },
    { key: "2", label: "2" },
    { key: "3", label: "3" },
    { key: "4", label: "4" },
    { key: "5_plus", label: "5+" }
  ];

  const values = bucketSpecs.map((item) => Number(buckets?.[item.key]?.volume || 0));

  if (!values.some((value) => value > 0)) {
    return null;
  }

  return {
    type: "bar",
    data: {
      labels: bucketSpecs.map((item) => item.label),
      datasets: [
        {
          label: "Volume sorti selon le nombre de passages P→P",
          data: values,
          borderWidth: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          position: "bottom"
        },
        tooltip: {
          callbacks: {
            label(context) {
              const value = Number(context.parsed?.y ?? context.raw ?? 0);
              const spec = bucketSpecs[context.dataIndex];
              const bucket = buckets?.[spec?.key] || {};
              const fragments = formatProfessionalSummaryInteger(bucket.fragment_count || 0);

              return `${context.dataset.label}: ${euro(value)} · ${fragments} fragment(s)`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback(value) {
              return Number(value || 0).toLocaleString("fr-FR", {
                maximumFractionDigits: 0
              });
            }
          }
        }
      }
    }
  };
}

function buildProfessionalReuseHistoryChartConfig(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const labels = items.map((item) => formatProfessionalReuseYearLabel(item));

  return {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Réemploi interne professionnel",
          data: items.map((item) => (
            item?.professionals?.weighted_internal_reuse_propensity ?? null
          )),
          yAxisID: "yReuse",
          tension: 0.28,
          pointRadius: 3,
          borderWidth: 2
        },
        {
          label: "Multiplicateur professionnel estimé",
          data: items.map((item) => (
            item?.professionals?.internal_multiplier_estimated ?? null
          )),
          yAxisID: "yMultiplier",
          tension: 0.28,
          pointRadius: 3,
          borderWidth: 2,
          borderDash: [7, 5]
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          position: "bottom"
        },
        tooltip: {
          callbacks: {
            label(context) {
              const value = context.parsed?.y ?? context.raw;

              if (context.dataset.yAxisID === "yReuse") {
                return `${context.dataset.label}: ${formatProfessionalSummaryRatio(value)}`;
              }

              return `${context.dataset.label}: ${formatProfessionalSummaryMultiple(value)}`;
            }
          }
        }
      },
      scales: {
        yReuse: {
          type: "linear",
          position: "left",
          beginAtZero: true,
          ticks: {
            callback(value) {
              return `${(Number(value || 0) * 100).toLocaleString("fr-FR", {
                maximumFractionDigits: 0
              })} %`;
            }
          }
        },
        yMultiplier: {
          type: "linear",
          position: "right",
          beginAtZero: false,
          grid: {
            drawOnChartArea: false
          },
          ticks: {
            callback(value) {
              return `${Number(value || 0).toLocaleString("fr-FR", {
                minimumFractionDigits: 1,
                maximumFractionDigits: 2
              })}×`;
            }
          }
        }
      }
    }
  };
}

function buildProfessionalReuseHistoryFootnote(items) {
  const partialYears = (items || []).filter(isProfessionalReusePartialYear);

  if (!partialYears.length) {
    return "";
  }

  return `
    <p class="professional-circulation-footnote">
      <strong>* Année partielle.</strong>
      La première année disponible et l’année en cours ne couvrent pas nécessairement
      douze mois complets. Leur comparaison avec les années pleines doit rester prudente.
    </p>
  `;
}

function buildProfessionalCirculationFlowsChartConfig(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const labels = items.map((item) => formatProfessionalCirculationMonthLabel(item));

  return {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Particuliers → professionnels",
          data: items.map((item) => Number(item?.flows?.up?.volume || 0)),
          tension: 0.28,
          pointRadius: 2,
          borderWidth: 2
        },
        {
          label: "Professionnels → professionnels",
          data: items.map((item) => Number(item?.flows?.pp?.volume || 0)),
          tension: 0.28,
          pointRadius: 2,
          borderWidth: 2
        },
        {
          label: "Professionnels → particuliers",
          data: items.map((item) => Number(item?.flows?.pu?.volume || 0)),
          tension: 0.28,
          pointRadius: 2,
          borderWidth: 2
        },
        {
          label: "Professionnels → compte technique",
          data: items.map((item) => Number(item?.flows?.pt_outflows?.volume || 0)),
          tension: 0.28,
          pointRadius: 2,
          borderWidth: 2,
          borderDash: [7, 5]
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          position: "bottom"
        },
        tooltip: {
          callbacks: {
            label(context) {
              const value = Number(context.parsed?.y ?? context.raw ?? 0);
              return `${context.dataset.label}: ${euro(value)}`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback(value) {
              return Number(value || 0).toLocaleString("fr-FR", {
                maximumFractionDigits: 0
              });
            }
          }
        }
      }
    }
  };
}

function destroyProfessionalCirculationCharts() {
  const chartKeys = [
    "professionalCirculationFlows",
    "professionalOutflowsComparison",
    "professionalChainFateDelay",
    "professionalChainFateDepth",
    "professionalReuseHistory"
  ];

  chartKeys.forEach((chartKey) => {
    const chart = appState.charts?.[chartKey];

    if (chart && typeof chart.destroy === "function") {
      chart.destroy();
    }

    if (appState.charts) {
      delete appState.charts[chartKey];
    }
  });
}

function renderProfessionalCirculationCharts() {
  const flowItems = appState.professionalCirculationTimeseries?.items || [];
  const flowCanvas = document.getElementById("professionalCirculationFlowsChart");
  const flowConfig = buildProfessionalCirculationFlowsChartConfig(flowItems);
  const flowExisting = appState.charts?.professionalCirculationFlows;

  if (flowExisting && typeof flowExisting.resize === "function") {
    flowExisting.resize();
  } else if (flowCanvas && flowConfig) {
    appState.charts.professionalCirculationFlows = new Chart(flowCanvas, flowConfig);
  }

  const outflowItems = appState.professionalCirculationTimeseries?.items || [];
  const outflowCanvas = document.getElementById("professionalOutflowsComparisonChart");
  const outflowConfig = buildProfessionalOutflowsComparisonChartConfig(outflowItems);
  const outflowExisting = appState.charts?.professionalOutflowsComparison;

  if (outflowExisting && typeof outflowExisting.resize === "function") {
    outflowExisting.resize();
  } else if (outflowCanvas && outflowConfig) {
    appState.charts.professionalOutflowsComparison = new Chart(outflowCanvas, outflowConfig);
  }

  const chainFateSummary = appState.professionalChainFateSummary || null;

  const chainDelayCanvas = document.getElementById("professionalChainFateDelayChart");
  const chainDelayConfig = buildProfessionalChainFateDelayChartConfig(chainFateSummary);
  const chainDelayExisting = appState.charts?.professionalChainFateDelay;

  if (chainDelayExisting && typeof chainDelayExisting.resize === "function") {
    chainDelayExisting.resize();
  } else if (chainDelayCanvas && chainDelayConfig) {
    appState.charts.professionalChainFateDelay = new Chart(chainDelayCanvas, chainDelayConfig);
  }

  const chainDepthCanvas = document.getElementById("professionalChainFateDepthChart");
  const chainDepthConfig = buildProfessionalChainFateDepthChartConfig(chainFateSummary);
  const chainDepthExisting = appState.charts?.professionalChainFateDepth;

  if (chainDepthExisting && typeof chainDepthExisting.resize === "function") {
    chainDepthExisting.resize();
  } else if (chainDepthCanvas && chainDepthConfig) {
    appState.charts.professionalChainFateDepth = new Chart(chainDepthCanvas, chainDepthConfig);
  }

  const reuseItems = appState.professionalReuseYearlySummary?.items || [];
  const reuseCanvas = document.getElementById("professionalReuseHistoryChart");
  const reuseConfig = buildProfessionalReuseHistoryChartConfig(reuseItems);
  const reuseExisting = appState.charts?.professionalReuseHistory;

  if (reuseExisting && typeof reuseExisting.resize === "function") {
    reuseExisting.resize();
  } else if (reuseCanvas && reuseConfig) {
    appState.charts.professionalReuseHistory = new Chart(reuseCanvas, reuseConfig);
  }

 }

function renderProfessionalConsumptionMapCard(consumptionMapSummary = null) {
  const consumptionMapPayload = getProfessionalConsumptionMapPayload(
    consumptionMapSummary
  );
  const consumptionMapCoverage = consumptionMapPayload?.coverage || {};
  const consumptionMapGeometry = consumptionMapPayload?.geometry || {};
  const consumptionMapSources = consumptionMapPayload?.sources || [];
  const consumptionMapDestinations = consumptionMapPayload?.destinations || [];
  const consumptionMapRoutes = consumptionMapPayload?.routes || [];
  const consumptionMapTimeline = consumptionMapPayload?.timeline || {};
  const consumptionMapTimelineSteps = consumptionMapTimeline?.steps || [];
  const consumptionMapTimelineLastIndex = Math.max(
    0,
    consumptionMapTimelineSteps.length - 1
  );
  const consumptionMapTimelineLastLabel =
    consumptionMapTimelineSteps[consumptionMapTimelineLastIndex]?.label
    || "Fin de période";

  const consumptionMapViewMode = getProfessionalConsumptionMapViewMode();

  const hasConsumptionMap = Array.isArray(consumptionMapRoutes)
    && consumptionMapRoutes.length > 0;

  return `
      <section class="card professional-consumption-map-card">
        <div class="professional-analysis-section-heading professional-consumption-map-heading">
          <div class="professional-consumption-map-heading-main">
            <div class="stat-label">Répartition territoriale des flux U→P</div>
            <h3>Comment les paiements des particuliers se distribuent vers les professionnels</h3>
            <p>
              Cette vue expérimentale représente les paiements <strong>U→P</strong>
              cartographiables, en agrégeant les particuliers par bassin postal.
              Les points de départ sont <strong>synthétiques</strong> :
              ils sont répartis de façon stable à l’intérieur des périmètres postaux,
              sans jamais indiquer une adresse réelle.
            </p>
          </div>

          <div class="professional-consumption-map-heading-actions">
            <button
              type="button"
              class="stats-chart-tool-btn"
              data-professional-consumption-map-help
              aria-label="Afficher l’aide de lecture de la carte"
              title="Aide à la lecture"
            >
              ?
            </button>

            <button
              type="button"
              class="stats-chart-tool-btn stats-chart-zoom-btn"
              data-professional-consumption-map-zoom
              aria-label="Agrandir la carte"
              title="Agrandir la carte"
            >
              ⤢
            </button>
          </div>
        </div>

        ${
          hasConsumptionMap
            ? `
              <div class="professional-consumption-map-kpi-grid">
                ${renderProfessionalSummaryKpiCard(
                  "Faisceaux visibles",
                  formatProfessionalSummaryInteger(consumptionMapCoverage.visible_route_count || 0),
                  "Routes bassin postal → professionnel avec au moins 2 particuliers distincts."
                )}

                ${renderProfessionalSummaryKpiCard(
                  "Volume représenté",
                  euro(consumptionMapCoverage.visible_volume || 0),
                  `${formatProfessionalSummaryRatio(consumptionMapCoverage.visible_volume_share_of_cartographiable)} du volume U→P cartographiable.`
                )}

                ${renderProfessionalSummaryKpiCard(
                  "Bassins sources",
                  formatProfessionalSummaryInteger(consumptionMapSources.length || 0),
                  "Codes postaux d’origine conservés après le seuil de confidentialité."
                )}

                ${renderProfessionalSummaryKpiCard(
                  "Professionnels atteints",
                  formatProfessionalSummaryInteger(consumptionMapDestinations.length || 0),
                  "Destinations professionnelles géolocalisées dans la représentation."
                )}
              </div>

              <div
                class="professional-consumption-map-mode-toggle"
                data-professional-consumption-map-mode-toggle
              >
                <button
                  type="button"
                  class="professional-consumption-map-mode-btn ${consumptionMapViewMode === "static" ? "is-active" : ""}"
                  data-consumption-map-view-mode="static"
                  aria-pressed="${consumptionMapViewMode === "static" ? "true" : "false"}"
                >
                  Carte statique
                </button>

                <button
                  type="button"
                  class="professional-consumption-map-mode-btn ${consumptionMapViewMode === "dynamic" ? "is-active" : ""}"
                  data-consumption-map-view-mode="dynamic"
                  aria-pressed="${consumptionMapViewMode === "dynamic" ? "true" : "false"}"
                >
                  Lecture dynamique
                </button>
              </div>

              <div class="professional-consumption-map-frame">
                <canvas id="professionalConsumptionMapCanvas"></canvas>

                <div
                  class="professional-consumption-map-player professional-consumption-map-player-overlay"
                  data-professional-consumption-map-player
                  aria-hidden="${consumptionMapViewMode === "dynamic" ? "false" : "true"}"
                  ${consumptionMapViewMode === "dynamic" ? "" : "hidden"}
                >
                <div class="professional-consumption-map-player-controls">
                  <div class="professional-consumption-map-player-buttons">
                    <button
                      type="button"
                      class="professional-consumption-map-player-btn"
                      data-consumption-map-play
                    >
                      ▶ Lecture
                    </button>

                    <button
                      type="button"
                      class="professional-consumption-map-player-btn"
                      data-consumption-map-pause
                      disabled
                    >
                      ⏸ Pause
                    </button>

                    <button
                      type="button"
                      class="professional-consumption-map-player-btn"
                      data-consumption-map-replay
                    >
                      ↺ Rejouer
                    </button>
                  </div>

                  <div class="professional-consumption-map-player-durations">
                    <span>Construire en</span>

                    <button
                      type="button"
                      class="professional-consumption-map-duration-btn"
                      data-consumption-map-duration="10000"
                    >
                      10 s
                    </button>

                    <button
                      type="button"
                      class="professional-consumption-map-duration-btn is-active"
                      data-consumption-map-duration="30000"
                    >
                      30 s
                    </button>

                    <button
                      type="button"
                      class="professional-consumption-map-duration-btn"
                      data-consumption-map-duration="60000"
                    >
                      60 s
                    </button>
                  </div>
                </div>

                <div class="professional-consumption-map-player-timeline">
                  <input
                    type="range"
                    min="0"
                    max="${consumptionMapTimelineLastIndex}"
                    value="${consumptionMapTimelineLastIndex}"
                    step="1"
                    data-consumption-map-range
                  />

                  <div class="professional-consumption-map-player-readout">
                    <strong data-consumption-map-current-label>
                      ${consumptionMapTimelineLastLabel}
                    </strong>
                    <span data-consumption-map-current-metrics>
                      ${formatProfessionalSummaryInteger(consumptionMapCoverage.visible_route_count || 0)} faisceau(x)
                      · ${formatProfessionalSummaryInteger(consumptionMapCoverage.visible_tx_count || 0)} paiement(s)
                      · ${euro(consumptionMapCoverage.visible_volume || 0)}
                    </span>
                  </div>
                </div>
                </div>
              </div>

              <div class="professional-consumption-map-note">
                <strong>Lecture.</strong>
                Les lignes illustrent des <strong>faisceaux de consommation</strong>,
                pas des trajets individuels réels.
                La carte affiche
                <strong>${formatProfessionalSummaryInteger(consumptionMapCoverage.visible_tx_count || 0)} paiements</strong>
                et
                <strong>${euro(consumptionMapCoverage.visible_volume || 0)}</strong>,
                retenus après un seuil minimal de
                <strong>2 particuliers distincts par faisceau</strong>.
                Les périmètres postaux sont disponibles pour
                <strong>${formatProfessionalSummaryInteger(consumptionMapGeometry?.route_area_status_counts?.available || 0)}</strong>
                routes visibles.
              </div>
            `
            : `
              <div class="professional-circulation-empty">
                Aucune donnée cartographique de consommation n’est disponible pour cette période.
              </div>
            `
        }
      </section>

  `;
}

function renderProfessionalCirculationPanel(
  flowSummary,
  pilotageSummary,
  circulationTimeseries,
  reuseYearlySummary,
  chainFateSummary,
  consumptionMapSummary
) {
  const flowPayload = flowSummary || {};
  const flows = flowPayload.flows || {};
  const aggregates = flowPayload.aggregates || {};
  const professionalCounts = flowPayload.professional_counts || {};

  const up = flows.up || {};
  const pp = flows.pp || {};
  const ptOutflows = flows.pt_outflows || {};

  const professionalReuse = (
    pilotageSummary?.pilotage_metrics?.internal_reuse?.professionals
    || {}
  );

  const reusePropensity = professionalReuse.weighted_internal_reuse_propensity;
  const multiplierEstimated = professionalReuse.internal_multiplier_estimated;

  const circulationItems = circulationTimeseries?.items || [];
  const hasCirculationItems = Array.isArray(circulationItems) && circulationItems.length > 0;

  const professionalReuseYearlyItems = reuseYearlySummary?.items || [];
  const hasProfessionalReuseYearlyItems = (
    Array.isArray(professionalReuseYearlyItems)
    && professionalReuseYearlyItems.length > 0
  );

  const professionalReuseHistoryFootnote = buildProfessionalReuseHistoryFootnote(
    professionalReuseYearlyItems
  );

  const chainFatePayload = chainFateSummary || null;
  const chainFateModel = getProfessionalChainFatePrimaryModel(chainFatePayload);
  const chainFateExtendedModel = getProfessionalChainFateExtendedModel(chainFatePayload);
  const chainExit = chainFateModel?.tracked_exit_to_t || {};
  const chainExitSummary = chainExit?.summary || {};
  const chainDelayDays = chainExitSummary?.delay_days || {};
  const chainFocus = chainFateModel?.focus_indicators || {};
  const chainLongLived = chainFocus?.long_lived_exit_gt_90d || {};
  const chainQuasiImmediate = chainFocus?.quasi_immediate_direct_exit_depth0_le_7d || {};
  const chainDeep = chainFocus?.deep_chains_depth_ge_3 || {};
  const chainCoverage = chainExit?.matched_share_of_p_to_t ?? null;
  const chainExtendedCoverage = chainFateExtendedModel?.tracked_exit_to_t?.matched_share_of_p_to_t ?? null;

  const chainMetadata = chainFatePayload?.metadata || {};
  const chainPeriodStart = formatIsoDateFr(
    String(chainMetadata?.first_transaction_date || "").slice(0, 10)
  );
  const chainPeriodEnd = formatIsoDateFr(
    String(chainMetadata?.last_transaction_date || "").slice(0, 10)
  );

  const hasChainFateSummary = Boolean(chainFateModel);

  return `
    <section class="professional-circulation-shell">
      <div class="professional-circulation-kpi-grid">
        ${renderProfessionalSummaryKpiCard(
          "Recettes depuis les particuliers",
          euro(up.volume || 0),
          "Volume U→P observé sur la période."
        )}

        ${renderProfessionalSummaryKpiCard(
          "Recettes interprofessionnelles",
          euro(pp.volume || 0),
          "Volume P→P reçu par les professionnels du réseau."
        )}

        ${renderProfessionalSummaryKpiCard(
          "Réemploi interne professionnel",
          formatProfessionalSummaryRatio(reusePropensity),
          "Part pondérée des recettes pros effectivement redépensée dans le réseau."
        )}

        ${renderProfessionalSummaryKpiCard(
          "Multiplicateur professionnel estimé",
          formatProfessionalSummaryMultiple(multiplierEstimated),
          "Capacité de recirculation associée au réemploi professionnel."
        )}
      </div>

      <section class="card professional-circulation-chart-card">
        <div class="professional-analysis-section-heading">
          <div class="stat-label">Flux professionnels dans le temps</div>
          <h3>Ce qui entre, ce qui circule, ce qui repart</h3>
          <p>
            Cette première série mensuelle suit les grands flux impliquant les professionnels :
            paiements des particuliers, échanges interprofessionnels, reversements vers les particuliers
            et sorties professionnelles vers les comptes techniques.
          </p>
        </div>

        ${
          hasCirculationItems
            ? `
              <div class="professional-circulation-chart-frame">
                <canvas id="professionalCirculationFlowsChart"></canvas>
              </div>
            `
            : `
              <div class="professional-circulation-empty">
                Aucun flux professionnel mensuel n’est disponible sur cette période.
              </div>
            `
        }
      </section>

      <section class="card professional-circulation-pressure-card">
        <div class="professional-analysis-section-heading">
          <div class="stat-label">Sorties professionnelles &amp; tension de réemploi</div>
          <h3>Ce qui repart dans le réseau, et ce qui sort du circuit</h3>
          <p>
            Les sorties professionnelles vers les comptes techniques éclairent un autre versant
            de l’usage de la Gonette : lorsqu’un professionnel encaisse, quelle part est remise
            en circulation dans le réseau, et quelle part quitte le circuit numérique observé ?
          </p>
        </div>

        <div class="professional-circulation-pressure-grid">
          ${renderProfessionalSummaryKpiCard(
            "Sorties professionnelles du circuit",
            euro(ptOutflows.volume || 0),
            `${formatProfessionalSummaryInteger(ptOutflows.count || 0)} flux P→T observé(s).`
          )}

          ${renderProfessionalSummaryKpiCard(
            "Sorties / recettes reçues",
            formatProfessionalSummaryRatio(aggregates.outflow_to_received_rate),
            "Rapport entre les volumes P→T et les recettes économiques reçues par les pros."
          )}

          ${renderProfessionalSummaryKpiCard(
            "Réémis / sorties",
            formatProfessionalSummaryMultiple(aggregates.reemission_to_outflow_ratio),
            "Comparaison entre les volumes réémis économiquement et les volumes sortis du circuit."
          )}

          ${renderProfessionalSummaryKpiCard(
            "Professionnels concernés",
            formatProfessionalSummaryInteger(professionalCounts.outflowing || 0),
            "Professionnels ayant porté au moins une sortie P→T sur la période."
          )}
        </div>

        <div class="professional-circulation-chart-frame professional-outflows-comparison-frame">
          <canvas id="professionalOutflowsComparisonChart"></canvas>
        </div>
      </section>

      <section class="card professional-chain-fate-card">
        <div class="professional-analysis-section-heading">
          <div class="stat-label">Destin des Gonettes encaissées par les professionnels</div>
          <h3>Après l’encaissement : sortie rapide, séjour prolongé ou circulation profonde&nbsp;?</h3>
          <p>
            Cette lecture suit, sur l’historique complet
            <strong>${chainPeriodStart} → ${chainPeriodEnd}</strong>,
            des lots de Gonettes reçus par les professionnels depuis les particuliers,
            puis estime leur délai et leur profondeur de circulation avant une sortie
            vers compte technique.
          </p>
        </div>

        ${
          hasChainFateSummary
            ? `
              <div class="professional-chain-fate-kpi-grid">
                ${renderProfessionalSummaryKpiCard(
                  "Délai médian avant sortie",
                  formatProfessionalChainFateDays(chainDelayDays.median),
                  "Temps médian entre l’encaissement U→P et la sortie P→T attribuée."
                )}

                ${renderProfessionalSummaryKpiCard(
                  "Sorties après plus de 90 jours",
                  euro(chainLongLived.volume || 0),
                  `${formatProfessionalSummaryInteger(chainLongLived.fragment_count || 0)} fragment(s) suivis.`
                )}

                ${renderProfessionalSummaryKpiCard(
                  "Sorties directes quasi immédiates",
                  euro(chainQuasiImmediate.volume || 0),
                  `${formatProfessionalSummaryInteger(chainQuasiImmediate.exit_professional_count || 0)} professionnel(s) concernés.`
                )}

                ${renderProfessionalSummaryKpiCard(
                  "Acteurs des chaînes longues",
                  formatProfessionalSummaryInteger(chainDeep.distinct_chain_actor_count || 0),
                  "Acteurs distincts impliqués dans des chaînes de profondeur ≥ 3."
                )}
              </div>

              <div class="professional-chain-fate-chart-grid">
                <article class="professional-chain-fate-chart-block">
                  <h4>Temps avant sortie vers compte technique</h4>
                  <div class="professional-chain-fate-chart-frame">
                    <canvas id="professionalChainFateDelayChart"></canvas>
                  </div>
                </article>

                <article class="professional-chain-fate-chart-block">
                  <h4>Profondeur de circulation avant sortie</h4>
                  <div class="professional-chain-fate-chart-frame">
                    <canvas id="professionalChainFateDepthChart"></canvas>
                  </div>
                </article>
              </div>

              <div class="professional-chain-fate-method-note">
                <strong>Modèle principal.</strong>
                Attribution FIFO par lots issus des paiements <strong>U→P</strong>.
                Il couvre <strong>${formatProfessionalSummaryRatio(chainCoverage)}</strong>
                des sorties professionnelles <strong>P→T</strong> observées.
                Le modèle de contrôle élargi <strong>U→P + T→P</strong>
                couvre <strong>${formatProfessionalSummaryRatio(chainExtendedCoverage)}</strong>.
              </div>
            `
            : `
              <div class="professional-circulation-empty">
                Le résumé précalculé des trajectoires professionnelles n’est pas disponible.
              </div>
            `
        }
      </section>

      <section class="card professional-circulation-chart-card">
        <div class="professional-analysis-section-heading">
          <div class="stat-label">Trajectoire historique</div>
          <h3>Réemploi interne et multiplicateur professionnel, année après année</h3>
          <p>
            Cette série reprend les indicateurs annuels déjà stabilisés dans le Pilotage monétaire,
            mais en isolant ici le rôle des professionnels : propension pondérée de réemploi interne
            et multiplicateur professionnel estimé.
          </p>
        </div>

        ${
          hasProfessionalReuseYearlyItems
            ? `
              <div class="professional-circulation-chart-frame professional-reuse-history-frame">
                <canvas id="professionalReuseHistoryChart"></canvas>
              </div>
              ${professionalReuseHistoryFootnote}
            `
            : `
              <div class="professional-circulation-empty">
                Aucun historique annuel de réemploi professionnel n’est disponible.
              </div>
            `
        }
      </section>
    </section>
  `;
}

function buildProfessionalAnalysisShell(flowSummary = null, holdingsSummary = null, pilotageSummary = null, circulationTimeseries = null, reuseYearlySummary = null, chainFateSummary = null, consumptionMapSummary = null) {
  const activeProfessionals = Array.isArray(appState.prosData)
    ? appState.prosData.length
    : 0;

  return `
    <section class="card professional-analysis-hero">
      <div class="professional-analysis-hero-main">
        <div class="stat-label">Professionnels &amp; particuliers · usages, circulation et ancrage des communautés d’échange</div>
        <h2>Comment les utilisateurs de la Gonette — particuliers et professionnels — structurent-ils la circulation, les pôles d’usage et les communautés d’échange&nbsp;?</h2>
        <p>
          Cette vue croise les flux, les soldes, les cartes, les secteurs et les trajectoires
          historiques pour analyser ensemble les particuliers et les professionnels :
          qui alimente la circulation, qui la capte, quels clusters se forment,
          et quels leviers peuvent renforcer l’ancrage de la Gonette dans ses usages réels.
        </p>
      </div>

      <div class="professional-analysis-hero-aside">
        <div class="professional-analysis-hero-kpi">
          <strong>${Number(activeProfessionals || 0).toLocaleString("fr-FR")}</strong>
          <span>professionnel(s) visibles dans le classement de la période</span>
        </div>
        <div class="professional-analysis-hero-note">
          Le classement professionnel existant reste disponible dans l’onglet
          <strong>Liste &amp; fiches</strong> pendant la refonte de cette vue élargie
          aux usages des particuliers et des professionnels.
        </div>
      </div>
    </section>

    <nav class="professional-analysis-tabs" aria-label="Analyse des professionnels et particuliers">
      <button
        type="button"
        class="professional-analysis-tab-btn"
        data-professional-analysis-tab="summary"
      >
        Synthèse
      </button>

      <button
        type="button"
        class="professional-analysis-tab-btn"
        data-professional-analysis-tab="circulation"
      >
        Circulation &amp; multiplicateur
      </button>

      <button
        type="button"
        class="professional-analysis-tab-btn"
        data-professional-analysis-tab="network"
      >
        Réseau
      </button>

      <button
        type="button"
        class="professional-analysis-tab-btn"
        data-professional-analysis-tab="clusters"
      >
        Cartographie des clusters
      </button>

      <button
        type="button"
        class="professional-analysis-tab-btn"
        data-professional-analysis-tab="structures"
      >
        Analyse sectorielle
      </button>

      <button
        type="button"
        class="professional-analysis-tab-btn"
        data-professional-analysis-tab="directory"
      >
        Liste &amp; fiches
      </button>
    </nav>

    <section
      class="professional-analysis-panel"
      data-professional-analysis-panel="summary"
    >
      ${renderProfessionalSummaryPanel(flowSummary, holdingsSummary, pilotageSummary)}
    </section>

    <section
      class="professional-analysis-panel hidden"
      data-professional-analysis-panel="circulation"
    >
      ${renderProfessionalCirculationPanel(
        flowSummary,
        pilotageSummary,
        circulationTimeseries,
        reuseYearlySummary,
        chainFateSummary,
        consumptionMapSummary
      )}
    </section>

    <section
      class="professional-analysis-panel hidden"
      data-professional-analysis-panel="network"
    >
      <section class="card professional-analysis-roadmap-card">
        <div class="professional-analysis-section-heading">
          <div class="stat-label">Onglet 3 · Réseau interprofessionnel</div>
          <h3>Explorer la structure relationnelle des échanges P→P</h3>
          <p>
            Cet onglet cartographie les relations monétaires entre professionnels :
            liens dirigés, volumes cumulés, profils de réception et de réémission,
            voisinages actifs et acteurs structurants du réseau.
          </p>
        </div>
      </section>

      <section
        id="professionalNetworkPanel"
        class="professional-network-panel"
        data-professional-network-hydrated="false"
      >
        <section class="card professional-analysis-roadmap-card">
          <div class="professional-analysis-section-heading">
            <div class="stat-label">Chargement à l’ouverture</div>
            <h3>L’atlas relationnel apparaîtra ici</h3>
            <p>
              Les données réseau sont chargées uniquement lorsque cet onglet est ouvert,
              afin de préserver le temps d’entrée dans la vue générale.
            </p>
          </div>
        </section>
      </section>
    </section>

    <section
      class="professional-analysis-panel hidden"
      data-professional-analysis-panel="clusters"
    >
      <section class="card professional-analysis-roadmap-card">
        <div class="professional-analysis-section-heading">
          <div class="stat-label">Onglet 4 · Cartographie des clusters</div>
          <h3>Relier les pôles d’activité et les territoires d’usage</h3>
          <p>
            Cet onglet devient l’espace cartographique de la vue
            <strong>Professionnels &amp; particuliers</strong>. Il réunit la cartographie
            des professionnels et l’analyse territoriale par code postal, afin de faire
            apparaître les pôles d’activité, les bassins d’usage et les structures spatiales
            de circulation de la Gonette.
          </p>
        </div>
      </section>

      <section
        id="professionalClustersPanel"
        class="professional-clusters-panel"
        data-professional-clusters-hydrated="false"
      >
        <section class="card professional-analysis-roadmap-card">
          <div class="professional-analysis-section-heading">
            <div class="stat-label">Chargement à l’ouverture</div>
            <h3>Les cartes et analyses territoriales apparaîtront ici</h3>
            <p>
              Les données cartographiques et territoriales sont chargées uniquement
              lorsque cet onglet est ouvert, afin de préserver le temps d’entrée
              dans la vue générale.
            </p>
          </div>
        </section>
      </section>
    </section>

    <section
      class="professional-analysis-panel hidden"
      data-professional-analysis-panel="structures"
    >
      <section class="card professional-analysis-roadmap-card">
        <div class="professional-analysis-section-heading">
          <div class="stat-label">Onglet 5 · Analyse sectorielle</div>
          <h3>Comprendre comment les secteurs structurent l’activité en Gonette</h3>
          <p>
            Cet onglet reprend désormais l’analyse sectorielle auparavant isolée
            dans le menu principal : poids des grandes familles d’activité,
            volumes reçus et réémis, origine des recettes, réutilisation
            et profils sectoriels du réseau.
          </p>
        </div>
      </section>

      <section
        id="professionalSectorAnalysisPanel"
        class="professional-sector-analysis-panel"
        data-professional-sector-analysis-hydrated="false"
      >
        <section class="card professional-analysis-roadmap-card">
          <div class="professional-analysis-section-heading">
            <div class="stat-label">Chargement à l’ouverture</div>
            <h3>L’analyse sectorielle apparaîtra ici</h3>
            <p>
              Les données sectorielles sont chargées uniquement lorsque cet onglet est ouvert,
              afin de ne pas alourdir l’arrivée dans la vue générale.
            </p>
          </div>
        </section>
      </section>
    </section>

    <section
      class="professional-analysis-panel hidden"
      data-professional-analysis-panel="directory"
    >
      <section class="card professional-analysis-directory-intro">
        <div class="professional-analysis-section-heading">
          <div class="stat-label">Onglet 6 · Liste &amp; fiches individuelles</div>
          <h3>Explorer les professionnels acteur par acteur</h3>
          <p>
            Le classement existant est conservé ici. Il servira de base à la future
            exploration enrichie : soldes, trajectoires, profils de réemploi,
            contexte sectoriel et territorial, puis enrichissements publics lorsque
            nous ouvrirons ce chantier.
          </p>
        </div>
      </section>

      <section id="professionalsDirectoryPanel"></section>
    </section>
  `;
}



function buildProfessionalClustersLoadingHtml() {
  return `
    <section class="card professional-analysis-roadmap-card">
      <div class="professional-analysis-section-heading">
        <div class="stat-label">Cartographie des clusters</div>
        <h3>Chargement de la carte et des territoires…</h3>
        <p>
          Les données sont recalculées pour la période actuellement sélectionnée.
        </p>
      </div>
    </section>
  `;
}

function buildProfessionalClustersErrorHtml() {
  return `
    <section class="card professional-analysis-roadmap-card">
      <div class="professional-analysis-section-heading">
        <div class="stat-label">Cartographie des clusters</div>
        <h3>Les données cartographiques ne sont pas disponibles</h3>
        <p>
          La carte des professionnels ou l’analyse territoriale n’ont pas pu être
          chargées pour cette période. Les autres onglets restent utilisables.
        </p>
      </div>
    </section>
  `;
}


function formatUserPostalClusterInteger(value) {
  return Number(value || 0).toLocaleString("fr-FR");
}

function formatUserPostalClusterAverage(value, decimals = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("fr-FR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

function buildUserPostalClusterGeoJson(points = []) {
  return {
    type: "FeatureCollection",
    features: (Array.isArray(points) ? points : [])
      .filter(point =>
        Number.isFinite(Number(point?.longitude))
        && Number.isFinite(Number(point?.latitude))
      )
      .map(point => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [
            Number(point.longitude),
            Number(point.latitude)
          ]
        },
        properties: {
          postal_code: point.postal_code || "",
          city_label: point.city_label || "",
          individual_count: Number(point.individual_count || 0),
          professional_count: Number(point.professional_count || 0),
          weight: Number(point.weight || point.individual_count || 0)
        }
      }))
  };
}

function fitUserPostalClustersMapToPoints(map, points = []) {
  if (!map || !window.maplibregl || !Array.isArray(points) || points.length === 0) {
    return;
  }

  const bounds = new window.maplibregl.LngLatBounds();
  let validCount = 0;

  points.forEach(point => {
    const longitude = Number(point?.longitude);
    const latitude = Number(point?.latitude);

    if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
      return;
    }

    bounds.extend([longitude, latitude]);
    validCount += 1;
  });

  if (!validCount) {
    return;
  }

  map.fitBounds(bounds, {
    padding: 58,
    maxZoom: 12.6,
    duration: 700
  });
}

function destroyUserPostalClustersMap(stateKey = "userPostalClustersMap") {
  const map = appState[stateKey];

  if (
    map
    && typeof map.remove === "function"
  ) {
    map.remove();
  }

  appState[stateKey] = null;
}

function initializeUserPostalClustersMap(points = [], options = {}) {
  const containerId = options.containerId || "userPostalClustersMap";
  const fitButtonId = options.fitButtonId || "userPostalClustersFitBtn";
  const stateKey = options.stateKey || "userPostalClustersMap";
  const mapNode = document.getElementById(containerId);
  if (!mapNode) {
    return;
  }

  const validPoints = (Array.isArray(points) ? points : []).filter(point =>
    Number.isFinite(Number(point?.longitude))
    && Number.isFinite(Number(point?.latitude))
  );

  if (!validPoints.length) {
    mapNode.innerHTML = `
      <div class="user-postal-clusters-map-empty">
        Aucun point cartographique exploitable pour cette période.
      </div>
    `;
    return;
  }

  if (!window.maplibregl) {
    mapNode.innerHTML = `
      <div class="user-postal-clusters-map-empty">
        La bibliothèque cartographique n’est pas disponible.
      </div>
    `;
    return;
  }

  destroyUserPostalClustersMap(stateKey);

  const maxIndividualCount = Math.max(
    1,
    ...validPoints.map(point => Number(point.individual_count || point.weight || 0))
  );

  const geojson = buildUserPostalClusterGeoJson(validPoints);

  const map = new window.maplibregl.Map({
    container: containerId,
    style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    center: [4.8357, 45.7640],
    zoom: 9,
    pitch: 0,
    bearing: 0
  });

  // Empêche la carte de capturer le scroll de page.
  map.scrollZoom.disable();

  map.addControl(new window.maplibregl.NavigationControl(), "top-right");

  map.once("load", () => {
    map.addSource("user-postal-clusters", {
      type: "geojson",
      data: geojson
    });

    map.addLayer({
      id: "user-postal-clusters-heat",
      type: "heatmap",
      source: "user-postal-clusters",
      maxzoom: 15,
      paint: {
        "heatmap-weight": [
          "interpolate",
          ["linear"],
          ["get", "weight"],
          0, 0,
          maxIndividualCount, 1
        ],
        "heatmap-intensity": [
          "interpolate",
          ["linear"],
          ["zoom"],
          8, 0.95,
          12, 1.55
        ],
        "heatmap-radius": [
          "interpolate",
          ["linear"],
          ["zoom"],
          8, 28,
          11, 46,
          14, 72
        ],
        "heatmap-opacity": [
          "interpolate",
          ["linear"],
          ["zoom"],
          8, 0.88,
          13, 0.70
        ],
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0, "rgba(37, 99, 235, 0)",
          0.18, "rgba(59, 130, 246, 0.42)",
          0.42, "rgba(14, 165, 233, 0.72)",
          0.64, "rgba(250, 204, 21, 0.86)",
          0.84, "rgba(249, 115, 22, 0.94)",
          1, "rgba(220, 38, 38, 0.98)"
        ]
      }
    });

    map.addLayer({
      id: "user-postal-clusters-points",
      type: "circle",
      source: "user-postal-clusters",
      paint: {
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["get", "individual_count"],
          5, 4,
          maxIndividualCount, 13
        ],
        "circle-color": "rgba(15, 23, 42, 0.82)",
        "circle-stroke-color": "rgba(255, 255, 255, 0.92)",
        "circle-stroke-width": 1.2,
        "circle-opacity": 0.72
      }
    });

    map.on("mouseenter", "user-postal-clusters-points", () => {
      map.getCanvas().style.cursor = "pointer";
    });

    map.on("mouseleave", "user-postal-clusters-points", () => {
      map.getCanvas().style.cursor = "";
    });

    map.on("click", "user-postal-clusters-points", event => {
      const feature = event?.features?.[0];
      const properties = feature?.properties || {};
      const coordinates = feature?.geometry?.coordinates;

      if (!coordinates || !window.maplibregl?.Popup) {
        return;
      }

      const postalCode = properties.postal_code || "Code postal inconnu";
      const cityLabel = properties.city_label || "";
      const individualCount = Number(properties.individual_count || 0);
      const professionalCount = Number(properties.professional_count || 0);

      new window.maplibregl.Popup({
        closeButton: true,
        closeOnClick: true
      })
        .setLngLat(coordinates)
        .setHTML(`
          <div class="user-postal-clusters-popup">
            <strong>${postalCode}${cityLabel ? ` — ${cityLabel}` : ""}</strong>
            <span>${formatUserPostalClusterInteger(individualCount)} particulier(s)</span>
            <span>${formatUserPostalClusterInteger(professionalCount)} professionnel(s)</span>
          </div>
        `)
        .addTo(map);
    });

    fitUserPostalClustersMapToPoints(map, validPoints);
  });

  const fitButton = document.getElementById(fitButtonId);
  if (fitButton) {
    fitButton.addEventListener("click", () => {
      fitUserPostalClustersMapToPoints(map, validPoints);
    });
  }

  appState[stateKey] = map;

  return map;
}

function buildProfessionalClusterMapZoomModalHtml({
  kicker,
  title,
  description,
  mapContainerId,
  mapClassName,
  fitButtonId
}) {
  return `
    <section class="professional-clusters-map-zoom-shell">
      <div class="professional-clusters-map-zoom-heading">
        <div>
          <p class="stats-chart-modal-kicker">${escapeHtml(kicker)}</p>
          <h2>${escapeHtml(title)}</h2>
          <p>${escapeHtml(description)}</p>
        </div>

        <button id="${escapeHtml(fitButtonId)}" class="secondary-btn" type="button">
          Recentrer
        </button>
      </div>

      <div class="professional-clusters-map-zoom-frame">
        <div
          id="${escapeHtml(mapContainerId)}"
          class="${escapeHtml(mapClassName)} professional-clusters-map-zoom-map"
        ></div>
      </div>
    </section>
  `;
}

function openUserPostalClustersMapZoom(points = []) {
  openStatsChartModal(
    buildProfessionalClusterMapZoomModalHtml({
      kicker: "Cartographie agrandie",
      title: "Foyers d’usage des particuliers",
      description: "Vue agrandie des concentrations territoriales de particuliers présents dans les flux U→P cartographiables.",
      mapContainerId: "userPostalClustersMapZoom",
      mapClassName: "user-postal-clusters-map",
      fitButtonId: "userPostalClustersZoomFitBtn"
    }),
    "cluster-cartography-zoom"
  );

  window.requestAnimationFrame(() => {
    const map = initializeUserPostalClustersMap(points, {
      containerId: "userPostalClustersMapZoom",
      fitButtonId: "userPostalClustersZoomFitBtn",
      stateKey: "userPostalClustersZoomMap"
    });

    if (map && typeof map.resize === "function") {
      window.setTimeout(() => map.resize(), 180);
    }
  });
}

function openProfessionalsCartographyZoom(professionals = []) {
  openStatsChartModal(
    buildProfessionalClusterMapZoomModalHtml({
      kicker: "Cartographie agrandie",
      title: "Implantation des professionnels",
      description: "Vue agrandie des professionnels géolocalisés et du relief d’activité monétaire sur la période analysée.",
      mapContainerId: "professionalsMapZoom",
      mapClassName: "cartography-map",
      fitButtonId: "cartographyZoomFitBtn"
    }),
    "cluster-cartography-zoom"
  );

  window.requestAnimationFrame(() => {
    const map = initializeProfessionalsMap(professionals, {
      containerId: "professionalsMapZoom",
      fitButtonId: "cartographyZoomFitBtn",
      mapStateKey: "zoomMap",
      overlayStateKey: "zoomOverlay"
    });

    if (map && typeof map.resize === "function") {
      window.setTimeout(() => map.resize(), 180);
    }
  });
}

function bindProfessionalClusterMapZoomButtons() {
  const userZoomButton = document.getElementById("userPostalClustersZoomBtn");
  const proZoomButton = document.getElementById("cartographyZoomBtn");

  if (userZoomButton) {
    userZoomButton.addEventListener("click", () => {
      openUserPostalClustersMapZoom(
        appState.userPostalClustersData?.heatmap_points || []
      );
    });
  }

  if (proZoomButton) {
    proZoomButton.addEventListener("click", () => {
      openProfessionalsCartographyZoom(
        appState.cartography.data?.professionals || []
      );
    });
  }
}

function syncProfessionalClustersMapPairHeights() {
  const userOverview = document.querySelector(
    ".professional-clusters-map-pair-users > .user-postal-clusters-overview-card"
  );
  const proOverview = document.querySelector(
    ".professional-clusters-map-pair-pros > .cartography-overview-card"
  );

  if (!userOverview || !proOverview) {
    return;
  }

  userOverview.style.minHeight = "";
  proOverview.style.minHeight = "";

  if (window.innerWidth < 1080) {
    return;
  }

  const targetHeight = Math.max(
    userOverview.offsetHeight,
    proOverview.offsetHeight
  );

  userOverview.style.minHeight = `${targetHeight}px`;
  proOverview.style.minHeight = `${targetHeight}px`;
}

function bindProfessionalClustersMapPairResizeSync() {
  if (appState.professionalClustersMapPairResizeBound) {
    return;
  }

  appState.professionalClustersMapPairResizeBound = true;

  let resizeTimer = null;

  window.addEventListener("resize", () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      syncProfessionalClustersMapPairHeights();
    }, 120);
  });
}

function buildUserPostalClustersTableHtml(postalCodes = []) {
  const rows = Array.isArray(postalCodes) ? postalCodes : [];

  if (!rows.length) {
    return `
      <div class="user-postal-clusters-empty-state">
        Aucun code postal ne franchit le seuil minimal de particuliers sur cette période.
      </div>
    `;
  }

  return `
    <div class="user-postal-clusters-table-wrap">
      <table class="data-table user-postal-clusters-table">
        <thead>
          <tr>
            <th>Code postal</th>
            <th>Ville</th>
            <th>Pros</th>
            <th>Particuliers</th>
            <th>Solde P début</th>
            <th>Solde P fin</th>
            <th>Solde U début</th>
            <th>Solde U fin</th>
            <th>Vol. moy. émis P</th>
            <th>Vol. moy. émis U</th>
            <th>Nb tx moy. P</th>
            <th>Nb tx moy. U</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map(row => `
            <tr>
              <td><strong>${row.postal_code || "—"}</strong></td>
              <td>${row.city_label || "—"}</td>
              <td>${formatUserPostalClusterInteger(row.professional_count)}</td>
              <td>${formatUserPostalClusterInteger(row.individual_count)}</td>
              <td>${euro(row.professional_opening_balance || 0)}</td>
              <td>${euro(row.professional_closing_balance || 0)}</td>
              <td>${euro(row.individual_opening_balance || 0)}</td>
              <td>${euro(row.individual_closing_balance || 0)}</td>
              <td>${row.avg_emitted_volume_per_professional_emitter === null ? "—" : euro(row.avg_emitted_volume_per_professional_emitter || 0)}</td>
              <td>${row.avg_emitted_volume_per_individual_emitter === null ? "—" : euro(row.avg_emitted_volume_per_individual_emitter || 0)}</td>
              <td>${formatUserPostalClusterAverage(row.avg_emitted_tx_count_per_professional_emitter)}</td>
              <td>${formatUserPostalClusterAverage(row.avg_emitted_tx_count_per_individual_emitter)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function buildUserPostalClustersMapPairHtml(userPostalClustersData = null) {
  const payload = userPostalClustersData || {};
  const summary = payload.summary || {};
  const effectivePeriod = payload.effective_period || {};
  const points = Array.isArray(payload.heatmap_points)
    ? payload.heatmap_points
    : [];

  return `
    <div class="professional-clusters-map-pair professional-clusters-map-pair-users">
      <section class="card user-postal-clusters-overview-card">
        <div class="user-postal-clusters-overview-header">
          <div>
            <div class="stat-label">2 · Foyers d’usage des particuliers</div>
            <h2>${formatUserPostalClusterInteger(summary.individual_count_included || 0)} particuliers répartis sur ${formatUserPostalClusterInteger(summary.postal_code_count || 0)} codes postaux</h2>
            <p>
              Cette carte met en évidence les foyers territoriaux d’usage. Les points sont agrégés
              par code postal et n’exposent jamais de localisation individuelle.
            </p>
            <p class="user-postal-clusters-period-note">
              Période analytique :
              <strong>${effectivePeriod.start || "—"}</strong>
              →
              <strong>${effectivePeriod.end || "—"}</strong>.
            </p>
          </div>

          <div class="user-postal-clusters-kpis">
            <div class="user-postal-clusters-kpi">
              <strong>${formatUserPostalClusterInteger(summary.postal_code_count || 0)}</strong>
              <span>codes postaux</span>
            </div>
            <div class="user-postal-clusters-kpi">
              <strong>${formatUserPostalClusterInteger(summary.heatmap_point_count || 0)}</strong>
              <span>points heatmap</span>
            </div>
            <div class="user-postal-clusters-kpi">
              <strong>${formatUserPostalClusterInteger(summary.professional_count_included || 0)}</strong>
              <span>professionnels associés</span>
            </div>
          </div>
        </div>
      </section>

      <section class="card user-postal-clusters-map-card">
        <div class="cartography-map-toolbar">
          <div>
            <strong>${formatUserPostalClusterInteger(points.length)}</strong> foyer(s) territoriaux ·
            intensité pondérée par le nombre de particuliers.
          </div>
          <div class="cartography-map-toolbar-actions">
            <button id="userPostalClustersZoomBtn" class="secondary-btn" type="button">
              Agrandir
            </button>
            <button id="userPostalClustersFitBtn" class="secondary-btn" type="button">
              Recentrer
            </button>
          </div>
        </div>

        <div id="userPostalClustersMap" class="user-postal-clusters-map"></div>

        <div class="user-postal-clusters-map-note">
          <strong>Lecture.</strong>
          La chaleur représente une concentration agrégée de particuliers par code postal,
          pas une localisation individuelle. Les points sont placés au niveau du centroïde
          géographique du code postal.
        </div>
      </section>
    </div>
  `;
}

function buildUserPostalClustersTableSectionHtml(userPostalClustersData = null) {
  const payload = userPostalClustersData || {};
  const postalCodes = Array.isArray(payload.postal_codes)
    ? payload.postal_codes
    : [];

  return `
    <section class="card user-postal-clusters-table-card">
      <div class="territory-section-heading">
        <h3>Tableau territorial U / P</h3>
      </div>

      <div class="user-postal-clusters-table-note">
        Les moyennes d’émission sont calculées par
        <strong>émetteur distinct actif sur la période</strong> :
        un professionnel ou un particulier n’entre dans la moyenne que s’il a émis
        au moins une transaction dans l’intervalle retenu.
      </div>

      ${buildUserPostalClustersTableHtml(postalCodes)}
    </section>
  `;
}

function buildProfessionalClustersPanelHtml(cartographyData = null, territoriesData = null, consumptionMapSummary = null, userPostalClustersData = null) {
  const cartographyPayload = cartographyData || {};
  const cartographySummary = cartographyPayload.summary || {};
  const professionals = Array.isArray(cartographyPayload.professionals)
    ? cartographyPayload.professionals
    : [];

  const territoriesPayload = territoriesData || {};
  const territorySummary = territoriesPayload.summary || {};
  const territories = Array.isArray(territoriesPayload.territories)
    ? territoriesPayload.territories
    : [];

  return `
    ${renderProfessionalConsumptionMapCard(consumptionMapSummary)}

    <section class="card professional-clusters-secondary-intro-card">
      <div class="professional-clusters-secondary-intro">
        <div class="stat-label">Lecture territoriale croisée</div>
        <h3>Où se situent les foyers d’usage et les pôles d’acceptation&nbsp;?</h3>
        <p>
          Ces deux cartes se lisent ensemble. À gauche, la Gonette est observée du point de vue
          des particuliers : on repère les foyers territoriaux d’usage, c’est-à-dire les zones où
          se concentrent les utilisateurs présents dans la période. À droite, on observe le réseau
          des professionnels effectivement implantés et géolocalisés, avec un relief d’activité
          qui signale les pôles de réception monétaire. Leur comparaison aide à repérer les
          centralités fortes, mais aussi les décalages entre présence d’usagers et densité de
          points d’acceptation.
        </p>
      </div>
    </section>

    ${buildUserPostalClustersMapPairHtml(userPostalClustersData)}

    <div class="professional-clusters-map-pair professional-clusters-map-pair-pros">
      <section class="card cartography-overview-card">
        <div class="cartography-overview-header">
          <div>
            <div class="stat-label">3 · Implantation des professionnels</div>
            <h2>${cartographySummary.cartographiable_count ?? professionals.length} professionnels affichés</h2>
            <p>
              Cette carte montre les professionnels géolocalisés et confirmés. Le relief 3D aide à
              repérer les pôles de réception monétaire et les concentrations d’activité de la période.
            </p>
          </div>

          <div class="cartography-kpis">
            <div class="cartography-kpi">
              <strong>${cartographySummary.total_enriched ?? 0}</strong>
              <span>pros enrichis</span>
            </div>
            <div class="cartography-kpi">
              <strong>${cartographySummary.confirmed ?? 0}</strong>
              <span>confirmés</span>
            </div>
            <div class="cartography-kpi">
              <strong>${cartographySummary.mismatch ?? 0}</strong>
              <span>divergences</span>
            </div>
          </div>
        </div>

        <div class="cartography-quality-note">
          Non affichés :
          ${cartographySummary.no_odoo_coordinates ?? 0} sans coordonnées Odoo,
          ${cartographySummary.no_cyclos_coordinates ?? 0} sans coordonnées Cyclos,
          ${cartographySummary.no_cyclos_address ?? 0} sans adresse Cyclos.
        </div>
      </section>

      <section class="card cartography-map-card">
        <div class="cartography-map-toolbar">
          <div>
            <strong>${professionals.length}</strong> points confirmés · relief d’activité monétaire.
          </div>
          <div class="cartography-map-toolbar-actions">
            <button id="cartographyZoomBtn" class="secondary-btn" type="button">
              Agrandir
            </button>
            <button id="cartographyFitBtn" class="secondary-btn" type="button">
              Recentrer
            </button>
          </div>
        </div>

        <div id="professionalsMap" class="cartography-map"></div>

        <div class="cartography-map-note">
          <strong>Lecture.</strong>
          La hauteur des colonnes représente une concentration d’activité monétaire sur la période.
          Elle signale des pôles de réception plus intenses, sans résumer à elle seule toute la
          diversité des usages locaux.
        </div>
      </section>
    </div>

    ${buildUserPostalClustersTableSectionHtml(userPostalClustersData)}

    <section class="card territory-overview-card">
      <div class="territory-overview-header">
        <div>
          <div class="stat-label">2 · Ancrage territorial des échanges</div>
          <h2>${Number(territorySummary.territory_count || 0).toLocaleString("fr-FR")} codes postaux analysés</h2>
          <p>
            Cette lecture ventile l’activité numérique des professionnels par code postal :
            gonettes reçues, gonettes réémises et taux de réutilisation territorial.
          </p>
        </div>

        <div class="territory-kpis">
          <div class="territory-kpi">
            <strong>${Number(territorySummary.territorialized_professional_count || 0).toLocaleString("fr-FR")}</strong>
            <span>pros rattachés à un CP</span>
          </div>
          <div class="territory-kpi">
            <strong>${Number(territorySummary.territorialized_active_professional_count || 0).toLocaleString("fr-FR")}</strong>
            <span>pros actifs</span>
          </div>
          <div class="territory-kpi">
            <strong>${formatTerritoryPercent(territorySummary.overall_reuse_rate)}</strong>
            <span>réutilisation globale</span>
          </div>
        </div>
      </div>

      <div class="territory-flow-grid">
        <div class="territory-flow-card">
          <span>Gonettes reçues territorialisées</span>
          <strong>${euro(territorySummary.territorialized_received_volume || 0)}</strong>
        </div>
        <div class="territory-flow-card">
          <span>Gonettes émises territorialisées</span>
          <strong>${euro(territorySummary.territorialized_emitted_volume || 0)}</strong>
        </div>
        <div class="territory-flow-card">
          <span>Volume total brassé</span>
          <strong>${euro(territorySummary.territorialized_total_flow_volume || 0)}</strong>
        </div>
      </div>

      <div class="territory-quality-note">
        Couverture :
        ${formatTerritoryPercent(territorySummary.received_volume_coverage)} du volume reçu
        et ${formatTerritoryPercent(territorySummary.emitted_volume_coverage)} du volume émis
        sont rattachés à un code postal.
        ${Number(territorySummary.professionals_without_zip || 0).toLocaleString("fr-FR")} professionnel(s)
        enrichi(s) restent sans code postal exploitable.
      </div>
    </section>

    <section class="card territory-ranking-card">
      <div class="territory-section-heading">
        <h3>Principaux territoires par gonettes reçues</h3>
      </div>
      ${buildTerritoryRankingHtml(territories)}
    </section>

    <section class="card territory-table-card">
      <div class="territory-section-heading">
        <h3>Détail par code postal</h3>
      </div>
      ${buildTerritoriesTableHtml(territories)}
    </section>
  `;
}

async function renderProfessionalClustersPanel(forceReload = false) {
  const panel = document.getElementById("professionalClustersPanel");
  if (!panel) {
    return;
  }

  const periodKey = getPeriodQueryParam() || "__no_period__";
  const alreadyHydrated = (
    panel.dataset.professionalClustersHydrated === "true"
    && panel.dataset.professionalClustersPeriodKey === periodKey
  );

  if (alreadyHydrated && !forceReload) {
    window.requestAnimationFrame(() => {
      renderProfessionalConsumptionMapCanvas();

      if (
        appState.userPostalClustersMap
        && typeof appState.userPostalClustersMap.resize === "function"
      ) {
        appState.userPostalClustersMap.resize();
      }

      if (appState.cartography?.map && typeof appState.cartography.map.resize === "function") {
        appState.cartography.map.resize();
      }
    });
    return;
  }

  destroyCartographyMap();
  destroyUserPostalClustersMap();

  panel.dataset.professionalClustersHydrated = "false";
  panel.dataset.professionalClustersPeriodKey = periodKey;
  panel.innerHTML = buildProfessionalClustersLoadingHtml();

  try {
    const userPostalClustersQuery = getPeriodQueryParam()
      ? `${getPeriodQueryParam()}&min_individuals=5`
      : "?min_individuals=5";

    const [cartographyData, territoriesData, userPostalClustersData] = await Promise.all([
      apiGet(`/api/professionals-map${getPeriodQueryParam()}`),
      apiGet(`/api/territories/zip${getPeriodQueryParam()}`),
      apiGet(`/api/user-postal-clusters${userPostalClustersQuery}`)
    ]);

    appState.cartography.data = cartographyData;
    appState.territories.data = territoriesData;
    appState.userPostalClustersData = userPostalClustersData;

    panel.innerHTML = buildProfessionalClustersPanelHtml(
      cartographyData,
      territoriesData,
      appState.professionalConsumptionMap,
      userPostalClustersData
    );

    panel.dataset.professionalClustersHydrated = "true";

    const professionals = Array.isArray(cartographyData?.professionals)
      ? cartographyData.professionals
      : [];

    window.requestAnimationFrame(() => {
      renderProfessionalConsumptionMapCanvas();
      initializeUserPostalClustersMap(userPostalClustersData?.heatmap_points || []);
      initializeProfessionalsMap(professionals);
      bindProfessionalClusterMapZoomButtons();
      bindProfessionalClustersMapPairResizeSync();
      syncProfessionalClustersMapPairHeights();
      window.setTimeout(syncProfessionalClustersMapPairHeights, 180);
    });
  } catch (error) {
    console.warn(
      "Cartographie des clusters indisponible dans la vue Professionnels & particuliers.",
      error
    );
    panel.innerHTML = buildProfessionalClustersErrorHtml();
    panel.dataset.professionalClustersHydrated = "false";
  }
}


function buildProfessionalSectorAnalysisLoadingHtml() {
  return `
    <section class="card professional-analysis-roadmap-card">
      <div class="professional-analysis-section-heading">
        <div class="stat-label">Analyse sectorielle</div>
        <h3>Chargement des répartitions par secteur…</h3>
        <p>
          Les données sont recalculées pour la période actuellement sélectionnée.
        </p>
      </div>
    </section>
  `;
}

function buildProfessionalSectorAnalysisErrorHtml() {
  return `
    <section class="card professional-analysis-roadmap-card">
      <div class="professional-analysis-section-heading">
        <div class="stat-label">Analyse sectorielle</div>
        <h3>Les données sectorielles ne sont pas disponibles</h3>
        <p>
          L’analyse par secteur n’a pas pu être chargée pour cette période.
          Les autres onglets restent utilisables.
        </p>
      </div>
    </section>
  `;
}

function buildProfessionalSectorAnalysisPanelHtml(sectorsData = null) {
  const sectorPayload = sectorsData || {};
  const summary = sectorPayload.summary || {};
  const sectors = Array.isArray(sectorPayload.sectors)
    ? sectorPayload.sectors
    : [];

  return `
    <section class="card sector-overview-card">
      <div class="sector-overview-header">
        <div>
          <div class="stat-label">Activité monétaire par secteur principal</div>
          <h2>${Number(summary.sector_count || 0).toLocaleString("fr-FR")} secteurs analysés</h2>
          <p>
            Cette lecture répartit l’activité numérique des professionnels par secteur principal :
            volume reçu, volume réémis, réutilisation et origine des recettes.
          </p>
        </div>

        <div class="sector-kpis">
          <div class="sector-kpi">
            <strong>${Number(summary.professionals_with_sector || 0).toLocaleString("fr-FR")}</strong>
            <span>pros sectorisés</span>
          </div>
          <div class="sector-kpi">
            <strong>${Number(summary.active_professionals_with_sector || 0).toLocaleString("fr-FR")}</strong>
            <span>pros actifs sectorisés</span>
          </div>
          <div class="sector-kpi">
            <strong>${formatSectorPercent(summary.overall_reuse_rate)}</strong>
            <span>réutilisation globale</span>
          </div>
        </div>
      </div>

      <div class="sector-flow-grid">
        <div class="sector-flow-card">
          <span>Gonettes reçues</span>
          <strong>${euro(summary.total_received_volume || 0)}</strong>
        </div>
        <div class="sector-flow-card">
          <span>Gonettes émises</span>
          <strong>${euro(summary.total_emitted_volume || 0)}</strong>
        </div>
        <div class="sector-flow-card">
          <span>Volume total brassé</span>
          <strong>${euro(summary.total_flow_volume || 0)}</strong>
        </div>
      </div>

      <div class="sector-quality-note">
        ${Number(summary.professionals_without_sector || 0).toLocaleString("fr-FR")} professionnel(s)
        restent sans secteur principal renseigné.
        Sur les recettes sectorialisées :
        ${euro(summary.total_c2b_received_volume || 0)} proviennent des particuliers,
        ${euro(summary.total_b2b_received_volume || 0)} des autres professionnels.
      </div>
    </section>

    <section class="card sector-ranking-card">
      <div class="sector-section-heading">
        <h3>Principaux secteurs par gonettes reçues</h3>
      </div>
      ${buildSectorRankingHtml(sectors)}
    </section>

    <section class="card sector-mix-card">
      <div class="sector-section-heading">
        <h3>Origine des recettes : C2B / B2B</h3>
      </div>
      ${buildSectorReceiptsMixHtml(sectors)}
    </section>

    <section class="card sector-table-card">
      <div class="sector-section-heading">
        <h3>Détail par secteur</h3>
      </div>
      ${buildSectorsTableHtml(sectors)}
    </section>
  `;
}

async function renderProfessionalSectorAnalysisPanel(forceReload = false) {
  const panel = document.getElementById("professionalSectorAnalysisPanel");
  if (!panel) {
    return;
  }

  const periodKey = getPeriodQueryParam() || "__no_period__";
  const alreadyHydrated = (
    panel.dataset.professionalSectorAnalysisHydrated === "true"
    && panel.dataset.professionalSectorAnalysisPeriodKey === periodKey
  );

  if (alreadyHydrated && !forceReload) {
    return;
  }

  panel.dataset.professionalSectorAnalysisHydrated = "false";
  panel.dataset.professionalSectorAnalysisPeriodKey = periodKey;
  panel.innerHTML = buildProfessionalSectorAnalysisLoadingHtml();

  try {
    const sectorsData = await apiGet(
      `/api/sectors/activity${getPeriodQueryParam()}`
    );

    appState.sectors.data = sectorsData;
    panel.innerHTML = buildProfessionalSectorAnalysisPanelHtml(sectorsData);
    panel.dataset.professionalSectorAnalysisHydrated = "true";
  } catch (error) {
    console.warn(
      "Analyse sectorielle indisponible dans la vue Professionnels & particuliers.",
      error
    );
    panel.innerHTML = buildProfessionalSectorAnalysisErrorHtml();
    panel.dataset.professionalSectorAnalysisHydrated = "false";
  }
}

function setProfessionalAnalysisTab(tabName) {
  appState.professionalsViewTab = tabName || "summary";
  updateProfessionalAnalysisTabs();

  if (appState.professionalsViewTab === "circulation") {
    window.requestAnimationFrame(() => {
      renderProfessionalCirculationCharts();
    });
  }

  if (appState.professionalsViewTab === "network") {
    window.requestAnimationFrame(() => {
      void renderProfessionalNetworkPanel(false);
    });
  }

  if (appState.professionalsViewTab === "clusters") {
    window.requestAnimationFrame(() => {
      void renderProfessionalClustersPanel(false);
    });
  }

  if (appState.professionalsViewTab === "structures") {
    window.requestAnimationFrame(() => {
      void renderProfessionalSectorAnalysisPanel(false);
    });
  }
}

function bindProfessionalAnalysisTabs() {
  document.querySelectorAll("[data-professional-analysis-tab]").forEach((button) => {
    if (button.dataset.bound === "true") {
      return;
    }

    button.addEventListener("click", () => {
      const tabName = button.dataset.professionalAnalysisTab || "summary";
      setProfessionalAnalysisTab(tabName);
    });

    button.dataset.bound = "true";
  });
}

function updateProfessionalAnalysisTabs() {
  const activeTab = appState.professionalsViewTab || "summary";

  document.querySelectorAll("[data-professional-analysis-tab]").forEach((button) => {
    const isActive = button.dataset.professionalAnalysisTab === activeTab;
    button.classList.toggle("professional-analysis-tab-btn-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });

  document.querySelectorAll("[data-professional-analysis-panel]").forEach((panel) => {
    const isActive = panel.dataset.professionalAnalysisPanel === activeTab;
    panel.classList.toggle("hidden", !isActive);
  });
}

async function renderProsView(forceReload = false) {
  const preserveVisibleView = shouldPreservePeriodRefreshView(
    "pros",
    forceReload
  );

  // La vue Pros reconstruit son HTML à chaque rendu / changement de période.
  // Lors d'un refresh doux, on conserve l'ancienne vue affichée pendant le chargement,
  // puis on détruit les charts juste avant le remplacement effectif du DOM.
  if (!preserveVisibleView) {
    destroyProfessionalCirculationCharts();
    destroyCartographyMap();
  }

  appState.currentView = "pros";
  syncSidebarView("pros");
  setTitle("Professionnels & particuliers");

  const periodQuery = getPeriodQueryParam();

  const shouldLoadProsData = (
    forceReload
    || appState.prosData.length === 0
  );

  const shouldLoadProfessionalActivityFlowSummary = (
    forceReload
    || !appState.professionalActivityFlowSummary
    || appState.professionalActivityFlowSummaryPeriodKey !== periodQuery
  );

  const shouldLoadProfessionalHoldingsSummary = (
    forceReload
    || !appState.professionalHoldingsSummary
    || appState.professionalHoldingsSummaryPeriodKey !== periodQuery
  );

  const shouldLoadProfessionalPilotageSummary = (
    forceReload
    || !appState.professionalPilotageSummary
    || appState.professionalPilotageSummaryPeriodKey !== periodQuery
  );

  const shouldLoadProfessionalCirculationTimeseries = (
    forceReload
    || !appState.professionalCirculationTimeseries
    || appState.professionalCirculationTimeseriesPeriodKey !== periodQuery
  );

  const shouldLoadProfessionalReuseYearlySummary = (
    forceReload
    || !appState.professionalReuseYearlySummary
  );

  const shouldLoadProfessionalChainFateSummary = (
    forceReload
    || !appState.professionalChainFateSummary
  );

  const professionalConsumptionMapQuery = periodQuery
    ? `${periodQuery}&min_users=2`
    : "?min_users=2";

  const shouldLoadProfessionalConsumptionMap = (
    forceReload
    || !appState.professionalConsumptionMap
    || appState.professionalConsumptionMapPeriodKey !== professionalConsumptionMapQuery
  );

  if (shouldLoadProsData && !preserveVisibleView) {
    content.innerHTML = `<div class="card">Chargement.</div>`;
  }

  const prosDataPromise = shouldLoadProsData
    ? apiGet(`/api/pros${periodQuery}`).then((data) => {
        appState.prosData = data;
      })
    : Promise.resolve();

  const professionalActivityFlowSummaryPromise = shouldLoadProfessionalActivityFlowSummary
    ? apiGet(`/api/professionals/activity-summary${periodQuery}`).then((data) => {
        appState.professionalActivityFlowSummary = data;
        appState.professionalActivityFlowSummaryPeriodKey = periodQuery;
      })
    : Promise.resolve();

  const professionalHoldingsSummaryPromise = shouldLoadProfessionalHoldingsSummary
    ? (async () => {
        try {
          appState.professionalHoldingsSummary = await apiGet(
            `/api/monetary-indicators/pilotage-holdings-summary${periodQuery}`
          );
        } catch (error) {
          console.warn(
            "Synthèse de détention indisponible pour la vue professionnels.",
            error
          );
          appState.professionalHoldingsSummary = null;
        }

        appState.professionalHoldingsSummaryPeriodKey = periodQuery;
      })()
    : Promise.resolve();

  const professionalPilotageSummaryPromise = shouldLoadProfessionalPilotageSummary
    ? (async () => {
        try {
          appState.professionalPilotageSummary = await apiGet(
            `/api/monetary-indicators/pilotage-summary${periodQuery}`
          );
        } catch (error) {
          console.warn(
            "Synthèse de pilotage indisponible pour la vue professionnels.",
            error
          );
          appState.professionalPilotageSummary = null;
        }

        appState.professionalPilotageSummaryPeriodKey = periodQuery;
      })()
    : Promise.resolve();

  const professionalCirculationTimeseriesPromise = shouldLoadProfessionalCirculationTimeseries
    ? apiGet(`/api/professionals/circulation-timeseries${periodQuery}`).then((data) => {
        appState.professionalCirculationTimeseries = data;
        appState.professionalCirculationTimeseriesPeriodKey = periodQuery;
      })
    : Promise.resolve();

  const professionalReuseYearlySummaryPromise = shouldLoadProfessionalReuseYearlySummary
    ? apiGet("/api/monetary-indicators/pilotage-reuse-yearly").then((data) => {
        appState.professionalReuseYearlySummary = data;
      })
    : Promise.resolve();

  const professionalChainFateSummaryPromise = shouldLoadProfessionalChainFateSummary
    ? (async () => {
        try {
          appState.professionalChainFateSummary = await apiGet(
            "/api/professionals/chain-fate-summary"
          );
        } catch (error) {
          console.warn(
            "Résumé des trajectoires professionnelles indisponible.",
            error
          );
          appState.professionalChainFateSummary = null;
        }
      })()
    : Promise.resolve();

  const professionalConsumptionMapPromise = shouldLoadProfessionalConsumptionMap
    ? (async () => {
        try {
          appState.professionalConsumptionMap = await apiGet(
            `/api/professionals/consumption-map${professionalConsumptionMapQuery}`
          );
          appState.professionalConsumptionMapPeriodKey = professionalConsumptionMapQuery;
          resetProfessionalConsumptionMapRenderCaches();
          appState.professionalConsumptionMapRenderPayload =
            getProfessionalConsumptionMapFinalRenderPayload(
              appState.professionalConsumptionMap
            );
          appState.professionalConsumptionMapPlayer = null;

          if (!appState.professionalConsumptionMapViewMode) {
            appState.professionalConsumptionMapViewMode = "static";
          }
        } catch (error) {
          console.warn(
            "Carte des bassins de consommation U→P indisponible.",
            error
          );
          appState.professionalConsumptionMap = null;
          appState.professionalConsumptionMapRenderPayload = null;
          appState.professionalConsumptionMapPlayer = null;
          appState.professionalConsumptionMapViewMode = "static";
          resetProfessionalConsumptionMapRenderCaches();
          restoreProfessionalConsumptionMapDynamicTheme();
          appState.professionalConsumptionMapPeriodKey = professionalConsumptionMapQuery;
        }
      })()
    : Promise.resolve();

  await Promise.all([
    prosDataPromise,
    professionalActivityFlowSummaryPromise,
    professionalHoldingsSummaryPromise,
    professionalPilotageSummaryPromise,
    professionalCirculationTimeseriesPromise,
    professionalReuseYearlySummaryPromise,
    professionalChainFateSummaryPromise,
    professionalConsumptionMapPromise
  ]);

  if (preserveVisibleView) {
    destroyProfessionalCirculationCharts();
    destroyCartographyMap();
  }

  content.innerHTML = buildProfessionalAnalysisShell(
    appState.professionalActivityFlowSummary,
    appState.professionalHoldingsSummary,
    appState.professionalPilotageSummary,
    appState.professionalCirculationTimeseries,
    appState.professionalReuseYearlySummary,
    appState.professionalChainFateSummary,
    appState.professionalConsumptionMap
  );
  drawProsTable();
  bindProfessionalAnalysisTabs();
  updateProfessionalAnalysisTabs();

  if (appState.professionalsViewTab === "circulation") {
    window.requestAnimationFrame(() => {
      renderProfessionalCirculationCharts();
    });
  }

  if (appState.professionalsViewTab === "network") {
    window.requestAnimationFrame(() => {
      void renderProfessionalNetworkPanel(forceReload);
    });
  }

  if (appState.professionalsViewTab === "clusters") {
    window.requestAnimationFrame(() => {
      void renderProfessionalClustersPanel(forceReload);
    });
  }

  if (appState.professionalsViewTab === "structures") {
    window.requestAnimationFrame(() => {
      void renderProfessionalSectorAnalysisPanel(forceReload);
    });
  }
}

function getDailyChartDatasets(charts, metric = "count") {
  const isVolume = metric === "volume";

  return [
    {
      label: "Activité économique",
      data: isVolume
        ? (charts.daily.activity_amount_values || charts.daily.payment_amount_values || [])
        : (charts.daily.activity_values || charts.daily.payment_values || charts.daily.values || []),
      fill: false,
      tension: 0.25
    },
    {
      label: "Alimentation du circuit",
      data: isVolume
        ? (charts.daily.inflow_amount_values || charts.daily.conversion_amount_values || [])
        : (charts.daily.inflow_values || charts.daily.conversion_values || []),
      fill: false,
      tension: 0.25
    },
    {
      label: "Sorties du circuit",
      data: isVolume
        ? (charts.daily.outflow_amount_values || charts.daily.reconversion_amount_values || [])
        : (charts.daily.outflow_values || charts.daily.reconversion_values || []),
      fill: false,
      tension: 0.25
    },
    {
      label: "Opérations associatives / techniques",
      data: isVolume
        ? (charts.daily.non_economic_amount_values || charts.daily.regularization_amount_values || [])
        : (charts.daily.non_economic_values || charts.daily.regularization_values || []),
      fill: false,
      tension: 0.25
    }
  ];
}


const PROFESSIONAL_CONSUMPTION_MAP_HELP = {
  title: "Répartition territoriale des flux U→P — trajectoires U→P",
  summary: "Cette carte représente une géographie agrégée des paiements des particuliers vers les professionnels. Elle ne montre jamais les adresses réelles des utilisateurs : les origines sont synthétiques et réparties à l’intérieur de bassins postaux.",
  usefulness: "Elle aide à comprendre d’où convergent les consommations en Gonettes numériques, quels professionnels captent des flux issus de plusieurs bassins d’usage, et comment certains itinéraires de consommation se créent puis se renforcent dans le temps.",
  reading: [
    "Chaque faisceau relie un bassin postal d’origine à un professionnel destinataire.",
    "Les points rouges ne sont pas des domiciles : ce sont des points-source graphiques synthétiques, placés dans le périmètre postal afin de rendre la carte lisible.",
    "Les nœuds verts correspondent aux professionnels recevant les paiements U→P représentés.",
    "En mode dynamique, une route se trace de U vers P lorsqu’elle devient visible ; une petite particule lumineuse en marque la tête.",
    "Une route qui est de plus en plus empruntée gagne progressivement en présence lumineuse : la carte ne montre donc pas seulement la création de liens, mais aussi leur fréquentation."
  ],
  crossReading: [
    "À lire avec les indicateurs de paiements U→P de l’onglet Circulation & multiplicateur.",
    "À croiser avec les analyses de territoires et de secteurs pour comprendre quels types de professionnels polarisent certains bassins de consommation.",
    "À rapprocher, plus tard, de l’onglet B2B : ici on observe la consommation des particuliers vers les pros, pas la circulation interprofessionnelle."
  ],
  pilotage: [
    "Un professionnel recevant des flux depuis de nombreux bassins peut jouer un rôle d’attraction au-delà de sa proximité immédiate.",
    "Des faisceaux denses et répétitifs peuvent signaler des couloirs de consommation stabilisés.",
    "Des zones postales faiblement reliées ou absentes peuvent inviter à questionner la couverture territoriale du réseau, en gardant à l’esprit que la carte ne représente que les flux cartographiables."
  ],
  perimeter: [
    "Périmètre : transactions U→P cartographiables sur la période sélectionnée dans le filtre latéral.",
    "Origines : codes postaux de particuliers disponibles via l’enrichissement Odoo, représentés par des points synthétiques.",
    "Destinations : professionnels dont la géolocalisation Cyclos est confirmée.",
    "Seuil de confidentialité : un faisceau n’est affiché qu’à partir de 2 particuliers distincts."
  ],
  formulas: [
    "Faisceau visible = code postal d’origine → professionnel destinataire, si au moins 2 particuliers distincts contribuent au lien.",
    "Carte dynamique = construction cumulative des faisceaux au fil de la période sélectionnée.",
    "Intensification visuelle = combinaison majoritairement fondée sur la fréquence cumulée des paiements, complétée par le volume cumulé.",
    "Les points-source synthétiques sont déterministes : ils restent stables d’un affichage à l’autre, sans représenter de localisation individuelle."
  ],
  sources: [
    "/api/professionals/consumption-map",
    "transactions filtrées sur U→P",
    "odoo_individual_enrichment.zip",
    "odoo_professional_enrichment.cyclos_latitude / cyclos_longitude",
    "server/data/consumption_postal_areas.json"
  ]
};

const STATS_CHART_DEFAULT_METRICS = {
  globalDailyCount: "count",
  activityWeeklyFlows: "volume",
  cumulativeActivity: "volume",
  hourlyActivity: "count",
  weekdayActivity: "count",
  circuitMonthlyFlows: "volume",
  circuitInflowDestinations: "volume",
  circuitCumulativeFlows: "volume",
  circuitNetGap: "volume",
  operationsMonthlyFamilies: "volume",
  operationsMonthlyOperatorProfiles: "volume",
  operationsStructuralFlowDistribution: "volume"
};

const STATS_CHART_HELP = {
  pilotageLm3History: {
    title: "LM3 estimé — profondeur de propagation des alimentations",
    summary: "Ce graphe représente la capacité de propagation des Gonettes nouvellement injectées. Il décompose le LM3 annuel en trois étages : dépense initiale, réemploi de deuxième vague et réemploi de troisième vague.",
    usefulness: "Il permet de distinguer une injection monétaire simplement dépensée une fois d’une injection qui continue de générer des recettes dans le réseau. C’est un indicateur très utile pour évaluer la profondeur des chaînes de circulation issues des alimentations.",
    reading: [
      "La base fixe à 1,000× correspond à la dépense initiale des Gonettes converties.",
      "Le segment « vague 2 » mesure les recettes supplémentaires générées par les acteurs directement atteints.",
      "Le segment « vague 3 » mesure la propagation supplémentaire au niveau suivant.",
      "La hauteur totale de la barre correspond au LM3 estimé."
    ],
    crossReading: [
      "À comparer au « Multiplicateur interne estimé » : celui-ci décrit le fonctionnement moyen de tout le réseau, tandis que le LM3 se concentre sur les Gonettes nouvellement injectées.",
      "À lire avec les volumes d’alimentations : davantage d’entrées ne produisent pas automatiquement un LM3 plus élevé.",
      "À croiser avec les acteurs P2 / P3 et, à terme, avec les secteurs ou territoires atteints."
    ],
    pilotage: [
      "Une hausse du LM3 signifie que les injections se propagent plus loin dans le réseau.",
      "Une baisse du LM3 malgré des alimentations élevées peut révéler un affaiblissement des débouchés de réemploi ou une propagation plus courte.",
      "Cet indicateur est particulièrement précieux pour analyser des dispositifs ciblés d’injection monétaire."
    ],
    perimeter: [
      "Calcul annuel à partir des conversions / alimentations A/C → P/U et des paiements économiques internes.",
      "Les propensions individuelles de réemploi sont bornées à 100 % pour éviter de surattribuer des dépenses issues d’un stock antérieur.",
      "Le calcul constitue une estimation transactionnelle du LM3, pas un traçage littéral de chaque unité de monnaie."
    ],
    formulas: [
      "LM3 = 1 + gain de vague 2 + gain de vague 3.",
      "Vague 2 = réemploi pondéré des acteurs atteints par P1.",
      "Vague 3 = réemploi pondéré propagé depuis P2 vers P3."
    ],
    sources: [
      "pilotage-lm3-yearly.items[].lm3_estimated",
      "pilotage-lm3-yearly.items[].wave_2",
      "pilotage-lm3-yearly.items[].wave_3",
      "pilotage-lm3-yearly.items[].p3_actor_count"
    ]
  },

  pilotageInternalReuseHistory: {
    title: "Réemploi interne & multiplicateur estimé — trajectoire annuelle",
    summary: "Ce graphe suit l’évolution annuelle de la capacité de recirculation économique du réseau : d’un côté la part pondérée des recettes réemployées, de l’autre le multiplicateur interne estimé qui en découle.",
    usefulness: "Il permet de voir si le réseau se structure progressivement autour de chaînes de redépense internes plus fortes. Une hausse durable du réemploi et du multiplicateur signale une circulation plus enracinée dans l’économie du réseau.",
    crossReading: [
      "Croisez cette trajectoire avec l’évolution de l’activité économique annuelle et du nombre d’acteurs receveurs pour distinguer croissance de volume et densification réelle du réemploi.",
      "Comparez le réseau global et les professionnels : le réemploi professionnel est souvent le signal le plus stratégique pour lire les capacités de débouchés internes.",
      "À lire avec les indicateurs de rotation économique : rotation et réemploi ne mesurent pas la même chose, mais racontent ensemble la vitalité de la circulation."
    ],
    reading: [
      "Les courbes pleines lisent la propension pondérée de réemploi interne en pourcentage.",
      "Les courbes en pointillés lisent le multiplicateur interne estimé dérivé par k = 1 / (1 - c).",
      "Les années marquées d’un astérisque sont partielles ; elles doivent être comparées avec prudence aux années complètes."
    ],
    perimeter: [
      "Le calcul porte sur les seules transactions d’activité économique retenues dans MLCFlux.",
      "Les recettes sont suivies acteur par acteur ; le volume réemployé est borné à 100 % par acteur avant pondération.",
      "Ce multiplicateur n’est pas encore le LM3 d’injection : il mesure une capacité moyenne de recirculation interne."
    ],
    formulas: [
      "Réemploi acteur = min(dépenses économiques internes, recettes économiques internes).",
      "Propension pondérée c = somme des réemplois bornés / somme des recettes économiques internes.",
      "Multiplicateur interne estimé k = 1 / (1 - c)."
    ],
    sources: [
      "pilotage-reuse-yearly.items[].global.weighted_internal_reuse_propensity",
      "pilotage-reuse-yearly.items[].global.internal_multiplier_estimated",
      "pilotage-reuse-yearly.items[].professionals.weighted_internal_reuse_propensity",
      "pilotage-reuse-yearly.items[].professionals.internal_multiplier_estimated"
    ]
  },

  pilotageRotation: {
    title: "Rotation économique annualisée",
    summary: "Ce graphe mesure mois par mois l’intensité de circulation de la Gonette numérique, rapportée à la masse disponible puis annualisée de manière indicative.",
    usefulness: "Cet indicateur aide à évaluer si la masse numérique disponible produit effectivement de l’activité économique. Il permet de distinguer une monnaie simplement présente en stock d’une monnaie réellement mobilisée dans les échanges.",
    crossReading: [
      "Croisez ce graphe avec la « Masse numérique moyenne » et le « Volume d’activité économique » de la Synthèse : une rotation qui baisse peut refléter une hausse récente de la masse plus rapide que l’activité.",
      "Comparez-le à la « Rétention nette des alimentations » : conserver davantage de Gonettes dans le circuit n’est réellement positif que si elles continuent aussi à circuler.",
      "Lisez-le avec les indicateurs « Activité générée pour 1 G alimenté » et « Activité générée pour 1 G sorti » dans l’onglet Circulation & rendement."
    ],
    reading: [
      "Chaque point correspond à un mois de la période de pilotage effective.",
      "Plus la courbe est haute, plus l’activité économique produite est importante au regard de la masse numérique moyenne disponible.",
      "La ligne en pointillés reprend la référence moyenne de la période sélectionnée.",
      "Un mois marqué d’un astérisque est incomplet : son ratio est ramené à une logique annualisée indicative."
    ],
    perimeter: [
      "Activité économique numérique retenue dans le périmètre MLCFlux.",
      "Masse numérique moyenne issue des stocks quotidiens Odoo sur le mois concerné.",
      "Les périodes partielles sont signalées dans les libellés et dans les infobulles."
    ],
    formulas: [
      "Intensité mensuelle = volume d’activité économique du mois / masse numérique moyenne du mois.",
      "Rotation annualisée indicative = intensité mensuelle × facteur d’annualisation lié à la durée couverte."
    ],
    sources: [
      "pilotage-timeseries.month_key",
      "pilotage-timeseries.day_count",
      "pilotage-timeseries.annualized_economic_activity_intensity_indicative",
      "pilotage-summary.pilotage_metrics.circulation"
    ]
  },

  pilotageFlowRhythm: {
    title: "Rythme des alimentations et des sorties",
    summary: "Ce graphe compare, mois par mois, les entrées et les sorties du circuit numérique en les ramenant à un équivalent 30 jours.",
    usefulness: "Ce graphique permet de voir si le circuit numérique est, mois après mois, davantage alimenté ou davantage vidé par les reconversions. Il est utile pour repérer des changements de rythme, des périodes de tension ou l’effet visible d’une dynamique d’injection.",
    crossReading: [
      "Croisez-le avec le graphe « Rétention nette des alimentations » : de fortes entrées sont plus intéressantes lorsqu’elles ne sont pas rapidement compensées par des sorties.",
      "Comparez-le aux indicateurs « Sorties / alimentations », « Pression d’alimentation » et « Pression de sortie » dans ce même onglet.",
      "Lisez-le avec la « Couverture apparente des reconversions » : une hausse des sorties prend un sens différent selon la robustesse apparente du fonds de garantie face à ce rythme."
    ],
    reading: [
      "Les alimentations apparaissent au-dessus de zéro.",
      "Les sorties apparaissent en dessous de zéro afin de visualiser immédiatement la tension entre entrées et sorties.",
      "Des barres plus longues signalent un rythme plus soutenu sur le mois considéré.",
      "Les mois incomplets sont ramenés en équivalent 30 jours pour rester comparables aux mois pleins."
    ],
    perimeter: [
      "Alimentations : entrées numériques du circuit retenues dans les flux Cyclos.",
      "Sorties : reconversions / sorties professionnelles retenues dans les flux Cyclos.",
      "Le graphe décrit des rythmes de flux, pas un stock monétaire."
    ],
    formulas: [
      "Alimentations équiv. 30 jours = volume alimenté observé / jours couverts × 30.",
      "Sorties équiv. 30 jours = volume sorti observé / jours couverts × 30."
    ],
    sources: [
      "pilotage-timeseries.month_key",
      "pilotage-timeseries.day_count",
      "pilotage-timeseries.inflow_volume",
      "pilotage-timeseries.outflow_volume"
    ]
  },

  pilotageRetention: {
    title: "Rétention nette des alimentations",
    summary: "Ce graphe mesure, mois par mois, la part nette des Gonettes nouvellement alimentées qui reste dans le circuit après déduction des sorties observées.",
    usefulness: "Cet indicateur aide à apprécier la capacité apparente du circuit à conserver une partie des Gonettes nouvellement alimentées au lieu de les voir ressortir immédiatement. Il renseigne sur la stabilité du flux entrant, mais pas à lui seul sur sa qualité de circulation.",
    crossReading: [
      "Croisez-le avec la « Rotation économique annualisée » : une rétention élevée est plus convaincante si l’activité économique reste dynamique.",
      "Comparez-le au graphe « Rythme des alimentations et des sorties » et au « Flux net relatif à la masse moyenne » pour comprendre si la rétention vient d’un afflux d’entrées, d’un ralentissement des sorties, ou des deux.",
      "À terme, cette lecture devra aussi être confrontée à la « Masse active / dormante » et à la « Distribution des soldes » dans l’onglet Détention & ancrage."
    ],
    reading: [
      "Une barre positive signifie que les alimentations du mois dépassent les sorties.",
      "Une barre négative signifie que les sorties dépassent les alimentations.",
      "Une valeur élevée ne prouve pas à elle seule une bonne circulation : elle doit être lue avec la rotation économique.",
      "Les mois incomplets restent comparables, mais leur lecture doit rester prudente."
    ],
    perimeter: [
      "Calcul fondé sur les volumes d’alimentations et de sorties identifiés dans Cyclos.",
      "Il s’agit d’un ratio de rétention des flux, pas d’une mesure directe de masse monétaire active.",
      "Les mois partiels sont signalés par un astérisque."
    ],
    formulas: [
      "Rétention nette = (alimentations − sorties) / alimentations × 100."
    ],
    sources: [
      "pilotage-timeseries.month_key",
      "pilotage-timeseries.day_count",
      "pilotage-timeseries.net_inflow_retention_rate",
      "pilotage-timeseries.inflow_volume",
      "pilotage-timeseries.outflow_volume"
    ]
  },

  pilotageHoldingsMassComposition: {
    title: "Composition de la masse numérique par catégorie de détenteurs",
    summary: "Ce graphe montre comment la masse numérique moyenne se répartit entre les particuliers, les professionnels du réseau, les comptes entreprise Gonette et un reste non encore ventilé.",
    usefulness: "Il donne une lecture structurelle de la détention : non pas combien de Gonettes circulent pendant le mois, mais où la monnaie numérique est, en moyenne, portée dans le circuit.",
    reading: [
      "Chaque barre représente 100 % de la masse numérique moyenne du mois.",
      "Le bleu correspond à la part portée par les particuliers, le rose à celle portée par les professionnels du réseau, l’orange aux comptes entreprise Gonette.",
      "La part « reste non encore ventilé » correspond à la fraction de masse numérique qui n’est pas expliquée par ces trois agrégats de soldes positifs.",
      "Une hausse de la part professionnelle indique que les pros portent une fraction plus importante de la masse numérique moyenne ; elle ne dit pas, à elle seule, si cette monnaie est rapidement redépensée."
    ],
    crossReading: [
      "À lire avec le graphe « Stocks numériques moyens par catégorie de détenteurs » : la composition donne les parts relatives, les stocks donnent les volumes absolus.",
      "À croiser avec les indicateurs de circulation économique : une masse fortement détenue par les professionnels n’est pleinement interprétable qu’en regard du réemploi interne, des paiements P→P et des reconversions.",
      "À rapprocher de l’onglet « Entrées, sorties & garanties » pour comprendre l’évolution de la masse numérique totale qui sert de dénominateur."
    ],
    pilotage: [
      "Une part professionnelle élevée peut signaler un ancrage de la monnaie dans le cœur économique du réseau, mais mérite d’être confrontée à la capacité de redépense des pros.",
      "Une hausse durable de la part particulière peut indiquer davantage de monnaie en attente d’usage côté utilisateurs, ou une croissance de la détention active ; la dormance permet de trancher partiellement.",
      "Le reste non ventilé est méthodologiquement important : s’il varie fortement, il faut surveiller le périmètre d’extraction et les catégories encore non rapprochées."
    ],
    perimeter: [
      "Les parts sont calculées sur les moyennes journalières alignées entre les soldes Cyclos disponibles et la masse numérique quotidienne Odoo.",
      "Les stocks affichés correspondent à des soldes positifs moyens agrégés par catégorie.",
      "La masse numérique de référence est issue des indicateurs comptables Odoo."
    ],
    formulas: [
      "Part particuliers = stock positif particulier moyen / masse numérique moyenne.",
      "Part professionnels du réseau = stock positif professionnel moyen hors P0000 / P9999 / masse numérique moyenne.",
      "Part comptes entreprise Gonette = stock positif moyen P0000 / P9999 / masse numérique moyenne.",
      "Reste non ventilé = 100 % − parts particulières − parts professionnelles − parts comptes entreprise Gonette."
    ],
    sources: [
      "pilotage-holdings-timeseries.items[].average_user_stock_share_of_numeric_mass",
      "pilotage-holdings-timeseries.items[].average_professional_network_stock_share_of_numeric_mass",
      "pilotage-holdings-timeseries.items[].average_gonette_business_accounts_stock_share_of_numeric_mass",
      "pilotage-holdings-timeseries.items[].average_numeric_mass"
    ]
  },

  pilotageHoldingsStockShare: {
    title: "Stocks numériques moyens par catégorie de détenteurs",
    summary: "Ce graphe suit, mois par mois, le volume moyen de Gonettes numériques détenu par les particuliers, les professionnels du réseau et les comptes entreprise Gonette.",
    usefulness: "Il permet de lire la détention en valeur absolue. Là où le graphe de composition montre des parts relatives, celui-ci montre le poids réel des stocks détenus et leurs déplacements au fil du temps.",
    reading: [
      "Chaque point correspond au stock positif moyen détenu pendant le mois par la catégorie concernée.",
      "La courbe des particuliers renseigne la quantité moyenne de Gonettes numériques stationnant chez les utilisateurs.",
      "La courbe des professionnels du réseau mesure la détention moyenne dans le tissu économique, hors comptes P0000 / P9999.",
      "La courbe des comptes entreprise Gonette isole les stocks présents sur les comptes opérateurs P0000 / P9999."
    ],
    crossReading: [
      "À lire avec le graphe de composition : un stock peut augmenter en valeur absolue tout en représentant une part stable ou décroissante de la masse numérique totale.",
      "À croiser avec les alimentations et les sorties : une hausse du stock détenu peut venir d’une croissance de la masse, d’un ralentissement de la circulation, ou des deux.",
      "À rapprocher de la masse active / dormante pour distinguer la détention particulière récente d’un stock qui s’éloigne de l’usage."
    ],
    pilotage: [
      "Une hausse du stock professionnel peut être positive si elle accompagne davantage de réemploi interne ; elle peut être plus préoccupante si elle coexiste avec des reconversions croissantes ou un affaiblissement du P→P.",
      "Une hausse du stock particulier n’est pas automatiquement une bonne ou une mauvaise nouvelle : elle peut refléter une confiance accrue, une accumulation préalable à la dépense, ou une mise en sommeil.",
      "L’évolution des comptes entreprise Gonette mérite d’être lue comme un signal opérateur spécifique, distinct de la détention du réseau professionnel ordinaire."
    ],
    perimeter: [
      "Stocks positifs moyens calculés sur les jours effectivement alignés avec la masse numérique quotidienne Odoo.",
      "Les professionnels du réseau excluent les comptes P0000 et P9999.",
      "Les comptes entreprise Gonette correspondent ici à P0000 / P9999."
    ],
    formulas: [
      "Stock particulier moyen = moyenne journalière des soldes positifs particuliers agrégés.",
      "Stock professionnel du réseau moyen = moyenne journalière des soldes positifs professionnels, hors P0000 / P9999.",
      "Stock comptes entreprise Gonette moyen = moyenne journalière des soldes positifs P0000 / P9999."
    ],
    sources: [
      "pilotage-holdings-timeseries.items[].average_positive_user_stock",
      "pilotage-holdings-timeseries.items[].average_positive_professional_network_stock",
      "pilotage-holdings-timeseries.items[].average_positive_gonette_business_accounts_stock"
    ]
  },

  pilotageHoldingsDormancy: {
    title: "Masse particulière active / dormante",
    summary: "Ce graphe répartit le stock positif particulier à la clôture de chaque mois selon l’ancienneté de la dernière activité du compte : actif récent, dormance intermédiaire ou dormance plus longue.",
    usefulness: "Il permet de dépasser une simple lecture du volume détenu par les particuliers. Deux mois peuvent afficher un stock particulier proche, tout en ayant une qualité d’ancrage très différente selon que ce stock reste vivant ou s’éloigne de l’activité récente.",
    reading: [
      "La partie « Actif ≤ 30 j » correspond aux soldes portés par des comptes ayant enregistré une activité récente.",
      "Les strates « Dormant 31–90 j », « Dormant 91–180 j » et « Dormant > 180 j » isolent des stocks de plus en plus éloignés de l’usage observé.",
      "Le graphe porte sur le stock particulier positif à la clôture du mois, et non sur une moyenne mensuelle.",
      "Un stock dormant n’est pas nécessairement perdu : il indique une absence de transaction récente, pas l’impossibilité d’un retour en circulation."
    ],
    crossReading: [
      "À lire avec le bloc « Masse active / dormante à la clôture », qui résume la situation en fin de période.",
      "À croiser avec la réactivation des stocks dormants : une dormance élevée n’a pas le même sens si une part importante de ces comptes se remet ensuite à transacter.",
      "À rapprocher de l’intensité de mobilisation du stock particulier : un stock très actif devrait, toutes choses égales par ailleurs, produire davantage de paiements vers les professionnels."
    ],
    pilotage: [
      "Une montée de la dormance longue peut signaler une difficulté à transformer la détention particulière en usage effectif.",
      "Une masse active forte suggère qu’une part importante du stock reste proche de la circulation, mais ne renseigne pas à elle seule sur la direction des paiements.",
      "Cet indicateur peut soutenir des stratégies de réactivation, de relance des usagers ou d’analyse de l’expérience d’usage côté particuliers."
    ],
    perimeter: [
      "Le calcul porte sur les comptes particuliers à solde positif à la date de clôture mensuelle retenue.",
      "La dormance est mesurée à partir de l’absence de transaction impliquant le compte particulier sur une fenêtre d’ancienneté.",
      "Les catégories sont exclusives : chaque compte est affecté à une seule classe de récence."
    ],
    formulas: [
      "Stock actif ≤ 30 j = somme des soldes positifs des comptes particuliers dont la dernière activité date de 30 jours ou moins.",
      "Stock dormant 31–90 j = somme des soldes positifs dont la dernière activité est comprise entre 31 et 90 jours.",
      "Stock dormant 91–180 j = somme des soldes positifs dont la dernière activité est comprise entre 91 et 180 jours.",
      "Stock dormant > 180 j = somme des soldes positifs dont la dernière activité dépasse 180 jours."
    ],
    sources: [
      "pilotage-holdings-timeseries.items[].dormancy_snapshot.buckets",
      "pilotage-holdings-summary.holdings_metrics.dormancy"
    ]
  },

  pilotageHoldingsMobilization: {
    title: "Intensité de mobilisation du stock particulier",
    summary: "Ce graphe mesure, mois par mois, combien de Gonettes sont payées vers les professionnels pour 100 G de stock particulier détenues en moyenne.",
    usefulness: "Il rapproche la détention particulière de son débouché économique. L’indicateur ne décrit pas la masse immobilisée en elle-même, mais l’intensité avec laquelle ce stock se traduit en paiements U→P.",
    reading: [
      "Une valeur de 60 G signifie que, sur le mois, 60 G de paiements vers les professionnels ont été observés pour 100 G de stock particulier moyen.",
      "Ce n’est pas un pourcentage : l’unité est « G dépensées vers les pros pour 100 G détenues en moyenne ».",
      "Une valeur supérieure à 100 est possible si le stock particulier tourne plusieurs fois au cours du mois.",
      "Une baisse de l’indicateur peut venir d’un ralentissement des paiements U→P, d’une hausse plus rapide du stock particulier moyen, ou d’une combinaison des deux."
    ],
    crossReading: [
      "À lire avec le graphe de stock particulier moyen : le dénominateur de l’indicateur peut évoluer fortement.",
      "À rapprocher de la masse active / dormante : un stock plus actif devrait contribuer davantage à la mobilisation, sans que la relation soit mécanique.",
      "À croiser avec les volumes U→P et avec la rotation économique globale afin de distinguer l’intensité spécifique de la mobilisation particulière de la vitalité générale du circuit."
    ],
    pilotage: [
      "Cet indicateur aide à savoir si la détention particulière constitue un réservoir effectivement mobilisé vers l’économie locale.",
      "Un repli durable peut inviter à regarder la disponibilité de débouchés professionnels, les usages de paiement, ou la croissance d’un stock particulier peu dépensé.",
      "Une hausse doit être interprétée avec le niveau de stock : elle peut traduire une meilleure mobilisation, mais aussi un stock moyen plus faible servant de dénominateur."
    ],
    perimeter: [
      "Numérateur : paiements économiques U→P observés sur le mois.",
      "Dénominateur : stock positif particulier moyen sur les jours alignés du mois.",
      "Les mois partiels sont calculés sur les jours effectivement disponibles et doivent être comparés avec prudence."
    ],
    formulas: [
      "Mobilisation = volume mensuel des paiements U→P / stock particulier moyen × 100.",
      "Unité de lecture = G vers les professionnels pour 100 G détenues en moyenne par les particuliers."
    ],
    sources: [
      "pilotage-holdings-timeseries.items[].economic_up_volume_per_100_g_average_user_stock",
      "pilotage-holdings-timeseries.items[].average_positive_user_stock",
      "pilotage-holdings-timeseries.items[].economic_up_volume"
    ]
  },

  globalDailyCount: {
    title: "Transactions par jour, par nature d’opération",
    summary: "Vue transversale des grands mouvements monétaires sur la période active.",
    perimeter: [
      "Activité économique : Compte / Compte Pro, hors flux vers Compte technique, hors P0000 et P9999.",
      "Alimentation du circuit : group_label = Émission.",
      "Sorties du circuit : Compte Pro · P→Compte technique.",
      "Opérations associatives / techniques : autres mouvements hors activité centrale."
    ],
    formulas: [
      "Nombre = nombre de transactions par jour et par famille analytique.",
      "Volume = somme des montants par jour et par famille analytique."
    ],
    sources: ["date", "amount", "group_label", "from_label", "to_label"]
  },

  activityWeeklyFlows: {
    title: "Activité économique par semaine, par type de flux",
    summary: "Évolution hebdomadaire de la circulation économique retenue, décomposée par flux structurel.",
    perimeter: [
      "Transactions retenues dans le périmètre d’activité économique.",
      "Flux détaillés : U→P, P→P, P→U, U→U.",
      "Flux atypiques : T→P et T→U inclus dans l’activité retenue."
    ],
    formulas: [
      "Nombre hebdomadaire d’un flux = nombre de transactions de ce flux dans la semaine ISO.",
      "Volume hebdomadaire d’un flux = somme des montants de ce flux dans la semaine ISO."
    ],
    sources: ["date", "amount", "from_label", "to_label", "group_label"]
  },

  cumulativeActivity: {
    title: "Activité économique cumulée",
    summary: "Progression cumulée de l’activité économique sur la période sélectionnée.",
    perimeter: [
      "Même périmètre que l’activité économique générale.",
      "Le cumul est calculé jour après jour sur la période active."
    ],
    formulas: [
      "Nombre cumulé au jour d = somme des transactions économiques du début de période jusqu’au jour d.",
      "Volume cumulé au jour d = somme des montants économiques du début de période jusqu’au jour d."
    ],
    sources: ["date", "amount", "group_label", "from_label", "to_label"]
  },

  hourlyActivity: {
    title: "Activité économique par heure",
    summary: "Répartition de l’activité économique selon l’heure de réalisation des transactions.",
    perimeter: [
      "Transactions retenues dans le périmètre d’activité économique.",
      "Les heures sont lues directement depuis la date/heure enregistrée dans la transaction."
    ],
    formulas: [
      "Nombre à l’heure h = nombre de transactions économiques réalisées pendant l’heure h.",
      "Volume à l’heure h = somme des montants économiques réalisés pendant l’heure h."
    ],
    sources: ["date", "amount", "group_label", "from_label", "to_label"]
  },

  weekdayActivity: {
    title: "Activité économique par jour de semaine",
    summary: "Répartition de l’activité économique selon le jour de la semaine.",
    perimeter: [
      "Transactions retenues dans le périmètre d’activité économique.",
      "Les jours sont ordonnés du lundi au dimanche."
    ],
    formulas: [
      "Nombre le jour j = nombre de transactions économiques associées au jour j.",
      "Volume le jour j = somme des montants économiques associés au jour j."
    ],
    sources: ["date", "amount", "group_label", "from_label", "to_label"]
  }
,

  circuitMonthlyFlows: {
    title: "Chaque mois : ce qui entre et ce qui sort",
    summary: "Ce graphe regarde les mois un par un. Il compare la monnaie numérique ajoutée au circuit et celle qui en ressort.",
    reading: [
      "Choisis un mois sur l’axe du bas.",
      "Si la courbe des alimentations est plus haute, ce mois-là il est entré plus de Gonettes qu’il n’en est sorti.",
      "Si la courbe des sorties est plus haute, ce mois-là il est sorti plus de Gonettes qu’il n’en est entré.",
      "Le dernier mois peut être incomplet si la période analysée s’arrête en cours de mois."
    ],
    perimeter: [
      "Alimentations : transactions classées dans le groupe Émission.",
      "Sorties : transactions Compte Pro · P→Compte technique."
    ],
    formulas: [
      "Nombre mensuel = nombre d’opérations du mois.",
      "Volume mensuel = somme des montants du mois."
    ],
    sources: ["date", "amount", "group_label", "from_label", "to_label"]
  },

  circuitInflowDestinations: {
    title: "Quand la monnaie entre : qui la reçoit ?",
    summary: "Ici, on ne regarde que la monnaie qui entre dans le circuit. Le graphe montre vers quels types de comptes elle va.",
    reading: [
      "La courbe T→U montre les alimentations vers les particuliers.",
      "La courbe T→P montre les alimentations vers les professionnels.",
      "Si une courbe est très proche de zéro, cela veut dire que ce cas est rare ou porte sur de petits montants.",
      "Les séries complètement vides ne sont pas affichées."
    ],
    perimeter: [
      "Uniquement les transactions d’alimentation du circuit numérique.",
      "T→U : vers particuliers.",
      "T→P : vers professionnels.",
      "T→T : résiduel technique très marginal."
    ],
    formulas: [
      "Nombre mensuel d’un flux = nombre d’alimentations de ce type dans le mois.",
      "Volume mensuel d’un flux = somme des montants de ce type dans le mois."
    ],
    sources: ["date", "amount", "group_label", "from_label", "to_label"]
  },

  circuitCumulativeFlows: {
    title: "Depuis le début : total entré et total sorti",
    summary: "Ce graphe additionne les mois les uns après les autres. Il ne raconte pas seulement le mois en cours, mais tout ce qui s’est accumulé depuis le début de la période.",
    reading: [
      "Les courbes montent au fil du temps parce qu’on additionne les mois.",
      "La courbe des alimentations montre tout ce qui est entré depuis le début.",
      "La courbe des sorties montre tout ce qui est sorti depuis le début.",
      "L’écart vertical entre les deux courbes donne une idée de leur différence cumulée."
    ],
    perimeter: [
      "Alimentations et sorties selon les mêmes définitions structurelles que les autres graphes de l’onglet.",
      "Le cumul est recalculé mois par mois."
    ],
    formulas: [
      "Nombre cumulé au mois m = total des opérations depuis le début jusqu’au mois m.",
      "Volume cumulé au mois m = total des montants depuis le début jusqu’au mois m."
    ],
    sources: ["date", "amount", "group_label", "from_label", "to_label"]
  },

  circuitNetGap: {
    title: "Depuis le début : entrées devant ou sorties devant ?",
    summary: "Ce graphe résume le précédent en une seule ligne. Il montre la différence entre ce qui est entré et ce qui est sorti depuis le début de la période.",
    reading: [
      "La ligne zéro veut dire : autant de volume entré que sorti depuis le début.",
      "Au-dessus de zéro : plus de Gonettes sont entrées qu’elles ne sont sorties.",
      "En dessous de zéro : plus de Gonettes sont sorties qu’elles ne sont entrées.",
      "Ce n’est pas un stock exact de monnaie en circulation : c’est un écart entre deux flux."
    ],
    perimeter: [
      "Calculé uniquement en volume.",
      "Alimentations : groupe Émission.",
      "Sorties : Compte Pro · P→Compte technique."
    ],
    formulas: [
      "Écart net cumulé au mois m = volume cumulé alimenté − volume cumulé sorti."
    ],
    sources: ["date", "amount", "group_label", "from_label", "to_label"]
  },

  operationsMonthlyFamilies: {
    title: "Chaque mois : quels types d’opérations hors activité économique ?",
    summary: "Ce graphe compare les deux grands blocs de l’onglet : les mouvements impliquant les comptes opérateurs et les flux particuliers vers l’compte technique.",
    reading: [
      "Chaque point correspond à un mois.",
      "La série « Comptes opérateurs » montre les opérations liées à P0000 ou P9999.",
      "La série « Particuliers → comptes techniques » montre les flux U→T.",
      "Quand une courbe monte, cela signifie que ce type d’opérations a été plus important ce mois-là.",
      "Le dernier mois peut être incomplet si la période s’arrête en cours de mois."
    ],
    perimeter: [
      "Comptes opérateurs : flux classés dans la famille impliquant P0000 / P9999.",
      "Particuliers → comptes techniques : flux U→T classés hors activité économique."
    ],
    formulas: [
      "Nombre mensuel = nombre d’opérations de la famille dans le mois.",
      "Volume mensuel = somme des montants de la famille dans le mois."
    ],
    sources: ["date", "amount", "group_label", "from_label", "to_label"]
  },

  operationsMonthlyOperatorProfiles: {
    title: "Chaque mois : quels comptes opérateurs sont concernés ?",
    summary: "Ce graphe détaille les opérations impliquant les comptes opérateurs P0000 et P9999.",
    reading: [
      "P0000 et P9999 sont deux comptes opérateurs distincts dans les données.",
      "Une série haute indique que ce profil porte davantage d’opérations ou de volume sur le mois.",
      "La série P0000 ↔ P9999 isole les mouvements directs entre ces deux comptes.",
      "Ce graphe sert à ne pas mélanger des rôles techniques différents."
    ],
    perimeter: [
      "Uniquement les opérations déjà classées dans la famille « comptes opérateurs ».",
      "P0000 impliqué, P9999 impliqué et P0000 ↔ P9999 sont distingués séparément."
    ],
    formulas: [
      "Nombre mensuel d’un profil = nombre d’opérations de ce profil dans le mois.",
      "Volume mensuel d’un profil = somme des montants de ce profil dans le mois."
    ],
    sources: ["date", "amount", "from_label", "to_label"]
  },

  operationsStructuralFlowDistribution: {
    title: "Qui transfère vers qui, hors activité économique ?",
    summary: "Ce graphe répartit les opérations de l’onglet 3 selon le rôle réel des comptes impliqués. Il évite volontairement les catégories brutes P→P ou U→P, trop proches du vocabulaire de l’activité économique.",
    reading: [
      "Chaque barre décrit un type de mouvement hors activité économique.",
      "« Professionnel → compte opérateur » désigne un professionnel qui envoie vers P0000 ou P9999.",
      "« Particulier → compte opérateur » désigne un particulier qui envoie vers un compte opérateur, et non un paiement économique ordinaire.",
      "En nombre, on voit quels mouvements sont les plus fréquents.",
      "En volume, on voit quels mouvements pèsent le plus monétairement."
    ],
    perimeter: [
      "Uniquement les opérations associatives / techniques de l’onglet 3.",
      "Ce périmètre regroupe les flux impliquant P0000 / P9999 et les flux particuliers vers compte technique.",
      "Les catégories affichées ne décrivent pas l’activité économique générale de la Gonette."
    ],
    formulas: [
      "Nombre par catégorie = nombre d’opérations hors activité correspondant à ce type de mouvement.",
      "Volume par catégorie = somme des montants de ces opérations."
    ],
    sources: ["amount", "from_label", "to_label"]
  }
};

function formatStatsChartCount(value) {
  return Number(value || 0).toLocaleString("fr-FR", {
    maximumFractionDigits: 0
  });
}

function formatStatsChartMetricValue(metric, value) {
  return metric === "volume"
    ? euro(value || 0)
    : formatStatsChartCount(value || 0);
}

function getStatsChartMetric(chartKey, fallbackMetric = "count") {
  if (chartKey === "globalDailyCount") {
    return appState.dailyChartMetric || fallbackMetric;
  }

  if (!appState.statsChartMetrics) {
    appState.statsChartMetrics = {};
  }

  return appState.statsChartMetrics[chartKey]
    || STATS_CHART_DEFAULT_METRICS[chartKey]
    || fallbackMetric;
}

const STATS_CHART_NO_METRIC_TOGGLE = new Set([
  "pilotageRotation",
  "pilotageFlowRhythm",
  "pilotageRetention",
  "pilotageInternalReuseHistory",
  "pilotageLm3History",
  "pilotageHoldingsStockShare",
  "pilotageHoldingsMobilization",
  "pilotageHoldingsDormancy"
]);

function statsChartSupportsMetricToggle(chartKey) {
  if (STATS_CHART_NO_METRIC_TOGGLE.has(chartKey)) {
    return false;
  }

  if ([
    "pilotageRotation",
    "pilotageFlowRhythm",
    "pilotageRetention"
  ].includes(chartKey)) {
    return false;
  }

  return chartKey !== "circuitNetGap";
}

function setStatsChartMetric(chartKey, metric) {
  if (chartKey === "globalDailyCount") {
    appState.dailyChartMetric = metric;
    return;
  }

  if (!appState.statsChartMetrics) {
    appState.statsChartMetrics = {};
  }

  appState.statsChartMetrics[chartKey] = metric;
}

function getStatsChartHiddenDatasetMap(chartKey) {
  if (chartKey === "globalDailyCount") {
    if (!appState.dailyChartHiddenDatasets) {
      appState.dailyChartHiddenDatasets = {};
    }
    return appState.dailyChartHiddenDatasets;
  }

  if (!appState.statsChartHiddenDatasets) {
    appState.statsChartHiddenDatasets = {};
  }

  if (!appState.statsChartHiddenDatasets[chartKey]) {
    appState.statsChartHiddenDatasets[chartKey] = {};
  }

  return appState.statsChartHiddenDatasets[chartKey];
}

function rememberStatsChartHiddenDatasets(chartKey, chart) {
  if (!chart) {
    return;
  }

  const hiddenMap = getStatsChartHiddenDatasetMap(chartKey);

  chart.data.datasets.forEach((dataset, index) => {
    hiddenMap[dataset.label] = !chart.isDatasetVisible(index);
  });
}

function applyStatsChartHiddenDatasets(chartKey, chart) {
  if (!chart) {
    return;
  }

  const hiddenMap = getStatsChartHiddenDatasetMap(chartKey);
  const hiddenLabels = Object.keys(hiddenMap || {});

  // Premier chargement : rien n'a encore été masqué par l'utilisateur.
  // On évite donc un chart.update() inutile juste après new Chart(...).
  if (!hiddenLabels.length) {
    return;
  }

  let visibilityChanged = false;

  chart.data.datasets.forEach((dataset, index) => {
    if (!Object.prototype.hasOwnProperty.call(hiddenMap, dataset.label)) {
      return;
    }

    const shouldBeVisible = !Boolean(hiddenMap[dataset.label]);

    if (chart.isDatasetVisible(index) !== shouldBeVisible) {
      chart.setDatasetVisibility(index, shouldBeVisible);
      visibilityChanged = true;
    }
  });

  // En cas de restauration réelle d'état, mise à jour sans animation.
  if (visibilityChanged) {
    chart.update("none");
  }
}

function buildStatsChartMetricToggle(chartKey, metric) {
  const toggleId = `statsChartMetricToggle_${chartKey}`;
  const checked = metric === "volume" ? "checked" : "";

  return `
    <label class="daily-chart-toggle stats-chart-metric-toggle" for="${toggleId}">
      <span class="daily-chart-toggle-label">Nombre</span>
      <span class="daily-chart-switch">
        <input
          id="${toggleId}"
          type="checkbox"
          data-stats-chart-metric="${chartKey}"
          ${checked}
        />
        <span class="daily-chart-slider"></span>
      </span>
      <span class="daily-chart-toggle-label">Volume</span>
    </label>
  `;
}

function buildStatsChartTools(chartKey) {
  return `
    <div class="stats-chart-tools">
      <button
        type="button"
        class="stats-chart-tool-btn"
        data-stats-chart-help="${chartKey}"
        aria-label="Afficher l’aide méthodologique du graphe"
        title="Aide méthodologique"
      >
        ?
      </button>
      <button
        type="button"
        class="stats-chart-tool-btn stats-chart-zoom-btn"
        data-stats-chart-zoom="${chartKey}"
        aria-label="Agrandir le graphe"
        title="Agrandir"
      >
        ⤢
      </button>
    </div>
  `;
}

function buildStatsZoomMetricToggle(chartKey, metric) {
  const toggleId = `statsZoomMetricToggle_${chartKey}`;
  const checked = metric === "volume" ? "checked" : "";

  return `
    <label class="daily-chart-toggle stats-chart-metric-toggle" for="${toggleId}">
      <span class="daily-chart-toggle-label">Nombre</span>
      <span class="daily-chart-switch">
        <input
          id="${toggleId}"
          type="checkbox"
          data-stats-chart-zoom-metric="${chartKey}"
          ${checked}
        />
        <span class="daily-chart-slider"></span>
      </span>
      <span class="daily-chart-toggle-label">Volume</span>
    </label>
  `;
}

function buildStatsChartHeader({
  chartKey,
  title,
  description = "",
  metric = "count",
  supportsMetricToggle = statsChartSupportsMetricToggle(chartKey)
}) {
  return `
    <div class="stats-chart-card-header">
      <div class="stats-chart-title-group">
        <h3>${title}</h3>
        ${description ? `<p>${description}</p>` : ""}
      </div>
      <div class="stats-chart-header-actions">
        ${supportsMetricToggle ? buildStatsChartMetricToggle(chartKey, metric) : ""}
        ${buildStatsChartTools(chartKey)}
      </div>
    </div>
  `;
}

function buildStatsChartBaseOptions(metric, rotateX = false) {
  return {
    responsive: true,
    maintainAspectRatio: true,
    interaction: {
      mode: "index",
      intersect: false
    },
    plugins: {
      legend: {
        position: "top"
      },
      tooltip: {
        callbacks: {
          label: function(context) {
            const label = context.dataset.statsTooltipLabel || context.dataset.label;
            return `${label}: ${formatStatsChartMetricValue(metric, context.raw)}`;
          }
        }
      }
    },
    scales: {
      x: {
        ticks: rotateX
          ? { maxRotation: 45, minRotation: 0 }
          : {}
      },
      y: {
        beginAtZero: true,
        ticks: {
          callback: function(value) {
            return formatStatsChartMetricValue(metric, value);
          }
        }
      }
    }
  };
}

function buildDailyTransactionsChartConfig(charts, metric) {
  return {
    type: "line",
    data: {
      labels: charts.daily.labels,
      datasets: getDailyChartDatasets(charts, metric)
    },
    options: buildStatsChartBaseOptions(metric, true)
  };
}

function buildWeeklyActivityFlowsChartConfig(charts, metric) {
  const weekly = charts.weekly_activity_flows || { labels: [], series: [] };

  return {
    type: "line",
    data: {
      labels: weekly.labels || [],
      datasets: (weekly.series || []).map((series) => ({
        label: series.short_label || series.key,
        statsTooltipLabel: series.label || series.short_label || series.key,
        data: metric === "volume"
          ? (series.amount_values || [])
          : (series.count_values || []),
        fill: false,
        tension: 0.24
      }))
    },
    options: buildStatsChartBaseOptions(metric, true)
  };
}

function buildCumulativeActivityChartConfig(charts, metric) {
  const cumulative = charts.cumulative_activity || {
    labels: [],
    count_values: [],
    amount_values: []
  };

  const datasetLabel = metric === "volume"
    ? "Volume cumulé de l’activité économique"
    : "Nombre cumulé de transactions économiques";

  return {
    type: "line",
    data: {
      labels: cumulative.labels || [],
      datasets: [{
        label: datasetLabel,
        data: metric === "volume"
          ? (cumulative.amount_values || [])
          : (cumulative.count_values || []),
        fill: true,
        tension: 0.2
      }]
    },
    options: buildStatsChartBaseOptions(metric, true)
  };
}

function buildHourlyActivityChartConfig(charts, metric) {
  const hourly = charts.hourly_activity || {
    labels: [],
    count_values: [],
    amount_values: []
  };

  return {
    type: "bar",
    data: {
      labels: hourly.labels || [],
      datasets: [{
        label: metric === "volume"
          ? "Volume économique"
          : "Transactions économiques",
        data: metric === "volume"
          ? (hourly.amount_values || [])
          : (hourly.count_values || [])
      }]
    },
    options: buildStatsChartBaseOptions(metric, false)
  };
}

function buildWeekdayActivityChartConfig(charts, metric) {
  const weekday = charts.weekday_activity || {
    labels: [],
    count_values: [],
    amount_values: []
  };

  return {
    type: "bar",
    data: {
      labels: weekday.labels || [],
      datasets: [{
        label: metric === "volume"
          ? "Volume économique"
          : "Transactions économiques",
        data: metric === "volume"
          ? (weekday.amount_values || [])
          : (weekday.count_values || [])
      }]
    },
    options: buildStatsChartBaseOptions(metric, false)
  };
}


function buildCircuitMonthlyFlowsChartConfig(charts, metric) {
  const monthly = charts.circuit_monthly_flows || { labels: [], series: [] };

  return {
    type: "line",
    data: {
      labels: monthly.labels || [],
      datasets: (monthly.series || []).map((series) => ({
        label: series.short_label || series.key,
        statsTooltipLabel: series.label || series.short_label || series.key,
        data: metric === "volume"
          ? (series.amount_values || [])
          : (series.count_values || []),
        fill: false,
        tension: 0.24
      }))
    },
    options: buildStatsChartBaseOptions(metric, true)
  };
}

function buildCircuitInflowDestinationsChartConfig(charts, metric) {
  const destinations = charts.circuit_monthly_inflow_destinations || {
    labels: [],
    series: []
  };

  return {
    type: "line",
    data: {
      labels: destinations.labels || [],
      datasets: (destinations.series || [])
        .filter((series) => {
          const values = metric === "volume"
            ? (series.amount_values || [])
            : (series.count_values || []);
          return values.some((value) => Number(value || 0) !== 0);
        })
        .map((series) => ({
        label: series.short_label || series.key,
        statsTooltipLabel: series.label || series.short_label || series.key,
        data: metric === "volume"
          ? (series.amount_values || [])
          : (series.count_values || []),
        fill: false,
        tension: 0.24
      }))
    },
    options: buildStatsChartBaseOptions(metric, true)
  };
}

function buildCircuitCumulativeFlowsChartConfig(charts, metric) {
  const cumulative = charts.circuit_cumulative_flows || {
    labels: [],
    series: []
  };

  return {
    type: "line",
    data: {
      labels: cumulative.labels || [],
      datasets: (cumulative.series || []).map((series) => ({
        label: series.short_label || series.key,
        statsTooltipLabel: series.label || series.short_label || series.key,
        data: metric === "volume"
          ? (series.amount_values || [])
          : (series.count_values || []),
        fill: false,
        tension: 0.22
      }))
    },
    options: buildStatsChartBaseOptions(metric, true)
  };
}

function buildCircuitNetGapChartConfig(charts) {
  const gap = charts.circuit_cumulative_net_gap || {
    labels: [],
    amount_values: []
  };

  return {
    type: "line",
    data: {
      labels: gap.labels || [],
      datasets: [{
        label: "Écart net cumulé",
        statsTooltipLabel: "Écart net cumulé alimentations – sorties",
        data: gap.amount_values || [],
        fill: true,
        tension: 0.22
      }]
    },
    options: buildStatsChartBaseOptions("volume", true)
  };
}


function buildOperationsMonthlyFamiliesChartConfig(charts, metric) {
  const monthly = charts.operations_monthly_families || {
    labels: [],
    series: []
  };

  return {
    type: "line",
    data: {
      labels: monthly.labels || [],
      datasets: (monthly.series || []).map((series) => ({
        label: series.short_label || series.key,
        statsTooltipLabel: series.label || series.short_label || series.key,
        data: metric === "volume"
          ? (series.amount_values || [])
          : (series.count_values || []),
        fill: false,
        tension: 0.24
      }))
    },
    options: buildStatsChartBaseOptions(metric, true)
  };
}

function buildOperationsMonthlyOperatorProfilesChartConfig(charts, metric) {
  const monthly = charts.operations_monthly_operator_profiles || {
    labels: [],
    series: []
  };

  return {
    type: "line",
    data: {
      labels: monthly.labels || [],
      datasets: (monthly.series || []).map((series) => ({
        label: series.short_label || series.key,
        statsTooltipLabel: series.label || series.short_label || series.key,
        data: metric === "volume"
          ? (series.amount_values || [])
          : (series.count_values || []),
        fill: false,
        tension: 0.24
      }))
    },
    options: buildStatsChartBaseOptions(metric, true)
  };
}

function buildOperationsStructuralFlowDistributionChartConfig(charts, metric) {
  const distribution = charts.operations_structural_flow_distribution || {
    labels: [],
    count_values: [],
    amount_values: []
  };

  return {
    type: "bar",
    data: {
      labels: distribution.labels || [],
      datasets: [{
        label: metric === "volume"
          ? "Volume par type de mouvement"
          : "Nombre par type de mouvement",
        statsTooltipLabel: metric === "volume"
          ? "Volume par type de mouvement"
          : "Nombre par type de mouvement",
        data: metric === "volume"
          ? (distribution.amount_values || [])
          : (distribution.count_values || [])
      }]
    },
    options: buildStatsChartBaseOptions(metric, true)
  };
}

function buildStatsChartConfig(chartKey, charts, metric) {
  switch (chartKey) {
    case "pilotageInternalReuseHistory":
      return buildPilotageInternalReuseHistoryChartConfig(
        charts?.pilotageReuseYearlyItems || []
      );
    case "pilotageLm3History":
      return buildPilotageLm3HistoryChartConfig(
        charts?.pilotageLm3YearlyItems || []
      );
    case "pilotageHoldingsStockShare":
      return buildPilotageHoldingsStockShareChartConfig(
        charts?.pilotageHoldingsItems || []
      );
    case "pilotageHoldingsMassComposition":
      return buildPilotageHoldingsMassCompositionChartConfig(
        charts?.pilotageHoldingsItems || []
      );
    case "pilotageHoldingsMobilization":
      return buildPilotageHoldingsMobilizationChartConfig(
        charts?.pilotageHoldingsItems || []
      );
    case "pilotageHoldingsDormancy":
      return buildPilotageHoldingsDormancyChartConfig(
        charts?.pilotageHoldingsItems || []
      );
    case "pilotageRotation":
      return buildPilotageRotationChartConfig(
        charts?.pilotageItems || [],
        charts?.pilotageSummary || null
      );
    case "pilotageFlowRhythm":
      return buildPilotageFlowRhythmChartConfig(
        charts?.pilotageItems || []
      );
    case "pilotageRetention":
      return buildPilotageRetentionChartConfig(
        charts?.pilotageItems || []
      );
    case "globalDailyCount":
      return buildDailyTransactionsChartConfig(charts, metric);
    case "activityWeeklyFlows":
      return buildWeeklyActivityFlowsChartConfig(charts, metric);
    case "cumulativeActivity":
      return buildCumulativeActivityChartConfig(charts, metric);
    case "hourlyActivity":
      return buildHourlyActivityChartConfig(charts, metric);
    case "weekdayActivity":
      return buildWeekdayActivityChartConfig(charts, metric);
    case "circuitMonthlyFlows":
      return buildCircuitMonthlyFlowsChartConfig(charts, metric);
    case "circuitInflowDestinations":
      return buildCircuitInflowDestinationsChartConfig(charts, metric);
    case "circuitCumulativeFlows":
      return buildCircuitCumulativeFlowsChartConfig(charts, metric);
    case "circuitNetGap":
      return buildCircuitNetGapChartConfig(charts);
    case "operationsMonthlyFamilies":
      return buildOperationsMonthlyFamiliesChartConfig(charts, metric);
    case "operationsMonthlyOperatorProfiles":
      return buildOperationsMonthlyOperatorProfilesChartConfig(charts, metric);
    case "operationsStructuralFlowDistribution":
      return buildOperationsStructuralFlowDistributionChartConfig(charts, metric);
    default:
      return null;
  }
}

function createStatsChart({
  chartKey,
  storeKey,
  canvasId,
  config
}) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !config) {
    return null;
  }

  if (appState.charts[storeKey]) {
    rememberStatsChartHiddenDatasets(chartKey, appState.charts[storeKey]);
    appState.charts[storeKey].destroy();
    appState.charts[storeKey] = null;
  }

  const chart = new Chart(canvas, config);
  appState.charts[storeKey] = chart;
  applyStatsChartHiddenDatasets(chartKey, chart);

  return chart;
}

function renderDailyTransactionsChart(charts, metric = "count") {
  createStatsChart({
    chartKey: "globalDailyCount",
    storeKey: "globalDailyCount",
    canvasId: "globalDailyCountChart",
    config: buildDailyTransactionsChartConfig(charts, metric)
  });
}

function renderWeeklyActivityFlowsChart(charts, metric = "volume") {
  createStatsChart({
    chartKey: "activityWeeklyFlows",
    storeKey: "globalWeeklyAvg",
    canvasId: "activityWeeklyFlowsChart",
    config: buildWeeklyActivityFlowsChartConfig(charts, metric)
  });
}

function renderCumulativeActivityChart(charts, metric = "volume") {
  createStatsChart({
    chartKey: "cumulativeActivity",
    storeKey: "globalCumulative",
    canvasId: "globalCumulativeChart",
    config: buildCumulativeActivityChartConfig(charts, metric)
  });
}

function renderHourlyActivityChart(charts, metric = "count") {
  createStatsChart({
    chartKey: "hourlyActivity",
    storeKey: "globalHourly",
    canvasId: "globalHourlyChart",
    config: buildHourlyActivityChartConfig(charts, metric)
  });
}

function renderWeekdayActivityChart(charts, metric = "count") {
  createStatsChart({
    chartKey: "weekdayActivity",
    storeKey: "globalWeekday",
    canvasId: "globalWeekdayChart",
    config: buildWeekdayActivityChartConfig(charts, metric)
  });
}


function renderCircuitMonthlyFlowsChart(charts, metric = "volume") {
  createStatsChart({
    chartKey: "circuitMonthlyFlows",
    storeKey: "circuitMonthlyFlows",
    canvasId: "circuitMonthlyFlowsChart",
    config: buildCircuitMonthlyFlowsChartConfig(charts, metric)
  });
}

function renderCircuitInflowDestinationsChart(charts, metric = "volume") {
  createStatsChart({
    chartKey: "circuitInflowDestinations",
    storeKey: "circuitInflowDestinations",
    canvasId: "circuitInflowDestinationsChart",
    config: buildCircuitInflowDestinationsChartConfig(charts, metric)
  });
}

function renderCircuitCumulativeFlowsChart(charts, metric = "volume") {
  createStatsChart({
    chartKey: "circuitCumulativeFlows",
    storeKey: "circuitCumulativeFlows",
    canvasId: "circuitCumulativeFlowsChart",
    config: buildCircuitCumulativeFlowsChartConfig(charts, metric)
  });
}

function renderCircuitNetGapChart(charts) {
  createStatsChart({
    chartKey: "circuitNetGap",
    storeKey: "circuitNetGap",
    canvasId: "circuitNetGapChart",
    config: buildCircuitNetGapChartConfig(charts)
  });
}


function renderOperationsMonthlyFamiliesChart(charts, metric = "volume") {
  createStatsChart({
    chartKey: "operationsMonthlyFamilies",
    storeKey: "operationsMonthlyFamilies",
    canvasId: "operationsMonthlyFamiliesChart",
    config: buildOperationsMonthlyFamiliesChartConfig(charts, metric)
  });
}

function renderOperationsMonthlyOperatorProfilesChart(charts, metric = "volume") {
  createStatsChart({
    chartKey: "operationsMonthlyOperatorProfiles",
    storeKey: "operationsMonthlyOperatorProfiles",
    canvasId: "operationsMonthlyOperatorProfilesChart",
    config: buildOperationsMonthlyOperatorProfilesChartConfig(charts, metric)
  });
}

function renderOperationsStructuralFlowDistributionChart(charts, metric = "volume") {
  createStatsChart({
    chartKey: "operationsStructuralFlowDistribution",
    storeKey: "operationsStructuralFlowDistribution",
    canvasId: "operationsStructuralFlowDistributionChart",
    config: buildOperationsStructuralFlowDistributionChartConfig(charts, metric)
  });
}

function rerenderStatsChart(chartKey, charts) {
  const metric = getStatsChartMetric(
    chartKey,
    STATS_CHART_DEFAULT_METRICS[chartKey] || "count"
  );

  switch (chartKey) {
    case "globalDailyCount":
      renderDailyTransactionsChart(charts, metric);
      break;
    case "activityWeeklyFlows":
      renderWeeklyActivityFlowsChart(charts, metric);
      break;
    case "cumulativeActivity":
      renderCumulativeActivityChart(charts, metric);
      break;
    case "hourlyActivity":
      renderHourlyActivityChart(charts, metric);
      break;
    case "weekdayActivity":
      renderWeekdayActivityChart(charts, metric);
      break;
    case "circuitMonthlyFlows":
      renderCircuitMonthlyFlowsChart(charts, metric);
      break;
    case "circuitInflowDestinations":
      renderCircuitInflowDestinationsChart(charts, metric);
      break;
    case "circuitCumulativeFlows":
      renderCircuitCumulativeFlowsChart(charts, metric);
      break;
    case "circuitNetGap":
      renderCircuitNetGapChart(charts);
      break;
    case "operationsMonthlyFamilies":
      renderOperationsMonthlyFamiliesChart(charts, metric);
      break;
    case "operationsMonthlyOperatorProfiles":
      renderOperationsMonthlyOperatorProfilesChart(charts, metric);
      break;
    case "operationsStructuralFlowDistribution":
      renderOperationsStructuralFlowDistributionChart(charts, metric);
      break;
  }
}

function bindStatsChartMetricToggles(charts) {
  document.querySelectorAll("[data-stats-chart-metric]").forEach((toggle) => {
    toggle.addEventListener("change", () => {
      const chartKey = toggle.dataset.statsChartMetric;
      const metric = toggle.checked ? "volume" : "count";

      setStatsChartMetric(chartKey, metric);
      rerenderStatsChart(chartKey, charts);
    });
  });
}

function buildAnalyticHelpHtml(help, {
  kicker = "Aide méthodologique",
  fallbackTitle = "Aide méthodologique",
  fallbackText = "Aucune aide détaillée n’est encore définie."
} = {}) {
  if (!help) {
    return `
      <div class="stats-chart-help-content">
        <h2>${escapeHtml(fallbackTitle)}</h2>
        <p>${escapeHtml(fallbackText)}</p>
      </div>
    `;
  }

  const usefulnessHtml = help.usefulness
    ? `
      <section class="stats-chart-help-section">
        <h3>Pourquoi c’est utile</h3>
        <p>${escapeHtml(help.usefulness)}</p>
      </section>
    `
    : "";

  const readingHtml = (help.reading || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  const crossReadingHtml = (help.crossReading || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  const pilotageHtml = (help.pilotage || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  const perimeterHtml = (help.perimeter || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  const formulasHtml = (help.formulas || [])
    .map((item) => `<li><code>${escapeHtml(item)}</code></li>`)
    .join("");

  const sourcesHtml = (help.sources || [])
    .map((item) => `<li><code>${escapeHtml(item)}</code></li>`)
    .join("");

  return `
    <div class="stats-chart-help-content">
      <p class="stats-chart-modal-kicker">${escapeHtml(kicker)}</p>
      <h2>${escapeHtml(help.title)}</h2>
      <p class="stats-chart-help-summary">${escapeHtml(help.summary)}</p>

      ${usefulnessHtml}

      ${readingHtml ? `
        <section class="stats-chart-help-section">
          <h3>Comment le lire</h3>
          <ul>${readingHtml}</ul>
        </section>
      ` : ""}

      ${crossReadingHtml ? `
        <section class="stats-chart-help-section stats-chart-help-cross-reading">
          <h3>À croiser avec</h3>
          <ul>${crossReadingHtml}</ul>
        </section>
      ` : ""}

      ${pilotageHtml ? `
        <section class="stats-chart-help-section stats-chart-help-pilotage">
          <h3>Ce que cela peut inviter à vérifier</h3>
          <ul>${pilotageHtml}</ul>
        </section>
      ` : ""}

      <section class="stats-chart-help-section">
        <h3>Périmètre</h3>
        <ul>${perimeterHtml}</ul>
      </section>

      <section class="stats-chart-help-section">
        <h3>Formules</h3>
        <ul>${formulasHtml}</ul>
      </section>

      <section class="stats-chart-help-section">
        <h3>Champs de données mobilisés</h3>
        <ul class="stats-chart-source-list">${sourcesHtml}</ul>
      </section>
    </div>
  `;
}

function buildStatsChartHelpHtml(chartKey) {
  return buildAnalyticHelpHtml(STATS_CHART_HELP[chartKey], {
    kicker: "Aide méthodologique",
    fallbackTitle: "Aide méthodologique",
    fallbackText: "Aucune aide détaillée n’est encore définie pour ce graphe."
  });
}

function buildPilotageIndicatorHelpHtml(indicatorKey) {
  return buildAnalyticHelpHtml(PILOTAGE_INDICATOR_HELP[indicatorKey], {
    kicker: "Aide à la lecture",
    fallbackTitle: "Aide à la lecture",
    fallbackText: "Aucune aide détaillée n’est encore définie pour cet indicateur."
  });
}

function ensureStatsChartModal() {
  let modal = document.getElementById("statsChartModal");

  if (modal) {
    return modal;
  }

  document.body.insertAdjacentHTML("beforeend", `
    <div id="statsChartModal" class="stats-chart-modal hidden" role="dialog" aria-modal="true">
      <div class="stats-chart-modal-backdrop" data-stats-chart-modal-close></div>
      <section class="stats-chart-modal-panel" role="document">
        <button
          type="button"
          class="stats-chart-modal-close"
          data-stats-chart-modal-close
          aria-label="Fermer"
        >
          ×
        </button>
        <div id="statsChartModalBody"></div>
      </section>
    </div>
  `);

  modal = document.getElementById("statsChartModal");

  modal.addEventListener("click", (event) => {
    if (
      event.target.matches("[data-stats-chart-modal-close]")
      || event.target.classList.contains("stats-chart-modal-backdrop")
    ) {
      closeStatsChartModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape"
      && modal
      && !modal.classList.contains("hidden")
    ) {
      closeStatsChartModal();
    }
  });

  return modal;
}

function openStatsChartModal(html, mode = "help") {
  const modal = ensureStatsChartModal();
  const body = document.getElementById("statsChartModalBody");

  if (!modal || !body) {
    return;
  }

  modal.dataset.mode = mode;
  body.innerHTML = html;
  modal.classList.remove("hidden");
  document.body.classList.add("stats-chart-modal-open");
}

function closeStatsChartModal() {
  const modal = document.getElementById("statsChartModal");
  const body = document.getElementById("statsChartModalBody");

  if (appState.statsZoomChart) {
    appState.statsZoomChart.destroy();
    appState.statsZoomChart = null;
  }

  destroyUserPostalClustersMap("userPostalClustersZoomMap");

  if (
    appState.cartography?.zoomMap
    && typeof appState.cartography.zoomMap.remove === "function"
  ) {
    appState.cartography.zoomMap.remove();
  }

  if (appState.cartography) {
    appState.cartography.zoomMap = null;
    appState.cartography.zoomOverlay = null;
  }

  if (body) {
    body.innerHTML = "";
  }

  if (modal) {
    modal.classList.add("hidden");
  }

  document.body.classList.remove("stats-chart-modal-open");
}

function openStatsChartHelp(chartKey) {
  openStatsChartModal(buildStatsChartHelpHtml(chartKey), "help");
}

function renderStatsZoomChart(chartKey, charts, metric) {
  const canvas = document.getElementById("statsChartZoomCanvas");
  const config = buildStatsChartConfig(chartKey, charts, metric);

  if (!canvas || !config) {
    return;
  }

  config.options.maintainAspectRatio = false;

  if (appState.statsZoomChart) {
    appState.statsZoomChart.destroy();
    appState.statsZoomChart = null;
  }

  appState.statsZoomChart = new Chart(canvas, config);
  applyStatsChartHiddenDatasets(chartKey, appState.statsZoomChart);
}

function openStatsChartZoom(chartKey, charts) {
  const help = STATS_CHART_HELP[chartKey];
  const metric = getStatsChartMetric(
    chartKey,
    STATS_CHART_DEFAULT_METRICS[chartKey] || "count"
  );

  openStatsChartModal(`
    <div class="stats-chart-zoom-shell">
      <p class="stats-chart-modal-kicker">Agrandissement</p>

      <div class="stats-chart-zoom-header">
        <div class="stats-chart-zoom-title-group">
          <h2>${escapeHtml(help?.title || "Graphique")}</h2>
          <p class="stats-chart-help-summary">
            ${escapeHtml(help?.summary || "Affichage agrandi du graphique sélectionné.")}
          </p>
        </div>

        <div class="stats-chart-zoom-actions">
          ${statsChartSupportsMetricToggle(chartKey) ? buildStatsZoomMetricToggle(chartKey, metric) : ""}

          <button
            type="button"
            class="stats-chart-tool-btn"
            data-stats-chart-zoom-help="${chartKey}"
            aria-label="Afficher l’aide méthodologique du graphe agrandi"
            title="Aide méthodologique"
          >
            ?
          </button>
        </div>
      </div>

      <aside id="statsChartZoomHelpPanel" class="stats-chart-zoom-help hidden">
        ${buildStatsChartHelpHtml(chartKey)}
      </aside>

      <div class="stats-chart-zoom-canvas-wrap">
        <canvas id="statsChartZoomCanvas" height="240"></canvas>
      </div>
    </div>
  `, "zoom");

  renderStatsZoomChart(chartKey, charts, metric);
  bindStatsZoomModalControls(chartKey, charts);
}

function bindStatsChartTools(charts) {
  document.querySelectorAll("[data-stats-chart-help]").forEach((button) => {
    button.addEventListener("click", () => {
      openStatsChartHelp(button.dataset.statsChartHelp);
    });
  });

  document.querySelectorAll("[data-stats-chart-zoom]").forEach((button) => {
    button.addEventListener("click", () => {
      openStatsChartZoom(button.dataset.statsChartZoom, charts);
    });
  });
}

function bindStatsZoomModalControls(chartKey, charts) {
  const modal = document.getElementById("statsChartModal");
  if (!modal) {
    return;
  }

  const metricToggle = modal.querySelector(`[data-stats-chart-zoom-metric="${chartKey}"]`);
  const helpButton = modal.querySelector(`[data-stats-chart-zoom-help="${chartKey}"]`);
  const helpPanel = modal.querySelector("#statsChartZoomHelpPanel");

  if (metricToggle) {
    metricToggle.addEventListener("change", () => {
      const metric = metricToggle.checked ? "volume" : "count";

      setStatsChartMetric(chartKey, metric);

      // Met à jour le graphe principal pour garder un seul état global.
      rerenderStatsChart(chartKey, charts);

      // Met à jour le graphe agrandi.
      renderStatsZoomChart(chartKey, charts, metric);
    });
  }

  if (helpButton && helpPanel) {
    helpButton.addEventListener("click", () => {
      helpPanel.classList.toggle("hidden");
      helpButton.classList.toggle("stats-chart-tool-btn-active", !helpPanel.classList.contains("hidden"));
    });
  }
}

function renderGlobalStatsChartsFromSeries(charts) {
  const overviewHost = document.getElementById("globalStatsOverviewCharts");
  const activityHost = document.getElementById("activityStatsCharts");
  const circuitHost = document.getElementById("circuitStatsCharts");
  const operationsHost = document.getElementById("operationsStatsCharts");

  if (!overviewHost || !activityHost || !circuitHost || !operationsHost) {
    return;
  }

  destroyGlobalStatsCharts();

  const overviewMetric = getStatsChartMetric("globalDailyCount", "count");
  const weeklyMetric = getStatsChartMetric("activityWeeklyFlows", "volume");
  const cumulativeMetric = getStatsChartMetric("cumulativeActivity", "volume");
  const hourlyMetric = getStatsChartMetric("hourlyActivity", "count");
  const weekdayMetric = getStatsChartMetric("weekdayActivity", "count");
  const circuitMonthlyMetric = getStatsChartMetric("circuitMonthlyFlows", "volume");
  const circuitDestinationsMetric = getStatsChartMetric("circuitInflowDestinations", "volume");
  const circuitCumulativeMetric = getStatsChartMetric("circuitCumulativeFlows", "volume");
  const operationsFamiliesMetric = getStatsChartMetric("operationsMonthlyFamilies", "volume");
  const operationsProfilesMetric = getStatsChartMetric("operationsMonthlyOperatorProfiles", "volume");
  const operationsStructuralMetric = getStatsChartMetric("operationsStructuralFlowDistribution", "volume");

  overviewHost.innerHTML = `
    <div class="card stats-overview-chart-card">
      ${buildStatsChartHeader({
        chartKey: "globalDailyCount",
        title: "Transactions par jour, par nature d’opération",
        description: "Vue transversale de l’activité économique, des entrées et sorties du circuit, et des opérations associatives ou techniques.",
        metric: overviewMetric
      })}
      <canvas id="globalDailyCountChart" height="90"></canvas>
    </div>
  `;

  activityHost.innerHTML = `
    <section class="stats-chart-section">
      <div class="stats-section-header">
        <h3>Dynamiques temporelles</h3>
        <p>
          Progression cumulée de l’activité économique et évolution hebdomadaire
          des principaux flux entre acteurs.
        </p>
      </div>

      <div class="stats-chart-grid">
        <div class="card stats-chart-card">
          ${buildStatsChartHeader({
            chartKey: "cumulativeActivity",
            title: "Activité économique cumulée",
            description: "Nombre ou volume cumulé de l’activité retenue, jour après jour.",
            metric: cumulativeMetric
          })}
          <canvas id="globalCumulativeChart" height="105"></canvas>
        </div>

        <div class="card stats-chart-card">
          ${buildStatsChartHeader({
            chartKey: "activityWeeklyFlows",
            title: "Activité économique par semaine, par type de flux",
            description: "Décomposition hebdomadaire des flux U→P, P→P, P→U, U→U et atypiques.",
            metric: weeklyMetric
          })}
          <canvas id="activityWeeklyFlowsChart" height="105"></canvas>
        </div>
      </div>
    </section>

    <section class="stats-chart-section">
      <div class="stats-section-header">
        <h3>Rythmes d’usage</h3>
        <p>
          Répartition de l’activité économique selon l’heure de la journée
          et le jour de la semaine.
        </p>
      </div>

      <div class="stats-chart-grid">
        <div class="card stats-chart-card">
          ${buildStatsChartHeader({
            chartKey: "hourlyActivity",
            title: "Activité économique par heure",
            description: "Répartition horaire en nombre ou en volume.",
            metric: hourlyMetric
          })}
          <canvas id="globalHourlyChart" height="95"></canvas>
        </div>

        <div class="card stats-chart-card">
          ${buildStatsChartHeader({
            chartKey: "weekdayActivity",
            title: "Activité économique par jour de semaine",
            description: "Répartition du lundi au dimanche, en nombre ou en volume.",
            metric: weekdayMetric
          })}
          <canvas id="globalWeekdayChart" height="95"></canvas>
        </div>
      </div>
    </section>
  `;

  circuitHost.innerHTML = `
    <section class="stats-chart-section">
      <div class="stats-section-header">
        <h3>Ce qui se passe mois par mois</h3>
        <p>
          Ces deux graphes répondent à deux questions simples :
          combien entre ou sort chaque mois, et quand ça entre, vers qui cela va.
        </p>
      </div>

      <div class="stats-chart-grid">
        <div class="card stats-chart-card">
          ${buildStatsChartHeader({
            chartKey: "circuitMonthlyFlows",
            title: "Chaque mois : ce qui entre et ce qui sort",
            description: "Compare mois par mois les Gonettes numériques ajoutées au circuit et celles qui en ressortent.",
            metric: circuitMonthlyMetric
          })}
          <canvas id="circuitMonthlyFlowsChart" height="105"></canvas>
        </div>

        <div class="card stats-chart-card">
          ${buildStatsChartHeader({
            chartKey: "circuitInflowDestinations",
            title: "Quand la monnaie entre : qui la reçoit ?",
            description: "Montre si les alimentations vont surtout vers des particuliers, des professionnels ou des cas techniques marginaux.",
            metric: circuitDestinationsMetric
          })}
          <canvas id="circuitInflowDestinationsChart" height="105"></canvas>
        </div>
      </div>
    </section>

    <section class="stats-chart-section">
      <div class="stats-section-header">
        <h3>Depuis le début de la période</h3>
        <p>
          Ces deux graphes additionnent les mois au fur et à mesure :
          ils montrent la tendance générale, pas seulement le dernier mois.
        </p>
      </div>

      <div class="stats-chart-grid">
        <div class="card stats-chart-card">
          ${buildStatsChartHeader({
            chartKey: "circuitCumulativeFlows",
            title: "Total cumulé : ce qui est entré et ce qui est sorti",
            description: "Addition progressive des alimentations et des sorties depuis le début de la période.",
            metric: circuitCumulativeMetric
          })}
          <canvas id="circuitCumulativeFlowsChart" height="105"></canvas>
        </div>

        <div class="card stats-chart-card">
          ${buildStatsChartHeader({
            chartKey: "circuitNetGap",
            title: "Écart cumulé : les entrées sont-elles devant les sorties ?",
            description: "Au-dessus de zéro, plus de volume est entré que sorti ; en dessous, c’est l’inverse.",
            metric: "volume",
            supportsMetricToggle: false
          })}
          <canvas id="circuitNetGapChart" height="105"></canvas>
        </div>
      </div>
    </section>
  `;

  operationsHost.innerHTML = `
    <section class="stats-chart-section">
      <div class="stats-section-header">
        <h3>Quand ces opérations ont-elles lieu ?</h3>
        <p>
          Ces deux graphes montrent, mois par mois, les volumes ou nombres d’opérations
          hors activité économique centrale.
        </p>
      </div>

      <div class="stats-chart-grid">
        <div class="card stats-chart-card">
          ${buildStatsChartHeader({
            chartKey: "operationsMonthlyFamilies",
            title: "Chaque mois : quelles familles d’opérations ?",
            description: "Compare les comptes opérateurs et les flux particuliers vers compte technique.",
            metric: operationsFamiliesMetric
          })}
          <canvas id="operationsMonthlyFamiliesChart" height="105"></canvas>
        </div>

        <div class="card stats-chart-card">
          ${buildStatsChartHeader({
            chartKey: "operationsMonthlyOperatorProfiles",
            title: "Chaque mois : quels comptes opérateurs ?",
            description: "Distingue P0000, P9999 et les flux directs entre ces deux comptes.",
            metric: operationsProfilesMetric
          })}
          <canvas id="operationsMonthlyOperatorProfilesChart" height="105"></canvas>
        </div>
      </div>
    </section>

    <section class="stats-chart-section">
      <div class="stats-section-header">
        <h3>Qui transfère vers qui, dans les opérations hors activité ?</h3>
        <p>
            Cette lecture ne suit plus le temps : elle distingue directement
            les rôles des comptes impliqués dans les opérations de cet onglet.
          </p>
      </div>

      <div class="stats-chart-grid">
        <div class="card stats-chart-card stats-chart-card-full">
          ${buildStatsChartHeader({
            chartKey: "operationsStructuralFlowDistribution",
            title: "Qui transfère vers qui, hors activité économique ?",
            description: "Les catégories affichent directement le rôle des comptes impliqués, pour éviter toute confusion avec les flux économiques de l’onglet 1.",
            metric: operationsStructuralMetric
          })}
          <canvas id="operationsStructuralFlowDistributionChart" height="105"></canvas>
        </div>
      </div>
    </section>
  `;

  renderDailyTransactionsChart(charts, overviewMetric);
  renderCumulativeActivityChart(charts, cumulativeMetric);
  renderWeeklyActivityFlowsChart(charts, weeklyMetric);
  renderHourlyActivityChart(charts, hourlyMetric);
  renderWeekdayActivityChart(charts, weekdayMetric);

  renderCircuitMonthlyFlowsChart(charts, circuitMonthlyMetric);
  renderCircuitInflowDestinationsChart(charts, circuitDestinationsMetric);
  renderCircuitCumulativeFlowsChart(charts, circuitCumulativeMetric);
  renderCircuitNetGapChart(charts);

  renderOperationsMonthlyFamiliesChart(charts, operationsFamiliesMetric);
  renderOperationsMonthlyOperatorProfilesChart(charts, operationsProfilesMetric);
  renderOperationsStructuralFlowDistributionChart(charts, operationsStructuralMetric);

  bindStatsChartMetricToggles(charts);
  bindStatsChartTools(charts);
}

function drawProsTable() {
  const filtered = getSortedAndFilteredPros();

  const tableRows = filtered.map(row => `
    <tr>
      <td>
        <button class="linkish" onclick="renderProDetail('${String(row.Professionnel).split(' - ')[0]}')">
          ${escapeHtml(row.Professionnel)}
        </button>
      </td>
      <td class="num">${euro(row["B2B Reçu"])}</td>
      <td class="num">${euro(row["B2B Emis"])}</td>
      <td class="num">${euro(row["B2C"])}</td>
      <td class="num">${euro(row["Rémunération"])}</td>
      <td class="num">${euro(row["Total Reçu"])}</td>
    </tr>
  `).join("");

  const professionalsDirectoryTarget = document.getElementById("professionalsDirectoryPanel") || content;
  professionalsDirectoryTarget.innerHTML = `
    <div class="topbar">
      <input type="text" id="searchPros" placeholder="Recherche rapide..." value="${escapeHtml(appState.prosSearch)}">
      <span>${filtered.length} résultat(s)</span>
    </div>

    <table>
      <thead>
        <tr>
          <th>${sortableHeader("Professionnel", "Professionnel")}</th>
          <th>${sortableHeader("B2B Reçu", "B2B Reçu")}</th>
          <th>${sortableHeader("B2B Emis", "B2B Emis")}</th>
          <th>${sortableHeader("B2C", "B2C")}</th>
          <th>${sortableHeader("Rémunération", "Rémunération")}</th>
          <th>${sortableHeader("Total Reçu", "Total Reçu")}</th>
        </tr>
      </thead>
      <tbody>
        ${tableRows || `<tr><td colspan="6">Aucun résultat</td></tr>`}
      </tbody>
    </table>
  `;

  const searchInput = document.getElementById("searchPros");

  if (appState.professionalsViewTab === "directory") {
    searchInput.focus();
    searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);
  }

  searchInput.addEventListener("input", (e) => {
    const nextValue = e.target.value;

    clearTimeout(appState.prosSearchDebounce);

    appState.prosSearchDebounce = setTimeout(() => {
      appState.prosSearch = nextValue;
      drawProsTable();
    }, 140);
  });
}

function toggleProsSort(column) {
  if (appState.prosSortBy === column) {
    appState.prosSortDir = appState.prosSortDir === "asc" ? "desc" : "asc";
  } else {
    appState.prosSortBy = column;
    appState.prosSortDir = column === "Professionnel" ? "asc" : "desc";
  }
  drawProsTable();
}

function statLabelWithHelp(label, helpText = null) {
  if (!helpText) {
    return `<div class="stat-label">${escapeHtml(label)}</div>`;
  }

  return `
    <div class="stat-label stat-label-with-help">
      <span>${escapeHtml(label)}</span>
      <span class="stat-help-badge" title="${escapeHtml(helpText)}">?</span>
    </div>
  `;
}

function clickableStatCard(label, value, action, isActive = false, helpText = null) {
  return `
    <button class="card stat-card-btn ${isActive ? "stat-card-btn-active" : ""}" onclick="${action}">
      ${statLabelWithHelp(label, helpText)}
      <div class="stat-value">${value}</div>
    </button>
  `;
}

function staticStatCard(label, value, isActive = false, helpText = null) {
  return `
    <div class="card stat-card-static ${isActive ? "stat-card-btn-active" : ""}">
      ${statLabelWithHelp(label, helpText)}
      <div class="stat-value">${value}</div>
    </div>
  `;
}

function clickableMiniStatCard(label, value, action, isActive = false) {
  return `
    <button class="card mini-stat-card mini-stat-card-btn ${isActive ? "mini-stat-card-active" : ""}" onclick="${action}">
      <div class="stat-label">${label}</div>
      <div class="mini-stat-value">${value}</div>
    </button>
  `;
}

function infoTagCard(label, value, isActive = false) {
  return `
    <div class="card mini-stat-card ${isActive ? "mini-stat-card-active" : ""}">
      <div class="stat-label">${label}</div>
      <div class="mini-stat-value">${value}</div>
    </div>
  `;
}

function getDetailModeLabel(mode) {
  const labels = {
    all: "Toutes les transactions",
    recues: "Transactions reçues",
    somme_recue: "Acheteurs / payeurs",
    payeurs_particuliers: "Particuliers payeurs",
    payeurs_professionnels: "Professionnels payeurs",
    emis_pro: "Vendeurs professionnels",
    emis_particuliers: "Destinataires particuliers",
    emis_total: "Destinataires des émissions hors reconversion",
    reconverti: "Opérations de reconversion",
    converti: "Opérations de conversion reçues"
  };

  return labels[mode] || mode;
}





function normalizeProfessionalReuseRate(value) {
  const numeric = Number(value || 0);

  if (!Number.isFinite(numeric) || numeric <= 0) {
    return 0;
  }

  // Les statistiques professionnelles expriment déjà les taux en points
  // de pourcentage : 3.2 signifie 3,2 %, et percent(...) attend cette forme.
  return numeric;
}

function formatProfessionalMeetingInteger(value) {
  return Number(value || 0).toLocaleString("fr-FR");
}

function buildProfessionalMeetingDiagnostic(filteredStats = {}) {
  const totalReceived = Number(filteredStats.montant_total_recu || 0);
  const c2bReceived = Number(filteredStats.montant_recu_particuliers || 0);
  const b2bReceived = Number(filteredStats.montant_recu_professionnels || 0);
  const totalReemitted = Number(filteredStats.total_montant_emis_sans_reconversion || 0);
  const reconverted = Number(filteredStats.montant_reconverti || 0);
  const individualPayers = Number(filteredStats.nb_particuliers || 0);
  const professionalPayers = Number(filteredStats.nb_professionnels || 0);
  const reuseRate = normalizeProfessionalReuseRate(filteredStats.taux_reutilisation);

  const c2bShare = totalReceived > 0 ? (c2bReceived / totalReceived) * 100 : 0;
  const b2bShare = totalReceived > 0 ? (b2bReceived / totalReceived) * 100 : 0;

  let profileTitle = "Usage à qualifier";
  let profileText = "Les volumes observés ne permettent pas encore de dégager un profil d’usage très installé sur la période.";

  if (totalReceived <= 0 && totalReemitted <= 0) {
    profileTitle = "Compte peu activé";
    profileText = "La période sélectionnée montre peu ou pas d’activité commerciale en Gonette. Le rendez-vous peut commencer par l’activation des usages de base.";
  } else if (c2bShare >= 75) {
    profileTitle = "Point de captation C2B";
    profileText = `Les encaissements proviennent très majoritairement des particuliers : ${percent(c2bShare)} des montants reçus. Le professionnel joue d’abord un rôle de point d’entrée de la Gonette dans la consommation quotidienne.`;
  } else if (b2bShare >= 45) {
    profileTitle = "Relais interprofessionnel";
    profileText = `Une part significative des montants reçus vient d’autres professionnels : ${percent(b2bShare)} des encaissements. Le professionnel est déjà inséré dans une logique de circulation B2B.`;
  } else if (reuseRate >= 55) {
    profileTitle = "Acteur de circulation active";
    profileText = `Le taux de réutilisation atteint ${percent(reuseRate)}. Le professionnel transforme une part importante des Gonettes reçues en nouveaux flux dans le réseau.`;
  } else {
    profileTitle = "Réception mixte à structurer";
    profileText = "Le professionnel reçoit des Gonettes depuis plusieurs types d’acteurs, mais son rôle dans la circulation peut encore être davantage qualifié.";
  }

  let strengthTitle = "Signal à documenter";
  let strengthText = "Le rendez-vous permettra de comprendre plus finement les usages réels derrière les transactions.";

  if (individualPayers >= 20) {
    strengthTitle = "Fond de commerce Gonette déjà visible";
    strengthText = `${formatProfessionalMeetingInteger(individualPayers)} particuliers distincts ont réglé ce professionnel sur la période. C’est un bon point d’appui pour travailler l’ancrage clientèle.`;
  } else if (individualPayers >= 5) {
    strengthTitle = "Première base clientèle Gonette";
    strengthText = `${formatProfessionalMeetingInteger(individualPayers)} particuliers distincts apparaissent déjà comme payeurs. Le professionnel dispose d’un socle d’usage à consolider.`;
  } else if (professionalPayers >= 3) {
    strengthTitle = "Insertion B2B repérable";
    strengthText = `${formatProfessionalMeetingInteger(professionalPayers)} professionnels distincts alimentent déjà ses encaissements. Cette assise réseau peut servir de levier de réemploi.`;
  } else if (totalReceived > 0) {
    strengthTitle = "Activité Gonette déjà amorcée";
    strengthText = "Des flux sont bien présents. L’enjeu est désormais de les rendre plus réguliers, plus lisibles et plus utiles au professionnel.";
  }

  let actionTitle = "Préparer un entretien exploratoire";
  let actionText = "Revenir sur les usages concrets, les freins et les dépenses susceptibles d’être réglées en Gonette.";
  let actionTone = "neutral";

  if (reconverted > 0 && reconverted >= totalReemitted) {
    actionTitle = "Comprendre la sortie du circuit";
    actionText = "La reconversion pèse autant ou davantage que le réemploi. Le rendez-vous doit identifier ce qui empêche les Gonettes d’être redépensées dans le réseau.";
    actionTone = "attention";
  } else if (reuseRate > 100) {
    actionTitle = "Documenter une mobilisation active du stock";
    actionText = "Le professionnel a réinjecté davantage de Gonettes qu’il n’en a reçu ou converti sur la période. Ce profil suggère l’utilisation d’un stock antérieur disponible et mérite d’être documenté : quels achats, quels fournisseurs, quelles habitudes rendent cette circulation possible ?";
    actionTone = "positive";
  } else if (totalReceived > 0 && reuseRate < 15) {
    actionTitle = "Ouvrir des débouchés de réemploi";
    actionText = "Les Gonettes sont bien captées mais très peu remises en circulation. Priorité : repérer 2 à 5 fournisseurs, charges ou partenaires compatibles avec un paiement en Gonette.";
    actionTone = "attention";
  } else if (totalReceived > 0 && reuseRate < 40) {
    actionTitle = "Structurer le réemploi";
    actionText = "Le réemploi existe, mais il reste limité. Le rendez-vous peut viser la transformation de dépenses ponctuelles en habitudes d’achat professionnelles en Gonette.";
    actionTone = "watch";
  } else if (reuseRate >= 65) {
    actionTitle = "Valoriser une pratique exemplaire";
    actionText = "Le professionnel réinjecte fortement ses Gonettes dans le réseau. L’entretien peut documenter les bonnes pratiques et identifier les maillons qui rendent cette circulation possible.";
    actionTone = "positive";
  } else if (c2bShare < 35 && individualPayers < 5) {
    actionTitle = "Renforcer la visibilité auprès des particuliers";
    actionText = "Le fond de commerce Gonette côté usagers particuliers semble encore modeste. Une piste consiste à travailler signalétique, communication et mobilisation de la clientèle.";
    actionTone = "watch";
  }

  return {
    profileTitle,
    profileText,
    strengthTitle,
    strengthText,
    actionTitle,
    actionText,
    actionTone,
  };
}

function drawProMeetingHeroSection() {
  const container = document.getElementById("proMeetingHeroSection");
  if (!container || !appState.detailData || !appState.currentPro) {
    return;
  }

  const data = appState.detailData;
  const numProf = appState.currentPro;
  const tx = data.transactions || [];
  const filteredStats = computeStatsFromTransactions(tx, numProf);
  const enrichment = data.odoo_enrichment || {};

  let professionalName = String(
    data.fullname || enrichment.odoo_name || numProf
  ).trim();

  const prefixHyphen = `${numProf} - `;
  const prefixDash = `${numProf} — `;

  if (professionalName.startsWith(prefixHyphen)) {
    professionalName = professionalName.slice(prefixHyphen.length).trim();
  } else if (professionalName.startsWith(prefixDash)) {
    professionalName = professionalName.slice(prefixDash.length).trim();
  }

  const detailedActivity = String(enrichment.detailed_activity || "").trim();
  const industryName = String(enrichment.industry_name || "").trim();
  const location = formatProfessionalLocation(enrichment);
  const description = plainTextFromHtml(enrichment.website_description_html);

  const totalReceived = Number(filteredStats.montant_total_recu || 0);
  const c2bReceived = Number(filteredStats.montant_recu_particuliers || 0);
  const totalReemitted = Number(filteredStats.total_montant_emis_sans_reconversion || 0);
  const individualPayers = Number(filteredStats.nb_particuliers || 0);
  const reuseRate = normalizeProfessionalReuseRate(filteredStats.taux_reutilisation);

  const diagnostic = buildProfessionalMeetingDiagnostic(filteredStats);

  const identityTags = [
    industryName
      ? `<span class="pro-meeting-identity-tag">${escapeHtml(industryName)}</span>`
      : "",
    location
      ? `<span class="pro-meeting-identity-tag pro-meeting-identity-tag-muted">${escapeHtml(location)}</span>`
      : "",
  ].filter(Boolean).join("");

  container.innerHTML = `
    <section class="card pro-meeting-hero-card">
      <div class="pro-meeting-hero-main">
        <div class="pro-meeting-identity">
          <div class="stat-label">Dossier d’accompagnement professionnel</div>

          <div class="pro-meeting-title-row">
            <span class="pro-meeting-professional-ref">${escapeHtml(numProf)}</span>
            <h2>${escapeHtml(professionalName || numProf)}</h2>
          </div>

          <p class="pro-meeting-activity">
            ${escapeHtml(detailedActivity || "Activité professionnelle à préciser")}
          </p>

          ${identityTags ? `<div class="pro-meeting-identity-tags">${identityTags}</div>` : ""}

          ${description
            ? `<p class="pro-meeting-description">${escapeHtml(description)}</p>`
            : ""}
        </div>

        <div class="pro-meeting-portrait-grid">
          <article class="pro-meeting-portrait-card">
            <span>Flux captés</span>
            <strong>${euro(totalReceived)}</strong>
            <small>dont ${euro(c2bReceived)} depuis les particuliers</small>
          </article>

          <article class="pro-meeting-portrait-card">
            <span>Fond de commerce Gonette</span>
            <strong>${formatProfessionalMeetingInteger(individualPayers)}</strong>
            <small>particulier(s) payeur(s) distinct(s)</small>
          </article>

          <article class="pro-meeting-portrait-card">
            <span>Réemploi engagé</span>
            <strong>${euro(totalReemitted)}</strong>
            <small>émis hors reconversion</small>
          </article>

          <article class="pro-meeting-portrait-card pro-meeting-portrait-card-highlight">
            <span>Taux de réutilisation</span>
            <strong>${percent(reuseRate)}</strong>
            <small>émis / reçu + converti sur la période</small>
          </article>
        </div>
      </div>

      <div class="pro-meeting-diagnostic-grid">
        <article class="pro-meeting-diagnostic-card">
          <span>Profil d’usage</span>
          <strong>${escapeHtml(diagnostic.profileTitle)}</strong>
          <p>${escapeHtml(diagnostic.profileText)}</p>
        </article>

        <article class="pro-meeting-diagnostic-card">
          <span>Point d’appui</span>
          <strong>${escapeHtml(diagnostic.strengthTitle)}</strong>
          <p>${escapeHtml(diagnostic.strengthText)}</p>
        </article>

        <article class="pro-meeting-diagnostic-card pro-meeting-diagnostic-card-${escapeHtml(diagnostic.actionTone)}">
          <span>Priorité de rendez-vous</span>
          <strong>${escapeHtml(diagnostic.actionTitle)}</strong>
          <p>${escapeHtml(diagnostic.actionText)}</p>
        </article>
      </div>

      <div class="pro-meeting-method-note">
        <strong>Lecture automatique.</strong>
        Ce diagnostic est généré à partir des transactions de la période sélectionnée :
        structure des encaissements, base de payeurs particuliers,
        réémission hors reconversion et taux de réutilisation.
      </div>
    </section>
  `;
}

function drawProOdooEnrichmentSection() {
  const container = document.getElementById("proOdooEnrichmentSection");
  if (!container || !appState.detailData) return;

  const enrichment = appState.detailData.odoo_enrichment;
  if (!enrichment) {
    container.innerHTML = "";
    return;
  }

  const detailedActivity = String(enrichment.detailed_activity || "").trim();
  const industryName = String(enrichment.industry_name || "").trim();
  const odooName = String(enrichment.odoo_name || "").trim();
  const displayedName = String(appState.detailData.fullname || "").trim();
  const shouldShowOdooName = Boolean(
    odooName
    && odooName.toLocaleLowerCase("fr-FR") !== displayedName.toLocaleLowerCase("fr-FR")
  );
  const naf = String(enrichment.naf || "").trim();
  const location = formatProfessionalLocation(enrichment);

  const secondaryIndustries = Array.isArray(enrichment.secondary_industries)
    ? enrichment.secondary_industries
        .map(item => String((item && item.industry_name) || "").trim())
        .filter(Boolean)
    : [];

  const hasVisibleContent = Boolean(
    detailedActivity ||
    industryName ||
    shouldShowOdooName ||
    naf ||
    location ||
    secondaryIndustries.length
  );

  if (!hasVisibleContent) {
    container.innerHTML = "";
    return;
  }

  const metaItems = [];

  if (shouldShowOdooName) {
    metaItems.push(`
      <div class="pro-context-meta-item">
        <span class="pro-context-meta-label">Nom annuaire</span>
        <span class="pro-context-meta-value">${escapeHtml(odooName)}</span>
      </div>
    `);
  }

  if (industryName) {
    metaItems.push(`
      <div class="pro-context-meta-item">
        <span class="pro-context-meta-label">Secteur principal</span>
        <span class="pro-context-meta-value">${escapeHtml(industryName)}</span>
      </div>
    `);
  }

  if (location) {
    metaItems.push(`
      <div class="pro-context-meta-item">
        <span class="pro-context-meta-label">Localisation</span>
        <span class="pro-context-meta-value">${escapeHtml(location)}</span>
      </div>
    `);
  }

  if (naf) {
    metaItems.push(`
      <div class="pro-context-meta-item">
        <span class="pro-context-meta-label">Code NAF</span>
        <span class="pro-context-meta-value">${escapeHtml(naf)}</span>
      </div>
    `);
  }

  const metaGridHtml = metaItems.length
    ? `<div class="pro-context-meta-grid">${metaItems.join("")}</div>`
    : "";

  const secondaryIndustriesHtml = secondaryIndustries.length
    ? `
      <div class="pro-context-secondary">
        <div class="pro-context-meta-label">Autres secteurs</div>
        <div class="pro-context-tags">
          ${secondaryIndustries
            .map(name => `<span class="pro-context-tag">${escapeHtml(name)}</span>`)
            .join("")}
        </div>
      </div>
    `
    : "";

   container.innerHTML = `
    <section class="card pro-context-card">
      <div class="pro-context-heading">
        <div class="stat-label">Profil professionnel</div>
        <h3>${escapeHtml(detailedActivity || "Informations d’activité")}</h3>
      </div>

      ${metaGridHtml}
      ${secondaryIndustriesHtml}
    </section>
  `;
}


function buildProfessionalFlowReading(filteredStats = {}) {
  const totalReceived = Number(filteredStats.montant_total_recu || 0);
  const c2bReceived = Number(filteredStats.montant_recu_particuliers || 0);
  const b2bReceived = Number(filteredStats.montant_recu_professionnels || 0);
  const converted = Number(filteredStats.montant_converti || 0);
  const emittedToPros = Number(filteredStats.montant_emis_vers_pro || 0);
  const emittedToIndividuals = Number(filteredStats.montant_emis_vers_particuliers || 0);
  const totalReemitted = Number(filteredStats.total_montant_emis_sans_reconversion || 0);
  const reconverted = Number(filteredStats.montant_reconverti || 0);
  const reuseRate = normalizeProfessionalReuseRate(filteredStats.taux_reutilisation);

  const availableFlow = totalReceived + converted;
  const c2bShare = totalReceived > 0 ? (c2bReceived / totalReceived) * 100 : 0;
  const b2bShare = totalReceived > 0 ? (b2bReceived / totalReceived) * 100 : 0;
  const professionalReuseShare = totalReemitted > 0
    ? (emittedToPros / totalReemitted) * 100
    : 0;
  const individualReuseShare = totalReemitted > 0
    ? (emittedToIndividuals / totalReemitted) * 100
    : 0;

  const outgoingTotal = totalReemitted + reconverted;
  const reconversionShareOfOutgoing = outgoingTotal > 0
    ? (reconverted / outgoingTotal) * 100
    : 0;

  let headline = "Une trajectoire monétaire à documenter";
  let interpretation = "Les flux de la période permettent d’observer les entrées et sorties de Gonettes, mais leur logique d’usage mérite encore d’être approfondie en rendez-vous.";

  if (availableFlow <= 0 && outgoingTotal <= 0) {
    headline = "Aucune trajectoire significative sur la période";
    interpretation = "Le compte ne présente pas de circulation monétaire notable sur l’intervalle sélectionné. L’accompagnement peut d’abord porter sur l’activation des usages.";
  } else if (reconverted > totalReemitted && reconverted > 0) {
    headline = "La sortie du circuit domine la trajectoire";
    interpretation = `Le professionnel reconvertit ${euro(reconverted)}, contre ${euro(totalReemitted)} seulement remis en circulation. Le rendez-vous doit prioritairement chercher ce qui empêche le réemploi local des Gonettes.`;
  } else if (reuseRate > 100) {
    headline = "Le professionnel mobilise activement un stock antérieur";
    interpretation = `Il réémet ${euro(totalReemitted)} alors que les flux reçus ou convertis sur la période représentent ${euro(availableFlow)}. Cette configuration signale l’usage d’un stock déjà disponible et constitue un cas intéressant à documenter.`;
  } else if (c2bShare >= 75 && reuseRate < 25) {
    headline = "La captation commerciale existe, le réemploi reste à structurer";
    interpretation = `Les particuliers représentent ${percent(c2bShare)} des encaissements, mais le taux de réutilisation atteint seulement ${percent(reuseRate)}. Le professionnel constitue un bon point de réception de Gonettes, sans encore les redéployer pleinement dans le réseau.`;
  } else if (b2bShare >= 45 && reuseRate < 25) {
    headline = "Un acteur B2B alimenté, mais peu redistributif";
    interpretation = `Les autres professionnels représentent ${percent(b2bShare)} des montants reçus. Pourtant, le réemploi reste limité à ${percent(reuseRate)} : un potentiel de redéploiement interprofessionnel est à travailler.`;
  } else if (reuseRate >= 65) {
    headline = "Une circulation interne déjà bien installée";
    interpretation = `Le taux de réutilisation atteint ${percent(reuseRate)}. Les Gonettes reçues alimentent donc effectivement de nouveaux paiements, ce qui fait de ce professionnel un maillon utile de la circulation locale.`;
  } else {
    headline = "Une circulation partielle, avec des leviers de progression";
    interpretation = `Le professionnel capte ${euro(totalReceived)} et remet ${euro(totalReemitted)} en circulation. Le profil n’est ni bloqué ni pleinement circulant : c’est un terrain favorable pour identifier des leviers concrets de réemploi.`;
  }

  return {
    totalReceived,
    c2bReceived,
    b2bReceived,
    converted,
    emittedToPros,
    emittedToIndividuals,
    totalReemitted,
    reconverted,
    reuseRate,
    availableFlow,
    c2bShare,
    b2bShare,
    professionalReuseShare,
    individualReuseShare,
    reconversionShareOfOutgoing,
    headline,
    interpretation,
  };
}

function buildProfessionalFlowNode({
  eyebrow,
  label,
  value,
  detail,
  action = "",
  active = false,
  tone = "",
}) {
  const className = [
    "pro-flow-node",
    active ? "pro-flow-node-active" : "",
    tone ? `pro-flow-node-${tone}` : "",
    action ? "pro-flow-node-clickable" : "",
  ].filter(Boolean).join(" ");

  const openingTag = action
    ? `<button type="button" class="${className}" onclick="${action}">`
    : `<article class="${className}">`;

  const closingTag = action ? "</button>" : "</article>";

  return `
    ${openingTag}
      ${eyebrow ? `<span>${eyebrow}</span>` : ""}
      <strong>${label}</strong>
      <b>${value}</b>
      ${detail ? `<small>${detail}</small>` : ""}
    ${closingTag}
  `;
}

function buildProfessionalFlowMeter(label, value, detail, tone = "") {
  const safeValue = Math.max(0, Math.min(100, Number(value || 0)));
  const toneClass = tone ? ` pro-flow-meter-${tone}` : "";

  return `
    <div class="pro-flow-meter${toneClass}">
      <div class="pro-flow-meter-heading">
        <span>${label}</span>
        <strong>${percent(value || 0)}</strong>
      </div>
      <div class="pro-flow-meter-track">
        <div class="pro-flow-meter-fill" style="width: ${safeValue}%"></div>
      </div>
      <small>${detail}</small>
    </div>
  `;
}

function drawProSummarySection() {
  const summaryContainer = document.getElementById("proSummarySection");
  if (!summaryContainer || !appState.detailData || !appState.currentPro) return;

  const data = appState.detailData;
  const numProf = appState.currentPro;
  const detailMode = appState.detailMode;
  const tx = data.transactions || [];
  const filteredStats = computeStatsFromTransactions(tx, numProf);
  const flow = buildProfessionalFlowReading(filteredStats);

  summaryContainer.innerHTML = `
    <section class="card pro-flow-reading-card">
      <div class="pro-flow-reading-heading">
        <div>
          <div class="stat-label">Trajectoire économique des Gonettes</div>
          <h3>${escapeHtml(flow.headline)}</h3>
          <p>${escapeHtml(flow.interpretation)}</p>
        </div>
      </div>

      <div class="pro-flow-stage">
        <section class="pro-flow-column pro-flow-column-in">
          <div class="pro-flow-column-heading">
            <span>1</span>
            <h4>Ce qui entre</h4>
          </div>

          <div class="pro-flow-node-stack">
            ${buildProfessionalFlowNode({
              eyebrow: "Clientèle particulière",
              label: "C2B reçu",
              value: euro(flow.c2bReceived),
              detail: `${formatProfessionalMeetingInteger(filteredStats.nb_particuliers || 0)} particulier(s) payeur(s)`,
              action: `renderProDetail('${escapeHtml(numProf)}', 'payeurs_particuliers')`,
              active: detailMode === "payeurs_particuliers",
              tone: "c2b",
            })}

            ${buildProfessionalFlowNode({
              eyebrow: "Réseau professionnel",
              label: "B2B reçu",
              value: euro(flow.b2bReceived),
              detail: `${formatProfessionalMeetingInteger(filteredStats.nb_professionnels || 0)} professionnel(s) payeur(s)`,
              action: `renderProDetail('${escapeHtml(numProf)}', 'payeurs_professionnels')`,
              active: detailMode === "payeurs_professionnels",
              tone: "b2b",
            })}

            ${buildProfessionalFlowNode({
              eyebrow: "Alimentation du compte",
              label: "Converti",
              value: euro(flow.converted),
              detail: "gonettes numériques créditées",
              action: `renderProDetail('${escapeHtml(numProf)}', 'converti')`,
              active: detailMode === "converti",
              tone: "conversion",
            })}
          </div>
        </section>

        <section class="pro-flow-column pro-flow-column-center">
          <div class="pro-flow-column-heading">
            <span>2</span>
            <h4>Ce qui est mobilisé</h4>
          </div>

          <article class="pro-flow-core-card">
            <span>Gonettes reçues ou converties</span>
            <strong>${euro(flow.availableFlow)}</strong>
            <small>
              ${euro(flow.totalReceived)} reçu · ${euro(flow.converted)} converti
            </small>
          </article>

          <div class="pro-flow-core-secondary">
            ${staticStatCard(
              "Transactions reçues",
              formatProfessionalMeetingInteger(filteredStats.nb_transactions_recues ?? 0),
              false,
              "Nombre total de transactions reçues sur la période."
            )}
          </div>
        </section>

        <section class="pro-flow-column pro-flow-column-out">
          <div class="pro-flow-column-heading">
            <span>3</span>
            <h4>Ce qui repart</h4>
          </div>

          <div class="pro-flow-node-stack">
            ${buildProfessionalFlowNode({
              eyebrow: "Réemploi B2B",
              label: "Émis vers pros",
              value: euro(flow.emittedToPros),
              detail: "achats ou paiements dans le réseau",
              action: `renderProDetail('${escapeHtml(numProf)}', 'emis_pro')`,
              active: detailMode === "emis_pro",
              tone: "reemission",
            })}

            ${buildProfessionalFlowNode({
              eyebrow: "Versements vers U",
              label: "Émis vers particuliers",
              value: euro(flow.emittedToIndividuals),
              detail: "défraiements, rémunérations ou assimilés",
              action: `renderProDetail('${escapeHtml(numProf)}', 'emis_particuliers')`,
              active: detailMode === "emis_particuliers",
              tone: "reemission",
            })}

            ${buildProfessionalFlowNode({
              eyebrow: "Sortie du circuit",
              label: "Reconverti",
              value: euro(flow.reconverted),
              detail: "gonettes retirées de la circulation numérique",
              action: `renderProDetail('${escapeHtml(numProf)}', 'reconverti')`,
              active: detailMode === "reconverti",
              tone: "reconversion",
            })}
          </div>
        </section>
      </div>

      <div class="pro-flow-insight-grid">
        ${buildProfessionalFlowMeter(
          "Part des encaissements depuis les particuliers",
          flow.c2bShare,
          "C2B reçu / total reçu",
          "c2b"
        )}

        ${buildProfessionalFlowMeter(
          "Part des encaissements depuis les professionnels",
          flow.b2bShare,
          "B2B reçu / total reçu",
          "b2b"
        )}

        ${buildProfessionalFlowMeter(
          "Part des sorties dédiées à la reconversion",
          flow.reconversionShareOfOutgoing,
          "reconverti / (réemploi + reconversion)",
          "reconversion"
        )}
      </div>

      <div class="pro-flow-legend-note">
        <strong>Comment lire cette section ?</strong>
        Elle distingue les <em>flux entrants</em> — clientèle particulière, encaissements B2B et conversions —
        des <em>flux sortants</em> — paiements réinjectés dans le réseau, versements vers particuliers et reconversions.
        Cette structure aide à préparer le rendez-vous : où les Gonettes arrivent-elles, où repartent-elles,
        et à quel endroit la circulation se bloque-t-elle ou se démultiplie-t-elle ?
      </div>
    </section>
  `;
}

function buildUserStats(transactions, userCode) {
  const tx = transactions.filter(row =>
    String(row["Réalisé par"] || "").includes(userCode) ||
    String(row["Vers"] || "").includes(userCode)
  );

  const recues = tx.filter(row => String(row["Vers"] || "").includes(userCode));
  const emises = tx.filter(row => String(row["Réalisé par"] || "").includes(userCode));

  const versPros = emises.filter(row => isPro(row["Vers"]));
  const versUsers = emises.filter(row => isUser(row["Vers"]));

  return {
    tx,
    nb_transactions: tx.length,
    somme_recue: recues.reduce((s, r) => s + Number(r["Montant"] || 0), 0),
    somme_emise: emises.reduce((s, r) => s + Number(r["Montant"] || 0), 0),
    nb_paiements_vers_pro: versPros.length,
    nb_paiements_vers_user: versUsers.length
  };
}

async function renderUserDetail(userCode) {
  if (!appState.detailData?.transactions?.length) {
    content.innerHTML = `<div class="card">Aucune donnée disponible.</div>`;
    return;
  }

  appState.currentView = "user-detail";
  setTitle(`Fiche particulier : ${userCode}`);

  const allTx = appState.detailData.transactions || [];
  const filteredTx = getFilteredTransactionsByPeriod(allTx).filter(row =>
    String(row["Réalisé par"] || "").includes(userCode) ||
    String(row["Vers"] || "").includes(userCode)
  );

  const stats = buildUserStats(filteredTx, userCode);

  content.innerHTML = `
    <div class="topbar">
      <button class="secondary-btn" onclick="renderProDetail('${escapeHtml(appState.currentPro)}', '${escapeHtml(appState.detailMode)}')">← Retour</button>
    </div>

    <div class="card">
      <h2>${escapeHtml(userCode)}</h2>
      <p><strong>Type :</strong> Particulier</p>
    </div>

    <div class="grid">
      <div class="card">
        <div class="stat-label">Transactions</div>
        <div class="stat-value">${stats.nb_transactions}</div>
      </div>
      <div class="card">
        <div class="stat-label">Somme reçue</div>
        <div class="stat-value">${euro(stats.somme_recue)}</div>
      </div>
      <div class="card">
        <div class="stat-label">Somme émise</div>
        <div class="stat-value">${euro(stats.somme_emise)}</div>
      </div>
      <div class="card">
        <div class="stat-label">Paiements vers pro</div>
        <div class="stat-value">${stats.nb_paiements_vers_pro}</div>
      </div>
      <div class="card">
        <div class="stat-label">Paiements vers particulier</div>
        <div class="stat-value">${stats.nb_paiements_vers_user}</div>
      </div>
    </div>

    <div class="card">
      <h3>Transactions</h3>
      ${transactionTable(filteredTx)}
    </div>
  `;
}

function setProTab(tabName) {
  appState.proTab = tabName;
  drawProTabContent();
}

function destroyProCharts() {
  if (appState.charts.activity) {
    appState.charts.activity.destroy();
    appState.charts.activity = null;
  }

  if (appState.charts.balance) {
    appState.charts.balance.destroy();
    appState.charts.balance = null;
  }

  if (
    appState.proDetailNetworkCy
    && typeof appState.proDetailNetworkCy.destroy === "function"
  ) {
    appState.proDetailNetworkCy.destroy();
  }

  if (appState.charts.proDetailBalanceHistory) {
    appState.charts.proDetailBalanceHistory.destroy();
    appState.charts.proDetailBalanceHistory = null;
  }

  if (appState.charts.proDetailCustomerConcentration) {
    appState.charts.proDetailCustomerConcentration.destroy();
    appState.charts.proDetailCustomerConcentration = null;
  }

  if (appState.proDetailPaymentBasinAnimationFrame) {
    window.cancelAnimationFrame(appState.proDetailPaymentBasinAnimationFrame);
  }

  appState.proDetailPaymentBasinAnimationFrame = null;
  appState.proDetailNetworkCy = null;
}

function destroyGlobalCharts() {
  const keys = [
    "globalDailyCount",
    "globalWeeklyAvg",
    "globalHourly",
    "globalWeekday",
    "globalCumulative"
  ];

  keys.forEach(key => {
    if (appState.charts[key]) {
      appState.charts[key].destroy();
      appState.charts[key] = null;
    }
  });
}

function getWeekStart(dateStr) {
  const d = parseFrDate(dateStr);
  if (Number.isNaN(d.getTime())) return null;

  const day = d.getDay();
  const diff = d.getDate() - (day === 0 ? 6 : day - 1);
  d.setDate(diff);

  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();

  return `${dd}/${mm}/${yyyy}`;
}

function buildGlobalDailyCountSeries(transactions) {
  const byDay = new Map();

  transactions.forEach(row => {
    const day = String(row.Date || "");
    if (!day) return;
    byDay.set(day, (byDay.get(day) || 0) + 1);
  });

  const labels = [...byDay.keys()].sort((a, b) => parseFrDate(a) - parseFrDate(b));
  return {
    labels,
    values: labels.map(d => byDay.get(d))
  };
}

function buildGlobalWeeklyAverageSeries(transactions) {
  const byWeek = new Map();

  transactions.forEach(row => {
    const week = getWeekStart(String(row.Date || ""));
    const amount = Number(row["Montant"] || 0);
    if (!week || Number.isNaN(amount)) return;

    if (!byWeek.has(week)) {
      byWeek.set(week, { sum: 0, count: 0 });
    }

    const bucket = byWeek.get(week);
    bucket.sum += amount;
    bucket.count += 1;
  });

  const labels = [...byWeek.keys()].sort((a, b) => parseFrDate(a) - parseFrDate(b));
  return {
    labels,
    values: labels.map(d => {
      const bucket = byWeek.get(d);
      return bucket.count ? bucket.sum / bucket.count : 0;
    })
  };
}

function buildGlobalHourlySeries(transactions) {
  const counts = Array(24).fill(0);

  transactions.forEach(row => {
    const raw = String(row.Date || "");
    const match = raw.match(/(\d{1,2}):(\d{2})/);
    if (!match) return;

    const hour = Number(match[1]);
    if (!Number.isNaN(hour) && hour >= 0 && hour < 24) {
      counts[hour] += 1;
    }
  });

  return {
    labels: Array.from({ length: 24 }, (_, i) => `${i}h`),
    values: counts
  };
}

function buildGlobalWeekdaySeries(transactions) {
  const counts = [0, 0, 0, 0, 0, 0, 0];
  const labels = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];

  transactions.forEach(row => {
    const d = parseFrDate(String(row.Date || ""));
    if (Number.isNaN(d.getTime())) return;

    const jsDay = d.getDay();
    const idx = jsDay === 0 ? 6 : jsDay - 1;
    counts[idx] += 1;
  });

  return { labels, values: counts };
}

function buildGlobalCumulativeSeries(transactions) {
  const sorted = [...transactions].sort(
    (a, b) => parseFrDate(String(a.Date || "")) - parseFrDate(String(b.Date || ""))
  );

  const labels = [];
  const values = [];
  let total = 0;

  sorted.forEach(row => {
    const day = String(row.Date || "");
    const amount = Number(row["Montant"] || 0);
    if (!day || Number.isNaN(amount)) return;

    total += amount;
    labels.push(day);
    values.push(total);
  });

  return { labels, values };
}

function renderGlobalCharts(transactions) {
  const host = document.getElementById("globalStatsCharts");
  if (!host) return;

  destroyGlobalCharts();

  host.innerHTML = `
    <div class="card">
      <h3>Transactions par jour, par nature d’opération</h3>
      <canvas id="globalDailyCountChart" height="110"></canvas>
    </div>

    <div class="card">
      <h3>Montant moyen hebdomadaire</h3>
      <canvas id="globalWeeklyAvgChart" height="110"></canvas>
    </div>

    <div class="card">
      <h3>Transactions par heure</h3>
      <canvas id="globalHourlyChart" height="90"></canvas>
    </div>

    <div class="card">
      <h3>Transactions par jour de la semaine</h3>
      <canvas id="globalWeekdayChart" height="90"></canvas>
    </div>

    <div class="card">
      <h3>Volume cumulé des transactions</h3>
      <canvas id="globalCumulativeChart" height="110"></canvas>
    </div>
  `;

  const daily = buildGlobalDailyCountSeries(transactions);
  const weekly = buildGlobalWeeklyAverageSeries(transactions);
  const hourly = buildGlobalHourlySeries(transactions);
  const weekday = buildGlobalWeekdaySeries(transactions);
  const cumulative = buildGlobalCumulativeSeries(transactions);

  appState.charts.globalDailyCount = new Chart(document.getElementById("globalDailyCountChart"), {
    type: "line",
    data: {
      labels: daily.labels,
      datasets: [{
        label: "Transactions",
        data: daily.values,
        fill: true,
        tension: 0.25
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: "top" }
      },
      scales: {
        x: {
          ticks: { maxRotation: 45, minRotation: 0 }
        },
        y: {
          beginAtZero: true
        }
      }
    }
  });

  appState.charts.globalWeeklyAvg = new Chart(document.getElementById("globalWeeklyAvgChart"), {
    type: "line",
    data: {
      labels: weekly.labels,
      datasets: [{
        label: "Montant moyen",
        data: weekly.values,
        fill: true,
        tension: 0.25
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: "top" },
        tooltip: {
          callbacks: {
            label: function(context) {
              return `${context.dataset.label}: ${euro(context.raw)}`;
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { maxRotation: 45, minRotation: 0 }
        },
        y: {
          beginAtZero: true
        }
      }
    }
  });

  appState.charts.globalHourly = new Chart(document.getElementById("globalHourlyChart"), {
    type: "bar",
    data: {
      labels: hourly.labels,
      datasets: [{
        label: "Transactions",
        data: hourly.values
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: "top" }
      },
      scales: {
        y: {
          beginAtZero: true
        }
      }
    }
  });

  appState.charts.globalWeekday = new Chart(document.getElementById("globalWeekdayChart"), {
    type: "bar",
    data: {
      labels: weekday.labels,
      datasets: [{
        label: "Transactions",
        data: weekday.values
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: "top" }
      },
      scales: {
        y: {
          beginAtZero: true
        }
      }
    }
  });

  appState.charts.globalCumulative = new Chart(document.getElementById("globalCumulativeChart"), {
    type: "line",
    data: {
      labels: cumulative.labels,
      datasets: [{
        label: "Volume cumulé",
        data: cumulative.values,
        fill: true,
        tension: 0.2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: "top" },
        tooltip: {
          callbacks: {
            label: function(context) {
              return `${context.dataset.label}: ${euro(context.raw)}`;
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { maxRotation: 45, minRotation: 0 }
        },
        y: {
          beginAtZero: true
        }
      }
    }
  });
}

function buildDailyActivitySeries(transactions, numProf) {
  const filtered = getFilteredTransactionsByPeriod(transactions);
  const byDay = new Map();

  function ensureDay(dateStr) {
    if (!byDay.has(dateStr)) {
      byDay.set(dateStr, { recu: 0, emis: 0, conversion: 0 });
    }
    return byDay.get(dateStr);
  }

  filtered.forEach(row => {
    const day = String(row.Date || "");
    const amount = Number(row["Montant"] || 0);
    const from = String(row["Réalisé par"] || "");
    const to = String(row["Vers"] || "");

    const bucket = ensureDay(day);

    const isReceived =
      to.includes(numProf) && !isConversion(from);

    const isEmitted =
      from.includes(numProf) &&
      !isConversion(to) &&
      (isPro(to) || isUser(to));

    const isConv =
      (from.includes(numProf) && isConversion(to)) ||
      (to.includes(numProf) && isConversion(from));

    if (isReceived) bucket.recu += amount;
    if (isEmitted) bucket.emis += amount;
    if (isConv) bucket.conversion += amount;
  });

  const labels = [...byDay.keys()].sort((a, b) => parseFrDate(a) - parseFrDate(b));
  return {
    labels,
    recu: labels.map(d => byDay.get(d).recu),
    emis: labels.map(d => byDay.get(d).emis),
    conversion: labels.map(d => byDay.get(d).conversion)
  };
}

function buildBalanceData(transactions, numProf) {
  const filtered = getFilteredTransactionsByPeriod(transactions);

  let recu = 0;
  let emis = 0;

  filtered.forEach(row => {
    const amount = Number(row["Montant"] || 0);
    const from = String(row["Réalisé par"] || "");
    const to = String(row["Vers"] || "");

    const isReceived =
      to.includes(numProf) && !isConversion(from);

    const isEmitted =
      from.includes(numProf) &&
      !isConversion(to) &&
      (isPro(to) || isUser(to));

    if (isReceived) recu += amount;
    if (isEmitted) emis += amount;
  });

  return { recu, emis };
}

function formatProfessionalNetworkCount(value) {
  return Number(value || 0).toLocaleString("fr-FR");
}

function formatProfessionalNetworkLocation(node = {}) {
  const zip = String(node?.zip || "").trim();
  const city = String(node?.city || "").trim();

  if (zip && city) {
    return `${zip} ${city}`;
  }

  return city || zip || "Localisation non renseignée";
}

function buildProfessionalDetailNetworkPositions(nodes = []) {
  const centerNode = nodes.find(node => node.role === "center");
  const inboundOnly = nodes.filter(node =>
    node.role !== "center"
    && Array.isArray(node.directions)
    && node.directions.includes("inbound")
    && !node.directions.includes("outbound")
  );
  const outboundOnly = nodes.filter(node =>
    node.role !== "center"
    && Array.isArray(node.directions)
    && node.directions.includes("outbound")
    && !node.directions.includes("inbound")
  );
  const reciprocal = nodes.filter(node =>
    node.role !== "center"
    && Array.isArray(node.directions)
    && node.directions.includes("inbound")
    && node.directions.includes("outbound")
  );

  const individualPayersNode = nodes.find(
    node => node.role === "individual_payers"
  );

  const positions = {};

  if (centerNode) {
    positions[centerNode.id] = { x: 0, y: 0 };
  }

  const distribute = (items, x, gap = 108, yOffset = 0) => {
    const count = items.length;
    const start = -((count - 1) * gap) / 2;

    items.forEach((item, index) => {
      positions[item.id] = {
        x,
        y: start + index * gap + yOffset
      };
    });
  };

  distribute(inboundOnly, -430, 104, 0);
  distribute(outboundOnly, 430, 104, 0);
  distribute(reciprocal, 0, 106, -240);

  if (individualPayersNode) {
    const inboundHeight = inboundOnly.length > 0
      ? ((inboundOnly.length - 1) * 104) / 2
      : 0;

    positions[individualPayersNode.id] = {
      x: -430,
      y: inboundOnly.length > 0 ? -inboundHeight - 150 : 0
    };
  }

  return positions;
}

function getProfessionalDetailNetworkNodeRelation(nodeId, dynamics) {
  const network = dynamics?.b2b_network || {};
  const links = Array.isArray(network.links) ? network.links : [];
  const centerRef = network.center?.professional_ref || "";

  const inboundLinks = links.filter(link =>
    link.source === nodeId && link.target === centerRef
  );

  const outboundLinks = links.filter(link =>
    link.source === centerRef && link.target === nodeId
  );

  const inboundVolume = inboundLinks.reduce(
    (sum, link) => sum + Number(link.volume || 0),
    0
  );

  const outboundVolume = outboundLinks.reduce(
    (sum, link) => sum + Number(link.volume || 0),
    0
  );

  const inboundTxCount = inboundLinks.reduce(
    (sum, link) => sum + Number(link.tx_count || 0),
    0
  );

  const outboundTxCount = outboundLinks.reduce(
    (sum, link) => sum + Number(link.tx_count || 0),
    0
  );

  return {
    inboundVolume,
    outboundVolume,
    inboundTxCount,
    outboundTxCount,
  };
}

function renderProfessionalDetailNetworkPanel(nodeId = null) {
  const panel = document.getElementById("proDetailB2BNetworkPanel");
  const dynamics = appState.proDetailDynamics;
  const network = dynamics?.b2b_network;

  if (!panel || !network) {
    return;
  }

  const center = network.center || {};
  const summary = network.summary || {};
  const node = (network.nodes || []).find(item => item.id === nodeId);

  if (node && node.role === "individual_payers") {
    panel.innerHTML = `
      <div class="pro-detail-network-panel-card">
        <div class="stat-label">Fond de commerce Gonette</div>
        <h4>Particuliers payeurs</h4>

        <div class="pro-detail-network-panel-ref">
          Agrégat U
        </div>

        <div class="pro-detail-network-panel-metrics pro-detail-network-panel-metrics-single">
          <div>
            <strong>${formatProfessionalNetworkCount(node.distinct_payer_count || 0)}</strong>
            <span>particulier(s) distinct(s)</span>
          </div>
        </div>

        <div class="pro-detail-network-relation-list">
          <div class="pro-detail-network-relation pro-detail-network-relation-individual">
            <span>Volume C2B reçu</span>
            <strong>${euro(node.volume || 0)}</strong>
            <small>${formatProfessionalNetworkCount(node.tx_count || 0)} transaction(s)</small>
          </div>

          <div class="pro-detail-network-relation pro-detail-network-relation-individual">
            <span>Ticket moyen C2B</span>
            <strong>${euro(node.average_transaction_amount || 0)}</strong>
            <small>volume / nombre de paiements</small>
          </div>

          <div class="pro-detail-network-relation pro-detail-network-relation-individual">
            <span>Volume moyen par payeur</span>
            <strong>${euro(node.average_volume_per_payer || 0)}</strong>
            <small>volume / particuliers distincts</small>
          </div>
        </div>

        <p class="pro-detail-network-individual-note">
          Ce nœud agrège l’ensemble des utilisateurs particuliers ayant payé
          le professionnel sur la période. Il ne représente jamais une localisation
          ni une identité individuelle.
        </p>
      </div>
    `;
    return;
  }

  if (!node || node.role === "center") {
    panel.innerHTML = `
      <div class="pro-detail-network-panel-card">
        <div class="stat-label">Lecture du graphe</div>
        <h4>${escapeHtml(center.name || center.professional_ref || "Professionnel")}</h4>

        <div class="pro-detail-network-panel-metrics">
          <div>
            <strong>${formatProfessionalNetworkCount(summary.inbound_counterparty_count || 0)}</strong>
            <span>pros acheteurs</span>
          </div>
          <div>
            <strong>${formatProfessionalNetworkCount(summary.outbound_counterparty_count || 0)}</strong>
            <span>pros payés</span>
          </div>
        </div>

        <p>
          Le graphe montre les relations B2B commerciales immédiates :
          à gauche les professionnels qui paient ce compte,
          à droite ceux auxquels il redépense ses Gonettes.
        </p>
      </div>
    `;
    return;
  }

  const relation = getProfessionalDetailNetworkNodeRelation(node.id, dynamics);
  const inboundVisible = relation.inboundVolume > 0 || relation.inboundTxCount > 0;
  const outboundVisible = relation.outboundVolume > 0 || relation.outboundTxCount > 0;

  panel.innerHTML = `
    <div class="pro-detail-network-panel-card">
      <div class="stat-label">Contrepartie B2B</div>
      <h4>${escapeHtml(node.name || node.professional_ref || node.id)}</h4>

      <div class="pro-detail-network-panel-ref">
        ${escapeHtml(node.professional_ref || node.id)}
      </div>

      ${
        node.industry_name
          ? `<p><strong>Secteur :</strong> ${escapeHtml(node.industry_name)}</p>`
          : ""
      }

      <p>
        <strong>Localisation :</strong>
        ${escapeHtml(formatProfessionalNetworkLocation(node))}
      </p>

      <div class="pro-detail-network-relation-list">
        ${
          inboundVisible
            ? `
              <div class="pro-detail-network-relation pro-detail-network-relation-inbound">
                <span>Verse vers le pro étudié</span>
                <strong>${euro(relation.inboundVolume)}</strong>
                <small>${formatProfessionalNetworkCount(relation.inboundTxCount)} transaction(s)</small>
              </div>
            `
            : ""
        }

        ${
          outboundVisible
            ? `
              <div class="pro-detail-network-relation pro-detail-network-relation-outbound">
                <span>Reçoit depuis le pro étudié</span>
                <strong>${euro(relation.outboundVolume)}</strong>
                <small>${formatProfessionalNetworkCount(relation.outboundTxCount)} transaction(s)</small>
              </div>
            `
            : ""
        }
      </div>

      <div class="pro-detail-network-panel-actions">
        <button
          type="button"
          class="primary-btn"
          onclick="renderProDetail('${escapeHtml(node.professional_ref || node.id)}')"
        >
          Ouvrir la fiche
        </button>
      </div>
    </div>
  `;
}

function bindProfessionalDetailNetworkControls(cy) {
  const fitBtn = document.getElementById("proDetailNetworkFitBtn");
  const zoomInBtn = document.getElementById("proDetailNetworkZoomInBtn");
  const zoomOutBtn = document.getElementById("proDetailNetworkZoomOutBtn");

  if (fitBtn) {
    fitBtn.addEventListener("click", () => {
      cy.fit(undefined, 56);
    });
  }

  if (zoomInBtn) {
    zoomInBtn.addEventListener("click", () => {
      cy.zoom({
        level: cy.zoom() * 1.14,
        renderedPosition: {
          x: cy.width() / 2,
          y: cy.height() / 2
        }
      });
    });
  }

  if (zoomOutBtn) {
    zoomOutBtn.addEventListener("click", () => {
      cy.zoom({
        level: cy.zoom() * 0.86,
        renderedPosition: {
          x: cy.width() / 2,
          y: cy.height() / 2
        }
      });
    });
  }
}

function renderProfessionalDetailB2BNetworkGraph(dynamics) {
  const container = document.getElementById("proDetailB2BNetworkGraph");
  const network = dynamics?.b2b_network;

  if (!container || !network || !window.cytoscape) {
    return;
  }

  const nodes = Array.isArray(network.nodes) ? network.nodes : [];
  const links = Array.isArray(network.links) ? network.links : [];

  if (!nodes.length || !links.length) {
    container.innerHTML = `
      <div class="pro-detail-network-empty">
        Aucun lien B2B commercial visible sur cette période.
      </div>
    `;
    renderProfessionalDetailNetworkPanel(null);
    return;
  }

  if (
    appState.proDetailNetworkCy
    && typeof appState.proDetailNetworkCy.destroy === "function"
  ) {
    appState.proDetailNetworkCy.destroy();
    appState.proDetailNetworkCy = null;
  }

  const positions = buildProfessionalDetailNetworkPositions(nodes);
  const maxVolume = Math.max(
    1,
    ...links.map(link => Number(link.volume || 0))
  );

  const elements = [
    ...nodes.map(node => {
      const directions = Array.isArray(node.directions) ? node.directions : [];
      const role = node.role || "counterparty";

      let relationClass = "counterparty-node";
      if (role === "center") {
        relationClass = "center-node";
      } else if (role === "individual_payers") {
        relationClass = "individual-payers-node";
      } else if (directions.includes("inbound") && directions.includes("outbound")) {
        relationClass = "reciprocal-node";
      } else if (directions.includes("outbound")) {
        relationClass = "outbound-node";
      } else {
        relationClass = "inbound-node";
      }

      return {
        group: "nodes",
        classes: relationClass,
        data: {
          id: node.id,
          professional_ref: node.professional_ref || node.id,
          label: node.role === "individual_payers"
            ? "U"
            : (node.professional_ref || node.id),
          name: node.name || node.professional_ref || node.id,
          role,
        },
        position: positions[node.id] || { x: 0, y: 0 }
      };
    }),

    ...links.map((link, index) => {
      const volume = Number(link.volume || 0);
      const displayWidth = 2.2 + (volume / maxVolume) * 6.2;

      return {
        group: "edges",
        classes: link.direction === "outbound"
          ? "outbound-edge"
          : (
              link.direction === "individual_inbound"
                ? "individual-edge"
                : "inbound-edge"
            ),
        data: {
          id: `pro-detail-network-edge-${index}`,
          source: link.source,
          target: link.target,
          volume,
          tx_count: Number(link.tx_count || 0),
          displayWidth,
          reciprocal: Boolean(link.reciprocal)
        }
      };
    })
  ];

  const cy = window.cytoscape({
    container,
    elements,
    layout: {
      name: "preset",
      fit: true,
      padding: 64
    },
    minZoom: 0.38,
    maxZoom: 2.6,
    style: [
      {
        selector: "node",
        style: {
          "label": "data(label)",
          "font-size": "11px",
          "font-weight": 800,
          "text-valign": "center",
          "text-halign": "center",
          "color": "#0f172a",
          "text-outline-width": 0,
          "width": 48,
          "height": 48,
          "border-width": 2,
          "border-color": "#ffffff",
          "background-color": "#cbd5e1",
          "overlay-opacity": 0
        }
      },
      {
        selector: "node.center-node",
        style: {
          "width": 82,
          "height": 82,
          "font-size": "12px",
          "color": "#ffffff",
          "background-color": "#0f172a",
          "border-color": "#334155",
          "border-width": 3
        }
      },
      {
        selector: "node.inbound-node",
        style: {
          "background-color": "#60a5fa",
          "border-color": "#2563eb"
        }
      },
      {
        selector: "node.outbound-node",
        style: {
          "background-color": "#fdba74",
          "border-color": "#ea580c"
        }
      },
      {
        selector: "node.reciprocal-node",
        style: {
          "background-color": "#c084fc",
          "border-color": "#7e22ce"
        }
      },
      {
        selector: "node.individual-payers-node",
        style: {
          "width": 60,
          "height": 60,
          "font-size": "13px",
          "color": "#064e3b",
          "background-color": "#6ee7b7",
          "border-color": "#059669",
          "border-width": 3
        }
      },
      {
        selector: "edge",
        style: {
          "width": "data(displayWidth)",
          "curve-style": "bezier",
          "target-arrow-shape": "triangle",
          "arrow-scale": 1.18,
          "opacity": 0.88,
          "line-cap": "round"
        }
      },
      {
        selector: "edge.inbound-edge",
        style: {
          "line-color": "#2563eb",
          "target-arrow-color": "#2563eb"
        }
      },
      {
        selector: "edge.outbound-edge",
        style: {
          "line-color": "#f97316",
          "target-arrow-color": "#f97316"
        }
      },
      {
        selector: "edge.individual-edge",
        style: {
          "line-color": "#10b981",
          "target-arrow-color": "#10b981"
        }
      },
      {
        selector: "node.selected-node",
        style: {
          "border-width": 4,
          "border-color": "#ef4444",
          "z-index": 99
        }
      },
      {
        selector: "edge.highlighted",
        style: {
          "opacity": 1,
          "z-index": 98
        }
      },
      {
        selector: "node.faded",
        style: {
          "opacity": 0.20
        }
      },
      {
        selector: "edge.faded",
        style: {
          "opacity": 0.10
        }
      }
    ]
  });

  cy.on("tap", "node", event => {
    const node = event.target;

    cy.elements().addClass("faded");
    cy.edges().removeClass("highlighted");
    cy.nodes().removeClass("selected-node");

    node.removeClass("faded");
    node.addClass("selected-node");

    const neighborhood = node.closedNeighborhood();
    neighborhood.removeClass("faded");
    node.connectedEdges().addClass("highlighted");

    renderProfessionalDetailNetworkPanel(node.id());
  });

  cy.on("tap", event => {
    if (event.target !== cy) {
      return;
    }

    cy.elements().removeClass("faded highlighted");
    cy.nodes().removeClass("selected-node");
    cy.getElementById(network.center?.professional_ref || "").addClass("selected-node");
    renderProfessionalDetailNetworkPanel(network.center?.professional_ref || null);
  });

  const centerId = network.center?.professional_ref || "";
  if (centerId) {
    cy.getElementById(centerId).addClass("selected-node");
  }

  appState.proDetailNetworkCy = cy;

  bindProfessionalDetailNetworkControls(cy);
  renderProfessionalDetailNetworkPanel(centerId);

  window.setTimeout(() => {
    if (!appState.proDetailNetworkCy) return;
    appState.proDetailNetworkCy.resize();
    appState.proDetailNetworkCy.fit(undefined, 56);
  }, 80);
}


function buildProfessionalBalanceTrajectoryReading(balanceTimeseries = {}) {
  const summary = balanceTimeseries?.summary || {};
  const openingBalance = summary.opening_balance;
  const closingBalance = summary.closing_balance;
  const minBalance = summary.min_balance;
  const maxBalance = summary.max_balance;
  const balanceChange = summary.balance_change;
  const pointCount = Number(summary.point_count || 0);

  if (
    pointCount <= 0
    || openingBalance === null
    || openingBalance === undefined
    || closingBalance === null
    || closingBalance === undefined
  ) {
    return {
      tone: "neutral",
      title: "Aucune série de solde exploitable sur cette période",
      text: "Les soldes historiques disponibles ne permettent pas encore de décrire une trajectoire de détention pour ce professionnel.",
      changeText: "—",
      relativeChange: null,
    };
  }

  const opening = Number(openingBalance || 0);
  const closing = Number(closingBalance || 0);
  const change = Number(balanceChange || 0);
  const relativeChange = opening !== 0
    ? (change / Math.abs(opening)) * 100
    : null;

  const amplitude = (
    minBalance !== null
    && minBalance !== undefined
    && maxBalance !== null
    && maxBalance !== undefined
  )
    ? Number(maxBalance || 0) - Number(minBalance || 0)
    : 0;

  const amplitudeRatio = Math.max(Math.abs(opening), Math.abs(closing), 1) > 0
    ? (amplitude / Math.max(Math.abs(opening), Math.abs(closing), 1)) * 100
    : 0;

  let tone = "neutral";
  let title = "Un niveau de détention relativement stable";
  let text = "Le solde varie au cours de la période sans dessiner de rupture marquée. Cette trajectoire peut être lue avec les flux d’encaissement, de réemploi et de reconversion.";
  let changeText = change >= 0
    ? `+${euro(change)}`
    : `−${euro(Math.abs(change))}`;

  if (opening === 0 && closing > 0) {
    tone = "watch";
    title = "Le professionnel constitue un stock de Gonettes";
    text = `Le solde part de zéro et atteint ${euro(closing)} en fin de période. Cette montée signale une accumulation nette à mettre en regard des débouchés de réemploi disponibles.`;
  } else if (closing > opening && relativeChange !== null && relativeChange >= 25) {
    tone = "watch";
    title = "Le stock de Gonettes progresse sensiblement";
    text = `Le solde passe de ${euro(opening)} à ${euro(closing)}. Cette hausse peut traduire une captation plus rapide que le réemploi et mérite d’être croisée avec les flux sortants.`;
  } else if (closing < opening && relativeChange !== null && relativeChange <= -25) {
    tone = "active";
    title = "Le solde disponible se réduit nettement";
    text = `Le solde passe de ${euro(opening)} à ${euro(closing)}. La courbe indique une mobilisation importante du stock, à interpréter avec les sorties vers le réseau ou les reconversions.`;
  } else if (amplitudeRatio >= 80) {
    tone = "watch";
    title = "Une détention très mobile au cours de la période";
    text = `Le solde oscille entre ${euro(minBalance || 0)} et ${euro(maxBalance || 0)}. Cette forte amplitude signale une circulation par à-coups ou des opérations ponctuelles d’ampleur.`;
  }

  return {
    tone,
    title,
    text,
    changeText,
    relativeChange,
  };
}

function renderProfessionalBalanceHistoryChart(balanceTimeseries = {}) {
  const canvas = document.getElementById("proDetailBalanceHistoryChart");
  const items = Array.isArray(balanceTimeseries?.items)
    ? balanceTimeseries.items
    : [];

  if (!canvas || !items.length) {
    return;
  }

  if (appState.charts.proDetailBalanceHistory) {
    appState.charts.proDetailBalanceHistory.destroy();
    appState.charts.proDetailBalanceHistory = null;
  }

  const labels = items.map(item => item.date);
  const balances = items.map(item => Number(item.balance || 0));

  appState.charts.proDetailBalanceHistory = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Solde professionnel",
          data: balances,
          tension: 0.22,
          fill: true,
          pointRadius: labels.length > 180 ? 0 : 1.6,
          pointHoverRadius: 4,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            title(items) {
              return items?.[0]?.label || "";
            },
            label(context) {
              return `Solde : ${euro(context.raw || 0)}`;
            }
          }
        }
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 12,
            maxRotation: 0,
            autoSkip: true
          }
        },
        y: {
          ticks: {
            callback(value) {
              return euro(value);
            }
          }
        }
      }
    }
  });
}

function buildProfessionalBalanceSectionHtml(balanceTimeseries = {}) {
  const summary = balanceTimeseries?.summary || {};
  const reading = buildProfessionalBalanceTrajectoryReading(balanceTimeseries);
  const hasItems = Array.isArray(balanceTimeseries?.items)
    && balanceTimeseries.items.length > 0;

  const pointCount = Number(summary.point_count || 0);

  return `
    <section class="card pro-detail-balance-card">
      <div class="pro-detail-balance-heading">
        <div>
          <div class="stat-label">Trajectoire de détention</div>
          <h3>${escapeHtml(reading.title)}</h3>
          <p>${escapeHtml(reading.text)}</p>
        </div>

        <div class="pro-detail-balance-change pro-detail-balance-change-${escapeHtml(reading.tone)}">
          <span>Variation nette du solde</span>
          <strong>${escapeHtml(reading.changeText)}</strong>
          <small>
            ${summary.opening_date || "—"} → ${summary.closing_date || "—"}
          </small>
        </div>
      </div>

      <div class="pro-detail-balance-kpis">
        <div>
          <span>Ouverture</span>
          <strong>${summary.opening_balance === null || summary.opening_balance === undefined ? "—" : euro(summary.opening_balance)}</strong>
        </div>
        <div>
          <span>Clôture</span>
          <strong>${summary.closing_balance === null || summary.closing_balance === undefined ? "—" : euro(summary.closing_balance)}</strong>
        </div>
        <div>
          <span>Minimum observé</span>
          <strong>${summary.min_balance === null || summary.min_balance === undefined ? "—" : euro(summary.min_balance)}</strong>
        </div>
        <div>
          <span>Maximum observé</span>
          <strong>${summary.max_balance === null || summary.max_balance === undefined ? "—" : euro(summary.max_balance)}</strong>
        </div>
      </div>

      ${
        hasItems
          ? `
            <div class="pro-detail-balance-chart-frame">
              <canvas id="proDetailBalanceHistoryChart"></canvas>
            </div>
          `
          : `
            <div class="pro-detail-balance-empty">
              Aucun point de solde disponible pour cette période.
            </div>
          `
      }

      <div class="pro-detail-balance-method-note">
        <strong>Lecture.</strong>
        ${formatProfessionalNetworkCount(pointCount)} point(s) quotidien(s) de solde sont utilisés ici.
        La courbe mesure un <em>stock détenu</em> à chaque date ; elle ne dit pas seule si une baisse résulte
        d’un réemploi dans le réseau ou d’une reconversion, d’où l’intérêt de la lire avec la trajectoire de flux.
      </div>
    </section>
  `;
}


function formatProfessionalHourWindow(hour) {
  const safeHour = Number(hour || 0);
  const nextHour = (safeHour + 1) % 24;
  return `${safeHour}h–${nextHour}h`;
}

function getProfessionalPaymentHeatLevel(txCount, maxTxCount) {
  const count = Number(txCount || 0);
  const max = Number(maxTxCount || 0);

  if (count <= 0 || max <= 0) {
    return 0;
  }

  const ratio = count / max;

  if (ratio >= 0.80) return 5;
  if (ratio >= 0.60) return 4;
  if (ratio >= 0.40) return 3;
  if (ratio >= 0.20) return 2;
  return 1;
}

function buildProfessionalPaymentRhythmReading(paymentRhythm = {}) {
  const summary = paymentRhythm?.summary || {};
  const txCount = Number(summary.tx_count || 0);
  const volume = Number(summary.volume || 0);
  const activeWeekdayCount = Number(summary.active_weekday_count || 0);
  const peakCell = summary.peak_cell || null;
  const peakWeekday = summary.peak_weekday || null;

  if (txCount <= 0) {
    return {
      title: "Aucun paiement particulier visible sur cette période",
      text: "La période sélectionnée ne montre pas de transaction U→P reçue par ce professionnel.",
    };
  }

  const peakWeekdayCount = Number(peakWeekday?.tx_count || 0);
  const peakWeekdayShare = txCount > 0
    ? (peakWeekdayCount / txCount) * 100
    : 0;

  let title = "Une clientèle Gonette répartie dans le temps";
  let text = `${formatProfessionalNetworkCount(txCount)} paiement(s) particulier(s) sont observés pour ${euro(volume)}.`;

  if (peakWeekday && peakWeekdayShare >= 35) {
    title = `Un rythme d’usage particulièrement marqué le ${String(peakWeekday.label || "").toLocaleLowerCase("fr-FR")}`;
    text = `${formatProfessionalNetworkCount(txCount)} paiement(s) particulier(s) sont observés pour ${euro(volume)}. Le ${String(peakWeekday.label || "").toLocaleLowerCase("fr-FR")} concentre ${percent(peakWeekdayShare)} des paiements reçus.`;
  } else if (activeWeekdayCount >= 5) {
    title = "Des paiements particuliers répartis sur l’ensemble de la semaine";
    text = `${formatProfessionalNetworkCount(txCount)} paiement(s) particulier(s) sont observés pour ${euro(volume)}. L’activité apparaît sur ${formatProfessionalNetworkCount(activeWeekdayCount)} jours de semaine distincts.`;
  } else if (activeWeekdayCount > 0) {
    title = "Un rythme de paiement concentré sur quelques jours";
    text = `${formatProfessionalNetworkCount(txCount)} paiement(s) particulier(s) sont observés pour ${euro(volume)}. Les usages sont concentrés sur ${formatProfessionalNetworkCount(activeWeekdayCount)} jour(s) de semaine.`;
  }

  if (peakCell && Number(peakCell.tx_count || 0) > 0) {
    text += ` Le créneau le plus dense est ${String(peakCell.weekday_label || "").toLocaleLowerCase("fr-FR")} ${formatProfessionalHourWindow(peakCell.hour)}, avec ${formatProfessionalNetworkCount(peakCell.tx_count || 0)} paiement(s).`;
  }

  return {
    title,
    text,
  };
}

function buildProfessionalPaymentHeatmapHtml(paymentRhythm = {}) {
  const heatmap = paymentRhythm?.heatmap || {};
  const summary = paymentRhythm?.summary || {};
  const weekdays = Array.isArray(heatmap.weekdays) ? heatmap.weekdays : [];
  const hours = Array.isArray(heatmap.hours) ? heatmap.hours : [];
  const cells = Array.isArray(heatmap.cells) ? heatmap.cells : [];
  const maxCellTxCount = Number(summary.max_cell_tx_count || 0);

  if (!weekdays.length || !hours.length || !cells.length) {
    return `
      <div class="pro-detail-payment-heatmap-empty">
        La matrice horaire ne contient pas de données exploitables.
      </div>
    `;
  }

  const cellMap = new Map(
    cells.map(cell => [
      `${cell.weekday_index}:${cell.hour}`,
      cell
    ])
  );

  return `
    <div class="pro-detail-payment-heatmap-wrap">
      <div class="pro-detail-payment-heatmap">
        <div class="pro-detail-payment-heatmap-corner"></div>

        ${hours.map(hour => `
          <div class="pro-detail-payment-heatmap-hour">
            ${hour}h
          </div>
        `).join("")}

        ${weekdays.map(weekday => {
          const weekdayIndex = Number(weekday.weekday_index || 0);
          const weekdayLabel = String(weekday.label || "");

          return `
            <div class="pro-detail-payment-heatmap-day">
              ${escapeHtml(weekdayLabel)}
            </div>

            ${hours.map(hour => {
              const cell = cellMap.get(`${weekdayIndex}:${hour}`) || {
                tx_count: 0,
                volume: 0,
                hour,
                weekday_label: weekdayLabel,
              };

              const level = getProfessionalPaymentHeatLevel(
                cell.tx_count,
                maxCellTxCount
              );

              const title = `${weekdayLabel} ${formatProfessionalHourWindow(hour)} · ${formatProfessionalNetworkCount(cell.tx_count || 0)} paiement(s) · ${euro(cell.volume || 0)}`;

              return `
                <div
                  class="pro-detail-payment-heatmap-cell pro-detail-payment-heatmap-level-${level}"
                  title="${escapeHtml(title)}"
                  aria-label="${escapeHtml(title)}"
                >
                  ${Number(cell.tx_count || 0) > 0 ? formatProfessionalNetworkCount(cell.tx_count || 0) : ""}
                </div>
              `;
            }).join("")}
          `;
        }).join("")}
      </div>
    </div>
  `;
}

function buildProfessionalPaymentRhythmSectionHtml(paymentRhythm = {}) {
  const summary = paymentRhythm?.summary || {};
  const reading = buildProfessionalPaymentRhythmReading(paymentRhythm);

  const txCount = Number(summary.tx_count || 0);
  const volume = Number(summary.volume || 0);
  const activeDayCount = Number(summary.active_day_count || 0);
  const activeSlotCount = Number(summary.active_slot_count || 0);
  const unplacedTxCount = Number(summary.unplaced_tx_count || 0);

  return `
    <section class="card pro-detail-payment-rhythm-card">
      <div class="pro-detail-payment-rhythm-heading">
        <div>
          <div class="stat-label">Rythme des paiements particuliers</div>
          <h3>${escapeHtml(reading.title)}</h3>
          <p>${escapeHtml(reading.text)}</p>
        </div>
      </div>

      <div class="pro-detail-payment-rhythm-kpis">
        <div>
          <span>Paiements U→P</span>
          <strong>${formatProfessionalNetworkCount(txCount)}</strong>
        </div>
        <div>
          <span>Volume C2B</span>
          <strong>${euro(volume)}</strong>
        </div>
        <div>
          <span>Jours actifs</span>
          <strong>${formatProfessionalNetworkCount(activeDayCount)}</strong>
        </div>
        <div>
          <span>Créneaux actifs</span>
          <strong>${formatProfessionalNetworkCount(activeSlotCount)}</strong>
        </div>
      </div>

      ${buildProfessionalPaymentHeatmapHtml(paymentRhythm)}

      <div class="pro-detail-payment-rhythm-note">
        <strong>Lecture.</strong>
        Chaque case représente un couple <em>jour de semaine × heure</em>.
        L’intensité visuelle est pondérée par le <strong>nombre de paiements</strong>,
        afin de faire ressortir les rythmes d’usage du fond de commerce Gonette.
        ${
          unplacedTxCount > 0
            ? ` ${formatProfessionalNetworkCount(unplacedTxCount)} transaction(s) n’ont pas pu être placées dans la matrice horaire.`
            : ""
        }
      </div>
    </section>
  `;
}


function buildProfessionalCustomerConcentrationReading(concentration = {}) {
  const summary = concentration?.summary || {};
  const payerCount = Number(summary.payer_count || 0);
  const top5Share = Number(summary.top_5_share_pct || 0);
  const top3Share = Number(summary.top_3_share_pct || 0);
  const effectivePayerCount = Number(summary.effective_payer_count || 0);
  const concentrationRatio = Number(summary.concentration_ratio_effective_to_observed || 0);

  if (payerCount <= 0) {
    return {
      tone: "neutral",
      title: "Aucun fond de commerce particulier visible sur cette période",
      text: "Aucun payeur particulier distinct n’est détecté dans les transactions U→P de la période sélectionnée.",
    };
  }

  if (top5Share >= 60 || concentrationRatio < 0.35) {
    return {
      tone: "attention",
      title: "Une activité C2B très concentrée autour de quelques payeurs",
      text: `Les 5 principaux payeurs représentent ${percent(top5Share)} du volume reçu depuis les particuliers. Le volume observé équivaut à une base d’environ ${formatProfessionalCustomerEffectiveCount(effectivePayerCount)} payeur(s) pleinement équilibré(s), pour ${formatProfessionalNetworkCount(payerCount)} payeur(s) distinct(s) réellement observé(s).`,
    };
  }

  if (top5Share <= 35 && concentrationRatio >= 0.60) {
    return {
      tone: "positive",
      title: "Un fond de commerce Gonette plutôt diffus",
      text: `Les 5 principaux payeurs concentrent ${percent(top5Share)} du volume C2B, ce qui signale une clientèle Gonette relativement répartie. Le top 3 pèse ${percent(top3Share)} seulement.`,
    };
  }

  return {
    tone: "watch",
    title: "Un fond de commerce Gonette modérément concentré",
    text: `Les 5 principaux payeurs représentent ${percent(top5Share)} du volume C2B. La dépendance à quelques usagers existe, sans dominer totalement la structure du fond de commerce.`,
  };
}

function formatProfessionalCustomerEffectiveCount(value) {
  const numeric = Number(value || 0);
  return numeric.toLocaleString("fr-FR", {
    minimumFractionDigits: numeric < 10 ? 1 : 0,
    maximumFractionDigits: 1,
  });
}

function renderProfessionalCustomerConcentrationChart(concentration = {}) {
  const canvas = document.getElementById("proDetailCustomerConcentrationChart");
  const points = Array.isArray(concentration?.lorenz_points)
    ? concentration.lorenz_points
    : [];

  if (!canvas || points.length === 0) {
    return;
  }

  if (appState.charts.proDetailCustomerConcentration) {
    appState.charts.proDetailCustomerConcentration.destroy();
    appState.charts.proDetailCustomerConcentration = null;
  }

  const actualPoints = points.map(point => ({
    x: Number(point.payer_share_pct || 0),
    y: Number(point.volume_share_pct || 0),
  }));

  const equalityPoints = points.map(point => {
    const share = Number(point.payer_share_pct || 0);
    return { x: share, y: share };
  });

  appState.charts.proDetailCustomerConcentration = new Chart(canvas, {
    type: "line",
    data: {
      datasets: [
        {
          label: "Répartition observée",
          data: actualPoints,
          tension: 0.18,
          pointRadius: 0,
          pointHoverRadius: 4,
          fill: false,
        },
        {
          label: "Répartition parfaitement équilibrée",
          data: equalityPoints,
          tension: 0,
          pointRadius: 0,
          pointHoverRadius: 0,
          borderDash: [6, 6],
          fill: false,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      interaction: {
        mode: "nearest",
        intersect: false
      },
      plugins: {
        legend: {
          position: "top"
        },
        tooltip: {
          callbacks: {
            title(items) {
              const point = items?.[0]?.raw;
              if (!point) return "";
              return `${Number(point.x || 0).toLocaleString("fr-FR", { maximumFractionDigits: 0 })} % des payeurs`;
            },
            label(context) {
              const value = Number(context.raw?.y || 0);
              return `${context.dataset.label} : ${percent(value)} du volume C2B`;
            }
          }
        }
      },
      scales: {
        x: {
          type: "linear",
          min: 0,
          max: 100,
          title: {
            display: true,
            text: "Part cumulée des payeurs particuliers"
          },
          ticks: {
            callback(value) {
              return `${value} %`;
            },
            maxTicksLimit: 6
          }
        },
        y: {
          min: 0,
          max: 100,
          title: {
            display: true,
            text: "Part cumulée du volume C2B"
          },
          ticks: {
            callback(value) {
              return `${value} %`;
            },
            maxTicksLimit: 6
          }
        }
      }
    }
  });
}

function buildProfessionalCustomerConcentrationSectionHtml(concentration = {}) {
  const summary = concentration?.summary || {};
  const reading = buildProfessionalCustomerConcentrationReading(concentration);

  const payerCount = Number(summary.payer_count || 0);
  const top5Share = Number(summary.top_5_share_pct || 0);
  const averageVolume = Number(summary.average_volume_per_payer || 0);
  const effectivePayerCount = Number(summary.effective_payer_count || 0);

  const hasCurve = Array.isArray(concentration?.lorenz_points)
    && concentration.lorenz_points.length > 0
    && payerCount > 0;

  return `
    <section class="card pro-detail-customer-concentration-card">
      <div class="pro-detail-customer-concentration-heading">
        <div>
          <div class="stat-label">Structure du fond de commerce Gonette</div>
          <h3>${escapeHtml(reading.title)}</h3>
          <p>${escapeHtml(reading.text)}</p>
        </div>
      </div>

      <div class="pro-detail-customer-concentration-kpis">
        <div>
          <span>Particuliers payeurs</span>
          <strong>${formatProfessionalNetworkCount(payerCount)}</strong>
        </div>
        <div>
          <span>Part du top 5</span>
          <strong>${percent(top5Share)}</strong>
        </div>
        <div>
          <span>Volume moyen / payeur</span>
          <strong>${euro(averageVolume)}</strong>
        </div>
        <div>
          <span>Payeurs effectifs</span>
          <strong>${formatProfessionalCustomerEffectiveCount(effectivePayerCount)}</strong>
        </div>
      </div>

      ${
        hasCurve
          ? `
            <div class="pro-detail-customer-concentration-chart-frame">
              <canvas id="proDetailCustomerConcentrationChart"></canvas>
            </div>
          `
          : `
            <div class="pro-detail-customer-concentration-empty">
              Aucune courbe de concentration exploitable pour cette période.
            </div>
          `
      }

      <div class="pro-detail-customer-concentration-note">
        <strong>Lecture.</strong>
        La courbe classe les payeurs particuliers du plus petit au plus gros volume cumulé.
        Plus la courbe observée s’éloigne vers le bas de la diagonale,
        plus le chiffre d’affaires Gonette dépend d’un petit nombre de payeurs.
        Le nombre de <strong>payeurs effectifs</strong> résume cette concentration :
        il correspond au nombre théorique de payeurs de poids égal produisant le même niveau de concentration.
      </div>
    </section>
  `;
}


function getProfessionalDetailDynamicsRequest(numProf) {
  const periodQuery = getPeriodQueryParam();
  const dynamicsQuery = periodQuery
    ? `${periodQuery}&network_limit=18`
    : "?network_limit=18";

  return {
    url: `/api/pro/${encodeURIComponent(numProf)}/dynamics${dynamicsQuery}`,
    cacheKey: `${numProf}::${dynamicsQuery}`,
  };
}

async function loadProfessionalDetailDynamics(numProf) {
  const request = getProfessionalDetailDynamicsRequest(numProf);

  if (
    appState.proDetailDynamics
    && appState.proDetailDynamicsKey === request.cacheKey
  ) {
    return appState.proDetailDynamics;
  }

  const dynamics = await apiGet(request.url);

  if (appState.currentPro === numProf) {
    appState.proDetailDynamics = dynamics;
    appState.proDetailDynamicsKey = request.cacheKey;
  }

  return dynamics;
}



function buildProfessionalCustomerLoyaltyReading(loyalty = {}) {
  const summary = loyalty?.summary || {};
  const payerCount = Number(summary.payer_count || 0);
  const newShare = Number(summary.new_payer_share_pct || 0);
  const returningShare = Number(summary.returning_payer_share_pct || 0);
  const recurrentShare = Number(summary.recurrent_payer_share_pct || 0);
  const recurrentVolumeShare = Number(summary.recurrent_payer_volume_share_pct || 0);

  if (payerCount <= 0) {
    return {
      tone: "neutral",
      title: "Aucune récurrence particulière observable sur la période",
      text: "La période sélectionnée ne montre pas de payeurs particuliers pour ce professionnel.",
    };
  }

  if (returningShare >= 45 && recurrentVolumeShare >= 55) {
    return {
      tone: "positive",
      title: "Une clientèle Gonette déjà installée",
      text: `${percent(returningShare)} des payeurs étaient déjà connus avant la période, et les payeurs récurrents portent ${percent(recurrentVolumeShare)} du volume C2B. Le professionnel dispose d’un noyau d’usage qui semble s’inscrire dans le temps.`,
    };
  }

  if (newShare >= 70 && recurrentShare < 25) {
    return {
      tone: "watch",
      title: "Une phase d’acquisition à transformer en fidélité",
      text: `${percent(newShare)} des payeurs sont nouveaux pour ce professionnel sur la période, mais seuls ${percent(recurrentShare)} ont payé au moins deux fois. L’enjeu peut être de transformer une première activation en habitude.`,
    };
  }

  if (recurrentVolumeShare >= 70 && recurrentShare < 40) {
    return {
      tone: "attention",
      title: "Un noyau fidèle porte une grande part de l’activité C2B",
      text: `Les payeurs récurrents ne représentent que ${percent(recurrentShare)} des payeurs, mais ils concentrent ${percent(recurrentVolumeShare)} du volume reçu depuis les particuliers. Cette fidélité est précieuse, tout en rendant l’activité dépendante d’un cœur d’usagers.`,
    };
  }

  return {
    tone: "neutral",
    title: "Un fond de commerce partagé entre nouveaux usages et retours",
    text: `${percent(newShare)} des payeurs sont nouveaux pour ce professionnel sur la période ; ${percent(recurrentShare)} ont réalisé au moins deux paiements. La clientèle Gonette montre à la fois de l’acquisition et un début de répétition des usages.`,
  };
}

function buildProfessionalLoyaltySegmentBar(segments = [], valueKey = "payer_share_pct") {
  const safeSegments = Array.isArray(segments) ? segments : [];

  return `
    <div class="pro-detail-loyalty-segment-track">
      ${safeSegments.map(segment => {
        const width = Math.max(0, Math.min(100, Number(segment?.[valueKey] || 0)));
        const key = String(segment?.key || "segment");

        return `
          <div
            class="pro-detail-loyalty-segment pro-detail-loyalty-segment-${escapeHtml(key)}"
            style="width: ${width}%"
            title="${escapeHtml(`${segment.label || ""} · ${percent(width)}`)}"
          ></div>
        `;
      }).join("")}
    </div>
  `;
}

function buildProfessionalLoyaltyLegend(segments = [], shareKey = "payer_share_pct") {
  const safeSegments = Array.isArray(segments) ? segments : [];

  return `
    <div class="pro-detail-loyalty-legend">
      ${safeSegments.map(segment => `
        <div class="pro-detail-loyalty-legend-item">
          <i class="pro-detail-loyalty-legend-swatch pro-detail-loyalty-legend-swatch-${escapeHtml(segment.key || "segment")}"></i>
          <span>${escapeHtml(segment.label || "—")}</span>
          <strong>${formatProfessionalNetworkCount(segment.payer_count || 0)} · ${percent(segment[shareKey] || 0)}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function buildProfessionalCustomerLoyaltySectionHtml(loyalty = {}) {
  const summary = loyalty?.summary || {};
  const reading = buildProfessionalCustomerLoyaltyReading(loyalty);
  const historySegments = Array.isArray(loyalty?.history_segments)
    ? loyalty.history_segments
    : [];
  const frequencySegments = Array.isArray(loyalty?.frequency_segments)
    ? loyalty.frequency_segments
    : [];

  const payerCount = Number(summary.payer_count || 0);
  const newPayers = Number(summary.new_payer_count || 0);
  const returningPayers = Number(summary.returning_payer_count || 0);
  const recurrentPayers = Number(summary.recurrent_payer_count || 0);
  const recurrentVolumeShare = Number(summary.recurrent_payer_volume_share_pct || 0);

  return `
    <section class="card pro-detail-loyalty-card">
      <div class="pro-detail-loyalty-heading">
        <div>
          <div class="stat-label">Fidélité & récurrence</div>
          <h3>${escapeHtml(reading.title)}</h3>
          <p>${escapeHtml(reading.text)}</p>
        </div>
      </div>

      <div class="pro-detail-loyalty-kpis">
        <div>
          <span>Nouveaux payeurs</span>
          <strong>${formatProfessionalNetworkCount(newPayers)}</strong>
        </div>
        <div>
          <span>Déjà vus avant</span>
          <strong>${formatProfessionalNetworkCount(returningPayers)}</strong>
        </div>
        <div>
          <span>Payeurs récurrents</span>
          <strong>${formatProfessionalNetworkCount(recurrentPayers)}</strong>
        </div>
        <div>
          <span>Volume des récurrents</span>
          <strong>${percent(recurrentVolumeShare)}</strong>
        </div>
      </div>

      ${
        payerCount > 0
          ? `
            <div class="pro-detail-loyalty-axes">
              <section class="pro-detail-loyalty-axis-card">
                <h4>Acquisition ou retour ?</h4>
                <p>
                  Les payeurs sont séparés entre ceux jamais vus auparavant chez ce professionnel
                  et ceux déjà présents avant le début de la période.
                </p>
                ${buildProfessionalLoyaltySegmentBar(historySegments)}
                ${buildProfessionalLoyaltyLegend(historySegments)}
              </section>

              <section class="pro-detail-loyalty-axis-card">
                <h4>À quelle fréquence reviennent-ils ?</h4>
                <p>
                  Les payeurs sont regroupés selon le nombre de paiements réalisés pendant la période sélectionnée.
                </p>
                ${buildProfessionalLoyaltySegmentBar(frequencySegments)}
                ${buildProfessionalLoyaltyLegend(frequencySegments)}
              </section>
            </div>
          `
          : `
            <div class="pro-detail-loyalty-empty">
              Aucun payeur particulier à analyser sur cette période.
            </div>
          `
      }

      <div class="pro-detail-loyalty-note">
        <strong>Lecture.</strong>
        Un payeur est dit <em>nouveau</em> s’il n’avait jamais payé ce professionnel avant le début de la période sélectionnée.
        Un payeur est dit <em>récurrent</em> s’il effectue au moins deux paiements pendant la période.
        Cette lecture permet de distinguer une simple activation ponctuelle d’un usage réellement réitéré.
      </div>
    </section>
  `;
}


function getProfessionalPaymentBasinMapRequest(numProf) {
  const periodQuery = getPeriodQueryParam();
  const basinQuery = periodQuery
    ? `${periodQuery}&min_users=5`
    : "?min_users=5";

  return {
    url: `/api/pro/${encodeURIComponent(numProf)}/payment-basin-map${basinQuery}`,
    cacheKey: `${numProf}::${basinQuery}`,
  };
}

async function loadProfessionalPaymentBasinMap(numProf) {
  const request = getProfessionalPaymentBasinMapRequest(numProf);

  if (
    appState.proDetailPaymentBasinMap
    && appState.proDetailPaymentBasinMapKey === request.cacheKey
  ) {
    return appState.proDetailPaymentBasinMap;
  }

  const payload = await apiGet(request.url);

  if (appState.currentPro === numProf) {
    appState.proDetailPaymentBasinMap = payload;
    appState.proDetailPaymentBasinMapKey = request.cacheKey;
  }

  return payload;
}

function professionalPaymentBasinHash(value) {
  const text = String(value || "");
  let hash = 0;

  for (let index = 0; index < text.length; index += 1) {
    hash = ((hash << 5) - hash) + text.charCodeAt(index);
    hash |= 0;
  }

  return Math.abs(hash);
}

function collectProfessionalPaymentBasinCoordinates(payload = {}) {
  const points = [];
  const center = payload?.center || {};

  if (
    Number.isFinite(Number(center.longitude))
    && Number.isFinite(Number(center.latitude))
  ) {
    points.push([Number(center.longitude), Number(center.latitude)]);
  }

  (payload?.routes || []).forEach(route => {
    const source = route?.source || {};
    if (
      Number.isFinite(Number(source.longitude))
      && Number.isFinite(Number(source.latitude))
    ) {
      points.push([Number(source.longitude), Number(source.latitude)]);
    }
  });

  const pushGeoJsonCoordinates = coords => {
    if (!Array.isArray(coords)) return;

    if (
      coords.length >= 2
      && Number.isFinite(Number(coords[0]))
      && Number.isFinite(Number(coords[1]))
    ) {
      points.push([Number(coords[0]), Number(coords[1])]);
      return;
    }

    coords.forEach(pushGeoJsonCoordinates);
  };

  Object.values(payload?.geometry?.visible_source_area_geojson || {}).forEach(featureCollection => {
    (featureCollection?.features || []).forEach(feature => {
      pushGeoJsonCoordinates(feature?.geometry?.coordinates || []);
    });
  });

  return points;
}

function buildProfessionalPaymentBasinProjection(payload, width, height) {
  const coords = collectProfessionalPaymentBasinCoordinates(payload);

  if (!coords.length) {
    return null;
  }

  const lons = coords.map(point => point[0]);
  const lats = coords.map(point => point[1]);

  let minLon = Math.min(...lons);
  let maxLon = Math.max(...lons);
  let minLat = Math.min(...lats);
  let maxLat = Math.max(...lats);

  const lonSpan = Math.max(maxLon - minLon, 0.01);
  const latSpan = Math.max(maxLat - minLat, 0.01);

  minLon -= lonSpan * 0.08;
  maxLon += lonSpan * 0.08;
  minLat -= latSpan * 0.08;
  maxLat += latSpan * 0.08;

  const margin = {
    top: 34,
    right: 34,
    bottom: 34,
    left: 34
  };

  const innerWidth = Math.max(1, width - margin.left - margin.right);
  const innerHeight = Math.max(1, height - margin.top - margin.bottom);

  const scaleX = innerWidth / Math.max(maxLon - minLon, 0.00001);
  const scaleY = innerHeight / Math.max(maxLat - minLat, 0.00001);
  const scale = Math.min(scaleX, scaleY);

  const projectedWidth = (maxLon - minLon) * scale;
  const projectedHeight = (maxLat - minLat) * scale;

  const offsetX = margin.left + Math.max(0, (innerWidth - projectedWidth) / 2);
  const offsetY = margin.top + Math.max(0, (innerHeight - projectedHeight) / 2);

  return {
    width,
    height,
    pixelsPerLongitudeDegree: scale,
    project(longitude, latitude) {
      return {
        x: offsetX + (Number(longitude) - minLon) * scale,
        y: offsetY + (maxLat - Number(latitude)) * scale
      };
    }
  };
}


function drawProfessionalPaymentBasinPostalLabel(ctx, point, route, radius = 8) {
  const postalCode = String(route?.source?.postal_code || "").trim();
  if (!postalCode) {
    return;
  }

  const isDark = document.body.classList.contains("dark-mode");
  const labelY = point.y - radius - 9;

  ctx.save();
  ctx.font = "700 11px system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";
  ctx.lineJoin = "round";
  ctx.lineWidth = 3.4;
  ctx.strokeStyle = isDark
    ? "rgba(15, 23, 42, 0.92)"
    : "rgba(255, 255, 255, 0.94)";
  ctx.fillStyle = isDark
    ? "rgba(226, 232, 240, 0.92)"
    : "rgba(30, 41, 59, 0.90)";

  ctx.strokeText(postalCode, point.x, labelY);
  ctx.fillText(postalCode, point.x, labelY);
  ctx.restore();
}

function formatProfessionalPaymentBasinDistance(kilometers) {
  const km = Number(kilometers || 0);

  if (km >= 1) {
    return `${km.toLocaleString("fr-FR", {
      maximumFractionDigits: km < 10 ? 1 : 0
    })} km`;
  }

  return `${Math.round(km * 1000)} m`;
}

function updateProfessionalPaymentBasinScale(projection, payload = {}) {
  const scaleNode = document.getElementById("proDetailPaymentBasinScale");

  if (!scaleNode || !projection) {
    return;
  }

  const centerLatitude = Number(payload?.center?.latitude);
  const pixelsPerLongitudeDegree = Number(projection?.pixelsPerLongitudeDegree || 0);

  if (
    !Number.isFinite(centerLatitude)
    || !Number.isFinite(pixelsPerLongitudeDegree)
    || pixelsPerLongitudeDegree <= 0
  ) {
    scaleNode.hidden = true;
    return;
  }

  const kilometersPerLongitudeDegree =
    111.32 * Math.cos(centerLatitude * Math.PI / 180);

  const kilometersPerPixel =
    kilometersPerLongitudeDegree / pixelsPerLongitudeDegree;

  if (
    !Number.isFinite(kilometersPerPixel)
    || kilometersPerPixel <= 0
  ) {
    scaleNode.hidden = true;
    return;
  }

  const targetPixelWidth = Math.min(
    150,
    Math.max(88, Number(projection.width || 960) * 0.15)
  );

  const targetKilometers = targetPixelWidth * kilometersPerPixel;
  const candidates = [
    0.1,
    0.2,
    0.5,
    1,
    2,
    5,
    10,
    20,
    50,
    100,
    200
  ];

  let selectedKilometers = candidates[0];

  candidates.forEach(candidate => {
    if (candidate <= targetKilometers) {
      selectedKilometers = candidate;
    }
  });

  const selectedPixelWidth = selectedKilometers / kilometersPerPixel;

  scaleNode.hidden = false;
  scaleNode.innerHTML = `
    <div class="pro-detail-payment-basin-scale-line" style="width: ${selectedPixelWidth.toFixed(1)}px;"></div>
    <span>${formatProfessionalPaymentBasinDistance(selectedKilometers)}</span>
  `;
}

function getProfessionalPaymentBasinThemePalette() {
  const isDark = document.body.classList.contains("dark-mode");

  return {
    isDark,
    backdrop: isDark ? "rgba(15, 23, 42, 0.12)" : "rgba(255, 255, 255, 0.18)",
    guide: isDark ? "rgba(148, 163, 184, 0.07)" : "rgba(100, 116, 139, 0.06)",
    areaFill: isDark ? "rgba(148, 163, 184, 0.13)" : "rgba(15, 23, 42, 0.05)",
    areaStroke: isDark ? "rgba(226, 232, 240, 0.20)" : "rgba(71, 85, 105, 0.16)",
    individualRoute: isDark ? "rgba(52, 211, 153, 0.86)" : "rgba(5, 150, 105, 0.78)",
    individualGlow: isDark ? "rgba(52, 211, 153, 0.24)" : "rgba(16, 185, 129, 0.18)",
    professionalRoute: isDark ? "rgba(96, 165, 250, 0.88)" : "rgba(37, 99, 235, 0.80)",
    professionalGlow: isDark ? "rgba(96, 165, 250, 0.24)" : "rgba(37, 99, 235, 0.16)",
    centerCore: isDark ? "#f8fafc" : "#0f172a",
    centerGlow: isDark ? "rgba(251, 191, 36, 0.34)" : "rgba(217, 119, 6, 0.26)",
  };
}

function drawProfessionalPaymentBasinGeoJson(ctx, projection, featureCollection) {
  const drawRing = ring => {
    if (!Array.isArray(ring) || !ring.length) return;

    ring.forEach((coords, index) => {
      const point = projection.project(coords[0], coords[1]);

      if (index === 0) {
        ctx.moveTo(point.x, point.y);
      } else {
        ctx.lineTo(point.x, point.y);
      }
    });

    ctx.closePath();
  };

  const drawGeometry = geometry => {
    if (!geometry) return;

    if (geometry.type === "Polygon") {
      (geometry.coordinates || []).forEach(drawRing);
    }

    if (geometry.type === "MultiPolygon") {
      (geometry.coordinates || []).forEach(polygon => {
        (polygon || []).forEach(drawRing);
      });
    }
  };

  ctx.beginPath();

  (featureCollection?.features || []).forEach(feature => {
    drawGeometry(feature?.geometry);
  });

  ctx.fill("evenodd");
  ctx.stroke();
}

function getProfessionalPaymentBasinQuadraticControl(source, destination, routeId) {
  const dx = destination.x - source.x;
  const dy = destination.y - source.y;
  const length = Math.max(1, Math.hypot(dx, dy));
  const nx = -dy / length;
  const ny = dx / length;
  const hash = professionalPaymentBasinHash(routeId);
  const direction = hash % 2 === 0 ? 1 : -1;
  const bend = Math.min(72, 24 + length * 0.14) * direction;

  return {
    x: (source.x + destination.x) / 2 + nx * bend,
    y: (source.y + destination.y) / 2 + ny * bend,
  };
}

function getProfessionalPaymentBasinQuadraticPoint(source, control, destination, ratio) {
  const t = Math.max(0, Math.min(1, Number(ratio || 0)));
  const mt = 1 - t;

  return {
    x: (mt * mt * source.x) + (2 * mt * t * control.x) + (t * t * destination.x),
    y: (mt * mt * source.y) + (2 * mt * t * control.y) + (t * t * destination.y),
  };
}

function drawProfessionalPaymentBasinBackdrop(ctx, projection, payload) {
  const palette = getProfessionalPaymentBasinThemePalette();
  const width = projection.width;
  const height = projection.height;
  const center = payload?.center || {};

  ctx.clearRect(0, 0, width, height);

  const centerPoint = projection.project(center.longitude, center.latitude);

  const glow = ctx.createRadialGradient(
    centerPoint.x,
    centerPoint.y,
    0,
    centerPoint.x,
    centerPoint.y,
    Math.max(width, height) * 0.62
  );

  glow.addColorStop(0, palette.backdrop);
  glow.addColorStop(1, "rgba(0,0,0,0)");

  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.strokeStyle = palette.guide;
  ctx.lineWidth = 1;

  [0.24, 0.48, 0.72].forEach(ratio => {
    ctx.beginPath();
    ctx.arc(
      centerPoint.x,
      centerPoint.y,
      Math.max(width, height) * ratio,
      0,
      Math.PI * 2
    );
    ctx.stroke();
  });

  ctx.restore();
}

function drawProfessionalPaymentBasinAreas(ctx, projection, payload) {
  const palette = getProfessionalPaymentBasinThemePalette();

  ctx.save();
  ctx.fillStyle = palette.areaFill;
  ctx.strokeStyle = palette.areaStroke;
  ctx.lineWidth = 1.1;

  Object.values(payload?.geometry?.visible_source_area_geojson || {}).forEach(featureCollection => {
    drawProfessionalPaymentBasinGeoJson(ctx, projection, featureCollection);
  });

  ctx.restore();
}

function drawProfessionalPaymentBasinRoutes(ctx, projection, payload, timestamp) {
  const palette = getProfessionalPaymentBasinThemePalette();
  const routes = Array.isArray(payload?.routes) ? payload.routes : [];

  const maxVolume = Math.max(1, ...routes.map(route => Number(route.volume || 0)));
  const center = payload?.center || {};
  const destination = projection.project(center.longitude, center.latitude);

  routes.forEach(route => {
    const sourceData = route?.source || {};
    const source = projection.project(sourceData.longitude, sourceData.latitude);
    const control = getProfessionalPaymentBasinQuadraticControl(
      source,
      destination,
      route.id
    );

    const volumeRatio = Math.sqrt(Number(route.volume || 0) / maxVolume);
    const width = 1.5 + volumeRatio * 4.6;
    const isIndividual = route.kind === "individual_postal";
    const lineColor = isIndividual ? palette.individualRoute : palette.professionalRoute;
    const glowColor = isIndividual ? palette.individualGlow : palette.professionalGlow;

    ctx.save();
    ctx.lineCap = "round";
    ctx.strokeStyle = glowColor;
    ctx.lineWidth = width * 2.8;
    ctx.beginPath();
    ctx.moveTo(source.x, source.y);
    ctx.quadraticCurveTo(control.x, control.y, destination.x, destination.y);
    ctx.stroke();

    ctx.strokeStyle = lineColor;
    ctx.lineWidth = width;
    ctx.beginPath();
    ctx.moveTo(source.x, source.y);
    ctx.quadraticCurveTo(control.x, control.y, destination.x, destination.y);
    ctx.stroke();
    ctx.restore();

    const hash = professionalPaymentBasinHash(route.id);
    const phase = (hash % 1000) / 1000;
    const speed = isIndividual ? 0.000075 : 0.000095;
    const progress = ((timestamp * speed) + phase) % 1;
    const particle = getProfessionalPaymentBasinQuadraticPoint(
      source,
      control,
      destination,
      progress
    );

    ctx.save();
    const particleGlow = ctx.createRadialGradient(
      particle.x,
      particle.y,
      0,
      particle.x,
      particle.y,
      12 + volumeRatio * 8
    );
    particleGlow.addColorStop(0, lineColor);
    particleGlow.addColorStop(1, "rgba(0,0,0,0)");

    ctx.fillStyle = particleGlow;
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, 12 + volumeRatio * 8, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = lineColor;
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, 2.2 + volumeRatio * 2.4, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  });
}

function drawProfessionalPaymentBasinSources(ctx, projection, payload) {
  const palette = getProfessionalPaymentBasinThemePalette();
  const routes = Array.isArray(payload?.routes) ? payload.routes : [];

  routes.forEach(route => {
    const sourceData = route?.source || {};
    const point = projection.project(sourceData.longitude, sourceData.latitude);
    const isIndividual = route.kind === "individual_postal";
    const magnitude = isIndividual
      ? Math.sqrt(Number(route.payer_count || 0))
      : Math.sqrt(Number(route.volume || 0) / 100);

    const radius = isIndividual
      ? 5 + Math.min(12, magnitude * 1.5)
      : 5 + Math.min(11, magnitude);

    const core = isIndividual ? palette.individualRoute : palette.professionalRoute;
    const glow = isIndividual ? palette.individualGlow : palette.professionalGlow;

    ctx.save();

    const radial = ctx.createRadialGradient(
      point.x,
      point.y,
      0,
      point.x,
      point.y,
      radius * 2.4
    );
    radial.addColorStop(0, glow);
    radial.addColorStop(1, "rgba(0,0,0,0)");

    ctx.fillStyle = radial;
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius * 2.4, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();

    if (isIndividual) {
      drawProfessionalPaymentBasinPostalLabel(ctx, point, route, radius);
    }
  });
}

function drawProfessionalPaymentBasinCenter(ctx, projection, payload) {
  const palette = getProfessionalPaymentBasinThemePalette();
  const center = payload?.center || {};
  const point = projection.project(center.longitude, center.latitude);

  ctx.save();

  const halo = ctx.createRadialGradient(
    point.x,
    point.y,
    0,
    point.x,
    point.y,
    42
  );

  halo.addColorStop(0, palette.centerGlow);
  halo.addColorStop(1, "rgba(0,0,0,0)");

  ctx.fillStyle = halo;
  ctx.beginPath();
  ctx.arc(point.x, point.y, 42, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = palette.centerCore;
  ctx.beginPath();
  ctx.arc(point.x, point.y, 10, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = palette.centerGlow;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(point.x, point.y, 17, 0, Math.PI * 2);
  ctx.stroke();

  ctx.restore();
}

function renderProfessionalPaymentBasinMapCanvas(payload = {}) {
  const canvas = document.getElementById("proDetailPaymentBasinCanvas");
  const frame = canvas?.closest(".pro-detail-payment-basin-map-frame");

  if (!canvas || !frame) {
    return;
  }

  if (appState.proDetailPaymentBasinAnimationFrame) {
    window.cancelAnimationFrame(appState.proDetailPaymentBasinAnimationFrame);
    appState.proDetailPaymentBasinAnimationFrame = null;
  }

  const width = Math.max(420, frame.clientWidth || 960);
  const height = Math.max(360, frame.clientHeight || 560);
  const dpr = window.devicePixelRatio || 1;

  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const projection = buildProfessionalPaymentBasinProjection(payload, width, height);
  updateProfessionalPaymentBasinScale(projection, payload);

  if (!projection || !payload?.center?.has_coordinates || !(payload?.routes || []).length) {
    ctx.clearRect(0, 0, width, height);
    return;
  }

  const draw = timestamp => {
    if (
      appState.proTab !== "commerce"
      || document.getElementById("proDetailPaymentBasinCanvas") !== canvas
    ) {
      appState.proDetailPaymentBasinAnimationFrame = null;
      return;
    }

    drawProfessionalPaymentBasinBackdrop(ctx, projection, payload);
    drawProfessionalPaymentBasinAreas(ctx, projection, payload);
    drawProfessionalPaymentBasinRoutes(ctx, projection, payload, timestamp);
    drawProfessionalPaymentBasinSources(ctx, projection, payload);
    drawProfessionalPaymentBasinCenter(ctx, projection, payload);

    appState.proDetailPaymentBasinAnimationFrame = window.requestAnimationFrame(draw);
  };

  appState.proDetailPaymentBasinAnimationFrame = window.requestAnimationFrame(draw);
}


function buildProfessionalPaymentBasinPostalBreakdownHtml(payload = {}) {
  const sources = Array.isArray(payload?.individual_sources)
    ? [...payload.individual_sources]
    : [];

  if (!sources.length) {
    return "";
  }

  sources.sort((a, b) => {
    const payerDiff = Number(b?.payer_count || 0) - Number(a?.payer_count || 0);
    if (payerDiff !== 0) return payerDiff;

    const volumeDiff = Number(b?.volume || 0) - Number(a?.volume || 0);
    if (volumeDiff !== 0) return volumeDiff;

    return String(a?.postal_code || "").localeCompare(String(b?.postal_code || ""), "fr");
  });

  return `
    <div class="pro-detail-payment-basin-postal-breakdown">
      <div class="pro-detail-payment-basin-postal-breakdown-heading">
        <span>Répartition des payeurs U représentés</span>
        <small>par code postal franchissant le seuil d’affichage</small>
      </div>

      <div class="pro-detail-payment-basin-postal-chips">
        ${sources.map(source => `
          <div class="pro-detail-payment-basin-postal-chip">
            <strong>${escapeHtml(source.postal_code || "—")}</strong>
            <span>${formatProfessionalNetworkCount(source.payer_count || 0)} payeur(s)</span>
            <small>${euro(source.volume || 0)}</small>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function buildProfessionalPaymentBasinSectionHtml(payload = {}) {
  const coverage = payload?.coverage || {};
  const center = payload?.center || {};
  const hasCenter = Boolean(center?.has_coordinates);
  const hasRoutes = Array.isArray(payload?.routes) && payload.routes.length > 0;

  const visibleUShare = coverage.individual_visible_volume_share;
  const visibleUPayerCount = Number(
    coverage.individual_visible_payer_count || 0
  );
  const visiblePCount = Number(coverage.professional_visible_source_count || 0);
  const hiddenU = coverage.individual_hidden_below_threshold || {};
  const missingPros = Number(coverage.professional_missing_geometry_source_count || 0);

  return `
    <section class="card pro-detail-payment-basin-card">
      <div class="pro-detail-payment-basin-heading">
        <div>
          <div class="stat-label">Bassin de paiement Gonette</div>
          <h3>D’où viennent les Gonettes reçues par ce professionnel ?</h3>
          <p>
            Cette carte met en scène les flux entrants :
            les foyers de particuliers <strong>U→P</strong> sont agrégés par code postal,
            tandis que les professionnels payeurs <strong>P→P</strong> apparaissent
            individuellement lorsqu’ils sont géolocalisables.
          </p>
        </div>
      </div>

      <div class="pro-detail-payment-basin-kpis">
        <div>
          <span>Foyers U visibles</span>
          <strong>${formatProfessionalNetworkCount(coverage.individual_visible_postal_source_count || 0)}</strong>
        </div>
        <div>
          <span>Payeurs U représentés</span>
          <strong>${formatProfessionalNetworkCount(visibleUPayerCount)}</strong>
        </div>
        <div>
          <span>Pros payeurs géolocalisés</span>
          <strong>${formatProfessionalNetworkCount(visiblePCount)}</strong>
        </div>
        <div>
          <span>Volume U représenté</span>
          <strong>${visibleUShare === null || visibleUShare === undefined ? "—" : percent(Number(visibleUShare || 0) * 100)}</strong>
        </div>
      </div>

      ${buildProfessionalPaymentBasinPostalBreakdownHtml(payload)}

      ${
        hasCenter && hasRoutes
          ? `
            <div class="pro-detail-payment-basin-map-frame">
              <canvas id="proDetailPaymentBasinCanvas"></canvas>

              <div
                id="proDetailPaymentBasinScale"
                class="pro-detail-payment-basin-scale"
                hidden
              ></div>

              <div class="pro-detail-payment-basin-legend">
                <span><i class="pro-detail-payment-basin-dot pro-detail-payment-basin-dot-u"></i> Foyers particuliers U→P</span>
                <span><i class="pro-detail-payment-basin-dot pro-detail-payment-basin-dot-p"></i> Professionnels payeurs P→P</span>
                <span><i class="pro-detail-payment-basin-dot pro-detail-payment-basin-dot-center"></i> Professionnel étudié</span>
              </div>
            </div>
          `
          : `
            <div class="pro-detail-payment-basin-empty">
              ${
                !hasCenter
                  ? "La localisation du professionnel étudié n’est pas suffisamment confirmée pour construire cette carte."
                  : "Aucun flux entrant cartographiable ne franchit les seuils de représentation sur cette période."
              }
            </div>
          `
      }

      <div class="pro-detail-payment-basin-note">
        <strong>Lecture.</strong>
        Les foyers particuliers ne représentent jamais des adresses individuelles :
        ils sont agrégés par code postal et ne sont affichés qu’à partir de
        <strong>${formatProfessionalNetworkCount(coverage.min_users || 5)} payeurs distincts</strong>.
        ${
          Number(hiddenU.payer_count || 0) > 0
            ? ` ${formatProfessionalNetworkCount(hiddenU.payer_count || 0)} payeur(s) U restent hors carte car leur code postal ne franchit pas ce seuil.`
            : ""
        }
        ${
          missingPros > 0
            ? ` ${formatProfessionalNetworkCount(missingPros)} professionnel(s) payeur(s) ne sont pas représentés faute de géolocalisation confirmée.`
            : ""
        }
      </div>
    </section>
  `;
}

async function renderProCustomerProfile() {
  const section = document.getElementById("proCustomerProfileSection");
  if (!section || !appState.detailData || !appState.currentPro) return;

  const numProf = appState.currentPro;

  section.innerHTML = `
    <section class="card pro-customer-profile-loading-card">
      Chargement du fond de commerce Gonette…
    </section>
  `;

  try {
    const [dynamics, paymentBasinMap] = await Promise.all([
      loadProfessionalDetailDynamics(numProf),
      loadProfessionalPaymentBasinMap(numProf),
    ]);

    if (
      appState.proTab !== "commerce"
      || appState.currentPro !== numProf
    ) {
      return;
    }

    section.innerHTML = `
      <section class="card pro-customer-profile-intro-card">
        <div class="stat-label">Fond de commerce Gonette</div>
        <h3>Comprendre la clientèle particulière qui active ce professionnel</h3>
        <p>
          Cet onglet observe les paiements U→P :
          leur rythme dans la semaine, leur fidélité dans le temps
          et la concentration du volume entre payeurs.
        </p>
      </section>

      ${buildProfessionalPaymentBasinSectionHtml(paymentBasinMap || {})}

      ${buildProfessionalPaymentRhythmSectionHtml(dynamics?.individual_payment_rhythm || {})}

      ${buildProfessionalCustomerLoyaltySectionHtml(dynamics?.individual_customer_loyalty || {})}

      ${buildProfessionalCustomerConcentrationSectionHtml(dynamics?.individual_customer_concentration || {})}
    `;

    window.requestAnimationFrame(() => {
      renderProfessionalPaymentBasinMapCanvas(paymentBasinMap || {});
    });

    renderProfessionalCustomerConcentrationChart(
      dynamics?.individual_customer_concentration || {}
    );
  } catch (error) {
    console.error("Erreur chargement fond de commerce professionnel :", error);
    section.innerHTML = `
      <section class="card">
        Impossible de charger l’analyse du fond de commerce Gonette.
      </section>
    `;
  }
}


function getProfessionalReuseProspectsRequest(numProf) {
  const periodQuery = getPeriodQueryParam();
  const prospectsQuery = periodQuery
    ? `${periodQuery}&limit=12`
    : "?limit=12";

  return {
    url: `/api/pro/${encodeURIComponent(numProf)}/reuse-prospects${prospectsQuery}`,
    cacheKey: `${numProf}::${prospectsQuery}`,
  };
}

async function loadProfessionalReuseProspects(numProf) {
  const request = getProfessionalReuseProspectsRequest(numProf);

  if (
    appState.proDetailReuseProspects
    && appState.proDetailReuseProspectsKey === request.cacheKey
  ) {
    return appState.proDetailReuseProspects;
  }

  const prospects = await apiGet(request.url);

  if (appState.currentPro === numProf) {
    appState.proDetailReuseProspects = prospects;
    appState.proDetailReuseProspectsKey = request.cacheKey;
  }

  return prospects;
}

function formatProfessionalProspectLocation(item = {}) {
  const zip = String(item?.zip || "").trim();
  const city = String(item?.city || "").trim();

  if (zip && city) {
    return `${zip} ${city}`;
  }

  return city || zip || "";
}

function getProfessionalProspectSignalLabel(signalLevel) {
  if (signalLevel === "strong") {
    return "Signal fort";
  }

  if (signalLevel === "medium") {
    return "Signal convergent";
  }

  return "Piste exploratoire";
}

function buildProfessionalProspectsReading(data = {}) {
  const summary = data?.summary || {};
  const candidateCount = Number(summary.candidate_count_displayed || 0);
  const activePeerCount = Number(summary.active_peer_count || 0);
  const sector = String(summary.target_industry_name || "").trim();

  if (!sector) {
    return {
      title: "Secteur de comparaison indisponible",
      text: "Le secteur principal Odoo de ce professionnel n’est pas renseigné, ce qui empêche de construire une comparaison robuste avec des pairs.",
    };
  }

  if (activePeerCount <= 0) {
    return {
      title: `Aucun pair actif du secteur « ${sector} » sur la période`,
      text: "La période sélectionnée ne fournit pas encore de base empirique suffisante pour suggérer des débouchés issus des pratiques du secteur.",
    };
  }

  if (candidateCount <= 0) {
    return {
      title: "Aucun débouché nouveau clairement repéré chez les pairs",
      text: `Les professionnels comparables du secteur « ${sector} » n’offrent pas, sur cette période, de piste supplémentaire suffisamment distincte des fournisseurs déjà activés.`,
    };
  }

  return {
    title: `${formatProfessionalNetworkCount(candidateCount)} piste(s) de réemploi observée(s) chez les pairs`,
    text: `Ces débouchés sont construits à partir des paiements B2B réalisés par ${formatProfessionalNetworkCount(activePeerCount)} professionnel(s) actif(s) du même secteur « ${sector} ». Ils servent à préparer des questions et hypothèses de rendez-vous, pas à produire une recommandation automatique.`,
  };
}

function buildProfessionalProspectPeerExamplesHtml(peerExamples = []) {
  const examples = Array.isArray(peerExamples) ? peerExamples : [];

  if (!examples.length) {
    return "";
  }

  return `
    <div class="pro-prospect-peers">
      <span>Observé chez :</span>
      <div class="pro-prospect-peer-chips">
        ${examples.map(peer => `
          <button
            type="button"
            class="pro-prospect-peer-chip"
            onclick="renderProDetail('${escapeHtml(peer.professional_ref || "")}')"
          >
            ${escapeHtml(peer.name || peer.professional_ref || "—")}
          </button>
        `).join("")}
      </div>
    </div>
  `;
}

function buildProfessionalProspectsSectionHtml(data = {}) {
  const summary = data?.summary || {};
  const items = Array.isArray(data?.items) ? data.items : [];
  const reading = buildProfessionalProspectsReading(data);
  const sector = String(summary.target_industry_name || "").trim();
  const activePeers = Number(summary.active_peer_count || 0);
  const totalCandidates = Number(summary.candidate_count_total || 0);
  const displayedCandidates = Number(summary.candidate_count_displayed || 0);

  return `
    <section class="card pro-prospects-overview-card">
      <div class="pro-prospects-overview-heading">
        <div>
          <div class="stat-label">Perspectives & débouchés</div>
          <h3>${escapeHtml(reading.title)}</h3>
          <p>${escapeHtml(reading.text)}</p>
        </div>
      </div>

      <div class="pro-prospects-summary-kpis">
        <div>
          <span>Secteur comparé</span>
          <strong>${escapeHtml(sector || "—")}</strong>
        </div>
        <div>
          <span>Pairs actifs</span>
          <strong>${formatProfessionalNetworkCount(activePeers)}</strong>
        </div>
        <div>
          <span>Pistes détectées</span>
          <strong>${formatProfessionalNetworkCount(totalCandidates)}</strong>
        </div>
        <div>
          <span>Pistes affichées</span>
          <strong>${formatProfessionalNetworkCount(displayedCandidates)}</strong>
        </div>
      </div>
    </section>

    ${
      items.length
        ? `
          <section class="pro-prospects-grid">
            ${items.map(item => {
              const location = formatProfessionalProspectLocation(item);
              const signalLabel = getProfessionalProspectSignalLabel(item.signal_level);

              return `
                <article class="card pro-prospect-card pro-prospect-card-${escapeHtml(item.signal_level || "exploratory")}">
                  <div class="pro-prospect-card-heading">
                    <div>
                      <div class="stat-label">${escapeHtml(item.professional_ref || "—")}</div>
                      <h4>${escapeHtml(item.name || item.professional_ref || "—")}</h4>
                    </div>

                    <span class="pro-prospect-signal pro-prospect-signal-${escapeHtml(item.signal_level || "exploratory")}">
                      ${escapeHtml(signalLabel)}
                    </span>
                  </div>

                  <div class="pro-prospect-meta">
                    ${
                      item.industry_name
                        ? `<span>${escapeHtml(item.industry_name)}</span>`
                        : ""
                    }
                    ${
                      location
                        ? `<span>${escapeHtml(location)}</span>`
                        : ""
                    }
                  </div>

                  <div class="pro-prospect-metrics">
                    <div>
                      <span>Pairs payeurs</span>
                      <strong>${formatProfessionalNetworkCount(item.peer_count || 0)}</strong>
                      <small>${percent(item.peer_share_pct || 0)} des pairs actifs</small>
                    </div>
                    <div>
                      <span>Volume observé</span>
                      <strong>${euro(item.volume || 0)}</strong>
                      <small>${formatProfessionalNetworkCount(item.tx_count || 0)} transaction(s)</small>
                    </div>
                  </div>

                  ${
                    item.already_buys_from_target_in_period
                      ? `
                        <div class="pro-prospect-flag pro-prospect-flag-reciprocal">
                          Ce professionnel paie déjà le pro étudié : une relation à rendre potentiellement réciproque.
                        </div>
                      `
                      : ""
                  }

                  ${
                    item.paid_before_period
                      ? `
                        <div class="pro-prospect-flag pro-prospect-flag-reactivation">
                          Ce débouché avait déjà été activé avant la période : piste de réactivation.
                        </div>
                      `
                      : ""
                  }

                  ${buildProfessionalProspectPeerExamplesHtml(item.peer_examples || [])}

                  <div class="pro-prospect-actions">
                    <button
                      type="button"
                      class="primary-btn"
                      onclick="renderProDetail('${escapeHtml(item.professional_ref || "")}')"
                    >
                      Ouvrir la fiche
                    </button>
                  </div>
                </article>
              `;
            }).join("")}
          </section>
        `
        : `
          <section class="card pro-prospects-empty-card">
            Aucune piste de débouché n’est proposée pour cette combinaison de secteur et de période.
          </section>
        `
    }

    <section class="card pro-prospects-method-card">
      <strong>Lecture méthodologique.</strong>
      Les pistes sont déduites des paiements B2B réalisés par des professionnels du même secteur principal Odoo.
      Les comptes opérateurs P0000 / P9999 sont exclus, ainsi que les fournisseurs déjà payés par le professionnel
      étudié pendant la période. Une piste peut donc signaler soit un débouché inédit, soit une relation ancienne à réactiver.
    </section>
  `;
}

async function renderProProspectsTab() {
  const section = document.getElementById("proProspectsSection");
  if (!section || !appState.currentPro) return;

  const numProf = appState.currentPro;

  section.innerHTML = `
    <section class="card pro-prospects-loading-card">
      Chargement des perspectives de réemploi…
    </section>
  `;

  try {
    const data = await loadProfessionalReuseProspects(numProf);

    if (
      appState.proTab !== "prospects"
      || appState.currentPro !== numProf
    ) {
      return;
    }

    section.innerHTML = buildProfessionalProspectsSectionHtml(data);
  } catch (error) {
    console.error("Erreur chargement perspectives de réemploi :", error);
    section.innerHTML = `
      <section class="card">
        Impossible de charger les perspectives de réemploi.
      </section>
    `;
  }
}

async function renderProCharts() {
  const chartsSection = document.getElementById("proChartsSection");
  if (!chartsSection || !appState.detailData || !appState.currentPro) return;

  const numProf = appState.currentPro;
   chartsSection.innerHTML = `
    <section class="card pro-detail-network-loading-card">
      Chargement des dynamiques réseau du professionnel…
    </section>
  `;

  destroyProCharts();

  try {
    const dynamics = await loadProfessionalDetailDynamics(numProf);

    if (
      appState.proTab !== "dynamics"
      || appState.currentPro !== numProf
    ) {
      return;
    }

    appState.proDetailDynamics = dynamics;

    const network = dynamics?.b2b_network || {};
    const summary = network.summary || {};
    const excludedOperators = network.excluded_operator_accounts || {};
    const excludedOutbound = excludedOperators.outbound || {};
    const excludedInbound = excludedOperators.inbound || {};

    const hasCommercialRelations = (
      Number(summary.inbound_counterparty_count || 0) > 0
      || Number(summary.outbound_counterparty_count || 0) > 0
    );

    const hasIndividualPayers = (
      Number(summary.individual_payer_count || 0) > 0
    );

    const hasVisibleNetworkRelations = (
      hasCommercialRelations || hasIndividualPayers
    );

    const operatorNoteVisible = (
      Number(excludedOutbound.volume || 0) > 0
      || Number(excludedInbound.volume || 0) > 0
    );

    chartsSection.innerHTML = `
      <section class="card pro-detail-network-card">
        <div class="pro-detail-network-heading">
          <div>
            <div class="stat-label">Réseau immédiat des flux</div>
            <h3>Qui alimente ce professionnel, et vers qui redépense-t-il ses Gonettes ?</h3>
            <p>
              Cette lecture distingue les relations commerciales professionnelles directes
              et agrège les particuliers payeurs dans un nœud unique, afin de lire ensemble
              fond de commerce Gonette et débouchés de réemploi.
            </p>
          </div>

          <div class="pro-detail-network-kpis">
            <div>
              <strong>${formatProfessionalNetworkCount(summary.inbound_counterparty_count || 0)}</strong>
              <span>pros acheteurs</span>
            </div>
            <div>
              <strong>${formatProfessionalNetworkCount(summary.outbound_counterparty_count || 0)}</strong>
              <span>pros payés</span>
            </div>
            <div>
              <strong>${formatProfessionalNetworkCount(summary.reciprocal_counterparty_count || 0)}</strong>
              <span>liens réciproques</span>
            </div>
          </div>
        </div>

        ${
          operatorNoteVisible
            ? `
              <div class="pro-detail-network-operator-note">
                <strong>Comptes opérateurs exclus.</strong>
                Les flux vers P0000 / P9999 ne sont pas traités comme des débouchés B2B commerciaux.
                ${
                  Number(excludedOutbound.volume || 0) > 0
                    ? ` Sorties opérateurs : <strong>${euro(excludedOutbound.volume || 0)}</strong>.`
                    : ""
                }
                ${
                  Number(excludedInbound.volume || 0) > 0
                    ? ` Entrées opérateurs : <strong>${euro(excludedInbound.volume || 0)}</strong>.`
                    : ""
                }
              </div>
            `
            : ""
        }

        ${
          hasVisibleNetworkRelations
            ? `
              <div class="pro-detail-network-toolbar">
                <div class="pro-detail-network-legend">
                  <span><i class="pro-detail-network-dot pro-detail-network-dot-individual"></i> Particuliers payeurs agrégés</span>
                  <span><i class="pro-detail-network-dot pro-detail-network-dot-inbound"></i> Paie le professionnel étudié</span>
                  <span><i class="pro-detail-network-dot pro-detail-network-dot-outbound"></i> Reçoit ses Gonettes</span>
                  <span><i class="pro-detail-network-dot pro-detail-network-dot-reciprocal"></i> Relation réciproque</span>
                </div>

                <div class="pro-detail-network-actions">
                  <button id="proDetailNetworkFitBtn" class="secondary-btn" type="button">Recentrer</button>
                  <button id="proDetailNetworkZoomInBtn" class="secondary-btn" type="button">Zoom +</button>
                  <button id="proDetailNetworkZoomOutBtn" class="secondary-btn" type="button">Zoom -</button>
                </div>
              </div>

              <div class="pro-detail-network-layout">
                <div class="pro-detail-network-main">
                  <div id="proDetailB2BNetworkGraph" class="pro-detail-network-graph"></div>
                </div>

                <aside id="proDetailB2BNetworkPanel" class="pro-detail-network-panel"></aside>
              </div>
            `
            : `
              <div class="pro-detail-network-empty-shell">
                Aucun lien B2B commercial direct n’est visible sur cette période.
              </div>
            `
        }
      </section>

      ${buildProfessionalBalanceSectionHtml(dynamics?.balance_timeseries || {})}
    `;

    if (hasVisibleNetworkRelations) {
      renderProfessionalDetailB2BNetworkGraph(dynamics);
    }

    renderProfessionalBalanceHistoryChart(dynamics?.balance_timeseries || {});
  } catch (error) {
    console.error("Erreur chargement dynamiques fiche pro :", error);
    chartsSection.innerHTML = `
      <section class="card">
        Impossible de charger les dynamiques réseau de cette fiche professionnelle.
      </section>
    `;
  }
}

function drawProTabContent() {
  const dataSection = document.getElementById("proDataSection");
  const commerceSection = document.getElementById("proCustomerProfileSection");
  const chartsSection = document.getElementById("proChartsSection");
  const prospectsSection = document.getElementById("proProspectsSection");

  if (!dataSection || !commerceSection || !chartsSection || !prospectsSection) return;

  dataSection.classList.toggle("hidden", appState.proTab !== "data");
  commerceSection.classList.toggle("hidden", appState.proTab !== "commerce");
  chartsSection.classList.toggle("hidden", appState.proTab !== "dynamics");
  prospectsSection.classList.toggle("hidden", appState.proTab !== "prospects");

  if (appState.proTab === "commerce") {
    destroyProCharts();
    void renderProCustomerProfile();
  } else if (appState.proTab === "dynamics") {
    void renderProCharts();
  } else if (appState.proTab === "prospects") {
    destroyProCharts();
    void renderProProspectsTab();
  } else {
    destroyProCharts();
  }

  updateProTabButtons();
}

function updateProTabButtons() {
  const btnData = document.getElementById("proTabData");
  const btnCommerce = document.getElementById("proTabCommerce");
  const btnDynamics = document.getElementById("proTabDynamics");
  const btnProspects = document.getElementById("proTabProspects");

  if (btnData) {
    btnData.classList.toggle("tab-btn-active", appState.proTab === "data");
  }

  if (btnCommerce) {
    btnCommerce.classList.toggle("tab-btn-active", appState.proTab === "commerce");
  }

  if (btnDynamics) {
    btnDynamics.classList.toggle("tab-btn-active", appState.proTab === "dynamics");
  }

  if (btnProspects) {
    btnProspects.classList.toggle("tab-btn-active", appState.proTab === "prospects");
  }
}

function normalizeProfessionalDetailRef(value) {
  const raw = String(value || "").trim();
  const match = raw.match(/^(P\d{4})\b/);
  return match ? match[1] : raw;
}


async function renderProDetail(numProf, detailMode = "all") {
  numProf = normalizeProfessionalDetailRef(numProf);

  const preserveVisibleView = Boolean(
    appState.periodRefreshInProgress
    && appState.currentView === "pro-detail"
    && content?.childElementCount > 0
  );

  destroyCartographyMap();
  const isSameProfessional = appState.currentPro === numProf;
  const needReload = !isSameProfessional || !appState.detailData;
  const isDetailModeChanged = appState.detailMode !== detailMode;

  appState.currentView = "pro-detail";
  syncSidebarView("pro-detail");
  appState.currentPro = numProf;
  

  // pour revenir automatiquement sur Données à chaque nouveau pro
  // appState.proTab = "data";
  if (needReload || isDetailModeChanged) {
    appState.detailPage = 1;
  }
  appState.detailMode = detailMode;

  if (needReload) {
    if (!preserveVisibleView) {
      content.innerHTML = `<div class="card">Chargement...</div>`;
    }
    const data = await apiGet(`/api/pro/${encodeURIComponent(numProf)}${getPeriodQueryParam()}`);
    appState.detailData = data;

  }

  const data = appState.detailData;
  const tx = data.transactions || [];

  setTitle(formatProfessionalPageTitle(numProf, data.fullname));

  if (detailMode === "all" || detailMode === "recues" || detailMode === "reconverti" || detailMode === "converti") {
    if (!["Date", "Réalisé par", "Vers", "Montant"].includes(appState.detailSortBy)) {
      appState.detailSortBy = "Date";
      appState.detailSortDir = "desc";
    }
  } else {
    if (!["Libelle", "Count", "Total"].includes(appState.detailSortBy)) {
      appState.detailSortBy = "Total";
      appState.detailSortDir = "desc";
    }
  }

  content.innerHTML = `
    <div class="topbar">
      <button class="secondary-btn" onclick="renderProsView()">← Retour au classement</button>
    </div>

    <div id="proMeetingHeroSection"></div>

    <div class="pro-tabs pro-detail-tabs">
      <button id="proTabData" class="tab-btn" onclick="setProTab('data')">Données</button>
      <button id="proTabCommerce" class="tab-btn" onclick="setProTab('commerce')">Fond de commerce</button>
      <button id="proTabDynamics" class="tab-btn" onclick="setProTab('dynamics')">Dynamiques & réseau</button>
      <button id="proTabProspects" class="tab-btn" onclick="setProTab('prospects')">Perspectives & débouchés</button>
    </div>

    <div id="proDataSection">
      <div id="proSummarySection"></div>
      <div id="detailSection"></div>
    </div>

    <div id="proCustomerProfileSection" class="hidden"></div>
    <div id="proChartsSection" class="hidden"></div>
    <div id="proProspectsSection" class="hidden"></div>
  `;
  drawProMeetingHeroSection();
  drawProSummarySection();
  drawDetailSection();
  drawProTabContent();
}

function syncSidebarView(view) {
  const map = {
    stats: "stats",
    "monetary-pilotage": "monetary-pilotage",
    pros: "pros",
    cartography: "cartography",
    territories: "territories",
    sectors: "sectors",
    network: "pros",
    tickets: "tickets",
    info: "info",
    "pro-detail": "pros"
  };

  const targetValue = map[view] || "stats";

  document.querySelectorAll('input[name="dataView"]').forEach(radio => {
    radio.checked = radio.value === targetValue;
  });
}

function applyTheme(theme, persist = true) {
  const isDark = theme === "dark";
  document.body.classList.toggle("dark-mode", isDark);

  const btn = document.getElementById("themeToggleBtn");
  if (btn) {
    btn.textContent = isDark ? "☀️ Mode clair" : "🌙 Mode sombre";
  }

  if (persist) {
    localStorage.setItem("mlcflux_theme", isDark ? "dark" : "light");
  }

  refreshProfessionalConsumptionMapThemeRendering();
}

function initThemeToggle() {
  const savedTheme = localStorage.getItem("mlcflux_theme") || "light";
  applyTheme(savedTheme);

  const btn = document.getElementById("themeToggleBtn");
  if (!btn || btn.dataset.bound === "true") return;

  btn.addEventListener("click", () => {
    const nextTheme = document.body.classList.contains("dark-mode")
      ? "light"
      : "dark";

    if (appState.professionalConsumptionMapThemeOverrideActive) {
      // L'utilisateur exprime son choix de thème pour l'après-mode dynamique,
      // mais l'expérience dynamique reste volontairement en dark mode.
      appState.professionalConsumptionMapThemeBeforeDynamic = nextTheme;
      localStorage.setItem("mlcflux_theme", nextTheme);
      applyTheme("dark", false);
      return;
    }

    applyTheme(nextTheme);
  });

  btn.dataset.bound = "true";
}

if (reloadButton) {
  reloadButton.addEventListener("click", async () => {
    try {
      reloadButton.disabled = true;
      reloadButton.textContent = "Synchronisation...";
      const result = await apiPost("/api/reload");
      alert(result.message || "Synchronisation terminée");

      appState.prosData = [];
      appState.detailData = null;
      appState.currentPro = null;

      if (appState.currentView === "pros") {
        await renderProsView(true);
      } else {
        await renderStatsView();
      }
    } catch (err) {
      alert(`Erreur : ${err.message}`);
    } finally {
      reloadButton.disabled = false;
      reloadButton.textContent = "Synchroniser les dernières transactions";
    }
  });
}

document.querySelectorAll('input[name="dataView"]').forEach(input => {
  input.addEventListener("change", (e) => {
    const view = e.target.value;

    void openViewProgressively(view);
  });
});

bindNetworkSearchOutsideClick();
initThemeToggle();
initSidebarCollapse();
renderProgressiveViewShell("stats");

waitForNextBrowserPaint()
  .then(() => initPeriodFilter())
  .then(() => runProgressiveViewHydration({
    viewKey: "stats",
    hydrate: () => renderStatsView(false),
    message: "Chargement des statistiques de l’année en cours…"
  }));

window.renderProDetail = renderProDetail;
window.renderProsView = renderProsView;
window.renderCartographyView = renderCartographyView;
window.renderTerritoriesView = renderTerritoriesView;
window.renderSectorsView = renderSectorsView;
window.renderMonetaryPilotageView = renderMonetaryPilotageView;
window.renderTicketsView = renderTicketsView;
window.renderTicketDetail = renderTicketDetail;
window.renderInfoView = renderInfoView;
window.toggleProsSort = toggleProsSort;
window.changeDetailTransactionPage = changeDetailTransactionPage;

window.renderUserDetail = renderUserDetail;
window.setProTab = setProTab;
window.selectNetworkSearchResult = selectNetworkSearchResult;
