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
    "globalCumulative"
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
      <h3>Nombre de transactions par jour</h3>
      <canvas id="globalDailyCountChart" height="90"></canvas>
    </div>

    <div class="card">
      <h3>Montant moyen par semaine</h3>
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
        label: "Volume cumulé",
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

function toggleCustomPeriodFields(preset) {
  const customFields = document.getElementById("customPeriodFields");
  const activeSummary = document.getElementById("periodActiveSummary");
  const isCustom = preset === "custom";

  if (customFields) {
    customFields.classList.toggle("hidden", !isCustom);
  }

  if (activeSummary) {
    activeSummary.setAttribute("aria-expanded", isCustom ? "true" : "false");
  }
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

  toggleCustomPeriodFields(preset || "custom");
}

function updatePeriodDraftFromPreset(preset) {
  if (preset === "custom") {
    toggleCustomPeriodFields("custom");
    return;
  }

  const { start, end } = getPresetPeriod(preset);
  syncPeriodInputsFromValues(preset, start, end);
}

function markPeriodAsCustom() {
  const presetEl = document.getElementById("periodPreset");
  if (presetEl) {
    presetEl.value = "custom";
  }

  toggleCustomPeriodFields("custom");
}

async function reloadCurrentViewForPeriod() {
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
  } else if (appState.currentView === "pros") {
    await renderProsView(true);
  } else if (appState.currentView === "network") {
    await renderNetworkView();
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
  const applyBtn = document.getElementById("applyPeriodButton");
  const resetBtn = document.getElementById("resetPeriodButton");
  const activeSummary = document.getElementById("periodActiveSummary");

  if (!presetEl || !startEl || !endEl || !applyBtn || !resetBtn || !activeSummary) return;

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

  presetEl.addEventListener("change", (e) => {
    updatePeriodDraftFromPreset(e.target.value);
  });

  activeSummary.addEventListener("click", () => {
    presetEl.value = "custom";
    toggleCustomPeriodFields("custom");
    startEl.focus();
  });

  startEl.addEventListener("change", markPeriodAsCustom);
  endEl.addEventListener("change", markPeriodAsCustom);

  applyBtn.addEventListener("click", async () => {
    await applyAnalysisPeriod();
  });

  resetBtn.addEventListener("click", async () => {
    await resetAnalysisPeriod();
  });

  presetEl.dataset.bound = "true";
}

async function renderStatsView(forceReload = false) {
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
  content.innerHTML = `
    <div class="grid">
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
    appState.prosData = await apiGet(`/api/pros${getPeriodQueryParam()}`);
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
      <h3>Nombre de transactions par jour</h3>
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
      <div id="proSummarySection"></div>
      <div id="detailSection"></div>
    </div>

    <div id="proChartsSection" class="hidden"></div>
  `;
  drawProSummarySection();
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
    } else if (view === "pros") {
      renderProsView();
    } else if (view === "network") {
      renderNetworkView();
    }
  });
});

bindNetworkSearchOutsideClick();
initThemeToggle();
initPeriodFilter().then(() => {
  renderStatsView();
});

window.renderProDetail = renderProDetail;
window.renderProsView = renderProsView;
window.toggleProsSort = toggleProsSort;
window.changeDetailTransactionPage = changeDetailTransactionPage;

window.renderUserDetail = renderUserDetail;
window.setProTab = setProTab;
window.selectNetworkSearchResult = selectNetworkSearchResult;