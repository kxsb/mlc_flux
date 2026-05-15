import { apiGet, apiPost } from "./utils/api.js";
import { euro, escapeHtml, normalizeText, formatFrDate } from "./utils/formatters.js";
import {
  parseFrDate,
  uniqueSortedDates,
  getPeriodBounds,
  getFilteredTransactionsByPeriod
} from "./utils/dates.js";
import {
  isPro,
  isUser,
  isConversion,
  extractActorCode
} from "./utils/actors.js";

const content = document.getElementById("content");
const pageTitle = document.getElementById("pageTitle");
const reloadButton = document.getElementById("reloadButton");

const appState = {
  currentView: "stats",
  selectedYear: null,
  availableYears: [],
  statsCache: {},

  prosSearch: "",
  prosSearchDebounce: null,
  prosSortBy: "Total Reçu",
  prosSortDir: "desc",
  prosData: [],


  detailSortBy: "Date",
  detailSortDir: "desc",
  detailMode: "all",
  detailData: null,
  currentPro: null,
  proTab: "data",

  periodFilterEnabled: false,
  periodPanelOpen: false,
  periodMinIndex: 0,
  periodMaxIndex: 0,

  charts: {
    activity: null,
    balance: null,
    globalDailyCount: null,
    globalWeeklyAvg: null,
    globalHourly: null,
    globalWeekday: null,
    globalCumulative: null
  },

  network: {
    minEdgeWeight: 500,
    searchTerm: "",
    cy: null,
    selectedNodeId: null,
    hoveredNodeId: null,
    rawData: null,
    enrichedData: null
  }
};

async function renderNetworkView() {
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

  const data = await apiGet(`/api/network${getYearQueryParam()}`);
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

function setTitle(title) {
  pageTitle.innerHTML = `<h1>${title}</h1>`;
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
      const ad = parseFrDate(av);
      const bd = parseFrDate(bv);
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


function renderActorLink(value) {
  const text = String(value || "").trim();
  if (!text) return "";

  const actorCode = extractActorCode(text);

  if (actorCode && isPro(actorCode)) {
    return `<button class="linkish" onclick="renderProDetail('${escapeHtml(actorCode)}')">${escapeHtml(text)}</button>`;
  }

  if (actorCode && isUser(actorCode)) {
    return `<button class="linkish" onclick="renderUserDetail('${escapeHtml(actorCode)}')">${escapeHtml(text)}</button>`;
  }

  return escapeHtml(text);
}


function computeStatsFromTransactions(allTx, numProf) {
  const tx = getFilteredTransactionsByPeriod(allTx, {
    minIndex: appState.periodMinIndex,
    maxIndex: appState.periodMaxIndex
  });

  const received = tx.filter(row => {
    const toLabel = String(row["Vers"] || "");
    const fromLabel = String(row["Réalisé par"] || "");
    return toLabel.includes(numProf) && !isConversion(fromLabel);
  });

  const particuliersPayeurs = tx.filter(row => {
    const toLabel = String(row["Vers"] || "");
    const fromLabel = String(row["Réalisé par"] || "");
    return (
      toLabel.includes(numProf) &&
      isUser(fromLabel) &&
      !isConversion(fromLabel)
    );
  });

  const professionnelsPayeurs = tx.filter(row => {
    const toLabel = String(row["Vers"] || "");
    const fromLabel = String(row["Réalisé par"] || "");
    return (
      toLabel.includes(numProf) &&
      isPro(fromLabel) &&
      !isConversion(fromLabel)
    );
  });

  const emisVersPro = tx.filter(row => {
    const fromLabel = String(row["Réalisé par"] || "");
    const toLabel = String(row["Vers"] || "");
    return fromLabel.includes(numProf) && isPro(toLabel);
  });

  const emisVersParticuliers = tx.filter(row => {
    const fromLabel = String(row["Réalisé par"] || "");
    const toLabel = String(row["Vers"] || "");
    return fromLabel.includes(numProf) && isUser(toLabel);
  });

  const reconverti = tx.filter(row => {
    const fromLabel = String(row["Réalisé par"] || "");
    const toLabel = String(row["Vers"] || "");
    return fromLabel.includes(numProf) && isConversion(toLabel);
  });

  const converti = tx.filter(row => {
    const fromLabel = String(row["Réalisé par"] || "");
    const toLabel = String(row["Vers"] || "");
    return toLabel.includes(numProf) && isConversion(fromLabel);
  });

  const sumMontant = rows =>
    rows.reduce((sum, row) => sum + Number(row["Montant"] || 0), 0);

  const bounds = getPeriodBounds(tx);

  const montantEmisVersPro = sumMontant(emisVersPro);
  const montantEmisVersParticuliers = sumMontant(emisVersParticuliers);

  return {
    tx,
    periode_debut: bounds.minDate || "-",
    periode_fin: bounds.maxDate || "-",
    nb_transactions_recues: received.length,
    somme_transactions_recues: sumMontant(received),
    nb_particuliers: new Set(
      particuliersPayeurs.map(row => String(row["Réalisé par"] || ""))
    ).size,
    nb_professionnels: new Set(
      professionnelsPayeurs.map(row => String(row["Réalisé par"] || ""))
    ).size,
    montant_emis_vers_pro: montantEmisVersPro,
    montant_emis_vers_particuliers: montantEmisVersParticuliers,
    montant_reconverti: sumMontant(reconverti),
    montant_converti: sumMontant(converti),
    total_montant_emis_sans_reconversion:
      montantEmisVersPro + montantEmisVersParticuliers
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
          <th>${detailSortableHeader("Montant", "Montant")}</th>
        </tr>
      </thead>
      <tbody>
        ${body || `<tr><td colspan="4">Aucune ligne</td></tr>`}
      </tbody>
    </table>
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
          <th>${detailSortableHeader("Nb opérations", "Count")}</th>
          <th>${detailSortableHeader("Montant total", "Total")}</th>
        </tr>
      </thead>
      <tbody>
        ${body || `<tr><td colspan="3">Aucune ligne</td></tr>`}
      </tbody>
    </table>
  `;
}

function buildDetailSection(numProf, allTx, mode) {
  const filteredTx = getFilteredTransactionsByPeriod(allTx, {
    minIndex: appState.periodMinIndex,
    maxIndex: appState.periodMaxIndex
  });
  
  let title = "Transactions";
  let html = "";

  if (mode === "recues") {
    const rows = filteredTx.filter(row =>
      String(row["Vers"] || "").includes(numProf) &&
      !isConversion(row["Réalisé par"])
    );
    title = `Transactions reçues (${rows.length})`;
    html = transactionTable(rows);
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

  if (mode === "reconverti") {
    const rows = filteredTx.filter(row =>
      String(row["Réalisé par"] || "").includes(numProf) &&
      isConversion(row["Vers"])
    );
    title = "Opérations de reconversion";
    html = transactionTable(rows);
  }

  if (mode === "converti") {
    const rows = filteredTx.filter(row =>
      String(row["Vers"] || "").includes(numProf) &&
      isConversion(row["Réalisé par"])
    );
    title = "Opérations de conversion reçues";
    html = transactionTable(rows);
  }

  if (mode === "all") {
    title = `Toutes les transactions (${filteredTx.length})`;
    html = transactionTable(filteredTx);
  }

  return `
    <div class="card">
      <div class="topbar">
        <h3 style="margin:0;">${title}</h3>
        <button class="secondary-btn" onclick="renderProDetail('${escapeHtml(numProf)}', 'all')">Tout voir</button>
      </div>
      ${html}
    </div>
  `;
}
  
function getYearQueryParam() {
  if (!appState.selectedYear) return "";
  return `?year=${encodeURIComponent(appState.selectedYear)}`;
}

async function initYearFilter() {
  const select = document.getElementById("yearFilterSelect");
  if (!select) return;

  try {
    const years = await apiGet("/api/years");
    appState.availableYears = Array.isArray(years) ? years : [];

    select.innerHTML = appState.availableYears.map(year => `
      <option value="${year}">${year}</option>
    `).join("");

    if (!appState.selectedYear && appState.availableYears.length > 0) {
      appState.selectedYear = appState.availableYears[appState.availableYears.length - 1];
    }

    select.value = appState.selectedYear;

  } catch (err) {
    console.error("Impossible de charger les années :", err);
  }

  if (select.dataset.bound === "true") return;

  select.addEventListener("change", async (e) => {
    appState.selectedYear = e.target.value;

    appState.statsCache = {};
    appState.prosData = [];
    appState.detailData = null;
    appState.currentPro = null;

    if (appState.currentView === "stats") {
      await renderStatsView(true);
    } else if (appState.currentView === "pros") {
      await renderProsView(true);
    } else if (appState.currentView === "network") {
      await renderNetworkView();
    }
  });

  select.dataset.bound = "true";
}

async function renderStatsView(forceReload = false) {
  appState.currentView = "stats";
  syncSidebarView("stats");
  setTitle("Statistiques globales");

  const cacheKey = String(appState.selectedYear || "default");

  if (!forceReload && appState.statsCache[cacheKey]) {
    const cached = appState.statsCache[cacheKey];
    renderStatsCardsAndCharts(cached.stats, cached.charts);
    return;
  }

  content.innerHTML = `<div class="card">Chargement...</div>`;

  const [stats, charts] = await Promise.all([
    apiGet(`/api/stats${getYearQueryParam()}`),
    apiGet(`/api/stats_charts${getYearQueryParam()}`)
  ]);

  appState.statsCache[cacheKey] = { stats, charts };
  renderStatsCardsAndCharts(stats, charts);
}

function renderStatsCardsAndCharts(stats, charts) {
  content.innerHTML = `
    <div class="grid">
      <div class="card">
        <div class="stat-label">Période</div>
        <div class="stat-value" style="font-size:18px;">${stats.periode || "-"}</div>
      </div>
      <div class="card">
        <div class="stat-label">Utilisateurs</div>
        <div class="stat-value">${stats.nb_utilisateurs ?? 0}</div>
      </div>
      <div class="card">
        <div class="stat-label">Moyenne P→P</div>
        <div class="stat-value">${euro(stats.moyenne_transactions_PP)}</div>
      </div>
      <div class="card">
        <div class="stat-label">Moyenne U→P</div>
        <div class="stat-value">${euro(stats.moyenne_paiement_UP)}</div>
      </div>
      <div class="card">
        <div class="stat-label">Moyenne U→U</div>
        <div class="stat-value">${euro(stats.moyenne_transactions_UU)}</div>
      </div>
    </div>

    <div id="globalStatsCharts"></div>
  `;

  renderGlobalStatsChartsFromSeries(charts);
}

async function renderProsView(forceReload = false) {
  appState.currentView = "pros";
  syncSidebarView("pros");
  setTitle("Activité des professionnels");

  if (forceReload || appState.prosData.length === 0) {
    content.innerHTML = `<div class="card">Chargement...</div>`;
    const data = await apiGet(`/api/pros${getYearQueryParam()}`);
    appState.prosData = Array.isArray(data) ? data : [];
  }

  drawProsTable();
}

function renderGlobalStatsChartsFromSeries(charts) {
  const chartsHost = document.getElementById("globalStatsCharts");
  if (!chartsHost) return;

  destroyGlobalStatsCharts();

  chartsHost.innerHTML = `
    <div class="card">
      <h3>Nombre de transactions par jour</h3>
      <canvas id="globalDailyCountChart" height="90"></canvas>
    </div>

    <div class="card">
      <h3>Montant moyen hebdomadaire</h3>
      <canvas id="globalWeeklyAvgChart" height="90"></canvas>
    </div>

    <div class="card">
      <h3>Transactions par heure</h3>
      <canvas id="globalHourlyChart" height="90"></canvas>
    </div>

    <div class="card">
      <h3>Transactions par jour de semaine</h3>
      <canvas id="globalWeekdayChart" height="90"></canvas>
    </div>

    <div class="card">
      <h3>Volume cumulé des transactions</h3>
      <canvas id="globalCumulativeChart" height="90"></canvas>
    </div>
  `;

  appState.charts.globalDailyCount = new Chart(document.getElementById("globalDailyCountChart"), {
    type: "line",
    data: {
      labels: charts.daily.labels,
      datasets: [{
        label: "Transactions",
        data: charts.daily.values,
        fill: true,
        tension: 0.25
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { position: "top" } },
      scales: {
        x: { ticks: { maxRotation: 45, minRotation: 0 } },
        y: { beginAtZero: true }
      }
    }
  });

  appState.charts.globalWeeklyAvg = new Chart(document.getElementById("globalWeeklyAvgChart"), {
    type: "line",
    data: {
      labels: charts.weekly_avg.labels,
      datasets: [{
        label: "Montant moyen",
        data: charts.weekly_avg.values,
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
        x: { ticks: { maxRotation: 45, minRotation: 0 } },
        y: { beginAtZero: true }
      }
    }
  });

  appState.charts.globalHourly = new Chart(document.getElementById("globalHourlyChart"), {
    type: "bar",
    data: {
      labels: charts.hourly.labels,
      datasets: [{
        label: "Transactions",
        data: charts.hourly.values
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { position: "top" } },
      scales: {
        y: { beginAtZero: true }
      }
    }
  });

  appState.charts.globalWeekday = new Chart(document.getElementById("globalWeekdayChart"), {
    type: "bar",
    data: {
      labels: charts.weekday.labels,
      datasets: [{
        label: "Transactions",
        data: charts.weekday.values
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { position: "top" } },
      scales: {
        y: { beginAtZero: true }
      }
    }
  });

  appState.charts.globalCumulative = new Chart(document.getElementById("globalCumulativeChart"), {
    type: "line",
    data: {
      labels: charts.cumulative.labels,
      datasets: [{
        label: "Volume cumulé",
        data: charts.cumulative.values,
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
        x: { ticks: { maxRotation: 45, minRotation: 0 } },
        y: { beginAtZero: true }
      }
    }
  });
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

function clickableStatCard(label, value, action, isActive = false) {
  return `
    <button class="card stat-card-btn ${isActive ? "stat-card-btn-active" : ""}" onclick="${action}">
      <div class="stat-label">${label}</div>
      <div class="stat-value">${value}</div>
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
    reconverti: "Opérations de reconversion",
    converti: "Opérations de conversion reçues"
  };

  return labels[mode] || mode;
}

function togglePeriodPanel() {
  appState.periodPanelOpen = !appState.periodPanelOpen;

  const panel = document.getElementById("periodPanel");
  if (!panel) return;

  panel.classList.toggle("hidden", !appState.periodPanelOpen);

  if (appState.periodPanelOpen) {
    updatePeriodPanelOnly();
  }
}

function resetPeriodFilter() {
  if (!appState.detailData?.transactions?.length) return;
  const dates = uniqueSortedDates(appState.detailData.transactions);
  appState.periodMinIndex = 0;
  appState.periodMaxIndex = Math.max(0, dates.length - 1);
  appState.periodFilterEnabled = false;
  drawProSummarySection();
  updatePeriodPanelOnly();
  drawDetailSection();
  if (appState.proTab === "graphs") renderProCharts();
}

function updatePeriodMin(value) {
  const v = Number(value);
  appState.periodMinIndex = Math.min(v, appState.periodMaxIndex);
  appState.periodFilterEnabled = true;
  drawProSummarySection();
  drawDetailSection();
  if (appState.proTab === "graphs") renderProCharts();
}

function updatePeriodMax(value) {
  const v = Number(value);
  appState.periodMaxIndex = Math.max(v, appState.periodMinIndex);
  appState.periodFilterEnabled = true;
  drawProSummarySection();
  drawDetailSection();
  if (appState.proTab === "graphs") renderProCharts();
}

function updatePeriodPanelOnly() {
  const el = document.getElementById("periodPanel");
  if (!el || !appState.detailData?.transactions?.length) return;

  const dates = uniqueSortedDates(appState.detailData.transactions);
  const minDate = dates[appState.periodMinIndex] || dates[0];
  const maxDate = dates[appState.periodMaxIndex] || dates[dates.length - 1];

  el.innerHTML = `
    <div class="period-panel-inner">
      <div class="period-labels">
        <span><strong>Début :</strong> ${minDate}</span>
        <span><strong>Fin :</strong> ${maxDate}</span>
      </div>

      <div class="range-wrap">
        <input type="range" min="0" max="${dates.length - 1}" value="${appState.periodMinIndex}"
          oninput="updatePeriodMin(this.value)">
        <input type="range" min="0" max="${dates.length - 1}" value="${appState.periodMaxIndex}"
          oninput="updatePeriodMax(this.value)">
      </div>

      <div class="period-actions">
        <button class="secondary-btn" onclick="resetPeriodFilter()">Réinitialiser</button>
      </div>
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
  

  summaryContainer.innerHTML = `
    <div class="grid">
      ${clickableStatCard(
        "Transactions reçues",
        filteredStats.nb_transactions_recues ?? 0,
        `renderProDetail('${escapeHtml(numProf)}', 'recues')`,
        detailMode === "recues"
      )}

      ${clickableStatCard(
        "Somme reçue",
        euro(filteredStats.somme_transactions_recues),
        `renderProDetail('${escapeHtml(numProf)}', 'somme_recue')`,
        detailMode === "somme_recue"
      )}

      ${clickableStatCard(
        "Émis vers pro",
        euro(filteredStats.montant_emis_vers_pro),
        `renderProDetail('${escapeHtml(numProf)}', 'emis_pro')`,
        detailMode === "emis_pro"
      )}

      ${clickableStatCard(
        "Émis vers particuliers",
        euro(filteredStats.montant_emis_vers_particuliers),
        `renderProDetail('${escapeHtml(numProf)}', 'emis_particuliers')`,
        detailMode === "emis_particuliers"
      )}

      ${clickableStatCard(
        "Reconverti",
        euro(filteredStats.montant_reconverti),
        `renderProDetail('${escapeHtml(numProf)}', 'reconverti')`,
        detailMode === "reconverti"
      )}

      ${clickableStatCard(
        "Converti",
        euro(filteredStats.montant_converti),
        `renderProDetail('${escapeHtml(numProf)}', 'converti')`,
        detailMode === "converti"
      )}
    </div>

    <div class="grid">
      ${clickableStatCard(
        "Particuliers payeurs",
        filteredStats.nb_particuliers ?? 0,
        `renderProDetail('${escapeHtml(numProf)}', 'payeurs_particuliers')`,
        detailMode === "payeurs_particuliers"
      )}

      ${clickableStatCard(
        "Professionnels payeurs",
        filteredStats.nb_professionnels ?? 0,
        `renderProDetail('${escapeHtml(numProf)}', 'payeurs_professionnels')`,
        detailMode === "payeurs_professionnels"
      )}

      ${infoTagCard(
        "Total émis hors reconversion",
        euro(filteredStats.total_montant_emis_sans_reconversion),
        detailMode === "emis_pro" || detailMode === "emis_particuliers"
      )}

      <button class="card stat-card-btn ${appState.periodPanelOpen ? "stat-card-btn-active" : ""}" onclick="togglePeriodPanel()">
        <div class="stat-label">Période</div>
        <div class="mini-stat-value">
          ${escapeHtml(filteredStats.periode_debut)} → ${escapeHtml(filteredStats.periode_fin)}
        </div>
      </button>

      ${infoTagCard(
        "Filtre actif",
        escapeHtml(getDetailModeLabel(detailMode)),
        true
      )}
    </div>
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
  const filteredTx = getFilteredTransactionsByPeriod(allTx, {
    minIndex: appState.periodMinIndex,
    maxIndex: appState.periodMaxIndex
  }).filter(row =>
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

function buildDailyActivitySeries(transactions, numProf) {
  const filtered = getFilteredTransactionsByPeriod(transactions, {
    minIndex: appState.periodMinIndex,
    maxIndex: appState.periodMaxIndex
  });
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
  const filtered = getFilteredTransactionsByPeriod(transactions, {
  minIndex: appState.periodMinIndex,
  maxIndex: appState.periodMaxIndex
});

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

  if (!activity.labels.length) {
    chartsSection.innerHTML = `
      <div class="card">
        <h3>Graphes</h3>
        <p>Aucune donnée exploitable pour cette période.</p>
      </div>
    `;
    return;
  }  

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
  const isSameProfessional = appState.currentPro === numProf;
  const needReload = !isSameProfessional || !appState.detailData;

  appState.currentView = "pro-detail";
  syncSidebarView("pro-detail");
  appState.currentPro = numProf;

  // pour revenir automatiquement sur Données à chaque nouveau pro
  appState.proTab = "data";
  appState.detailMode = detailMode;

  setTitle(`Fiche professionnel : ${numProf}`);

  if (needReload) {
    content.innerHTML = `<div class="card">Chargement...</div>`;
    const data = await apiGet(`/api/pro/${encodeURIComponent(numProf)}${getYearQueryParam()}`);
    appState.detailData = data;

    const dates = uniqueSortedDates(data.transactions || []);
    appState.periodMinIndex = 0;
    appState.periodMaxIndex = Math.max(0, dates.length - 1);
    appState.periodFilterEnabled = false;
    appState.periodPanelOpen = false;
  }

  const data = appState.detailData;
  const tx = data.transactions || [];

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

    <div class="card">
      <h2>${escapeHtml(data.fullname || numProf)}</h2>
      <p><strong>Professionnel :</strong> ${escapeHtml(numProf)}</p>
    </div>

    <div class="pro-tabs">
      <button id="proTabData" class="tab-btn" onclick="setProTab('data')">Données</button>
      <button id="proTabGraphs" class="tab-btn" onclick="setProTab('graphs')">Graphes</button>
    </div>

    <div id="proDataSection">
      <div id="proSummarySection"></div>
      <div id="periodPanel" class="${appState.periodPanelOpen ? "" : "hidden"}"></div>
      <div id="detailSection"></div>
    </div>

    <div id="proChartsSection" class="hidden"></div>
  `;
  drawProSummarySection();
  updatePeriodPanelOnly();
  drawDetailSection();
  drawProTabContent();
}

function syncSidebarView(view) {
  const map = {
    stats: "stats",
    pros: "pros",
    network: "network",
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

reloadButton.addEventListener("click", async () => {
  try {
    reloadButton.disabled = true;
    reloadButton.textContent = "Rechargement...";
    const result = await apiPost("/api/reload");
    alert(result.message || "Données rechargées");

    appState.prosData = [];
    appState.detailData = null;
    appState.currentPro = null;

    if (appState.currentView === "pros") {
      await renderProsView(true);
    } else if (appState.currentView === "network") {
      await renderNetworkView();
    } else {
      await renderStatsView(true);
    }

  } catch (err) {
    alert(`Erreur : ${err.message}`);
  } finally {
    reloadButton.disabled = false;
    reloadButton.textContent = "Recharger les données";
  }
});

document.querySelectorAll('input[name="dataView"]').forEach(input => {
  input.addEventListener("change", (e) => {
    const view = e.target.value;

    if (view === "stats") {
      renderStatsView();
    } else if (view === "pros") {
      renderProsView();
    } else if (view === "network") {
      renderNetworkView();
    }
  });
});

bindNetworkSearchOutsideClick();
initThemeToggle();
initYearFilter().then(() => {
  renderStatsView();
});

window.renderProDetail = renderProDetail;
window.renderProsView = renderProsView;
window.toggleProsSort = toggleProsSort;

window.togglePeriodPanel = togglePeriodPanel;
window.updatePeriodMin = updatePeriodMin;
window.updatePeriodMax = updatePeriodMax;
window.resetPeriodFilter = resetPeriodFilter;
window.renderUserDetail = renderUserDetail;
window.setProTab = setProTab;
window.selectNetworkSearchResult = selectNetworkSearchResult;