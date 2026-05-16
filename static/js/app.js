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
    pilotageHoldingsMobilization: null,
    pilotageHoldingsDormancy: null
  },

  network: {
    minEdgeWeight: 500,
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
    markdown: null
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


function initializeProfessionalsMap(professionals) {
  const mapNode = document.getElementById("professionalsMap");
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
    container: "professionalsMap",
    style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    center: [4.8357, 45.7640],
    zoom: 9,
    pitch: 52,
    bearing: -12
  });

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

  const fitButton = document.getElementById("cartographyFitBtn");
  if (fitButton) {
    fitButton.addEventListener("click", () => {
      fitCartographyMapToProfessionals(map, professionals);
    });
  }

  appState.cartography.map = map;
  appState.cartography.overlay = overlay;
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
  destroyCartographyMap();

  appState.currentView = "sectors";
  syncSidebarView("sectors");
  setTitle("Analyse sectorielle");

  content.innerHTML = `<div class="card">Chargement de l’analyse sectorielle...</div>`;

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
  destroyCartographyMap();

  appState.currentView = "territories";
  syncSidebarView("territories");
  setTitle("Analyse territoriale — codes postaux");

  content.innerHTML = `<div class="card">Chargement de l’analyse territoriale...</div>`;

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
  destroyCartographyMap();

  appState.currentView = "cartography";
  syncSidebarView("cartography");
  setTitle("Cartographie des professionnels");

  content.innerHTML = `<div class="card">Chargement de la cartographie...</div>`;

  if (!appState.cartography.data || forceReload) {
    appState.cartography.data = await apiGet(`/api/professionals-map${getPeriodQueryParam()}`);
  }

  const data = appState.cartography.data || {};
  const summary = data.summary || {};
  const professionals = Array.isArray(data.professionals) ? data.professionals : [];

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


async function renderNetworkView() {
  destroyCartographyMap();
  appState.currentView = "network";
  syncSidebarView("network");
  setTitle("Network économique");

  content.innerHTML = `
    <div class="card">
      <div class="network-toolbar">
        <div class="network-search-box">
          <input
            id="networkSearch"
            type="text"
            placeholder="Rechercher un acteur (ex: P0512, biocoop, melting...)"
            value="${escapeHtml(appState.network.searchTerm)}"
          />
          <div id="networkSearchPreview" class="network-search-preview hidden"></div>
        </div>

        <div class="network-slider-group">
          <label for="networkThreshold">
            Seuil relations : <strong id="networkThresholdValue">${appState.network.minEdgeWeight} €</strong>
          </label>
          <input
            id="networkThreshold"
            type="range"
            min="0"
            max="5000"
            step="100"
            value="${appState.network.minEdgeWeight}"
          />
        </div>

        <div class="network-actions">
          <button id="networkFitBtn" class="secondary-btn">Recentrer</button>
          <button id="networkZoomInBtn" class="secondary-btn">Zoom +</button>
          <button id="networkZoomOutBtn" class="secondary-btn">Zoom -</button>
        </div>
      </div>

      <div class="network-layout">
        <div class="network-main">
          <div class="network-legend">
            <span><span class="legend-dot legend-dot-blue"></span> Acteur du réseau</span>
            <span><span class="legend-dot legend-dot-dark"></span> Acteur sélectionné</span>
            <span><span class="legend-line legend-line-red"></span> Relations mises en avant</span>
          </div>
            <div class="network-graph-shell">
              <div id="networkGraph"></div>
              <div id="networkFloatingLabel" class="network-floating-label hidden"></div>
            </div>       
          </div>

        <aside id="networkSidePanel" class="network-sidepanel">
          <div class="network-sidepanel-empty">
            Clique sur un acteur pour voir ses informations.
          </div>
        </aside>
      </div>
    </div>
  `;

  const data = await apiGet(`/api/network${getPeriodQueryParam()}`);
  appState.network.rawData = data;
  appState.network.enrichedData = enrichNetworkData(data);

  renderNetworkGraph(data);
  bindNetworkControls();
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

function renderNetworkSidePanel(node) {
  const panel = document.getElementById("networkSidePanel");
  if (!panel) return;

  if (!node) {
    panel.innerHTML = `
      <div class="network-sidepanel-empty">
        Clique sur un acteur pour voir ses informations.
      </div>
    `;
    return;
  }

  const label = node.data("label") || node.id();
  const degree = node.data("degree") || 0;
  const volume = node.data("volume") || 0;

  panel.innerHTML = `
    <div class="network-sidepanel-card">
      <h3>${escapeHtml(label)}</h3>
      <p><strong>Code :</strong> ${escapeHtml(node.id())}</p>
      <p><strong>Connexions :</strong> ${degree}</p>
      <p><strong>Volume relationnel :</strong> ${euro(volume)}</p>

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
            "background-color": "#4f86f7",
            "width": "mapData(volume, 0, 20000, 16, 54)",
            "height": "mapData(volume, 0, 20000, 16, 54)",
            "border-width": 2,
            "border-color": "#ffffff",
            "overlay-padding": 10,
            "z-index": 10
          }
        },
        {
          selector: "edge",
          style: {
            "width": "mapData(weight, 0, 10000, 1.5, 7)",
            "line-color": "#cbd5e1",
            "target-arrow-color": "#cbd5e1",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "curve-style": "bezier",
            "opacity": 0.32
          }
        },
        {
          selector: ".faded",
          style: {
            "opacity": 0.06
          }
        },
        {
          selector: ".highlighted",
          style: {
            "line-color": "#ef4444",
            "target-arrow-color": "#ef4444",
            "opacity": 0.95,
            "z-index": 30
          }
        },
        {
          selector: ".selected-node",
          style: {
            "background-color": "#0f172a",
            "border-color": "#ef4444",
            "border-width": 4
          }
        },
        {
          selector: ".search-match",
          style: {
            "border-color": "#f59e0b",
            "border-width": 4
          }
        }
      ],
      layout: {
        name: "cose",
        animate: false,
        fit: true,
        padding: 60
      },
      wheelSensitivity: 0.2
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
    await renderNetworkView();
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

    const { start, end } = getPresetPeriod("all");

    appState.analysisPeriod = {
      preset: "all",
      start,
      end
    };

    syncPeriodInputsFromValues("all", start, end);
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

function bindInfoEditor() {
  const editButton = document.getElementById("infoEditButton");
  const reader = document.getElementById("infoMarkdownReader");
  const editor = document.getElementById("infoMarkdownEditor");
  const textarea = document.getElementById("infoMarkdownTextarea");
  const preview = document.getElementById("infoMarkdownPreview");
  const saveButton = document.getElementById("infoSaveButton");
  const cancelButton = document.getElementById("infoCancelButton");

  if (
    !editButton
    || !reader
    || !editor
    || !textarea
    || !preview
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
      const result = await apiPostJson("/api/info-content", { markdown });

      appState.info.markdown = markdown;
      reader.innerHTML = renderInfoMarkdown(markdown);
      decorateInfoMarkdownHeadings(reader);

      closeEditor();
      setInfoFeedback(result.message || "Documentation enregistrée.");
    } catch (err) {
      setInfoFeedback(`Erreur : ${err.message}`, true);
    } finally {
      saveButton.disabled = false;
      cancelButton.disabled = false;
      saveButton.textContent = "Enregistrer";
    }
  });
}

async function renderInfoView(forceReload = false) {
  appState.currentView = "info";
  syncSidebarView("info");
  destroyCartographyMap();
  setTitle("Info & méthodologie");

  content.innerHTML = `
    <section class="card info-view-card">
      <div class="info-view-header">
        <div>
          <p class="info-view-kicker">Documentation éditoriale</p>
          <h2>À propos des données et des calculs</h2>
          <p class="info-view-intro">
            Cette page est alimentée par un fichier Markdown modifiable directement depuis MLCFlux.
          </p>
        </div>
        <button id="infoEditButton" class="primary-btn" type="button">
          Modifier le Markdown
        </button>
      </div>

      <div id="infoFeedback" class="info-feedback hidden"></div>

      <div id="infoMarkdownReader" class="markdown-body info-markdown-reader">
        <p>Chargement de la documentation…</p>
      </div>

      <div id="infoMarkdownEditor" class="info-editor hidden">
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
  `;

  try {
    if (forceReload || appState.info.markdown === null) {
      const data = await apiGet("/api/info-content");
      appState.info.markdown = data.markdown || "";
    }

    const reader = document.getElementById("infoMarkdownReader");
    if (reader) {
      reader.innerHTML = renderInfoMarkdown(appState.info.markdown || "");
      decorateInfoMarkdownHeadings(reader);
    }

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

async function renderStatsView(forceReload = false) {
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

  content.innerHTML = `<div class="card">Chargement...</div>`;

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
      key: "A→U",
      title: "Vers les particuliers",
      description: "Alimentations numériques adressées à des comptes particuliers."
    },
    {
      key: "A→P",
      title: "Vers les professionnels",
      description: "Alimentations numériques adressées à des comptes professionnels."
    },
    {
      key: "A→A",
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
    <div id="globalStatsOverviewCharts"></div>

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
          <div class="stat-label">Particuliers → acteur masqué</div>
          <div class="stat-value">${integerFr(stats.nb_operations_user_to_masked_actor || 0)}</div>
          <div class="stat-subtext">${euro(stats.volume_operations_user_to_masked_actor || 0)} sur la période</div>
        </div>

        <div class="card stat-card-static">
          <div class="stat-label">Montant moyen U→acteur masqué</div>
          <div class="stat-value">${euro(stats.montant_moyen_user_to_masked_actor || 0)}</div>
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

      <section class="card activity-flow-overview operations-masked-flow-overview">
        <div class="activity-flow-overview-header">
          <h3>Flux particuliers vers acteur masqué</h3>
          <p>
            Cette famille regroupe structurellement les flux <strong>U→A</strong>.
            L’audit des libellés montre qu’il s’agit très majoritairement d’annulations,
            avoirs, clôtures ou corrections, mais la classification affichée ici ne dépend pas des libellés libres.
          </p>
        </div>

        <div class="activity-flow-grid operations-masked-flow-grid">
          <article class="activity-flow-card">
            <div class="activity-flow-heading">
              <span class="activity-flow-code">U→A</span>
              <h4>Particuliers vers acteur technique / masqué</h4>
            </div>
            <p class="activity-flow-description">
              Mouvements sortant d’un compte particulier vers l’acteur technique.
              Ce bloc doit être lu à part de l’activité économique.
            </p>
            <div class="activity-flow-metrics">
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Opérations</span>
                <strong>${integerFr(stats.nb_operations_user_to_masked_actor || 0)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Volume</span>
                <strong>${euro(stats.volume_operations_user_to_masked_actor || 0)}</strong>
              </div>
              <div class="activity-flow-metric">
                <span class="activity-flow-metric-label">Montant moyen</span>
                <strong>${euro(stats.montant_moyen_user_to_masked_actor || 0)}</strong>
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
      <strong>Périmètre monétaire effectif :</strong>
      les stocks Odoo disponibles couvrent ici la période
      <strong>${formatIsoDateFr(effectivePeriod.start)} → ${formatIsoDateFr(effectivePeriod.end)}</strong>,
      qui diffère du filtre global demandé
      (${formatIsoDateFr(requestedPeriod.start)} → ${formatIsoDateFr(requestedPeriod.end)}).
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
      data: items.map(() => periodReference),
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
      communs effectivement disponibles entre soldes particuliers et stocks Odoo.
    </p>
  `;
}

function getPilotageHoldingsDormancyStock(item, bucketKey) {
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
          label: "Part de la masse numérique",
          data: items.map((item) => (
            item.average_user_stock_share_of_numeric_mass === null ||
            item.average_user_stock_share_of_numeric_mass === undefined
              ? null
              : item.average_user_stock_share_of_numeric_mass * 100
          )),
          yAxisID: "yShare",
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

              if (context.dataset.yAxisID === "yShare") {
                return `${label} : ${formatPilotageChartPercent(context.raw)}`;
              }

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
        },
        yShare: {
          beginAtZero: true,
          position: "right",
          grid: {
            drawOnChartArea: false
          },
          title: {
            display: true,
            text: "Part de la masse numérique (%)"
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

  return {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "G U→P pour 100 G de stock particulier moyen",
          data: items.map((item) => (
            item.economic_up_volume_per_100_g_average_user_stock ?? null
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
              return `Mobilisation : ${formatPilotageGonetteYield(context.raw)} pour 100 G détenues`;
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
            text: "G dépensées vers les pros / 100 G détenues"
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
  destroyMonetaryPilotageCharts();

  appState.currentView = "monetary-pilotage";
  syncSidebarView("monetary-pilotage");
  setTitle("Pilotage monétaire");

  content.innerHTML = `<div class="card">Chargement du pilotage monétaire...</div>`;

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

    content.innerHTML = `
      <section class="card pilotage-overview-card">
        <div class="pilotage-overview-header pilotage-overview-header-refined">
          <div>
            <div class="stat-label">Analyse croisée Odoo × Cyclos</div>
            <h2>Pilotage monétaire</h2>
            <p>
              Cette vue analyse la vitalité de la Gonette numérique à partir de cinq dimensions :
              <strong>rotation économique</strong>, <strong>rétention des alimentations</strong>,
              <strong>rendement circulatoire</strong>, <strong>robustesse apparente face aux reconversions</strong>
              et <strong>détention mobilisable chez les particuliers</strong>.
            </p>
          </div>
        </div>

        <div class="pilotage-period-line">
          ${pilotagePeriodLabel} :
          <strong>${effectiveStartLabel} → ${effectiveEndLabel}</strong>
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
            <h3>Des soldes particuliers à leur mobilisation économique</h3>
            <p>
              Cette lecture observe la part de Gonettes numériques stationnée chez les particuliers,
              la frontière entre masse active et masse dormante, ainsi que la capacité de ce stock
              à se transformer en paiements vers les professionnels.
            </p>
          </div>

          <div class="pilotage-period-line">
            Période de détention effective :
            <strong>${holdingsEffectiveStartLabel} → ${holdingsEffectiveEndLabel}</strong>
          </div>

          <div class="pilotage-metric-grid pilotage-holdings-kpi-grid">
            <article class="pilotage-metric-card pilotage-holdings-highlight-card">
              <span>Stock particulier moyen</span>
              <strong>${gonettes(holdingsReference.average_positive_user_stock || 0)}</strong>
              <small>
                ${formatPilotagePercent(holdingsReference.average_user_stock_share_of_numeric_mass)}
                de la masse numérique moyenne
              </small>
            </article>

            <article class="pilotage-metric-card pilotage-holdings-highlight-card">
              <span>Particuliers avec solde positif</span>
              <strong>${formatPilotageInteger(holdingsClosing.users_positive || 0)}</strong>
              <small>
                ${gonettes(holdingsClosing.positive_user_stock || 0)}
                détenues à la clôture
              </small>
            </article>

            <article class="pilotage-metric-card pilotage-holdings-highlight-card">
              <span>Stock actif ≤ 30 jours</span>
              <strong>${gonettes(holdingsActive30Bucket.positive_user_stock || 0)}</strong>
              <small>
                ${formatPilotagePercent(holdingsActive30Bucket.stock_share_of_positive_user_stock)}
                du stock particulier de clôture
              </small>
            </article>

            <article class="pilotage-metric-card pilotage-holdings-highlight-card">
              <span>Mobilisation du stock particulier</span>
              <strong>${formatPilotageGonetteYield(holdingsMobilization.economic_up_volume_per_100_g_average_user_stock)}</strong>
              <small>
                dépensées vers les pros pour 100 G détenues en moyenne
              </small>
            </article>
          </div>
        </section>

        <section class="pilotage-charts-stack">
          <article class="card stats-chart-card stats-chart-card-full pilotage-chart-card">
            ${buildStatsChartHeader({
              chartKey: "pilotageHoldingsStockShare",
              title: "Stock particulier moyen et poids dans la masse numérique",
              description: "Ce graphe suit le stock positif moyen détenu par les particuliers et sa part dans la masse numérique Odoo moyenne, mois par mois.",
              supportsMetricToggle: false
            })}

            <div class="pilotage-chart-frame">
              <canvas id="pilotageHoldingsStockShareChart"></canvas>
            </div>
          </article>

          <article class="card stats-chart-card stats-chart-card-full pilotage-chart-card">
            ${buildStatsChartHeader({
              chartKey: "pilotageHoldingsMobilization",
              title: "Mobilisation économique du stock particulier",
              description: "Chaque barre indique le volume U→P observé pour 100 G de stock particulier moyen sur le mois.",
              supportsMetricToggle: false
            })}

            <div class="pilotage-chart-frame pilotage-chart-frame-compact">
              <canvas id="pilotageHoldingsMobilizationChart"></canvas>
            </div>
          </article>

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

          ${holdingsPartialMonthNote}
        </section>

        <section class="pilotage-dashboard-grid">
          <article class="card pilotage-section-card pilotage-holdings-dormancy-card">
            <div class="pilotage-section-heading">
              <h3>Masse active / dormante à la clôture</h3>
              <p>
                La dormance est mesurée par l’absence de toute transaction impliquant le compte particulier.
                Elle ne signifie pas automatiquement qu’un solde est « perdu », mais qu’il s’éloigne de l’activité récente.
              </p>
            </div>

            <div class="pilotage-metric-grid pilotage-holdings-dormancy-grid">
              <article class="pilotage-metric-card">
                <span>Actif ≤ 30 j</span>
                <strong>${gonettes(holdingsActive30Bucket.positive_user_stock || 0)}</strong>
                <small>
                  ${formatPilotageInteger(holdingsActive30Bucket.user_count || 0)} comptes ·
                  ${formatPilotagePercent(holdingsActive30Bucket.stock_share_of_positive_user_stock)}
                </small>
              </article>

              <article class="pilotage-metric-card">
                <span>Dormant 31–90 j</span>
                <strong>${gonettes(holdingsDormant31To90Bucket.positive_user_stock || 0)}</strong>
                <small>
                  ${formatPilotageInteger(holdingsDormant31To90Bucket.user_count || 0)} comptes ·
                  ${formatPilotagePercent(holdingsDormant31To90Bucket.stock_share_of_positive_user_stock)}
                </small>
              </article>

              <article class="pilotage-metric-card">
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

          <article class="card pilotage-section-card pilotage-holdings-reactivation-card">
            <div class="pilotage-section-heading">
              <h3>Réactivation des stocks dormants</h3>
              <p>
                Un compte réactivé détenait un solde positif et était dormant depuis plus de 90 jours
                à l’ouverture de la période, puis a enregistré au moins une transaction.
              </p>
            </div>

            <div class="pilotage-metric-grid pilotage-holdings-reactivation-grid">
              <article class="pilotage-metric-card">
                <span>Comptes réactivés</span>
                <strong>${formatPilotageInteger(holdingsReactivation.reactivated_user_count || 0)}</strong>
                <small>
                  ${formatPilotagePercent(holdingsReactivation.reactivated_user_share_of_dormant_gt_90_opening_users)}
                  des comptes dormants &gt; 90 j identifiés à l’ouverture
                </small>
              </article>

              <article class="pilotage-metric-card">
                <span>Stock dormant porté par ces comptes</span>
                <strong>${gonettes(holdingsReactivation.reactivated_opening_stock || 0)}</strong>
                <small>
                  ${formatPilotagePercent(holdingsReactivation.reactivated_stock_share_of_dormant_gt_90_opening_stock)}
                  du stock dormant &gt; 90 j d’ouverture
                </small>
              </article>

              <article class="pilotage-metric-card">
                <span>Paiements U→P issus des comptes réactivés</span>
                <strong>${gonettes(holdingsReactivation.economic_up_volume_from_reactivated_users || 0)}</strong>
                <small>
                  ${formatPilotageInteger(holdingsReactivation.economic_up_transaction_count_from_reactivated_users || 0)}
                  transaction(s) économiques vers les pros
                </small>
              </article>
            </div>
          </article>
        </section>
      </section>
    `;

    bindPilotageIndicatorHelpButtons();
    bindPilotageTabs();
    bindPilotageLm3ChainsDetails();
    renderMonetaryPilotageCharts(
      pilotageSeries,
      data,
      pilotageReuseYearlySeries,
      pilotageLm3YearlySeries,
      holdingsSeries,
      holdingsSummary
    );
  } catch (error) {
    console.error("Erreur lors du chargement du pilotage monétaire :", error);

    content.innerHTML = `
      <section class="card pilotage-empty-card">
        <h2>Pilotage monétaire</h2>
        <p>Le chargement des indicateurs de pilotage a échoué.</p>
      </section>
    `;
  }
}

async function renderProsView(forceReload = false) {
  destroyCartographyMap();
  appState.currentView = "pros";
  syncSidebarView("pros");
  setTitle("Activité des professionnels");

  if (forceReload || appState.prosData.length === 0) {
    content.innerHTML = `<div class="card">Chargement...</div>`;
    appState.prosData = await apiGet(`/api/pros${getPeriodQueryParam()}`);
  }

  drawProsTable();
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

  globalDailyCount: {
    title: "Transactions par jour, par nature d’opération",
    summary: "Vue transversale des grands mouvements monétaires sur la période active.",
    perimeter: [
      "Activité économique : Compte / Compte Pro, hors flux vers Acteur masqué, hors P0000 et P9999.",
      "Alimentation du circuit : group_label = Émission.",
      "Sorties du circuit : Compte Pro · P→Acteur masqué.",
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
      "Flux atypiques : A→P et A→U inclus dans l’activité retenue."
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
      "Sorties : transactions Compte Pro · P→Acteur masqué."
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
      "La courbe A→U montre les alimentations vers les particuliers.",
      "La courbe A→P montre les alimentations vers les professionnels.",
      "Si une courbe est très proche de zéro, cela veut dire que ce cas est rare ou porte sur de petits montants.",
      "Les séries complètement vides ne sont pas affichées."
    ],
    perimeter: [
      "Uniquement les transactions d’alimentation du circuit numérique.",
      "A→U : vers particuliers.",
      "A→P : vers professionnels.",
      "A→A : résiduel technique très marginal."
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
      "Sorties : Compte Pro · P→Acteur masqué."
    ],
    formulas: [
      "Écart net cumulé au mois m = volume cumulé alimenté − volume cumulé sorti."
    ],
    sources: ["date", "amount", "group_label", "from_label", "to_label"]
  },

  operationsMonthlyFamilies: {
    title: "Chaque mois : quels types d’opérations hors activité économique ?",
    summary: "Ce graphe compare les deux grands blocs de l’onglet : les mouvements impliquant les comptes opérateurs et les flux particuliers vers l’acteur masqué.",
    reading: [
      "Chaque point correspond à un mois.",
      "La série « Comptes opérateurs » montre les opérations liées à P0000 ou P9999.",
      "La série « Particuliers → acteur masqué » montre les flux U→A.",
      "Quand une courbe monte, cela signifie que ce type d’opérations a été plus important ce mois-là.",
      "Le dernier mois peut être incomplet si la période s’arrête en cours de mois."
    ],
    perimeter: [
      "Comptes opérateurs : flux classés dans la famille impliquant P0000 / P9999.",
      "Particuliers → acteur masqué : flux U→A classés hors activité économique."
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
      "Ce périmètre regroupe les flux impliquant P0000 / P9999 et les flux particuliers vers acteur masqué.",
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

  chart.data.datasets.forEach((dataset, index) => {
    const isHidden = Boolean(hiddenMap[dataset.label]);
    chart.setDatasetVisibility(index, !isHidden);
  });

  chart.update();
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
            description: "Compare les comptes opérateurs et les flux particuliers vers acteur masqué.",
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

  content.innerHTML = `
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
  searchInput.focus();
  searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);

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
  const location = formatProfessionalLocation(enrichment);
  const description = plainTextFromHtml(enrichment.website_description_html);

  const secondaryIndustries = Array.isArray(enrichment.secondary_industries)
    ? enrichment.secondary_industries
        .map(item => String((item && item.industry_name) || "").trim())
        .filter(Boolean)
    : [];

  const hasVisibleContent = Boolean(
    detailedActivity ||
    industryName ||
    location ||
    description ||
    secondaryIndustries.length
  );

  if (!hasVisibleContent) {
    container.innerHTML = "";
    return;
  }

  const metaItems = [];

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

  const descriptionHtml = description
    ? `<p class="pro-context-description">${escapeHtml(description)}</p>`
    : "";

  container.innerHTML = `
    <section class="card pro-context-card">
      <div class="pro-context-heading">
        <div class="stat-label">Profil professionnel</div>
        <h3>${escapeHtml(detailedActivity || "Informations d’activité")}</h3>
      </div>

      ${metaGridHtml}
      ${secondaryIndustriesHtml}
      ${descriptionHtml}
    </section>
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
  

  summaryContainer.innerHTML = `
    <section class="pro-summary-group">
      <div class="pro-summary-heading">
        <h3>Ce que le professionnel reçoit</h3>
      </div>

      <div class="grid pro-summary-main-grid">
        ${clickableStatCard(
          "C2B reçu",
          euro(filteredStats.montant_recu_particuliers),
          `renderProDetail('${escapeHtml(numProf)}', 'payeurs_particuliers')`,
          detailMode === "payeurs_particuliers",
          "Montant reçu depuis les comptes particuliers."
        )}

        ${clickableStatCard(
          "B2B reçu",
          euro(filteredStats.montant_recu_professionnels),
          `renderProDetail('${escapeHtml(numProf)}', 'payeurs_professionnels')`,
          detailMode === "payeurs_professionnels",
          "Montant reçu depuis les autres professionnels du réseau."
        )}

        ${clickableStatCard(
          "Total reçu",
          euro(filteredStats.montant_total_recu),
          `renderProDetail('${escapeHtml(numProf)}', 'somme_recue')`,
          detailMode === "somme_recue",
          "Total reçu depuis les particuliers et les professionnels, hors conversions reçues."
        )}
      </div>

      <div class="grid pro-summary-mini-grid">
        ${clickableMiniStatCard(
          "Particuliers payeurs",
          filteredStats.nb_particuliers ?? 0,
          `renderProDetail('${escapeHtml(numProf)}', 'payeurs_particuliers')`,
          detailMode === "payeurs_particuliers"
        )}

        ${clickableMiniStatCard(
          "Professionnels payeurs",
          filteredStats.nb_professionnels ?? 0,
          `renderProDetail('${escapeHtml(numProf)}', 'payeurs_professionnels')`,
          detailMode === "payeurs_professionnels"
        )}

        ${clickableMiniStatCard(
          "Transactions reçues",
          filteredStats.nb_transactions_recues ?? 0,
          `renderProDetail('${escapeHtml(numProf)}', 'recues')`,
          detailMode === "recues"
        )}
      </div>
    </section>

    <section class="pro-summary-group">
      <div class="pro-summary-heading">
        <h3>Ce qu’il remet en circulation</h3>
      </div>

      <div class="grid pro-summary-main-grid">
        ${clickableStatCard(
          "Émis vers pro",
          euro(filteredStats.montant_emis_vers_pro),
          `renderProDetail('${escapeHtml(numProf)}', 'emis_pro')`,
          detailMode === "emis_pro",
          "Achats ou paiements réalisés auprès d’autres professionnels du réseau."
        )}

        ${clickableStatCard(
          "Émis vers particuliers",
          euro(filteredStats.montant_emis_vers_particuliers),
          `renderProDetail('${escapeHtml(numProf)}', 'emis_particuliers')`,
          detailMode === "emis_particuliers",
          "Rémunérations, défraiements ou autres versements vers des comptes particuliers."
        )}

        ${clickableStatCard(
          "Total émis hors reconversion",
          euro(filteredStats.total_montant_emis_sans_reconversion),
          `renderProDetail('${escapeHtml(numProf)}', 'emis_total')`,
          detailMode === "emis_total",
          "Somme des montants émis vers les professionnels et les particuliers, hors reconversion."
        )}
      </div>
    </section>

    <section class="pro-summary-group">
      <div class="pro-summary-heading">
        <h3>Conversion et réutilisation</h3>
      </div>

      <div class="grid pro-summary-main-grid">
        ${clickableStatCard(
          "Converti",
          euro(filteredStats.montant_converti),
          `renderProDetail('${escapeHtml(numProf)}', 'converti')`,
          detailMode === "converti",
          "Montant crédité par conversion en gonettes numériques."
        )}

        ${clickableStatCard(
          "Reconverti",
          euro(filteredStats.montant_reconverti),
          `renderProDetail('${escapeHtml(numProf)}', 'reconverti')`,
          detailMode === "reconverti",
          "Montant sorti du circuit via une reconversion."
        )}

        ${staticStatCard(
          "Taux de réutilisation",
          percent(filteredStats.taux_reutilisation),
          false,
          "Total émis hors reconversion / (total reçu + total converti)."
        )}
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

function renderProCharts() {
  const chartsSection = document.getElementById("proChartsSection");
  if (!chartsSection || !appState.detailData || !appState.currentPro) return;

  const numProf = appState.currentPro;
  const tx = appState.detailData.transactions || [];
  const activity = buildDailyActivitySeries(tx, numProf);
  const balance = buildBalanceData(tx, numProf);

  chartsSection.innerHTML = `
    <div class="card">
      <h3>Activité dans le temps</h3>
      <canvas id="activityChart" height="110"></canvas>
    </div>

    <div class="card">
      <h3>Balance reçu / émis hors reconversion</h3>
      <canvas id="balanceChart" height="90"></canvas>
    </div>
  `;

  destroyProCharts();

  const activityCtx = document.getElementById("activityChart");
  const balanceCtx = document.getElementById("balanceChart");

  if (!activityCtx || !balanceCtx) return;

  appState.charts.activity = new Chart(activityCtx, {
    type: "bar",
    data: {
      labels: activity.labels,
      datasets: [
        {
          type: "bar",
          label: "Reçu",
          data: activity.recu
        },
        {
          type: "bar",
          label: "Émis",
          data: activity.emis
        },
        {
          type: "line",
          label: "Conversions",
          data: activity.conversion,
          tension: 0.25
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
        }
      },
      scales: {
        x: {
          ticks: {
            maxRotation: 45,
            minRotation: 0
          }
        },
        y: {
          beginAtZero: true
        }
      }
    }
  });

  appState.charts.balance = new Chart(balanceCtx, {
    type: "bar",
    data: {
      labels: ["Balance"],
      datasets: [
        {
          label: "Reçu",
          data: [balance.recu],
          stack: "balance"
        },
        {
          label: "Émis",
          data: [balance.emis],
          stack: "balance"
        }
      ]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          position: "top"
        },
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
          beginAtZero: true,
          stacked: true
        },
        y: {
          stacked: true
        }
      }
    }
  });
}

function drawProTabContent() {
  const dataSection = document.getElementById("proDataSection");
  const chartsSection = document.getElementById("proChartsSection");

  if (!dataSection || !chartsSection) return;

  if (appState.proTab === "graphs") {
    dataSection.classList.add("hidden");
    chartsSection.classList.remove("hidden");
    renderProCharts();
  } else {
    chartsSection.classList.add("hidden");
    destroyProCharts();
    dataSection.classList.remove("hidden");
  }

  updateProTabButtons();
}

function updateProTabButtons() {
  const btnData = document.getElementById("proTabData");
  const btnGraphs = document.getElementById("proTabGraphs");

  if (!btnData || !btnGraphs) return;

  btnData.classList.toggle("tab-btn-active", appState.proTab === "data");
  btnGraphs.classList.toggle("tab-btn-active", appState.proTab === "graphs");
}

async function renderProDetail(numProf, detailMode = "all") {
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
    content.innerHTML = `<div class="card">Chargement...</div>`;
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

    <div class="pro-tabs">
      <button id="proTabData" class="tab-btn" onclick="setProTab('data')">Données</button>
      <button id="proTabGraphs" class="tab-btn" onclick="setProTab('graphs')">Graphes</button>
    </div>

    <div id="proDataSection">
      <div id="proOdooEnrichmentSection"></div>
      <div id="proSummarySection"></div>
      <div id="detailSection"></div>
    </div>

    <div id="proChartsSection" class="hidden"></div>
  `;
  drawProOdooEnrichmentSection();
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
    network: "network",
    tickets: "tickets",
    info: "info",
    "pro-detail": "pros"
  };

  const targetValue = map[view] || "stats";

  document.querySelectorAll('input[name="dataView"]').forEach(radio => {
    radio.checked = radio.value === targetValue;
  });
}

function applyTheme(theme) {
  const isDark = theme === "dark";
  document.body.classList.toggle("dark-mode", isDark);

  const btn = document.getElementById("themeToggleBtn");
  if (btn) {
    btn.textContent = isDark ? "☀️ Mode clair" : "🌙 Mode sombre";
  }

  localStorage.setItem("mlcflux_theme", isDark ? "dark" : "light");
}

function initThemeToggle() {
  const savedTheme = localStorage.getItem("mlcflux_theme") || "light";
  applyTheme(savedTheme);

  const btn = document.getElementById("themeToggleBtn");
  if (!btn || btn.dataset.bound === "true") return;

  btn.addEventListener("click", () => {
    const nextTheme = document.body.classList.contains("dark-mode") ? "light" : "dark";
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

    if (view === "stats") {
      renderStatsView();
    } else if (view === "monetary-pilotage") {
      renderMonetaryPilotageView();
    } else if (view === "pros") {
      renderProsView();
    } else if (view === "cartography") {
      renderCartographyView();
    } else if (view === "territories") {
      renderTerritoriesView();
    } else if (view === "sectors") {
      renderSectorsView();
    } else if (view === "network") {
      renderNetworkView();
    } else if (view === "tickets") {
      renderTicketsView();
    } else if (view === "info") {
      renderInfoView();
    }
  });
});

bindNetworkSearchOutsideClick();
initThemeToggle();
initSidebarCollapse();
initPeriodFilter().then(() => {
  renderStatsView();
});

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
