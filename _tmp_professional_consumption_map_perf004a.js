/* CARTO_UP011G_DEDUP_FOCUS_AND_PARTICLES */
/* CARTO_UP011E_FIX_SEARCH_REF_HIGHLIGHT */
/* CARTO_UP011D_UNIFY_SEARCH_AND_CLICK_ROUTE_HIGHLIGHT */
/* CARTO_UP011C_EXTRA_ROUTES_HIGHLIGHT_ALPHA */
/* CARTO_UP011B_PP_KEEP_POINTS_FIX_PARTICLE_GATE */
/* CARTO_UP010Q_HOVER_CLICK_PRO_IDENTITY_FROM_DATA */
/* CARTO_UP010P_EXTRA_FOCUS_MATCH_KEYS */
/* CARTO_UP010O_EXTRA_FLOWS_REQUIRE_PRO_FOCUS */
/* CARTO_UP010N3_FIX_MISSING_ENABLED_FAMILIES */
/* CARTO_UP010N2_PATCH_ROUTEPATHDATA_PP */
/* CARTO_UP010N_FIX_PP_ROUTE_VISIBILITY */
/* CARTO_UP010M_SINGLE_PRO_REF_LABELS */
/* CARTO_UP010L_UNIFIED_PRO_LABELS */
/* CARTO_UP010K_SEARCH_FOCUS_STARTS_PARTICLES */
/* CARTO_UP010J_SEARCH_ROUTES_TRIGGER_PARTICLES */
/* CARTO_UP010I_SEARCH_USES_LOCKED_HIGHLIGHT */
/* CARTO_UP010H_SEARCH_BAR_PRO_STATS */
/* CARTO_UP010G_FIX_SEARCH_AMOUNT_FORMATTER */
/* CARTO_UP010F_SEARCH_ANCHOR_ROUTE */
/* CARTO_UP010E3_ALLOW_SEARCH_POINT_NO_ROUTES_ROBUST */
/* CARTO_UP010D_RENDER_SEARCH_POINT_WITHOUT_ROUTES */
/* CARTO_UP010C_ROBUST_ROUTE_PRO_MATCH */
/* CARTO_UP010B2_FIX_PRO_SEARCH_BEHAVIOR_ROBUST */
/* CARTO_UP010A_PRO_SEARCH_FILTER */
/* CARTO_UP009F_ADAPTIVE_LOCKED_ZOOM */
/* CARTO_UP009E_EASE_TO_LOCKED_POINT */
/* CARTO_UP009D2_FIX_HOVER_PP_KEYS_ROBUST */

/* CARTO_UP006E_ROUTE_QUEUE_PLUS_PARTICLES
 * - routage GPS plus rapide (concurrency 4, pauses réduites)
 * - particules légèrement plus visibles, halo réduit
 */

/*
 * MLCFlux — Carte de consommation U→P
 * Extraction MAPJS001 depuis static/js/app.js
 *
 * Objectif :
 * - isoler la grosse cartographie transactionnelle dans un fichier dédié ;
 * - conserver strictement les noms de fonctions existants ;
 * - ne modifier ni les API, ni les comportements, ni les dépendances globales.
 */


/*
 * CARTO_UP002A_SAFE — tooltip professionnel au survol du canvas.
 */
function getProfessionalConsumptionMapDestinationLabel(destination) {
  const ref = String(destination?.professional_ref || "").trim();
  const name = String(
    destination?.professional_name
    || destination?.name
    || destination?.label
    || destination?.display_name
    || ""
  ).trim();

  if (ref && name) return `${ref} · ${name}`;
  return name || ref || "Professionnel";
}

function getProfessionalConsumptionMapDestinationSubtitle(destination) {
  const parts = [];

  const txCount = Number(destination?.tx_count || destination?.final_tx_count || 0);
  const volume = Number(destination?.volume || destination?.final_volume || 0);

  if (txCount || volume) {
    parts.push(`${formatProfessionalSummaryInteger(txCount)} paiement(s) · ${euro(volume)}`);
  }

  const postalCode = String(destination?.postal_code || destination?.zip || "").trim();
  const city = String(destination?.city || destination?.source_city || "").trim();

  if (postalCode || city) {
    parts.push([postalCode, city].filter(Boolean).join(" · "));
  }

  return parts.join(" — ");
}

function ensureProfessionalConsumptionMapTooltip() {
  let tooltip = document.getElementById("professionalConsumptionMapHoverTooltip");

  if (!tooltip) {
    tooltip = document.createElement("div");
    tooltip.id = "professionalConsumptionMapHoverTooltip";
    tooltip.className = "professional-consumption-map-hover-tooltip hidden";
    document.body.appendChild(tooltip);
  }

  return tooltip;
}

function hideProfessionalConsumptionMapTooltip() {
  const tooltip = document.getElementById("professionalConsumptionMapHoverTooltip");
  if (tooltip) tooltip.classList.add("hidden");
}

function showProfessionalConsumptionMapTooltip(destination, clientX, clientY) {
  const tooltip = ensureProfessionalConsumptionMapTooltip();

  tooltip.innerHTML = `
    <div class="professional-consumption-map-hover-title">
      ${escapeHtml(getProfessionalConsumptionMapDestinationLabel(destination))}
    </div>
    <div class="professional-consumption-map-hover-subtitle">
      ${escapeHtml(getProfessionalConsumptionMapDestinationSubtitle(destination))}
    </div>
  `;

  tooltip.style.left = `${Math.round(clientX + 14)}px`;
  tooltip.style.top = `${Math.round(clientY + 14)}px`;
  tooltip.classList.remove("hidden");
}

function findProfessionalConsumptionMapHoveredDestination(canvas, event) {
  const rawPayload = appState.professionalConsumptionMapRenderPayload
    || appState.professionalConsumptionMap
    || null;

  const payload = buildProfessionalConsumptionMapVisualPayload(rawPayload);
  if (!payload) return null;

  const frame = canvas.parentElement;
  const rect = frame?.getBoundingClientRect?.() || canvas.getBoundingClientRect();
  const canvasRect = canvas.getBoundingClientRect();

  const width = Math.max(720, Math.round(rect?.width || 1080));
  const height = Math.max(520, Math.round(rect?.height || 680));
  const dpr = window.devicePixelRatio || 1;

  const surface = getProfessionalConsumptionMapRenderSurface(
    "main",
    payload,
    width,
    height,
    dpr
  );

  if (!surface?.projection) return null;

  const pointer = {
    x: event.clientX - canvasRect.left,
    y: event.clientY - canvasRect.top
  };

  let best = null;
  let bestDistance = Infinity;

  (payload.destinations || []).forEach((destination) => {
    const point = getProfessionalConsumptionMapProjectedDestinationPoint(
      destination,
      surface
    );

    if (!point) return;

    const dx = point.x - pointer.x;
    const dy = point.y - pointer.y;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const volume = Number(destination?.volume || destination?.final_volume || 0);
    const radius = Math.max(9, Math.min(24, 8 + Math.sqrt(Math.max(volume, 0)) / 42));

    if (distance <= radius && distance < bestDistance) {
      best = destination;
      bestDistance = distance;
    }
  });

  return best;
}

function bindProfessionalConsumptionMapCanvasHover() {
  const canvas = document.getElementById("professionalConsumptionMapCanvas");

  if (!canvas || canvas.dataset.hoverBound === "true") {
    return;
  }

  canvas.addEventListener("mousemove", (event) => {
    const destination = findProfessionalConsumptionMapHoveredDestination(canvas, event);

    if (destination) {
      canvas.classList.add("professional-consumption-map-canvas-hovering");
      showProfessionalConsumptionMapTooltip(destination, event.clientX, event.clientY);
    } else {
      canvas.classList.remove("professional-consumption-map-canvas-hovering");
      hideProfessionalConsumptionMapTooltip();
    }
  });

  canvas.addEventListener("mouseleave", () => {
    canvas.classList.remove("professional-consumption-map-canvas-hovering");
    hideProfessionalConsumptionMapTooltip();
  });

  canvas.dataset.hoverBound = "true";
}



/*
 * CARTO_UP003B_MAPLIBRE_DARK
 * Carte U→P navigable : MapLibre + deck.gl.
 * Le canvas actuel reste un fallback et le mode dynamique conserve le canvas.
 */

/*
 * CARTO_UP009A_PRESERVE_MAP_VIEW_FOCUS
 * Préserve le viewport et le focus de la carte lors des rerenders provoqués
 * par les filtres ou les changements de période.
 */
function captureProfessionalConsumptionMapLibreInteractiveState() {
  const map = appState.professionalConsumptionMapLibreMap || null;

  const state = {
    viewState: null,
    // CARTO_UP009C_CLEAR_STALE_HOVER_FOCUS
    // On ne conserve pas le hover temporaire : il peut masquer toute la carte après rerender.
    hoverHighlight: null,
    lockedHighlight: appState.professionalConsumptionMapLibreLockedHighlight || null,
    selectedSourcePostalCode: appState.professionalConsumptionMapSelectedSourcePostalCode || "",
    overviewLimit: appState.professionalConsumptionMapOverviewLimit,
    flowFamilies: appState.professionalConsumptionMapFlowFamilies
      ? { ...appState.professionalConsumptionMapFlowFamilies }
      : null
  };

  if (map && typeof map.getCenter === "function") {
    const center = map.getCenter();

    state.viewState = {
      center: [center.lng, center.lat],
      zoom: map.getZoom(),
      bearing: typeof map.getBearing === "function" ? map.getBearing() : 0,
      pitch: typeof map.getPitch === "function" ? map.getPitch() : 0
    };
  }

  return state;
}


/*
 * CARTO_UP009C_CLEAR_STALE_HOVER_FOCUS
 * Un hover temporaire ne doit jamais survivre à un rerender.
 * Un focus verrouillé par clic ne survit que si l'objet existe encore.
 */
function isProfessionalConsumptionMapHighlightRepresentedInData(highlight, data) {
  /* CARTO_UP009D2_FIX_HOVER_PP_KEYS_ROBUST */
  if (!highlight?.type || !highlight?.id || !data) {
    return false;
  }

  const id = String(highlight.id || "");

  if (highlight.type === "source") {
    return (data.sources || []).some((source) => (
      getProfessionalConsumptionMapRenderedSourceFocusId(source) === id
    ));
  }

  if (highlight.type === "professional") {
    return (data.destinations || []).some((destination) => (
      getProfessionalConsumptionMapRenderedDestinationFocusId(destination) === id
    ));
  }

  if (highlight.type === "route") {
    return (data.routes || []).some((route) => (
      getProfessionalConsumptionMapRenderedRouteFocusId(route) === id
    ));
  }

  return false;
}

function cleanupProfessionalConsumptionMapStaleFocus(data) {
  // CARTO_UP009D2_FIX_HOVER_PP_KEYS_ROBUST
  // Ne pas vider le hover actif ici : cela casse le filtre au survol.
  const locked = appState.professionalConsumptionMapLibreLockedHighlight;

  if (
    locked
    && !isProfessionalConsumptionMapHighlightRepresentedInData(locked, data)
  ) {
    appState.professionalConsumptionMapLibreLockedHighlight = null;
  }
}


function restoreProfessionalConsumptionMapLibreInteractiveState(map, state) {
  if (!state) {
    return;
  }

  if (state.flowFamilies) {
    appState.professionalConsumptionMapFlowFamilies = {
      ...state.flowFamilies
    };
  }

  appState.professionalConsumptionMapSelectedSourcePostalCode =
    state.selectedSourcePostalCode || appState.professionalConsumptionMapSelectedSourcePostalCode || "";

  if (state.overviewLimit !== undefined) {
    appState.professionalConsumptionMapOverviewLimit = state.overviewLimit;
  }

  appState.professionalConsumptionMapLibreLockedHighlight =
    state.lockedHighlight || null;

  // CARTO_UP009C_CLEAR_STALE_HOVER_FOCUS — hover temporaire vidé au rerender.
  appState.professionalConsumptionMapLibreHighlight = null;

  if (map && state.viewState && typeof map.jumpTo === "function") {
    map.jumpTo({
      center: state.viewState.center,
      zoom: state.viewState.zoom,
      bearing: state.viewState.bearing || 0,
      pitch: state.viewState.pitch || 0
    });
  }
}

function hasProfessionalConsumptionMapLibrePreservedView(state) {
  return Boolean(
    state
    && state.viewState
    && Array.isArray(state.viewState.center)
    && Number.isFinite(Number(state.viewState.center[0]))
    && Number.isFinite(Number(state.viewState.center[1]))
    && Number.isFinite(Number(state.viewState.zoom))
  );
}


function destroyProfessionalConsumptionMapLibre(options = {}) {
  const preserveInteractiveState = Boolean(options.preserveInteractiveState);
  stopProfessionalConsumptionMapParticleAnimation();
  if (appState.professionalConsumptionMapLibreOverlay) {
    try {
      appState.professionalConsumptionMapLibreMap?.removeControl(
        appState.professionalConsumptionMapLibreOverlay
      );
    } catch (_err) {
      // Overlay déjà détaché.
    }
  }

  if (appState.professionalConsumptionMapLibreMap) {
    try {
      appState.professionalConsumptionMapLibreMap.remove();
    } catch (_err) {
      // Carte déjà détruite.
    }
  }

  appState.professionalConsumptionMapLibreMap = null;
  appState.professionalConsumptionMapLibreOverlay = null;
  appState.professionalConsumptionMapLibreData = null;

  // CARTO_CLUSTER_MAIN_PERF003B_CANVAS_CAMERA_SYNC
  clearProfessionalConsumptionMapParticleCanvas();
  appState.professionalConsumptionMapCanvasParticlesCameraMoving = false;
  if (appState.professionalConsumptionMapCanvasParticlesResumeTimeout) {
    window.clearTimeout(appState.professionalConsumptionMapCanvasParticlesResumeTimeout);
    appState.professionalConsumptionMapCanvasParticlesResumeTimeout = null;
  }
  if (!preserveInteractiveState) {
    appState.professionalConsumptionMapLibreHighlight = null;
    appState.professionalConsumptionMapLibreLockedHighlight = null;
  }

  const container = document.getElementById("professionalConsumptionMapLibre");
  if (container) {
    container.classList.remove("is-ready");
    container.innerHTML = "";
  }
}

function isProfessionalConsumptionMapDarkTheme() {
  /*
   * CARTO_UP007A_THEME_AWARE_BASEMAP
   * Suit le mode d'apparence global MLCFlux.
   */
  return Boolean(
    document.documentElement.classList.contains("dark-mode")
    || document.body.classList.contains("dark-mode")
    || document.documentElement.dataset.theme === "dark"
    || document.body.dataset.theme === "dark"
  );
}

function getProfessionalConsumptionMapLibreStyleUrl() {
  return isProfessionalConsumptionMapDarkTheme()
    ? "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
    : "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
}

function syncProfessionalConsumptionMapLibreThemeClass(container) {
  if (!container) return;

  const isDark = isProfessionalConsumptionMapDarkTheme();

  container.classList.toggle("is-dark-map", isDark);
  container.classList.toggle("is-light-map", !isDark);
}

function bindProfessionalConsumptionMapThemeObserver() {
  if (appState.professionalConsumptionMapThemeObserverBound) {
    return;
  }

  const refresh = () => {
    const container = document.getElementById("professionalConsumptionMapLibre");
    if (!container) return;

    syncProfessionalConsumptionMapLibreThemeClass(container);

    if (
      appState.professionalConsumptionMapLibreMap
      && getProfessionalConsumptionMapViewMode() === "static"
    ) {
      renderProfessionalConsumptionMapLibre();
    }
  };

  const observer = new MutationObserver(refresh);

  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class", "data-theme"]
  });

  observer.observe(document.body, {
    attributes: true,
    attributeFilter: ["class", "data-theme"]
  });

  appState.professionalConsumptionMapThemeObserver = observer;
  appState.professionalConsumptionMapThemeObserverBound = true;
}

function getProfessionalConsumptionMapLibreRouteCoordinates(route) {
  const source = route?.source || {};
  const destination = route?.destination || {};

  const sourceLongitude = Number(source.longitude);
  const sourceLatitude = Number(source.latitude);
  const destinationLongitude = Number(destination.longitude);
  const destinationLatitude = Number(destination.latitude);

  if (
    !Number.isFinite(sourceLongitude)
    || !Number.isFinite(sourceLatitude)
    || !Number.isFinite(destinationLongitude)
    || !Number.isFinite(destinationLatitude)
  ) {
    return null;
  }

  return {
    source: [sourceLongitude, sourceLatitude],
    target: [destinationLongitude, destinationLatitude]
  };
}


/*
 * CARTO_UP008C_FLOW_FAMILY_FRONTEND
 * Filtres visuels des familles de flux cartographiques.
 */

/*
 * CARTO_UP008F_DEDUP_PRO_LABEL_PREFIX
 * Nettoyage frontend de sécurité pour éviter :
 * P0001 - P0001 - Nom du pro
 */
function cleanProfessionalConsumptionMapProfessionalLabel(label, ref = "") {
  let value = String(label || "").trim();
  const professionalRef = String(ref || "").trim()
    || (value.match(/^(P[0-9]{4,})\b/) || [])[1]
    || "";

  if (!value) {
    return professionalRef;
  }

  if (!professionalRef) {
    return value;
  }

  const escapedRef = professionalRef.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  const duplicateDash = new RegExp(
    `^(${escapedRef})\\s*[-–—]\\s*${escapedRef}\\s*[-–—]\\s*`,
    "i"
  );

  while (duplicateDash.test(value)) {
    value = value.replace(duplicateDash, `${professionalRef} - `).trim();
  }

  const duplicateSpace = new RegExp(
    `^(${escapedRef})\\s+${escapedRef}\\s*[-–—]\\s*`,
    "i"
  );

  while (duplicateSpace.test(value)) {
    value = value.replace(duplicateSpace, `${professionalRef} - `).trim();
  }

  return value;
}



/*
 * CARTO_UP010A_PRO_SEARCH_FILTER
 * Recherche rapide d'un professionnel dans la carte.
 */
function normalizeProfessionalConsumptionMapSearchText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function getProfessionalConsumptionMapProfessionalCatalog(payload) {
  return Array.isArray(payload?.professional_search_catalog?.professionals)
    ? payload.professional_search_catalog.professionals
    : [];
}


/*
 * CARTO_UP010L_UNIFIED_PRO_LABELS
 * Source unique de vérité pour les libellés professionnels affichés.
 * Priorité :
 * 1) professional_search_catalog ;
 * 2) label métier déjà présent ;
 * 3) ref Pxxxx seule si aucune meilleure info.
 */
function escapeProfessionalConsumptionMapRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function cleanProfessionalConsumptionMapDisplayText(value) {
  return String(value || "")
    .replace(/\ufeff/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function isProfessionalConsumptionMapTechnicalLabel(value) {
  const text = cleanProfessionalConsumptionMapDisplayText(value);

  if (!text) {
    return true;
  }

  if (/^p_[0-9a-f_-]{8,}$/i.test(text)) {
    return true;
  }

  if (/^u_[0-9a-f_-]{8,}$/i.test(text)) {
    return true;
  }

  if (/^[a-f0-9]{12,}$/i.test(text)) {
    return true;
  }

  return false;
}

function normalizeProfessionalConsumptionMapProfessionalRef(value) {
  const text = cleanProfessionalConsumptionMapDisplayText(value);
  const match = text.match(/\b(P[0-9]{4,})\b/);
  return match ? match[1] : "";
}

function stripProfessionalConsumptionMapDuplicatedRef(label, ref) {
  let text = cleanProfessionalConsumptionMapDisplayText(label);
  const professionalRef = cleanProfessionalConsumptionMapDisplayText(ref);

  if (!text || !professionalRef) {
    return text;
  }

  const escapedRef = escapeProfessionalConsumptionMapRegExp(professionalRef);

  // P0010 - P0010 - Nom -> P0010 - Nom
  text = text.replace(
    new RegExp(`^${escapedRef}\\s*[-–—]\\s*${escapedRef}\\s*[-–—]\\s*`, "i"),
    `${professionalRef} - `
  );

  // P0010 P0010 - Nom -> P0010 - Nom
  text = text.replace(
    new RegExp(`^${escapedRef}\\s+${escapedRef}\\s*[-–—]\\s*`, "i"),
    `${professionalRef} - `
  );

  // P0010 - P0010 -> P0010
  text = text.replace(
    new RegExp(`^${escapedRef}\\s*[-–—]\\s*${escapedRef}$`, "i"),
    professionalRef
  );

  return cleanProfessionalConsumptionMapDisplayText(text);
}


/*
 * CARTO_UP010M_SINGLE_PRO_REF_LABELS
 * Sépare le label complet du nom court.
 *
 * Exemple :
 * - full label : P0017 - Boucherie de la Ferme (La)
 * - short name : Boucherie de la Ferme (La)
 */
function getProfessionalConsumptionMapProfessionalShortName(label, ref) {
  const professionalRef = cleanProfessionalConsumptionMapDisplayText(ref);
  let text = stripProfessionalConsumptionMapDuplicatedRef(label, professionalRef);

  if (!professionalRef || !text) {
    return text;
  }

  const escapedRef = escapeProfessionalConsumptionMapRegExp(professionalRef);

  text = text
    .replace(new RegExp(`^${escapedRef}\\s*[-–—·•]\\s*`, "i"), "")
    .replace(new RegExp(`^${escapedRef}\\s+`, "i"), "")
    .trim();

  return cleanProfessionalConsumptionMapDisplayText(text) || professionalRef;
}

function getProfessionalConsumptionMapProfessionalFullLabel(label, ref) {
  const professionalRef = cleanProfessionalConsumptionMapDisplayText(ref);
  const cleanLabel = stripProfessionalConsumptionMapDuplicatedRef(label, professionalRef);

  if (!professionalRef) {
    return cleanLabel;
  }

  if (!cleanLabel || cleanLabel === professionalRef) {
    return professionalRef;
  }

  if (cleanLabel.startsWith(`${professionalRef} - `)) {
    return cleanLabel;
  }

  const shortName = getProfessionalConsumptionMapProfessionalShortName(cleanLabel, professionalRef);

  return shortName && shortName !== professionalRef
    ? `${professionalRef} - ${shortName}`
    : professionalRef;
}

function normalizeProfessionalConsumptionMapTooltipDuplicateRefs(value) {
  return String(value || "")
    .replace(/\b(P[0-9]{4,})\s*[·•]\s*\1\s*[-–—]\s*/g, "$1 - ")
    .replace(/\b(P[0-9]{4,})\s*[-–—]\s*\1\s*[-–—]\s*/g, "$1 - ")
    .replace(/\b(P[0-9]{4,})\s*[·•]\s*\1\b/g, "$1");
}


function buildProfessionalConsumptionMapProfessionalLabelIndex(payload) {
  const index = new Map();
  const catalog = getProfessionalConsumptionMapProfessionalCatalog(payload);

  catalog.forEach((item) => {
    const ref = normalizeProfessionalConsumptionMapProfessionalRef(
      item?.professional_ref || item?.label || item?.search_label
    );

    if (!ref) {
      return;
    }

    const label = getProfessionalConsumptionMapUnifiedProfessionalLabelFromCandidates(
      ref,
      [
        item?.label,
        item?.search_label,
        item?.name,
        item?.display_label
      ],
      null
    );

    index.set(ref, {
      ...item,
      professional_ref: ref,
      unified_label: label
    });
  });

  return index;
}

function getProfessionalConsumptionMapUnifiedProfessionalLabelFromCandidates(ref, candidates, labelIndex) {
  const professionalRef = normalizeProfessionalConsumptionMapProfessionalRef(ref);

  const safeCandidates = (candidates || [])
    .map(cleanProfessionalConsumptionMapDisplayText)
    .filter(Boolean)
    .map((label) => professionalRef ? stripProfessionalConsumptionMapDuplicatedRef(label, professionalRef) : label)
    .filter((label) => !isProfessionalConsumptionMapTechnicalLabel(label));

  if (labelIndex && professionalRef && labelIndex.has(professionalRef)) {
    const indexed = cleanProfessionalConsumptionMapDisplayText(
      labelIndex.get(professionalRef)?.unified_label
      || labelIndex.get(professionalRef)?.label
      || labelIndex.get(professionalRef)?.search_label
    );

    if (indexed && !isProfessionalConsumptionMapTechnicalLabel(indexed)) {
      return stripProfessionalConsumptionMapDuplicatedRef(indexed, professionalRef);
    }
  }

  const rich = safeCandidates.find((label) => {
    if (!professionalRef) {
      return true;
    }

    return label !== professionalRef && !new RegExp(`^${escapeProfessionalConsumptionMapRegExp(professionalRef)}\\s*$`, "i").test(label);
  });

  if (rich) {
    if (professionalRef && !rich.startsWith(`${professionalRef} - `)) {
      const withoutRefPrefix = rich.replace(
        new RegExp(`^${escapeProfessionalConsumptionMapRegExp(professionalRef)}\\s*[-–—]?\\s*`, "i"),
        ""
      ).trim();

      return withoutRefPrefix
        ? `${professionalRef} - ${withoutRefPrefix}`
        : professionalRef;
    }

    return stripProfessionalConsumptionMapDuplicatedRef(rich, professionalRef);
  }

  return professionalRef || safeCandidates[0] || "";
}

function getProfessionalConsumptionMapUnifiedProfessionalLabel(payload, ref, ...candidates) {
  const labelIndex = buildProfessionalConsumptionMapProfessionalLabelIndex(payload);
  const professionalRef = normalizeProfessionalConsumptionMapProfessionalRef(ref)
    || normalizeProfessionalConsumptionMapProfessionalRef(candidates.join(" "));

  return getProfessionalConsumptionMapUnifiedProfessionalLabelFromCandidates(
    professionalRef,
    candidates,
    labelIndex
  );
}

function harmonizeProfessionalConsumptionMapProfessionalLabels(payload, data) {
  /*
   * CARTO_UP010L_UNIFIED_PRO_LABELS
   * Harmonise :
   * - points pros ;
   * - endpoints route.source / route.destination ;
   * - source_label / destination_label ;
   * - professional_ref / professionalRef.
   */
  const labelIndex = buildProfessionalConsumptionMapProfessionalLabelIndex(payload);

  const normalizePoint = (point) => {
    if (!point || typeof point !== "object") {
      return point;
    }

    const ref = normalizeProfessionalConsumptionMapProfessionalRef(
      point.professional_ref
      || point.professionalRef
      || point.label
      || point.name
      || point.display_label
      || point.key
      || point.destination_key
      || point.source_key
    );

    const family = String(point.actor_family || point.family || "").toUpperCase();
    const isProfessional = family === "P" || Boolean(ref);

    if (!isProfessional || !ref) {
      return point;
    }

    const label = getProfessionalConsumptionMapUnifiedProfessionalLabelFromCandidates(
      ref,
      [
        point.label,
        point.name,
        point.display_label,
        point.professional_name,
        point.professional_label
      ],
      labelIndex
    );

    if (label) {
      const fullLabel = getProfessionalConsumptionMapProfessionalFullLabel(label, ref);
      const shortName = getProfessionalConsumptionMapProfessionalShortName(fullLabel, ref);

      point.professional_ref = ref;
      point.professionalRef = ref;
      point.label = shortName;
      point.name = shortName;
      point.display_label = fullLabel;
      point.professional_label = fullLabel;
    }

    return point;
  };

  const normalizeRouteEndpoint = (route, endpointKey, labelKey, familyKey) => {
    const endpoint = route?.[endpointKey] || {};
    const endpointFamily = String(
      route?.[familyKey]
      || endpoint?.actor_family
      || endpoint?.family
      || ""
    ).toUpperCase();

    const ref = normalizeProfessionalConsumptionMapProfessionalRef(
      endpoint?.professional_ref
      || endpoint?.professionalRef
      || route?.[`${endpointKey}_professional_ref`]
      || route?.[`${endpointKey}ProfessionalRef`]
      || route?.[labelKey]
      || endpoint?.label
      || endpoint?.name
      || endpoint?.display_label
    );

    const isProfessional = endpointFamily === "P" || Boolean(ref);

    if (!isProfessional || !ref) {
      return;
    }

    const label = getProfessionalConsumptionMapUnifiedProfessionalLabelFromCandidates(
      ref,
      [
        route?.[labelKey],
        endpoint?.label,
        endpoint?.name,
        endpoint?.display_label,
        endpoint?.professional_name,
        endpoint?.professional_label
      ],
      labelIndex
    );

    if (!label) {
      return;
    }

    const fullLabel = getProfessionalConsumptionMapProfessionalFullLabel(label, ref);
    const shortName = getProfessionalConsumptionMapProfessionalShortName(fullLabel, ref);

    route[labelKey] = shortName;
    route[`${labelKey}_full`] = fullLabel;

    if (route[endpointKey] && typeof route[endpointKey] === "object") {
      const fullLabel = getProfessionalConsumptionMapProfessionalFullLabel(label, ref);
      const shortName = getProfessionalConsumptionMapProfessionalShortName(fullLabel, ref);

      route[endpointKey].professional_ref = ref;
      route[endpointKey].professionalRef = ref;
      route[endpointKey].label = shortName;
      route[endpointKey].name = shortName;
      route[endpointKey].display_label = fullLabel;
      route[endpointKey].professional_label = fullLabel;
    }

    if (endpointKey === "destination") {
      route.professional_ref = route.professional_ref || ref;
      route.professionalRef = route.professionalRef || ref;
      route.destination_label = label;
    }

    if (endpointKey === "source") {
      route.source_label = label;
    }
  };

  const normalizeRoute = (route) => {
    if (!route || typeof route !== "object") {
      return route;
    }

    normalizeRouteEndpoint(route, "source", "source_label", "source_family");
    normalizeRouteEndpoint(route, "destination", "destination_label", "destination_family");

    const destinationRef = normalizeProfessionalConsumptionMapProfessionalRef(
      route.professional_ref
      || route.professionalRef
      || route.destination_label
      || route?.destination?.label
    );

    if (destinationRef) {
      const label = getProfessionalConsumptionMapUnifiedProfessionalLabelFromCandidates(
        destinationRef,
        [
          route.destination_label,
          route.professional_name,
          route.professional_label,
          route?.destination?.label,
          route?.destination?.name
        ],
        labelIndex
      );

      if (label) {
        route.professional_ref = destinationRef;
        route.professionalRef = destinationRef;
        const fullLabel = getProfessionalConsumptionMapProfessionalFullLabel(label, destinationRef);
        const shortName = getProfessionalConsumptionMapProfessionalShortName(fullLabel, destinationRef);

        route.destination_label = shortName;
        route.destination_label_full = fullLabel;

        if (route.destination && typeof route.destination === "object") {
          route.destination.professional_ref = destinationRef;
          route.destination.professionalRef = destinationRef;
          const fullLabel = getProfessionalConsumptionMapProfessionalFullLabel(label, destinationRef);
        const shortName = getProfessionalConsumptionMapProfessionalShortName(fullLabel, destinationRef);

        route.destination.label = shortName;
        route.destination.name = shortName;
        route.destination.display_label = fullLabel;
        route.destination.professional_label = fullLabel;
        }
      }
    }

    return route;
  };

  const result = {
    routes: Array.isArray(data?.routes) ? data.routes.map(normalizeRoute) : [],
    sources: Array.isArray(data?.sources) ? data.sources.map(normalizePoint) : [],
    destinations: Array.isArray(data?.destinations) ? data.destinations.map(normalizePoint) : []
  };

  return result;
}



function getProfessionalConsumptionMapSelectedProfessionalRef() {
  return String(appState.professionalConsumptionMapSearchProfessionalRef || "").trim();
}

function clearProfessionalConsumptionMapProfessionalSearch() {
  /*
   * CARTO_UP010I_SEARCH_USES_LOCKED_HIGHLIGHT
   */
  appState.professionalConsumptionMapSearchProfessionalRef = "";
  appState.professionalConsumptionMapSearchProfessionalQuery = "";
  appState.professionalConsumptionMapPendingSearchLockedProfessionalRef = "";
  appState.professionalConsumptionMapLibreHighlight = null;
  appState.professionalConsumptionMapLibreLockedHighlight = null;
  refreshProfessionalConsumptionMapVisualRender();
  if (typeof startProfessionalConsumptionMapParticleAnimationSoon === "function") {
    startProfessionalConsumptionMapParticleAnimationSoon();
  }
}


/*
 * CARTO_UP010I_SEARCH_USES_LOCKED_HIGHLIGHT
 * Une sélection depuis la barre de recherche doit activer le même focus
 * qu'un clic sur un point professionnel dans la carte.
 */
function findProfessionalConsumptionMapSearchProfessionalPoint(data, professionalRef) {
  const ref = String(professionalRef || "").trim();

  if (!ref) {
    return null;
  }

  const destinations = Array.isArray(data?.destinations) ? data.destinations : [];
  const sources = Array.isArray(data?.sources) ? data.sources : [];
  const candidates = [...destinations, ...sources];

  // Priorité : point réellement impliqué dans une route visible.
  const routeConnected = candidates.find((point) => (
    String(point?.professional_ref || point?.professionalRef || "") === ref
    && !point?.search_focus_result
  ));

  if (routeConnected) {
    return routeConnected;
  }

  // Sinon : point de recherche seul, utile pour les pros sans route visible.
  return candidates.find((point) => (
    String(point?.professional_ref || point?.professionalRef || "") === ref
  )) || null;
}

function buildProfessionalConsumptionMapSearchLockedHighlight(data) {
  const ref = getProfessionalConsumptionMapSelectedProfessionalRef();

  if (!ref) {
    return null;
  }

  const point = findProfessionalConsumptionMapSearchProfessionalPoint(data, ref);

  if (!point) {
    return null;
  }

  const highlight = getProfessionalConsumptionMapLibreObjectHighlight(point);

  if (!highlight) {
    return null;
  }

  return {
    ...highlight,
    professional_ref: ref,
    from_professional_search: true
  };
}

function syncProfessionalConsumptionMapSearchLockedHighlight(data) {
  const ref = getProfessionalConsumptionMapSelectedProfessionalRef();

  if (!ref) {
    return null;
  }

  const highlight = buildProfessionalConsumptionMapSearchLockedHighlight(data);

  if (!highlight) {
    return null;
  }

  appState.professionalConsumptionMapLibreHighlight = null;
  appState.professionalConsumptionMapLibreLockedHighlight = highlight;

  return highlight;
}

function easeProfessionalConsumptionMapToSearchLockedHighlightSoon() {
  window.setTimeout(() => {
    const highlight = appState.professionalConsumptionMapLibreLockedHighlight;

    if (
      highlight
      && highlight.from_professional_search
      && Array.isArray(highlight.center)
      && typeof easeProfessionalConsumptionMapLibreToLockedHighlight === "function"
    ) {
      easeProfessionalConsumptionMapLibreToLockedHighlight(highlight);
    }
  }, 180);
}


function setProfessionalConsumptionMapProfessionalSearch(professionalRef, query = "") {
  /*
   * CARTO_UP010I_SEARCH_USES_LOCKED_HIGHLIGHT
   * La recherche devient un vrai focus verrouillé, comme un clic carte.
   */
  appState.professionalConsumptionMapSearchProfessionalRef = String(professionalRef || "").trim();
  appState.professionalConsumptionMapSearchProfessionalQuery = String(query || "").trim();

  appState.professionalConsumptionMapLibreHighlight = null;
  appState.professionalConsumptionMapLibreLockedHighlight = null;
  appState.professionalConsumptionMapPendingSearchLockedProfessionalRef =
    appState.professionalConsumptionMapSearchProfessionalRef;

  refreshProfessionalConsumptionMapVisualRender();
  easeProfessionalConsumptionMapToSearchLockedHighlightSoon();

  // CARTO_UP010K_SEARCH_FOCUS_STARTS_PARTICLES
  startProfessionalConsumptionMapParticleAnimationSoon();
}

function findProfessionalConsumptionMapCatalogMatch(payload, query) {
  const normalizedQuery = normalizeProfessionalConsumptionMapSearchText(query);

  if (!normalizedQuery) {
    return null;
  }

  const catalog = getProfessionalConsumptionMapProfessionalCatalog(payload);

  const exact = catalog.find((item) => (
    normalizeProfessionalConsumptionMapSearchText(item.professional_ref) === normalizedQuery
    || normalizeProfessionalConsumptionMapSearchText(item.label) === normalizedQuery
    || normalizeProfessionalConsumptionMapSearchText(item.search_label) === normalizedQuery
  ));

  if (exact) {
    return exact;
  }

  return catalog.find((item) => {
    const ref = normalizeProfessionalConsumptionMapSearchText(item.professional_ref);
    const label = normalizeProfessionalConsumptionMapSearchText(item.label);
    const city = normalizeProfessionalConsumptionMapSearchText(item.city);
    return ref.includes(normalizedQuery) || label.includes(normalizedQuery) || city.includes(normalizedQuery);
  }) || null;
}


/*
 * CARTO_UP010B2_FIX_PRO_SEARCH_BEHAVIOR_ROBUST
 * Recherche professionnelle robuste.
 */
function extractProfessionalConsumptionMapProfessionalRefFromText(value) {
  const text = String(value || "").trim();
  const match = text.match(/\b(P[0-9]{4,})\b/);
  return match ? match[1] : "";
}

function collectProfessionalConsumptionMapProfessionalRefsFromObject(value, refs = new Set(), seen = new WeakSet(), depth = 0) {
  /*
   * CARTO_UP010C_ROBUST_ROUTE_PRO_MATCH
   * Parcours récursif large : les routes U→P/P→P/P→U n'ont pas toutes
   * les mêmes noms de champs après enrichissements successifs.
   */
  if (value === null || value === undefined || depth > 7) {
    return refs;
  }

  if (typeof value === "string" || typeof value === "number") {
    const text = String(value || "");
    const matches = text.match(/\bP[0-9]{4,}\b/g) || [];
    matches.forEach((ref) => refs.add(ref));
    return refs;
  }

  if (typeof value === "boolean" || typeof value === "function") {
    return refs;
  }

  if (Array.isArray(value)) {
    value.forEach((item) => {
      collectProfessionalConsumptionMapProfessionalRefsFromObject(item, refs, seen, depth + 1);
    });
    return refs;
  }

  if (typeof value === "object") {
    if (seen.has(value)) {
      return refs;
    }

    seen.add(value);

    Object.entries(value).forEach(([key, item]) => {
      // Les géométries GPS peuvent être longues ; elles ne contiennent pas les refs P.
      if (
        key === "roadPath"
        || key === "path"
        || key === "coordinates"
        || key === "sourcePosition"
        || key === "targetPosition"
      ) {
        return;
      }

      collectProfessionalConsumptionMapProfessionalRefsFromObject(item, refs, seen, depth + 1);
    });
  }

  return refs;
}

function doesProfessionalConsumptionMapObjectInvolveProfessional(value, professionalRef) {
  /*
   * CARTO_UP010C_ROBUST_ROUTE_PRO_MATCH
   * Vérifie si une route / un point / un endpoint implique le pro recherché.
   */
  const ref = String(professionalRef || "").trim();

  if (!ref) {
    return true;
  }

  if (!/^P[0-9]{4,}$/.test(ref)) {
    return false;
  }

  return collectProfessionalConsumptionMapProfessionalRefsFromObject(value).has(ref);
}


function doesProfessionalConsumptionMapRouteInvolveProfessional(route, professionalRef) {
  /*
   * CARTO_UP010B2_FIX_PRO_SEARCH_BEHAVIOR_ROBUST
   * Matching robuste sur les routes U→P.
   */
  return doesProfessionalConsumptionMapObjectInvolveProfessional(route, professionalRef);
}

function doesProfessionalConsumptionMapExtraRouteInvolveProfessional(route, professionalRef) {
  /*
   * CARTO_UP010B2_FIX_PRO_SEARCH_BEHAVIOR_ROBUST
   * Matching robuste sur les extra_flow_families P→P / P→U.
   */
  return doesProfessionalConsumptionMapObjectInvolveProfessional(route, professionalRef);
}

function appendProfessionalConsumptionMapSearchResultMarker({
  payload,
  routeData,
  destinationMap
}) {
  /*
   * CARTO_UP010F_SEARCH_ANCHOR_ROUTE
   * Si la recherche pro ne produit aucune route visible, on ajoute :
   * - le point du professionnel ;
   * - une route d'ancrage invisible, strictement technique, pour éviter
   *   les chemins de rendu qui exigent data.routes.length > 0.
   */
  const ref = getProfessionalConsumptionMapSelectedProfessionalRef();

  if (!ref) {
    return;
  }

  const catalogItem = getProfessionalConsumptionMapProfessionalCatalog(payload)
    .find((item) => item.professional_ref === ref);

  if (!catalogItem || !catalogItem.cartographiable) {
    console.warn("[CARTO_UP010F] Professionnel recherché non cartographiable", ref, catalogItem);
    return;
  }

  const longitude = Number(catalogItem.longitude);
  const latitude = Number(catalogItem.latitude);

  if (
    !Number.isFinite(longitude)
    || !Number.isFinite(latitude)
    || longitude < -180
    || longitude > 180
    || latitude < -90
    || latitude > 90
  ) {
    console.warn("[CARTO_UP010F] Coordonnées invalides pour le professionnel recherché", ref, catalogItem);
    return;
  }

  const hasRenderedRoute = routeData.some((route) => (
    doesProfessionalConsumptionMapObjectInvolveProfessional(route, ref)
  ));

  const key = `search:${ref}`;
  const activeOnPeriod = Boolean(catalogItem.active_on_period);
  const label = catalogItem.label || ref;

  destinationMap.set(key, {
    type: "professional",
    key,
    destination_key: key,
    professional_ref: ref,
    actor_family: "P",
    flow_family: "SEARCH",
    search_focus_result: true,
    inactive_search_result: !hasRenderedRoute,
    search_result_status: hasRenderedRoute
      ? "active_visible_routes"
      : activeOnPeriod
        ? "active_on_period_but_hidden_by_current_filters"
        : "no_transaction_on_period",
    name: label,
    label,
    display_label: label,
    postal_code: catalogItem.postal_code || "",
    city: catalogItem.city || "",
    longitude,
    latitude,
    tx_count: Number(catalogItem.active_tx_count || 0),
    volume: Number(catalogItem.active_volume || 0),
    route_count: Number(catalogItem.active_route_count || 0)
  });

  if (hasRenderedRoute) {
    return;
  }

  routeData.push({
    type: "route",
    id: `search-anchor:${ref}`,
    base_route_id: `search-anchor:${ref}`,
    search_anchor_route: true,
    is_search_anchor_route: true,
    flowFamily: "SEARCH",
    flow_family: "SEARCH",
    sourceCode: catalogItem.postal_code || "",
    sourceKey: key,
    source_key: key,
    professionalRef: ref,
    professional_ref: ref,
    destinationKey: key,
    destination_key: key,
    sourcePosition: [longitude, latitude],
    targetPosition: [longitude, latitude],
    roadPath: [
      [longitude, latitude],
      [longitude, latitude]
    ],
    roadPathChecked: true,
    roadRoutingStatus: "routed",
    road_provider: "search_anchor",
    tx_count: 0,
    volume: 0,
    visual_tx_count: 0,
    visual_volume: 0,
    distinct_users: 0,
    payment_day_count: 0,
    source_label: label,
    destination_label: label,
    source_family: "P",
    destination_family: "P"
  });
}


/*
 * CARTO_UP010G_FIX_SEARCH_AMOUNT_FORMATTER
 * Formatter local pour la barre de recherche pro.
 * Évite l'appel à formatProfessionalConsumptionAmount, absent dans ce fichier.
 */
function formatProfessionalConsumptionMapSearchAmount(value) {
  const number = Number(value || 0);

  if (!Number.isFinite(number)) {
    return "0 G";
  }

  return `${number.toLocaleString("fr-FR", {
    maximumFractionDigits: 0
  })} G`;
}



/*
 * CARTO_UP010H_SEARCH_BAR_PRO_STATS
 * Helpers UI pour la barre de recherche professionnelle.
 */
function formatProfessionalConsumptionMapSearchStatAmount(value) {
  const number = Number(value || 0);

  if (!Number.isFinite(number)) {
    return "0 G";
  }

  return `${number.toLocaleString("fr-FR", {
    maximumFractionDigits: 0
  })} G`;
}

function getProfessionalConsumptionMapProfessionalSearchStatsLabel(item) {
  const receivedTx = Number(item?.received_tx_count || 0);
  const receivedVolume = Number(item?.received_volume || 0);
  const emittedTx = Number(item?.emitted_tx_count || 0);
  const emittedVolume = Number(item?.emitted_volume || 0);
  const activeTx = Number(item?.active_tx_count || 0);
  const activeVolume = Number(item?.active_volume || 0);

  const parts = [];

  if (receivedTx > 0 || receivedVolume > 0) {
    parts.push(`reçu ${formatProfessionalSummaryInteger(receivedTx)} tx · ${formatProfessionalConsumptionMapSearchStatAmount(receivedVolume)}`);
  }

  if (emittedTx > 0 || emittedVolume > 0) {
    parts.push(`émis ${formatProfessionalSummaryInteger(emittedTx)} tx · ${formatProfessionalConsumptionMapSearchStatAmount(emittedVolume)}`);
  }

  if (parts.length) {
    return parts.join(" · ");
  }

  if (activeTx > 0 || activeVolume > 0) {
    return `${formatProfessionalSummaryInteger(activeTx)} tx · ${formatProfessionalConsumptionMapSearchStatAmount(activeVolume)}`;
  }

  return "pas de transaction détectée sur la période";
}

function getProfessionalConsumptionMapProfessionalSearchMatches(payload, query, limit = 8) {
  const catalog = getProfessionalConsumptionMapProfessionalCatalog(payload);
  const normalizedQuery = normalizeProfessionalConsumptionMapSearchText(query);

  const scored = catalog.map((item) => {
    const ref = normalizeProfessionalConsumptionMapSearchText(item.professional_ref);
    const label = normalizeProfessionalConsumptionMapSearchText(item.label);
    const city = normalizeProfessionalConsumptionMapSearchText(item.city);
    const haystack = `${ref} ${label} ${city}`;

    let score = 0;

    if (!normalizedQuery) {
      score = item.active_on_period ? 20 : 5;
    } else if (ref === normalizedQuery || label === normalizedQuery) {
      score = 100;
    } else if (ref.startsWith(normalizedQuery)) {
      score = 90;
    } else if (label.startsWith(normalizedQuery)) {
      score = 80;
    } else if (haystack.includes(normalizedQuery)) {
      score = 55;
    }

    if (item.active_on_period) {
      score += 8;
    }

    return { item, score };
  });

  return scored
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || String(a.item.label).localeCompare(String(b.item.label)))
    .slice(0, limit)
    .map((entry) => entry.item);
}

function getProfessionalConsumptionMapProfessionalSearchStatus(item) {
  if (!item) {
    return "";
  }

  if (!item.cartographiable) {
    return "non cartographiable";
  }

  if (!item.active_on_period) {
    return "hors flux période";
  }

  return "actif période";
}


function ensureProfessionalConsumptionMapProfessionalSearchControls(payload) {
  /*
   * CARTO_UP010H_SEARCH_BAR_PRO_STATS
   * Barre de recherche minimaliste, sans datalist natif.
   */
  const controls = document.querySelector(".professional-consumption-map-visual-controls");

  if (!controls) {
    return;
  }

  let node = controls.querySelector("[data-professional-consumption-map-search-controls]");

  if (!node) {
    node = document.createElement("div");
    node.className = "professional-consumption-map-professional-search";
    node.setAttribute("data-professional-consumption-map-search-controls", "true");
    controls.appendChild(node);
  }

  const catalog = getProfessionalConsumptionMapProfessionalCatalog(payload);
  const selectedRef = getProfessionalConsumptionMapSelectedProfessionalRef();
  const selected = catalog.find((item) => item.professional_ref === selectedRef) || null;
  const query = appState.professionalConsumptionMapSearchProfessionalQuery || selected?.label || "";

  node.innerHTML = `
    <label class="professional-consumption-map-search-label" for="professionalConsumptionMapProfessionalSearchInput">
      Rechercher un professionnel
    </label>

    <div class="professional-consumption-map-search-shell">
      <span class="professional-consumption-map-search-icon" aria-hidden="true">⌕</span>
      <input
        id="professionalConsumptionMapProfessionalSearchInput"
        class="professional-consumption-map-search-input"
        type="search"
        placeholder="Nom, code Pxxxx, commune…"
        value="${escapeHtml(query)}"
        autocomplete="off"
        spellcheck="false"
      >
      <button
        type="button"
        class="professional-consumption-map-search-inline-clear"
        title="Effacer la recherche"
        aria-label="Effacer la recherche"
      >×</button>

      <div class="professional-consumption-map-search-suggestions" hidden></div>
    </div>

    <div class="professional-consumption-map-search-actions">
      <button type="button" class="professional-consumption-map-search-apply">Filtrer</button>
      <button type="button" class="professional-consumption-map-search-clear">Effacer</button>
    </div>

    <div class="professional-consumption-map-search-status"></div>
  `;

  const input = node.querySelector(".professional-consumption-map-search-input");
  const suggestions = node.querySelector(".professional-consumption-map-search-suggestions");
  const applyButton = node.querySelector(".professional-consumption-map-search-apply");
  const clearButton = node.querySelector(".professional-consumption-map-search-clear");
  const inlineClearButton = node.querySelector(".professional-consumption-map-search-inline-clear");
  const status = node.querySelector(".professional-consumption-map-search-status");

  let activeIndex = -1;
  let currentMatches = [];

  const setStatus = (message, variant = "") => {
    status.className = `professional-consumption-map-search-status ${variant}`.trim();
    status.textContent = message;
  };

  const renderStatus = () => {
    if (selected) {
      const statusLabel = getProfessionalConsumptionMapProfessionalSearchStatus(selected);
      const statsLabel = getProfessionalConsumptionMapProfessionalSearchStatsLabel(selected);

      setStatus(
        `${selected.label || selected.professional_ref} · ${statusLabel} · ${statsLabel}`,
        selected.active_on_period ? "is-active" : "is-inactive"
      );
      return;
    }

    setStatus(`${formatProfessionalSummaryInteger(catalog.length)} professionnel(s) dans le catalogue de recherche`);
  };

  const renderSuggestions = () => {
    currentMatches = getProfessionalConsumptionMapProfessionalSearchMatches(payload, input.value, 9);
    activeIndex = -1;

    if (!currentMatches.length) {
      suggestions.innerHTML = `
        <div class="professional-consumption-map-search-empty">
          Aucun professionnel trouvé.
        </div>
      `;
      suggestions.hidden = false;
      return;
    }

    suggestions.innerHTML = currentMatches.map((item, index) => {
      const isInactive = !item.active_on_period;
      const meta = getProfessionalConsumptionMapProfessionalSearchStatsLabel(item);
      const statusLabel = getProfessionalConsumptionMapProfessionalSearchStatus(item);

      return `
        <button
          type="button"
          class="professional-consumption-map-search-suggestion ${isInactive ? "is-inactive" : "is-active"}"
          data-index="${index}"
          data-ref="${escapeHtml(item.professional_ref)}"
        >
          <span class="professional-consumption-map-search-suggestion-main">
            <span class="professional-consumption-map-search-suggestion-title">${escapeHtml(item.label || item.professional_ref)}</span>
            <span class="professional-consumption-map-search-suggestion-badge">${escapeHtml(statusLabel)}</span>
          </span>
          <span class="professional-consumption-map-search-suggestion-meta">
            ${escapeHtml(meta)}
          </span>
        </button>
      `;
    }).join("");

    suggestions.hidden = false;
  };

  const hideSuggestions = () => {
    suggestions.hidden = true;
    activeIndex = -1;
  };

  const selectItem = (item) => {
    if (!item) {
      return;
    }

    setProfessionalConsumptionMapProfessionalSearch(
      item.professional_ref,
      item.label || item.professional_ref
    );
  };

  const applySearch = () => {
    const match = findProfessionalConsumptionMapCatalogMatch(payload, input.value);

    if (!match) {
      renderSuggestions();
      setStatus("Aucun professionnel trouvé.", "is-error");
      return;
    }

    selectItem(match);
  };

  const updateActiveSuggestion = () => {
    Array.from(suggestions.querySelectorAll(".professional-consumption-map-search-suggestion"))
      .forEach((button, index) => {
        button.classList.toggle("is-selected", index === activeIndex);
      });
  };

  input.addEventListener("focus", renderSuggestions);

  input.addEventListener("input", () => {
    appState.professionalConsumptionMapSearchProfessionalQuery = input.value;
    renderSuggestions();
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (suggestions.hidden) renderSuggestions();
      activeIndex = Math.min(currentMatches.length - 1, activeIndex + 1);
      updateActiveSuggestion();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = Math.max(0, activeIndex - 1);
      updateActiveSuggestion();
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      if (activeIndex >= 0 && currentMatches[activeIndex]) {
        selectItem(currentMatches[activeIndex]);
      } else {
        applySearch();
      }
      return;
    }

    if (event.key === "Escape") {
      hideSuggestions();
    }
  });

  suggestions.addEventListener("mousedown", (event) => {
    event.preventDefault();

    const button = event.target.closest(".professional-consumption-map-search-suggestion");
    if (!button) {
      return;
    }

    const index = Number(button.dataset.index);
    selectItem(currentMatches[index]);
  });

  document.addEventListener("click", (event) => {
    if (!node.contains(event.target)) {
      hideSuggestions();
    }
  }, { once: true });

  applyButton.addEventListener("click", applySearch);

  const clear = () => {
    clearProfessionalConsumptionMapProfessionalSearch();
  };

  clearButton.addEventListener("click", clear);
  inlineClearButton.addEventListener("click", clear);

  renderStatus();
}


function getProfessionalConsumptionMapFlowFamilyState() {
  if (!appState.professionalConsumptionMapFlowFamilies) {
    appState.professionalConsumptionMapFlowFamilies = {
      U_TO_P: true,
      P_TO_P: false,
      P_TO_U: false
    };
  }

  return appState.professionalConsumptionMapFlowFamilies;
}


/*
 * CARTO_UP010N3_FIX_MISSING_ENABLED_FAMILIES
 * Helper attendu par les patchs P→P/P→U.
 * Déduit les familles cochées depuis l'état existant.
 */
function getProfessionalConsumptionMapEnabledFlowFamilies() {
  const families = ["U_TO_P", "P_TO_P", "P_TO_U"];
  const enabled = new Set();

  families.forEach((family) => {
    try {
      if (typeof isProfessionalConsumptionMapFlowFamilyEnabled === "function") {
        if (isProfessionalConsumptionMapFlowFamilyEnabled(family)) {
          enabled.add(family);
        }
        return;
      }
    } catch (error) {
      // fallback ci-dessous
    }

    const state = appState?.professionalConsumptionMapFlowFamilies
      || appState?.professionalConsumptionMapFlowFamilyState
      || appState?.professionalConsumptionMapFlowFamilyVisibility
      || {};

    if (state[family]) {
      enabled.add(family);
    }
  });

  if (!enabled.size) {
    enabled.add("U_TO_P");
  }

  return enabled;
}


function isProfessionalConsumptionMapFlowFamilyEnabled(flowFamily) {
  const state = getProfessionalConsumptionMapFlowFamilyState();
  return Boolean(state[flowFamily]);
}

function setProfessionalConsumptionMapFlowFamily(flowFamily, enabled) {
  const state = getProfessionalConsumptionMapFlowFamilyState();
  state[flowFamily] = Boolean(enabled);
  clearProfessionalConsumptionMapFocusMatchMemoCache();
  refreshProfessionalConsumptionMapVisualRender();

  // CARTO_UP010N2_PATCH_ROUTEPATHDATA_PP
  if (typeof startProfessionalConsumptionMapParticleAnimationSoon === "function") {
    startProfessionalConsumptionMapParticleAnimationSoon();
  }
}

function getProfessionalConsumptionMapExtraFlowFamilies(payload) {
  const extra = payload?.extra_flow_families || {};
  return extra?.families || {};
}

function getProfessionalConsumptionMapExtraRoutesForEnabledFamilies(payload) {
  const families = getProfessionalConsumptionMapExtraFlowFamilies(payload);
  const result = [];

  ["P_TO_P", "P_TO_U"].forEach((flowFamily) => {
    if (!isProfessionalConsumptionMapFlowFamilyEnabled(flowFamily)) {
      return;
    }

    const routes = Array.isArray(families?.[flowFamily]?.routes)
      ? families[flowFamily].routes
      : [];

    routes.forEach((route) => {
      if (
        doesProfessionalConsumptionMapExtraRouteInvolveProfessional(
          route,
          getProfessionalConsumptionMapSelectedProfessionalRef()
        )
      ) {
        result.push({
          ...route,
          flow_family: flowFamily
        });
      }
    });
  });

  return result;
}

function getProfessionalConsumptionMapFlowFamilyLabel(flowFamily) {
  if (flowFamily === "P_TO_P") return "P→P";
  if (flowFamily === "P_TO_U") return "P→U";
  return "U→P";
}

function getProfessionalConsumptionMapFlowFamilyFullLabel(flowFamily) {
  if (flowFamily === "P_TO_P") return "Professionnels → professionnels";
  if (flowFamily === "P_TO_U") return "Professionnels → particuliers";
  return "Particuliers → professionnels";
}

function getProfessionalConsumptionMapRouteColor(route, alpha, variant = "core") {
  const flowFamily = route?.flowFamily || route?.flow_family || "U_TO_P";
  const safeAlpha = Math.max(0, Math.min(255, Math.round(alpha)));

  if (flowFamily === "P_TO_P") {
    return variant === "glow"
      ? [56, 189, 248, safeAlpha]
      : [125, 211, 252, safeAlpha];
  }

  if (flowFamily === "P_TO_U") {
    return variant === "glow"
      ? [244, 114, 182, safeAlpha]
      : [251, 113, 133, safeAlpha];
  }

  return variant === "glow"
    ? [255, 196, 120, safeAlpha]
    : [246, 176, 76, safeAlpha];
}

function getProfessionalConsumptionMapActorPointColor(point, alpha, variant = "core") {
  const family = point?.actor_family
    || point?.source_family
    || point?.destination_family
    || point?.family
    || "";

  const safeAlpha = Math.max(0, Math.min(255, Math.round(alpha)));

  if (point?.inactive_search_result) {
    return variant === "glow"
      ? [251, 191, 36, safeAlpha]
      : [148, 163, 184, safeAlpha];
  }

  if (family === "P") {
    return variant === "glow"
      ? [45, 212, 191, safeAlpha]
      : [52, 211, 153, safeAlpha];
  }

  if (family === "U") {
    return variant === "glow"
      ? [255, 120, 100, safeAlpha]
      : [255, 92, 72, safeAlpha];
  }

  return [226, 232, 240, safeAlpha];
}

function ensureProfessionalConsumptionMapFlowFamilyControls(payload) {
  const controls = document.querySelector(".professional-consumption-map-visual-controls");

  if (!controls) {
    return;
  }

  let node = controls.querySelector("[data-professional-consumption-map-flow-family-controls]");

  if (!node) {
    node = document.createElement("div");
    node.className = "professional-consumption-map-flow-family-controls";
    node.setAttribute("data-professional-consumption-map-flow-family-controls", "true");
    controls.appendChild(node);
  }

  const families = getProfessionalConsumptionMapExtraFlowFamilies(payload);
  const state = getProfessionalConsumptionMapFlowFamilyState();

  const pToP = families?.P_TO_P || {};
  const pToU = families?.P_TO_U || {};

  node.innerHTML = `
    <div class="professional-consumption-map-flow-family-title">
      Familles de flux affichées
    </div>
    <div class="professional-consumption-map-flow-family-options">
      <label class="professional-consumption-map-flow-family-option is-up">
        <input type="checkbox" data-flow-family="U_TO_P" ${state.U_TO_P ? "checked" : ""}>
        <span>U→P</span>
        <small>particuliers → pros</small>
      </label>
      <label class="professional-consumption-map-flow-family-option is-pp">
        <input type="checkbox" data-flow-family="P_TO_P" ${state.P_TO_P ? "checked" : ""}>
        <span>P→P</span>
        <small>${formatProfessionalSummaryInteger(pToP.pair_count || 0)} faisceau(x)</small>
      </label>
      <label class="professional-consumption-map-flow-family-option is-pu">
        <input type="checkbox" data-flow-family="P_TO_U" ${state.P_TO_U ? "checked" : ""}>
        <span>P→U</span>
        <small>${formatProfessionalSummaryInteger(pToU.pair_count || 0)} faisceau(x)</small>
      </label>
    </div>
  `;

  node.querySelectorAll("input[data-flow-family]").forEach((input) => {
    input.addEventListener("change", () => {
      setProfessionalConsumptionMapFlowFamily(
        input.getAttribute("data-flow-family"),
        input.checked
      );
    });
  });
}

function readProfessionalConsumptionMapLngLatFromPayloadPoint(point) {
  if (!point || typeof point !== "object") return null;

  const longitude = Number(
    point.longitude
    ?? point.lon
    ?? point.lng
    ?? point?.coordinates?.[0]
  );

  const latitude = Number(
    point.latitude
    ?? point.lat
    ?? point?.coordinates?.[1]
  );

  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
    return null;
  }

  return [longitude, latitude];
}

function appendProfessionalConsumptionMapExtraFlowRoutesToData({
  payload,
  routeData,
  sourceMap,
  destinationMap
}) {
  const extraRoutes = getProfessionalConsumptionMapExtraRoutesForEnabledFamilies(payload);

  extraRoutes.forEach((route) => {
    const flowFamily = route.flow_family || route.flowFamily || "";
    const source = route.source || {};
    const destination = route.destination || {};

    const sourcePosition = readProfessionalConsumptionMapLngLatFromPayloadPoint(source);
    const targetPosition = readProfessionalConsumptionMapLngLatFromPayloadPoint(destination);

    if (!sourcePosition || !targetPosition) {
      return;
    }

    const sourceKey = String(route.source_key || source.key || "").trim();
    const destinationKey = String(route.destination_key || destination.key || "").trim();

    if (!sourceKey || !destinationKey) {
      return;
    }

    const sourceFamily = route.source_family || "P";
    const destinationFamily = route.destination_family || (flowFamily === "P_TO_U" ? "U" : "P");

    // CARTO_UP008E_PRO_LABELS_EXTRA_FLOWS
    // Les keys p_xxx/u_xxx restent des identifiants techniques ; jamais des labels.
    const sourceProfessionalRef = source.professional_ref || "";
    const destinationProfessionalRef = destination.professional_ref || "";

    const sourceDisplayLabel = cleanProfessionalConsumptionMapProfessionalLabel(
      source.label
        || source.name
        || source.display_label
        || sourceProfessionalRef
        || getProfessionalConsumptionMapFlowFamilyFullLabel(flowFamily),
      sourceProfessionalRef
    );

    const destinationDisplayLabel = cleanProfessionalConsumptionMapProfessionalLabel(
      destination.label
        || destination.name
        || destination.display_label
        || destinationProfessionalRef
        || getProfessionalConsumptionMapFlowFamilyFullLabel(flowFamily),
      destinationProfessionalRef
    );

    if (!sourceMap.has(sourceKey)) {
      sourceMap.set(sourceKey, {
        type: "source",
        key: sourceKey,
        source_key: sourceKey,
        actor_family: sourceFamily,
        flow_family: flowFamily,
        postal_code: source.postal_code || "",
        city: source.city || "",
        professional_ref: sourceProfessionalRef,
        name: sourceDisplayLabel,
        label: sourceDisplayLabel,
        display_label: sourceDisplayLabel,
        longitude: sourcePosition[0],
        latitude: sourcePosition[1],
        tx_count: 0,
        volume: 0,
        route_count: 0
      });
    }

    if (!destinationMap.has(destinationKey)) {
      destinationMap.set(destinationKey, {
        type: "professional",
        key: destinationKey,
        destination_key: destinationKey,
        professional_ref: destinationProfessionalRef || destinationKey,
        actor_family: destinationFamily,
        flow_family: flowFamily,
        name: destinationDisplayLabel,
        label: destinationDisplayLabel,
        display_label: destinationDisplayLabel,
        postal_code: destination.postal_code || "",
        city: destination.city || "",
        longitude: targetPosition[0],
        latitude: targetPosition[1],
        tx_count: 0,
        volume: 0,
        route_count: 0
      });
    }

    const txCount = Number(route.tx_count || 0);
    const volume = Number(route.volume || 0);

    const sourceItem = sourceMap.get(sourceKey);
    sourceItem.tx_count += txCount;
    sourceItem.volume += volume;
    sourceItem.route_count += 1;

    const destinationItem = destinationMap.get(destinationKey);
    destinationItem.tx_count += txCount;
    destinationItem.volume += volume;
    destinationItem.route_count += 1;

    routeData.push({
      type: "route",
      id: String(route.id || `${flowFamily}:${sourceKey}->${destinationKey}`),
      flowFamily,
      flow_family: flowFamily,
      sourceCode: source.postal_code || "",
      sourceKey,
      professionalRef: destinationKey,
      destinationKey,
      sourcePosition,
      targetPosition,
      tx_count: txCount,
      volume,
      visual_tx_count: txCount,
      visual_volume: volume,
      distinct_users: 0,
      payment_day_count: Number(route.payment_day_count || 0),
      source_label: sourceDisplayLabel,
      destination_label: destinationDisplayLabel,
      source_family: sourceFamily,
      destination_family: destinationFamily
    });
  });
}


function buildProfessionalConsumptionMapLibreData(payload) {
  /*
   * CARTO_UP005A_DISPERSED_SOURCES_TEST\n   * CARTO_UP005G_STABLE_SOURCE_POINT_KEY
   *
   * Test visuel :
   * - les routes MapLibre partent des points source dispersés/anonymisés
   *   lorsqu'ils sont disponibles dans le payload ;
   * - fallback : centre agrégé du bassin source ;
   * - on plafonne à 5 points dispersés par faisceau pour éviter de saturer
   *   OSRM et la carte.
   *
   * Important : ces points ne sont pas des adresses réelles exposées.
   */
  const selectedProfessionalRef = getProfessionalConsumptionMapSelectedProfessionalRef();
  const baseRoutes = Array.isArray(payload?.routes) ? payload.routes : [];
  const routes = isProfessionalConsumptionMapFlowFamilyEnabled("U_TO_P")
    ? baseRoutes.filter((route) => (
        doesProfessionalConsumptionMapRouteInvolveProfessional(route, selectedProfessionalRef)
      ))
    : [];
  const sourceMap = new Map();
  const destinationMap = new Map();
  const maxSourcePointsPerRoute = 5;
  const routeData = [];

  function readLngLat(point) {
    if (!point || typeof point !== "object") return null;

    const longitude = Number(
      point.longitude
      ?? point.lon
      ?? point.lng
      ?? point[0]
    );

    const latitude = Number(
      point.latitude
      ?? point.lat
      ?? point[1]
    );

    if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
      return null;
    }

    return [longitude, latitude];
  }

  function getRouteSourcePoints(route) {
    const candidates = [];

    [
      route?.source_points,
      route?.source?.points,
      route?.source?.source_points,
      route?.sources
    ].forEach((list) => {
      if (Array.isArray(list)) {
        list.forEach((point) => {
          const coordinates = readLngLat(point);
          if (coordinates) {
            candidates.push({
              coordinates,
              original: point
            });
          }
        });
      }
    });

    if (candidates.length) {
      return candidates.slice(0, maxSourcePointsPerRoute);
    }

    const fallback = readLngLat(route?.source || {});
    return fallback
      ? [{ coordinates: fallback, original: route?.source || {} }]
      : [];
  }

  function makeSourceKey(sourceCode, coordinates, sourceOriginal = {}) {
    /*
     * CARTO_UP005G_STABLE_SOURCE_POINT_KEY
     * Une source dispersée doit conserver la même clé sur toutes ses routes.
     * On ne dépend donc plus de l'index local du point dans une route.
     *
     * Priorité :
     * 1. clé explicite si le payload en fournit une ;
     * 2. sinon coordonnées anonymisées/synthétiques arrondies.
     */
    const explicitKey = String(
      sourceOriginal.source_key
      || sourceOriginal.point_key
      || sourceOriginal.anonymized_point_key
      || sourceOriginal.synthetic_point_key
      || ""
    ).trim();

    if (explicitKey) {
      return [
        sourceCode || "source",
        explicitKey
      ].join("|");
    }

    return [
      sourceCode || "source",
      Number(coordinates[0]).toFixed(5),
      Number(coordinates[1]).toFixed(5)
    ].join("|");
  }

  routes.forEach((route) => {
    const source = route?.source || {};
    const destination = route?.destination || {};

    const destinationCoordinates = readLngLat(destination);
    if (!destinationCoordinates) {
      return;
    }

    const sourceCode = String(
      route?.source_postal_code
      || source?.postal_code
      || ""
    ).trim();

    const professionalRef = String(
      route?.professional_ref
      || destination?.professional_ref
      || ""
    ).trim();

    const routeSourcePoints = getRouteSourcePoints(route);
    if (!routeSourcePoints.length) {
      return;
    }

    const originalTxCount = Number(route?.tx_count || route?.final_tx_count || 0);
    const originalVolume = Number(route?.volume || route?.final_volume || 0);
    const splitFactor = Math.max(1, routeSourcePoints.length);

    // Destination : on agrège une seule fois par route originale.
    if (professionalRef && !destinationMap.has(professionalRef)) {
      const professionalLabel = cleanProfessionalConsumptionMapProfessionalLabel(
        getProfessionalConsumptionMapDestinationLabel(destination)
          || destination?.name
          || route?.professional_name
          || destination?.label
          || professionalRef,
        professionalRef
      );

      destinationMap.set(professionalRef, {
        type: "professional",
        professional_ref: professionalRef,
        actor_family: "P",
        flow_family: "U_TO_P",
        name: professionalLabel,
        label: professionalLabel,
        postal_code: destination?.postal_code || "",
        city: destination?.city || "",
        longitude: destinationCoordinates[0],
        latitude: destinationCoordinates[1],
        tx_count: 0,
        volume: 0,
        route_count: 0
      });
    }

    if (professionalRef && destinationMap.has(professionalRef)) {
      const destinationItem = destinationMap.get(professionalRef);
      destinationItem.tx_count += originalTxCount;
      destinationItem.volume += originalVolume;
      destinationItem.route_count += 1;
    }

    routeSourcePoints.forEach((sourcePoint, index) => {
      const sourceKey = makeSourceKey(sourceCode, sourcePoint.coordinates, sourcePoint.original || {});
      const sourceOriginal = sourcePoint.original || {};
      const sourceLabel = getProfessionalConsumptionMapSourceDisplayLabel({
        postal_code: sourceCode,
        city: sourceOriginal.city || source.city || route?.source_city || ""
      });

      if (!sourceMap.has(sourceKey)) {
        sourceMap.set(sourceKey, {
          type: "source",
          source_key: sourceKey,
          actor_family: "U",
          flow_family: "U_TO_P",
          postal_code: sourceCode,
          city: sourceOriginal.city || source.city || route?.source_city || "",
          longitude: sourcePoint.coordinates[0],
          latitude: sourcePoint.coordinates[1],
          tx_count: 0,
          volume: 0,
          route_count: 0,
          label: `${sourceLabel} · point dispersé`
        });
      }

      const sourceItem = sourceMap.get(sourceKey);
      sourceItem.tx_count += originalTxCount / splitFactor;
      sourceItem.volume += originalVolume / splitFactor;
      sourceItem.route_count += 1 / splitFactor;

      routeData.push({
        type: "route",
        id: `${route?.id || `${sourceCode}->${professionalRef}`}::${index}`,
        base_route_id: route?.id || `${sourceCode}->${professionalRef}`,
        flowFamily: "U_TO_P",
        flow_family: "U_TO_P",
        sourceCode,
        sourceKey,
        professionalRef,
        sourcePosition: sourcePoint.coordinates,
        targetPosition: destinationCoordinates,
        tx_count: originalTxCount,
        volume: originalVolume,
        visual_tx_count: originalTxCount / splitFactor,
        visual_volume: originalVolume / splitFactor,
        distinct_users: Number(route?.distinct_users || 0),
        source_label: sourceLabel,
        destination_label: getProfessionalConsumptionMapDestinationLabel(destination),
        source_mode: routeSourcePoints.length > 1 ? "dispersed_source_point" : "single_or_fallback_source_point"
      });
    });
  });

  appendProfessionalConsumptionMapExtraFlowRoutesToData({
    payload,
    routeData,
    sourceMap,
    destinationMap
  });

  appendProfessionalConsumptionMapSearchResultMarker({
    payload,
    routeData,
    destinationMap
  });

  return harmonizeProfessionalConsumptionMapProfessionalLabels(payload, {
    routes: routeData,
    sources: Array.from(sourceMap.values()),
    destinations: Array.from(destinationMap.values())
  });
}

function fitProfessionalConsumptionMapLibreToData(map, data) {
  if (!map || !window.maplibregl) return;

  // CARTO_UP010E3_FIT_POINT_WITHOUT_ROUTES
  if (!Array.isArray(data?.routes) || !data.routes.length) {
    const firstPoint = getProfessionalConsumptionMapFirstRenderablePoint(data);

    if (firstPoint && typeof map.fitBounds === "function") {
      const padLon = 0.012;
      const padLat = 0.009;

      map.fitBounds(
        [
          [firstPoint[0] - padLon, firstPoint[1] - padLat],
          [firstPoint[0] + padLon, firstPoint[1] + padLat]
        ],
        {
          padding: { top: 90, right: 90, bottom: 90, left: 90 },
          maxZoom: 14.8,
          duration: 520
        }
      );
    }

    return;
  }

  const bounds = new window.maplibregl.LngLatBounds();
  let count = 0;

  const push = (position) => {
    if (
      Array.isArray(position)
      && Number.isFinite(Number(position[0]))
      && Number.isFinite(Number(position[1]))
    ) {
      bounds.extend([Number(position[0]), Number(position[1])]);
      count += 1;
    }
  };

  data.routes.forEach((route) => {
    push(route.sourcePosition);
    push(route.targetPosition);
  });

  if (!count) return;

  const isFocus = getProfessionalConsumptionMapSelectedSourcePostalCode();

  map.fitBounds(bounds, {
    padding: isFocus
      ? { top: 92, right: 92, bottom: 92, left: 92 }
      : { top: 72, right: 72, bottom: 72, left: 72 },
    maxZoom: isFocus ? 12.8 : 11.2,
    duration: 650
  });
}

function getProfessionalConsumptionMapLibreTooltip({ object }) {
  if (!object) return null;

  // CARTO_UP005E_LOCKED_FOCUS_ALL — la tooltip stabilise le hover, sauf focus verrouillé.
  if (!appState.professionalConsumptionMapLibreLockedHighlight && ["source", "professional", "route"].includes(object.type)) {
    const nextHighlight = getProfessionalConsumptionMapLibreObjectHighlight(object);
    if (nextHighlight?.type && nextHighlight?.id) {
      window.requestAnimationFrame(() => {
        setProfessionalConsumptionMapLibreHighlight(nextHighlight);
      });
    }
  }


  if (object.type === "professional") {
    return {
      html: `
        <div class="professional-consumption-maplibre-tooltip-title">
          ${escapeHtml(getProfessionalConsumptionMapDestinationLabel(object))}
        </div>
        <div class="professional-consumption-maplibre-tooltip-line">
          ${formatProfessionalSummaryInteger(object.tx_count || 0)} paiement(s) · ${euro(object.volume || 0)}
        </div>
        <div class="professional-consumption-maplibre-tooltip-muted">
          ${escapeHtml([object.postal_code, object.city].filter(Boolean).join(" · "))}
        </div>
      `,
      style: {
        backgroundColor: "rgba(15, 23, 42, 0.96)",
        color: "#ffffff",
        borderRadius: "12px",
        padding: "10px 12px",
        maxWidth: "360px",
        fontSize: "13px",
        lineHeight: "1.45"
      }
    };
  }

  if (object.type === "source") {
    return {
      html: `
        <div class="professional-consumption-maplibre-tooltip-title">
          ${escapeHtml(object.label || "Bassin source")}
        </div>
        <div class="professional-consumption-maplibre-tooltip-line">
          ${formatProfessionalSummaryInteger(object.route_count || 0)} faisceau(x) ·
          ${formatProfessionalSummaryInteger(object.tx_count || 0)} paiement(s) ·
          ${euro(object.volume || 0)}
        </div>
      `,
      style: {
        backgroundColor: "rgba(15, 23, 42, 0.96)",
        color: "#ffffff",
        borderRadius: "12px",
        padding: "10px 12px",
        maxWidth: "360px",
        fontSize: "13px",
        lineHeight: "1.45"
      }
    };
  }

  if (object.type === "route") {
    return {
      html: `
        <div class="professional-consumption-maplibre-tooltip-title">
          ${escapeHtml(object.source_label)} → ${escapeHtml(object.destination_label)}
        </div>
        <div class="professional-consumption-maplibre-tooltip-line">
          ${formatProfessionalSummaryInteger(object.tx_count || 0)} paiement(s) ·
          ${euro(object.volume || 0)} ·
          ${formatProfessionalSummaryInteger(object.distinct_users || 0)} particulier(s)
        </div>
      `,
      style: {
        backgroundColor: "rgba(15, 23, 42, 0.96)",
        color: "#ffffff",
        borderRadius: "12px",
        padding: "10px 12px",
        maxWidth: "420px",
        fontSize: "13px",
        lineHeight: "1.45"
      }
    };
  }

  return null;
}


/*
 * CARTO_UP004D_HOVER_FOCUS
 * Focus interactif :
 * - survol source rouge -> routes issues de cette source renforcées ;
 * - survol pro vert -> routes arrivant vers ce pro renforcées ;
 * - le reste devient fantôme.
 */
function getProfessionalConsumptionMapLibreHighlight() {
  return appState.professionalConsumptionMapLibreLockedHighlight
    || appState.professionalConsumptionMapLibreHighlight
    || null;
}

function getProfessionalConsumptionMapLibreHighlightKey(highlight) {
  if (!highlight || !highlight.type || !highlight.id) return "";
  return `${highlight.type}:${highlight.id}`;
}

function setProfessionalConsumptionMapLibreHighlight(highlight) {
  const nextKey = getProfessionalConsumptionMapLibreHighlightKey(highlight);
  const currentKey = getProfessionalConsumptionMapLibreHighlightKey(
    appState.professionalConsumptionMapLibreHighlight
  );

  if (nextKey === currentKey) {
    return;
  }

  appState.professionalConsumptionMapLibreHighlight = highlight || null;
  clearProfessionalConsumptionMapFocusMatchMemoCache();

  const overlay = appState.professionalConsumptionMapLibreOverlay;
  const data = appState.professionalConsumptionMapLibreData;

  if (!overlay || !data) {
    return;
  }

  cleanupProfessionalConsumptionMapStaleFocus(data);

  const layerConfig = buildProfessionalConsumptionMapLibreLayers(data);
  if (layerConfig?.layers) {
    overlay.setProps({ layers: layerConfig.layers });
  }

  if (nextKey) {
    startProfessionalConsumptionMapParticleAnimation();
  } else if (!appState.professionalConsumptionMapLibreLockedHighlight) {
    stopProfessionalConsumptionMapParticleAnimation();
  }
}

function clearProfessionalConsumptionMapLibreHighlight() {
  setProfessionalConsumptionMapLibreHighlight(null);
}

function setProfessionalConsumptionMapLibreLockedHighlight(highlight) {
  /*
   * CARTO_UP005E_LOCKED_FOCUS_ALL
   * CARTO_UP006C_ROAD_ONLY_ROUTES
   * Clic point source/pro = focus verrouillé.
   */
  const nextKey = getProfessionalConsumptionMapLibreHighlightKey(highlight);
  const currentKey = getProfessionalConsumptionMapLibreHighlightKey(
    appState.professionalConsumptionMapLibreLockedHighlight
  );

  if (nextKey === currentKey) {
    return;
  }

  appState.professionalConsumptionMapLibreLockedHighlight = highlight || null;
  clearProfessionalConsumptionMapFocusMatchMemoCache();
  appState.professionalConsumptionMapLibreHighlight = null;

  const overlay = appState.professionalConsumptionMapLibreOverlay;
  const data = appState.professionalConsumptionMapLibreData;

  if (!overlay || !data) {
    return;
  }

  const layerConfig = buildProfessionalConsumptionMapLibreLayers(data);
  if (layerConfig?.layers) {
    overlay.setProps({ layers: layerConfig.layers });
  }

  if (nextKey) {
    startProfessionalConsumptionMapParticleAnimation();
  } else {
    stopProfessionalConsumptionMapParticleAnimation();
  }

  // CARTO_UP009E_EASE_TO_LOCKED_POINT_CALL
  // Recentrage fluide uniquement si le focus vient d'un point cliqué.
  if (highlight && Array.isArray(highlight.center)) {
    easeProfessionalConsumptionMapLibreToLockedHighlight(highlight);
  }
}

function clearProfessionalConsumptionMapLibreLockedHighlight() {
  setProfessionalConsumptionMapLibreLockedHighlight(null);
}


/* CARTO_UP009D2_FIX_HOVER_PP_KEYS_ROBUST
 * Répare le hover/focus sur les couches mixtes U→P / P→P / P→U.
 * Les objets affichés peuvent utiliser source_key, destination_key, key,
 * professional_ref, professionalRef. Le focus doit comparer la clé rendue.
 */
function getProfessionalConsumptionMapRenderedSourceFocusId(object) {
  return String(
    object?.source_key
    || object?.sourceKey
    || object?.key
    || object?.professional_ref
    || object?.professionalRef
    || ""
  ).trim();
}

function getProfessionalConsumptionMapRenderedDestinationFocusId(object) {
  return String(
    object?.destination_key
    || object?.destinationKey
    || object?.key
    || object?.professional_ref
    || object?.professionalRef
    || ""
  ).trim();
}

function getProfessionalConsumptionMapRenderedRouteSourceFocusId(route) {
  return String(
    route?.sourceKey
    || route?.source_key
    || route?.source?.key
    || ""
  ).trim();
}

function getProfessionalConsumptionMapRenderedRouteDestinationFocusId(route) {
  return String(
    route?.professionalRef
    || route?.professional_ref
    || route?.destinationKey
    || route?.destination_key
    || route?.destination?.key
    || ""
  ).trim();
}

function getProfessionalConsumptionMapRenderedRouteFocusId(route) {
  return String(route?.id || "").trim();
}



/*
 * CARTO_UP009E_EASE_TO_LOCKED_POINT
 * Au clic sur un point U/P, on verrouille le filtre et on recentre doucement
 * la carte sur ce point. On ne le fait pas au survol, ni au rerender.
 */
function readProfessionalConsumptionMapObjectLngLat(object) {
  if (!object || typeof object !== "object") {
    return null;
  }

  const candidates = [
    [object.longitude, object.latitude],
    [object.lon, object.lat],
    [object.lng, object.lat],
    object.coordinates,
    object.position,
    object.sourcePosition,
    object.targetPosition
  ];

  for (const candidate of candidates) {
    if (!Array.isArray(candidate) || candidate.length < 2) {
      continue;
    }

    const longitude = Number(candidate[0]);
    const latitude = Number(candidate[1]);

    if (
      Number.isFinite(longitude)
      && Number.isFinite(latitude)
      && longitude >= -180
      && longitude <= 180
      && latitude >= -90
      && latitude <= 90
    ) {
      return [longitude, latitude];
    }
  }

  return null;
}

function attachProfessionalConsumptionMapHighlightCenter(highlight, object) {
  if (!highlight) {
    return null;
  }

  if (!["source", "professional"].includes(highlight.type)) {
    return highlight;
  }

  const center = readProfessionalConsumptionMapObjectLngLat(object);

  if (!center) {
    return highlight;
  }

  return {
    ...highlight,
    center
  };
}


/*
 * CARTO_UP009F_ADAPTIVE_LOCKED_ZOOM
 * Zoom fluide adapté à l'échelle du réseau filtré.
 * On utilise la médiane des distances pour éviter qu'un outlier force un
 * cadrage trop large.
 */
function getProfessionalConsumptionMapHaversineKm(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b)) {
    return 0;
  }

  const lon1 = Number(a[0]);
  const lat1 = Number(a[1]);
  const lon2 = Number(b[0]);
  const lat2 = Number(b[1]);

  if (
    !Number.isFinite(lon1)
    || !Number.isFinite(lat1)
    || !Number.isFinite(lon2)
    || !Number.isFinite(lat2)
  ) {
    return 0;
  }

  const radiusKm = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const rLat1 = lat1 * Math.PI / 180;
  const rLat2 = lat2 * Math.PI / 180;

  const value =
    Math.sin(dLat / 2) * Math.sin(dLat / 2)
    + Math.cos(rLat1) * Math.cos(rLat2)
    * Math.sin(dLon / 2) * Math.sin(dLon / 2);

  return radiusKm * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}

function getProfessionalConsumptionMapRouteCoordinatesForZoom(route) {
  const candidates = [
    route?.roadPath,
    route?.path,
    route?.coordinates
  ];

  for (const candidate of candidates) {
    if (Array.isArray(candidate) && candidate.length >= 2) {
      const clean = candidate
        .map((point) => [Number(point?.[0]), Number(point?.[1])])
        .filter((point) => (
          Number.isFinite(point[0])
          && Number.isFinite(point[1])
          && point[0] >= -180
          && point[0] <= 180
          && point[1] >= -90
          && point[1] <= 90
        ));

      if (clean.length >= 2) {
        return clean;
      }
    }
  }

  const source = Array.isArray(route?.sourcePosition)
    ? route.sourcePosition
    : null;

  const target = Array.isArray(route?.targetPosition)
    ? route.targetPosition
    : null;

  if (source && target) {
    return [source, target];
  }

  return [];
}

function getProfessionalConsumptionMapRouteDistanceKmForZoom(route) {
  const roadDistanceKm = Number(route?.road_distance_m || 0) / 1000;

  if (Number.isFinite(roadDistanceKm) && roadDistanceKm > 0) {
    return roadDistanceKm;
  }

  const coords = getProfessionalConsumptionMapRouteCoordinatesForZoom(route);

  if (coords.length >= 2) {
    return getProfessionalConsumptionMapHaversineKm(
      coords[0],
      coords[coords.length - 1]
    );
  }

  return 0;
}

function medianProfessionalConsumptionMapDistanceKm(routes) {
  const values = (routes || [])
    .map(getProfessionalConsumptionMapRouteDistanceKmForZoom)
    .filter((value) => Number.isFinite(value) && value > 0)
    .sort((a, b) => a - b);

  if (!values.length) {
    return 0;
  }

  const middle = Math.floor(values.length / 2);

  if (values.length % 2) {
    return values[middle];
  }

  return (values[middle - 1] + values[middle]) / 2;
}

function getProfessionalConsumptionMapAdaptiveMaxZoom(medianKm) {
  const distance = Number(medianKm || 0);

  if (distance <= 0.35) return 16.4;
  if (distance <= 0.8) return 15.8;
  if (distance <= 1.6) return 15.1;
  if (distance <= 3.0) return 14.4;
  if (distance <= 6.0) return 13.5;
  if (distance <= 12.0) return 12.5;
  if (distance <= 25.0) return 11.2;
  if (distance <= 50.0) return 10.2;
  return 9.2;
}

function isProfessionalConsumptionMapRouteInHighlight(route, highlight) {
  if (!route || !highlight?.type || !highlight?.id) {
    return false;
  }

  const highlightId = String(highlight.id || "");

  if (highlight.type === "route") {
    return String(route.id || "") === highlightId;
  }

  if (highlight.type === "source") {
    return getProfessionalConsumptionMapRenderedRouteSourceFocusId(route) === highlightId;
  }

  if (highlight.type === "professional") {
    return getProfessionalConsumptionMapRenderedRouteDestinationFocusId(route) === highlightId;
  }

  return false;
}

function getProfessionalConsumptionMapRoutesForLockedHighlight(highlight) {
  const data = appState.professionalConsumptionMapLibreData;

  if (!data || !Array.isArray(data.routes)) {
    return [];
  }

  return data.routes.filter((route) => (
    isProfessionalConsumptionMapRouteInHighlight(route, highlight)
  ));
}

function buildProfessionalConsumptionMapBoundsFromRoutesAndCenter(routes, center) {
  const points = [];

  if (Array.isArray(center)) {
    points.push(center);
  }

  (routes || []).forEach((route) => {
    getProfessionalConsumptionMapRouteCoordinatesForZoom(route).forEach((point) => {
      points.push(point);
    });
  });

  const clean = points
    .map((point) => [Number(point?.[0]), Number(point?.[1])])
    .filter((point) => (
      Number.isFinite(point[0])
      && Number.isFinite(point[1])
      && point[0] >= -180
      && point[0] <= 180
      && point[1] >= -90
      && point[1] <= 90
    ));

  if (!clean.length) {
    return null;
  }

  let minLon = clean[0][0];
  let maxLon = clean[0][0];
  let minLat = clean[0][1];
  let maxLat = clean[0][1];

  clean.forEach(([lon, lat]) => {
    minLon = Math.min(minLon, lon);
    maxLon = Math.max(maxLon, lon);
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
  });

  const lonPad = Math.max(0.0025, (maxLon - minLon) * 0.16);
  const latPad = Math.max(0.0025, (maxLat - minLat) * 0.16);

  return [
    [minLon - lonPad, minLat - latPad],
    [maxLon + lonPad, maxLat + latPad]
  ];
}

function getProfessionalConsumptionMapFitPaddingForLockedZoom() {
  return {
    top: 92,
    right: 92,
    bottom: 92,
    left: 92
  };
}


function easeProfessionalConsumptionMapLibreToLockedHighlight(highlight) {
  /*
   * CARTO_UP009F_ADAPTIVE_LOCKED_ZOOM
   * Clic point :
   * - on garde le recentrage fluide ;
   * - on ajoute un fitBounds fluide à l'échelle du réseau concerné ;
   * - zoom max déterminé par la distance médiane des routes impliquées.
   */
  const map = appState.professionalConsumptionMapLibreMap;

  if (!map || !highlight || !Array.isArray(highlight.center)) {
    return;
  }

  const longitude = Number(highlight.center[0]);
  const latitude = Number(highlight.center[1]);

  if (
    !Number.isFinite(longitude)
    || !Number.isFinite(latitude)
    || longitude < -180
    || longitude > 180
    || latitude < -90
    || latitude > 90
  ) {
    return;
  }

  if (typeof map.stop === "function") {
    map.stop();
  }

  const involvedRoutes = getProfessionalConsumptionMapRoutesForLockedHighlight(highlight);
  const medianKm = medianProfessionalConsumptionMapDistanceKm(involvedRoutes);
  const maxZoom = getProfessionalConsumptionMapAdaptiveMaxZoom(medianKm);
  const bounds = buildProfessionalConsumptionMapBoundsFromRoutesAndCenter(
    involvedRoutes,
    [longitude, latitude]
  );

  if (
    bounds
    && involvedRoutes.length > 0
    && typeof map.fitBounds === "function"
  ) {
    map.fitBounds(bounds, {
      padding: getProfessionalConsumptionMapFitPaddingForLockedZoom(),
      duration: 780,
      maxZoom,
      essential: true,
      easing: (t) => 1 - Math.pow(1 - t, 3)
    });
    return;
  }

  map.easeTo({
    center: [longitude, latitude],
    zoom: Math.max(
      typeof map.getZoom === "function" ? map.getZoom() : 12,
      14.2
    ),
    duration: 620,
    essential: true,
    easing: (t) => 1 - Math.pow(1 - t, 3)
  });
}


function getProfessionalConsumptionMapLibreObjectHighlight(object) {
  /*
   * CARTO_UP009E_EASE_TO_LOCKED_POINT
   * Retourne un highlight avec coordonnées pour les points cliquables.
   */
  if (!object || typeof object !== "object") {
    return null;
  }

  if (object.type === "route") {
    const id = String(object.id || "").trim();
    return id ? { type: "route", id } : null;
  }

  if (object.type === "source") {
    const id = String(
      object.source_key
      || object.sourceKey
      || object.key
      || object.professional_ref
      || object.professionalRef
      || ""
    ).trim();

    return id
      ? attachProfessionalConsumptionMapHighlightCenter({ type: "source", id }, object)
      : null;
  }

  if (object.type === "professional") {
    const id = String(
      object.destination_key
      || object.destinationKey
      || object.key
      || object.professional_ref
      || object.professionalRef
      || ""
    ).trim();

    return id
      ? attachProfessionalConsumptionMapHighlightCenter({ type: "professional", id }, object)
      : null;
  }

  return null;
}

function handleProfessionalConsumptionMapLibreHover(info) {
  /*
   * CARTO_UP005E_LOCKED_FOCUS_ALL
   * Si un focus est verrouillé par clic, le hover ne le remplace pas.
   */
  if (appState.professionalConsumptionMapLibreLockedHighlight) {
    return;
  }

  const object = info?.object || null;

  if (!object) {
    clearProfessionalConsumptionMapLibreHighlight();
    return;
  }

  const highlight = getProfessionalConsumptionMapLibreObjectHighlight(object);

  if (highlight?.type && highlight?.id) {
    setProfessionalConsumptionMapLibreHighlight(highlight);
  }
}

function handleProfessionalConsumptionMapLibreClick(info) {
  /*
   * Clic point source/pro = verrouillage.
   * Clic route = verrouillage route.
   * Clic vide = réinitialisation, via map.on("click") en fallback.
   */
  const object = info?.object || null;

  if (!object) {
    clearProfessionalConsumptionMapLibreLockedHighlight();
    clearProfessionalConsumptionMapLibreHighlight();
    return;
  }

  const highlight = getProfessionalConsumptionMapLibreObjectHighlight(object);

  if (highlight?.type && highlight?.id) {
    appState.professionalConsumptionMapLibreLastObjectClickAt = Date.now();
    setProfessionalConsumptionMapLibreLockedHighlight(highlight);
  }
}



/*
 * CARTO_UP006A_FLOW_PARTICLES
 * Particules animées dans le sens U→P sur le réseau sélectionné.
 *
 * Vitesse :
 * - idéalement tx_count / payment_day_count ;
 * - si payment_day_count n’existe pas encore dans le payload, fallback prudent.
 *
 * Taille / lumière :
 * - montant moyen = volume / tx_count ;
 * - < 5 : peu visible ;
 * - 5–20 : normal ;
 * - 20–50 : bonne visibilité ;
 * - 50–80 : visibilité accrue ;
 * - > 80 : visibilité max.
 */
function getProfessionalConsumptionMapRoutePaymentDayCount(route) {
  const directCandidates = [
    route?.payment_day_count,
    route?.payment_days_count,
    route?.days_with_payments,
    route?.active_payment_days,
    route?.paymentDayCount
  ];

  for (const value of directCandidates) {
    const numberValue = Number(value);
    if (Number.isFinite(numberValue) && numberValue > 0) {
      return numberValue;
    }
  }

  const timelineCandidates = [
    route?.timeline,
    route?.daily,
    route?.daily_counts,
    route?.payment_days
  ];

  for (const candidate of timelineCandidates) {
    if (Array.isArray(candidate)) {
      const count = candidate.filter((item) => {
        if (!item) return false;
        if (typeof item === "number") return item > 0;
        return Number(item.tx_count || item.count || item.payments || 0) > 0;
      }).length;

      if (count > 0) {
        return count;
      }
    }
  }

  // Fallback expérimental : évite de transformer une rafale d’un jour en fréquence infinie.
  return Math.max(
    1,
    Math.min(
      Number(route?.tx_count || route?.final_tx_count || 1),
      Number(route?.distinct_users || route?.tx_count || route?.final_tx_count || 1)
    )
  );
}

function getProfessionalConsumptionMapRouteAveragePayment(route) {
  const txCount = Math.max(
    1,
    Number(route?.tx_count || route?.final_tx_count || route?.visual_tx_count || 0)
  );

  const volume = Number(
    route?.volume || route?.final_volume || route?.visual_volume || 0
  );

  return volume / txCount;
}

function getProfessionalConsumptionMapParticleVisibility(avgPayment) {
  /*
   * CARTO_UP006F_THEME_AWARE_PARTICLES
   * Particules plus contrastées en mode clair, sans revenir au gros halo.
   *
   * Mode clair :
   * - coeur plus orange / or ;
   * - opacité renforcée ;
   * - rayon légèrement augmenté ;
   * - halo court mais plus visible.
   *
   * Mode sombre :
   * - rendu plus doux, mais lisible.
   */
  const value = Number(avgPayment || 0);
  const isDark = typeof isProfessionalConsumptionMapDarkTheme === "function"
    ? isProfessionalConsumptionMapDarkTheme()
    : true;

  const table = isDark
    ? [
        { max: 5, radius: 1.9, alpha: 95, glowAlpha: 14, glowRadiusFactor: 1.55, label: "low" },
        { max: 20, radius: 2.4, alpha: 120, glowAlpha: 18, glowRadiusFactor: 1.65, label: "normal" },
        { max: 50, radius: 3.0, alpha: 150, glowAlpha: 23, glowRadiusFactor: 1.75, label: "good" },
        { max: 80, radius: 3.6, alpha: 178, glowAlpha: 28, glowRadiusFactor: 1.85, label: "high" },
        { max: Infinity, radius: 4.3, alpha: 208, glowAlpha: 34, glowRadiusFactor: 1.95, label: "max" }
      ]
    : [
        { max: 5, radius: 2.4, alpha: 145, glowAlpha: 24, glowRadiusFactor: 1.45, label: "low" },
        { max: 20, radius: 3.0, alpha: 178, glowAlpha: 30, glowRadiusFactor: 1.55, label: "normal" },
        { max: 50, radius: 3.8, alpha: 212, glowAlpha: 38, glowRadiusFactor: 1.65, label: "good" },
        { max: 80, radius: 4.6, alpha: 235, glowAlpha: 46, glowRadiusFactor: 1.75, label: "high" },
        { max: Infinity, radius: 5.4, alpha: 252, glowAlpha: 56, glowRadiusFactor: 1.85, label: "max" }
      ];

  return table.find((item) => value < item.max) || table[table.length - 1];
}

function getProfessionalConsumptionMapPointAlongPath(path, progress) {
  if (!Array.isArray(path) || path.length < 2) {
    return null;
  }

  const validPath = path
    .map((point) => [Number(point?.[0]), Number(point?.[1])])
    .filter((point) => Number.isFinite(point[0]) && Number.isFinite(point[1]));

  if (validPath.length < 2) {
    return null;
  }

  const segments = [];
  let totalLength = 0;

  for (let index = 0; index < validPath.length - 1; index += 1) {
    const a = validPath[index];
    const b = validPath[index + 1];
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const length = Math.sqrt(dx * dx + dy * dy);

    if (length > 0) {
      segments.push({
        a,
        b,
        length
      });
      totalLength += length;
    }
  }

  if (!segments.length || totalLength <= 0) {
    return validPath[0];
  }

  let targetLength = totalLength * (
    ((Number(progress) % 1) + 1) % 1
  );

  for (const segment of segments) {
    if (targetLength <= segment.length) {
      const t = targetLength / segment.length;
      return [
        segment.a[0] + (segment.b[0] - segment.a[0]) * t,
        segment.a[1] + (segment.b[1] - segment.a[1]) * t
      ];
    }

    targetLength -= segment.length;
  }

  return validPath[validPath.length - 1];
}


/*
 * CARTO_UP010J_SEARCH_ROUTES_TRIGGER_PARTICLES
 * Les particules ne doivent pas dépendre uniquement du hover/clic deck.gl.
 * Quand un pro est sélectionné depuis la barre de recherche, toutes les routes
 * qui l'impliquent sont considérées comme actives pour l'animation.
 */
function isProfessionalConsumptionMapSearchFocusActive() {
  return Boolean(getProfessionalConsumptionMapSelectedProfessionalRef());
}

function isProfessionalConsumptionMapRouteInSearchFocus(route) {
  /*
   * CARTO_UP011E_FIX_SEARCH_REF_HIGHLIGHT
   */
  const ref = getProfessionalConsumptionMapSelectedSearchProfessionalRefStrict();

  if (!ref) {
    return false;
  }

  if (doesProfessionalConsumptionMapValueContainProfessionalRefLoose(route, ref)) {
    return true;
  }

  if (typeof doesProfessionalConsumptionMapObjectInvolveProfessional === "function") {
    return doesProfessionalConsumptionMapObjectInvolveProfessional(route, ref);
  }

  return false;
}


function buildProfessionalConsumptionMapParticleData(routePathData, isRouteHighlighted, options = {}) {
  // CARTO_CLUSTER_MAIN_PERF001B_PARTICLE_TOGGLE
  // CARTO_CLUSTER_MAIN_PERF003A_CANVAS_PARTICLES
  // Par défaut, les particules deck.gl sont désactivées :
  // l'animation fluide passe par un canvas 2D séparé.
  if (
    !options.forceCanvasSource
    && typeof shouldUseProfessionalConsumptionMapCanvasParticles === "function"
    && shouldUseProfessionalConsumptionMapCanvasParticles()
  ) {
    return [];
  }

  if (!shouldRunProfessionalConsumptionMapParticleAnimation()) {
    return [];
  }


  // CARTO_UP010J_SEARCH_ROUTES_TRIGGER_PARTICLES
  const shouldAnimateProfessionalConsumptionMapParticleRoute = (route) => {
    if (typeof isRouteHighlighted === "function" && isRouteHighlighted(route)) {
      return true;
    }

    if (isProfessionalConsumptionMapRouteInSearchFocus(route)) {
      return true;
    }

    return doesProfessionalConsumptionMapRouteMatchFocusedProfessional(route);
  };

  const highlight = getProfessionalConsumptionMapLibreHighlight();
  const hasSearchFocus = isProfessionalConsumptionMapSearchFocusActive();

  // CARTO_UP010K_SEARCH_FOCUS_STARTS_PARTICLES
  // La recherche pro filtre déjà les routes : elle doit donc aussi autoriser
  // les particules, même sans hover/clic deck.gl actif.
  // CARTO_UP010O_EXTRA_FLOWS_REQUIRE_PRO_FOCUS
  // Les particules exigent un vrai focus : hover/clic carte ou recherche pro.
  if ((!highlight?.type || !highlight?.id) && !hasSearchFocus) {
    return [];
  }

  const now = performance.now();

  // CARTO_CLUSTER_MAIN_PERF002A_THROTTLED_PARTICLES
  const animationSettings = getProfessionalConsumptionMapParticleAnimationSettings();
  const animatedRoutes = routePathData
    .filter((route) => shouldAnimateProfessionalConsumptionMapParticleRoute(route))
    .sort((a, b) => (
      getProfessionalConsumptionMapRouteAnimationWeight(b)
      - getProfessionalConsumptionMapRouteAnimationWeight(a)
    ))
    .slice(0, animationSettings.maxRoutes);

  return animatedRoutes
    .map((route, index) => {
      const path = Array.isArray(route.roadPath) && route.roadPath.length >= 2
        ? route.roadPath
        : null;

      if (!path) return null;

      const paymentDays = getProfessionalConsumptionMapRoutePaymentDayCount(route);
      const txCount = Number(route?.tx_count || route?.final_tx_count || route?.visual_tx_count || 0);
      const frequency = txCount / Math.max(1, paymentDays);

      const avgPayment = getProfessionalConsumptionMapRouteAveragePayment(route);
      const visibility = getProfessionalConsumptionMapParticleVisibility(avgPayment);

      // Plus la fréquence moyenne est forte, plus la particule va vite.
      const speedFactor = Math.max(
        0.45,
        Math.min(3.6, 0.55 + Math.log1p(frequency) * 0.68)
      );

      const phase = (
        Math.abs(hashStringToUnitInterval(String(route.id || index))) + index * 0.073
      ) % 1;

      const progress = ((now / 7200) * speedFactor + phase) % 1;
      const position = getProfessionalConsumptionMapPointAlongPath(path, progress);

      if (!position) return null;

      return {
        type: "particle",
        id: `particle:${route.id || index}`,
        route_id: route.id,
        sourceCode: route.sourceCode,
        sourceKey: route.sourceKey,
        professionalRef: route.professionalRef,
        position,
        frequency,
        avgPayment,
        radius: visibility.radius,
        alpha: visibility.alpha,
        glowAlpha: visibility.glowAlpha,
        glowRadiusFactor: visibility.glowRadiusFactor,
        visibilityLabel: visibility.label
      };
    })
    .filter(Boolean);
}

function hashStringToUnitInterval(value) {
  const text = String(value || "");
  let hash = 0;

  for (let index = 0; index < text.length; index += 1) {
    hash = ((hash << 5) - hash) + text.charCodeAt(index);
    hash |= 0;
  }

  return (Math.abs(hash) % 100000) / 100000;
}


/*
 * CARTO_UP010K_SEARCH_FOCUS_STARTS_PARTICLES
 * Démarrage différé : laisse le temps au render de recréer map/overlay/data.
 */






/* CARTO_CLUSTER_MAIN_PERF001_DISABLE_PARTICLES_BY_DEFAULT
 * Les particules/animations deck.gl sont désactivées par défaut.
 * Le profiler Firefox montrait une boucle coûteuse :
 * RefreshDriver tick → requestAnimationFrame → deck.gl setLayers/updateBuffer.
 *
 * Réactivation temporaire possible en console :
 *   appState.professionalConsumptionMapParticlesEnabled = true;
 *   startProfessionalConsumptionMapParticleAnimationSoon();
 */
function shouldRunProfessionalConsumptionMapParticleAnimation() {
  if (!appState) return false;

  if (typeof document !== "undefined" && document.hidden) {
    return false;
  }

  if (
    typeof window !== "undefined"
    && typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    return false;
  }

  return appState.professionalConsumptionMapParticlesEnabled !== false;
}



/* CARTO_CLUSTER_MAIN_PERF001B_PARTICLE_TOGGLE
 * OFF : particules masquées + aucune boucle animation.
 * ON  : particules visibles + animation requestAnimationFrame.
 */
function setProfessionalConsumptionMapParticlesEnabled(enabled) {
  /*
   * CARTO_CLUSTER_MAIN_PERF002C_NO_FULL_RERENDER_ON_TOGGLE
   * Ne pas relancer renderProfessionalConsumptionMapLibre() au toggle :
   * cela peut recréer/réinitialiser la carte et provoquer "WebGL context was lost".
   * On met seulement à jour les layers deck.gl existants.
   */
  appState.professionalConsumptionMapParticlesEnabled = Boolean(enabled);

  // CARTO_CLUSTER_MAIN_PERF003C_TOGGLE_AND_CANVAS_LIGHT
  updateProfessionalConsumptionMapParticleControlsUi();

  if (!appState.professionalConsumptionMapParticlesEnabled) {
    if (typeof stopProfessionalConsumptionMapParticleAnimation === "function") {
      stopProfessionalConsumptionMapParticleAnimation();
    }
  }

  const overlay = appState.professionalConsumptionMapLibreOverlay;
  const data = appState.professionalConsumptionMapLibreData;

  if (overlay && data && typeof buildProfessionalConsumptionMapLibreLayers === "function") {
    const layerConfig = buildProfessionalConsumptionMapLibreLayers(data);

    if (layerConfig?.layers) {
      overlay.setProps({ layers: layerConfig.layers });
    }
  }

  if (appState.professionalConsumptionMapParticlesEnabled) {
    if (typeof startProfessionalConsumptionMapParticleAnimationSoon === "function") {
      startProfessionalConsumptionMapParticleAnimationSoon();
    } else if (typeof startProfessionalConsumptionMapParticleAnimation === "function") {
      startProfessionalConsumptionMapParticleAnimation();
    }
  }
}

function ensureProfessionalConsumptionMapParticleControls() {
  const controls = document.querySelector(".professional-consumption-map-visual-controls");
  if (!controls) return;

  let node = controls.querySelector("[data-professional-consumption-map-particle-controls]");

  if (!node) {
    node = document.createElement("div");
    node.className = "professional-consumption-map-particle-controls";
    node.setAttribute("data-professional-consumption-map-particle-controls", "true");
    controls.appendChild(node);
  }

  const enabled = appState.professionalConsumptionMapParticlesEnabled !== false;

  node.innerHTML = `
    <button
      type="button"
      class="professional-consumption-map-chip ${enabled ? "is-active" : ""}"
      data-professional-consumption-map-particles-toggle
      aria-pressed="${enabled ? "true" : "false"}"
      title="Active ou désactive les particules animées. OFF réduit fortement la charge CPU/GPU."
    >
      Animation flux : ${enabled ? "ON" : "OFF"}
    </button>
  `;

  const button = node.querySelector("[data-professional-consumption-map-particles-toggle]");
  button?.addEventListener("click", () => {
    setProfessionalConsumptionMapParticlesEnabled(!(appState.professionalConsumptionMapParticlesEnabled !== false));
  });
}



/* CARTO_CLUSTER_MAIN_PERF003C_TOGGLE_AND_CANVAS_LIGHT
 * Met à jour le bouton sans rerender complet de la carte.
 */
function updateProfessionalConsumptionMapParticleControlsUi() {
  const button = document.querySelector("[data-professional-consumption-map-particles-toggle]");

  if (!button) {
    return;
  }

  const enabled = appState.professionalConsumptionMapParticlesEnabled !== false;

  button.classList.toggle("is-active", enabled);
  button.setAttribute("aria-pressed", enabled ? "true" : "false");
  button.textContent = `Animation flux : ${enabled ? "ON" : "OFF"}`;
}


/* CARTO_CLUSTER_MAIN_PERF002A_THROTTLED_PARTICLES
 * Animation volontairement plafonnée.
 * Avant : requestAnimationFrame continu + rebuild complet des layers deck.gl.
 * Après : FPS bas, routes animées limitées, arrêt automatique.
 */
function getProfessionalConsumptionMapParticleAnimationSettings() {
  // CARTO_CLUSTER_MAIN_PERF003C_TOGGLE_AND_CANVAS_LIGHT
  // Animation décorative : légère par défaut.
  return {
    fps: 12,
    maxRoutes: 24,
  // CARTO_CLUSTER_MAIN_PERF004A_ANIMATION_DEFAULT_ON
    maxRuntimeMs: 0
  };
}

function getProfessionalConsumptionMapRouteAnimationWeight(route) {
  return Math.max(
    Number(route?.visual_volume || route?.volume || route?.final_volume || 0),
    Number(route?.visual_tx_count || route?.tx_count || route?.final_tx_count || 0)
  );
}

function scheduleProfessionalConsumptionMapParticleAnimationTick(tick, delayMs) {
  if (!appState) return;

  const delay = Math.max(80, Number(delayMs || 160));

  appState.professionalConsumptionMapParticleAnimationTimeout = window.setTimeout(() => {
    appState.professionalConsumptionMapParticleAnimationTimeout = null;
    appState.professionalConsumptionMapParticleAnimationFrame =
      window.requestAnimationFrame(tick);
  }, delay);
}


/* CARTO_CLUSTER_MAIN_PERF003A_CANVAS_PARTICLES
 * Les routes/sources/destinations restent dans deck.gl.
 * Les particules animées sont dessinées sur un canvas 2D superposé.
 * Objectif : ne plus invalider les buffers WebGL deck.gl à chaque frame.
 */
function shouldUseProfessionalConsumptionMapCanvasParticles() {
  return true;
}

function ensureProfessionalConsumptionMapParticleCanvas() {
  const container = document.getElementById("professionalConsumptionMapLibre");

  if (!container) {
    return null;
  }

  if (getComputedStyle(container).position === "static") {
    container.style.position = "relative";
  }

  let canvas = container.querySelector("canvas[data-professional-consumption-map-particle-canvas='true']");

  if (!canvas) {
    canvas = document.createElement("canvas");
    canvas.setAttribute("data-professional-consumption-map-particle-canvas", "true");
    canvas.className = "professional-consumption-map-particle-canvas";
    canvas.style.position = "absolute";
    canvas.style.inset = "0";
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.pointerEvents = "none";
    canvas.style.zIndex = "8";
    canvas.style.mixBlendMode = "normal";
    container.appendChild(canvas);
  }

  const rect = container.getBoundingClientRect();
  const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
  const width = Math.max(1, Math.floor(rect.width * dpr));
  const height = Math.max(1, Math.floor(rect.height * dpr));

  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }

  canvas.dataset.dpr = String(dpr);

  return canvas;
}

function clearProfessionalConsumptionMapParticleCanvas() {
  const canvas = document.querySelector("canvas[data-professional-consumption-map-particle-canvas='true']");

  if (!canvas) {
    return;
  }

  const ctx = canvas.getContext("2d");

  if (!ctx) {
    return;
  }

  ctx.clearRect(0, 0, canvas.width, canvas.height);
}



/* CARTO_CLUSTER_MAIN_PERF003B_CANVAS_CAMERA_SYNC
 * Le canvas particules est séparé de deck.gl.
 * Pendant zoom/pan/resize, on le vide pour éviter un décalage visuel
 * entre les routes WebGL et les points canvas projetés.
 */
function suspendProfessionalConsumptionMapCanvasParticlesForCameraMove() {
  appState.professionalConsumptionMapCanvasParticlesCameraMoving = true;
  clearProfessionalConsumptionMapParticleCanvas();
}

function resumeProfessionalConsumptionMapCanvasParticlesAfterCameraMove() {
  appState.professionalConsumptionMapCanvasParticlesCameraMoving = false;

  if (appState.professionalConsumptionMapCanvasParticlesResumeTimeout) {
    window.clearTimeout(appState.professionalConsumptionMapCanvasParticlesResumeTimeout);
  }

  appState.professionalConsumptionMapCanvasParticlesResumeTimeout = window.setTimeout(() => {
    appState.professionalConsumptionMapCanvasParticlesResumeTimeout = null;

    if (
      appState.professionalConsumptionMapParticlesEnabled !== false
      && typeof startProfessionalConsumptionMapParticleAnimationSoon === "function"
    ) {
      startProfessionalConsumptionMapParticleAnimationSoon();
    }
  }, 120);
}

function bindProfessionalConsumptionMapCanvasParticleCameraSync(map) {
  if (!map || map.__professionalConsumptionMapCanvasParticleCameraSyncBound) {
    return;
  }

  map.__professionalConsumptionMapCanvasParticleCameraSyncBound = true;

  const suspend = () => {
    suspendProfessionalConsumptionMapCanvasParticlesForCameraMove();
  };

  const resume = () => {
    resumeProfessionalConsumptionMapCanvasParticlesAfterCameraMove();
  };

  [
    "movestart",
    "zoomstart",
    "dragstart",
    "rotatestart",
    "pitchstart"
  ].forEach((eventName) => {
    try {
      map.on(eventName, suspend);
    } catch (_err) {}
  });

  [
    "moveend",
    "zoomend",
    "dragend",
    "rotateend",
    "pitchend",
    "resize"
  ].forEach((eventName) => {
    try {
      map.on(eventName, resume);
    } catch (_err) {}
  });

  try {
    map.on("remove", () => {
      clearProfessionalConsumptionMapParticleCanvas();
      appState.professionalConsumptionMapCanvasParticlesCameraMoving = false;
      if (appState.professionalConsumptionMapCanvasParticlesResumeTimeout) {
        window.clearTimeout(appState.professionalConsumptionMapCanvasParticlesResumeTimeout);
        appState.professionalConsumptionMapCanvasParticlesResumeTimeout = null;
      }
    });
  } catch (_err) {}
}

function getProfessionalConsumptionMapCanvasParticleRoutePathData(data) {
  if (!data || !Array.isArray(data.routes)) {
    return [];
  }

  const flowState = typeof getProfessionalConsumptionMapFlowFamilyState === "function"
    ? getProfessionalConsumptionMapFlowFamilyState()
    : {};

  const cacheKey = [
    appState.professionalConsumptionMapPeriodKey || "",
    data.routes.length,
    flowState.U_TO_P === true ? "U1" : "U0",
    flowState.P_TO_P === true ? "PP1" : "PP0",
    flowState.P_TO_U === true ? "PU1" : "PU0"
  ].join("|");

  if (
    appState.professionalConsumptionMapCanvasParticleRoutePathCache
    && appState.professionalConsumptionMapCanvasParticleRoutePathCache.key === cacheKey
  ) {
    return appState.professionalConsumptionMapCanvasParticleRoutePathCache.routes;
  }

  const routes = data.routes
    .filter((route) => shouldProfessionalConsumptionMapRenderRoute(route))
    .map((route) => {
      const roadPath = Array.isArray(route.roadPath) && route.roadPath.length >= 2
        ? route.roadPath
        : Array.isArray(route.path) && route.path.length >= 2
          ? route.path
          : null;

      return {
        ...route,
        type: "route",
        flowFamily: getProfessionalConsumptionMapRouteFlowFamily(route),
        flow_family: getProfessionalConsumptionMapRouteFlowFamily(route),
        path: roadPath,
        roadPath,
        isRoadRouted: Boolean(roadPath)
      };
    })
    .filter((route) => route.isRoadRouted && Array.isArray(route.path) && route.path.length >= 2);

  appState.professionalConsumptionMapCanvasParticleRoutePathCache = {
    key: cacheKey,
    routes
  };

  return routes;
}

function drawProfessionalConsumptionMapCanvasParticles(particles) {
  // CARTO_CLUSTER_MAIN_PERF003B_CANVAS_CAMERA_SYNC
  if (appState.professionalConsumptionMapCanvasParticlesCameraMoving) {
    clearProfessionalConsumptionMapParticleCanvas();
    return;
  }

  const map = appState.professionalConsumptionMapLibreMap;
  const canvas = ensureProfessionalConsumptionMapParticleCanvas();

  if (!map || !canvas) {
    return;
  }

  const ctx = canvas.getContext("2d");

  if (!ctx) {
    return;
  }

  const dpr = Number(canvas.dataset.dpr || 1);

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!Array.isArray(particles) || !particles.length) {
    return;
  }

  const isDark = typeof isProfessionalConsumptionMapDarkTheme === "function"
    ? isProfessionalConsumptionMapDarkTheme()
    : false;

  particles.forEach((particle) => {
    if (!Array.isArray(particle.position) || particle.position.length < 2) {
      return;
    }

    let point = null;

    try {
      point = map.project([
        Number(particle.position[0]),
        Number(particle.position[1])
      ]);
    } catch (_err) {
      point = null;
    }

    if (!point) {
      return;
    }

    const x = Number(point.x) * dpr;
    const y = Number(point.y) * dpr;

    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return;
    }

    // CARTO_CLUSTER_MAIN_PERF003C_TOGGLE_AND_CANVAS_LIGHT
    // Dessin volontairement minimal : un seul cercle par particule.
    const radius = Math.max(2.5, Math.min(6, Number(particle.radius || 4))) * dpr;
    const alpha = Math.max(0.22, Math.min(0.80, Number(particle.alpha || 180) / 255));

    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = isDark
      ? `rgba(254, 240, 138, ${alpha})`
      : `rgba(234, 88, 12, ${alpha})`;
    ctx.fill();
  });
}

function startProfessionalConsumptionMapParticleAnimation() {
  // CARTO_CLUSTER_MAIN_PERF001_DISABLE_PARTICLES_BY_DEFAULT
  if (!shouldRunProfessionalConsumptionMapParticleAnimation()) {
    if (appState) {
      appState.professionalConsumptionMapParticlesEnabled = true;
    }
    if (typeof stopProfessionalConsumptionMapParticleAnimation === "function") {
      stopProfessionalConsumptionMapParticleAnimation();
    }
    return;
  }

  /*
   * CARTO_CLUSTER_MAIN_PERF002A_THROTTLED_PARTICLES
   * Une seule boucle, mais plafonnée.
   */
  if (
    appState.professionalConsumptionMapParticleAnimationFrame
    || appState.professionalConsumptionMapParticleAnimationTimeout
  ) {
    return;
  }

  const settings = getProfessionalConsumptionMapParticleAnimationSettings();
  const minFrameDelayMs = Math.max(80, 1000 / Math.max(1, settings.fps));

  appState.professionalConsumptionMapParticleAnimationStartedAt = performance.now();

  const tick = () => {
    appState.professionalConsumptionMapParticleAnimationFrame = null;

    if (!shouldRunProfessionalConsumptionMapParticleAnimation()) {
      stopProfessionalConsumptionMapParticleAnimation();
      return;
    }

    const now = performance.now();
    const startedAt = Number(appState.professionalConsumptionMapParticleAnimationStartedAt || now);

    if (now - startedAt > settings.maxRuntimeMs) {
      // CARTO_CLUSTER_MAIN_PERF003C_TOGGLE_AND_CANVAS_LIGHT
      appState.professionalConsumptionMapParticlesEnabled = false;
      updateProfessionalConsumptionMapParticleControlsUi();
      stopProfessionalConsumptionMapParticleAnimation();
      return;
    }

    const overlay = appState.professionalConsumptionMapLibreOverlay;
    const data = appState.professionalConsumptionMapLibreData;
    const highlight = getProfessionalConsumptionMapLibreHighlight();
    const hasSearchFocus = isProfessionalConsumptionMapSearchFocusActive();
    const identity = getProfessionalConsumptionMapFocusedProfessionalIdentity();

    const hasFocus = Boolean(
      hasSearchFocus
      || (highlight?.type && highlight?.id)
      || identity.ref
      || identity.keys.size
      || identity.refs.size
    );

    if (!overlay || !data || !hasFocus) {
      stopProfessionalConsumptionMapParticleAnimation();
      return;
    }

    // CARTO_CLUSTER_MAIN_PERF003A_CANVAS_PARTICLES
    // Ne plus reconstruire les couches deck.gl à chaque tick.
    // On ne redessine que les particules sur canvas 2D.
    const routePathData = getProfessionalConsumptionMapCanvasParticleRoutePathData(data);
    const particleData = buildProfessionalConsumptionMapParticleData(
      routePathData,
      (route) => doesProfessionalConsumptionMapRouteMatchFocusedProfessional(route),
      { forceCanvasSource: true }
    );

    drawProfessionalConsumptionMapCanvasParticles(particleData);

    scheduleProfessionalConsumptionMapParticleAnimationTick(tick, minFrameDelayMs);
  };

  scheduleProfessionalConsumptionMapParticleAnimationTick(tick, 0);
}


function stopProfessionalConsumptionMapParticleAnimation() {
  const frame = appState.professionalConsumptionMapParticleAnimationFrame;
  const timeout = appState.professionalConsumptionMapParticleAnimationTimeout;

  if (frame) {
    window.cancelAnimationFrame(frame);
  }

  if (timeout) {
    window.clearTimeout(timeout);
  }

  appState.professionalConsumptionMapParticleAnimationFrame = null;
  appState.professionalConsumptionMapParticleAnimationTimeout = null;
  appState.professionalConsumptionMapParticleAnimationStartedAt = null;

  // CARTO_CLUSTER_MAIN_PERF003A_CANVAS_PARTICLES
  clearProfessionalConsumptionMapParticleCanvas();
}




/*
 * CARTO_UP010N_FIX_PP_ROUTE_VISIBILITY
 * Normalisation robuste des familles de flux pour éviter que P→P/P→U
 * soient présents dans les données mais invisibles dans les couches.
 */
function getProfessionalConsumptionMapRouteFlowFamily(route) {
  return String(
    route?.flow_family
    || route?.flowFamily
    || route?.family
    || route?.route_family
    || route?.flow
    || "U_TO_P"
  ).trim().toUpperCase();
}

function isProfessionalConsumptionMapFlowFamilyEnabledForRoute(route) {
  const family = getProfessionalConsumptionMapRouteFlowFamily(route);
  const enabled = getProfessionalConsumptionMapEnabledFlowFamilies();

  if (!enabled || !enabled.size) {
    return family === "U_TO_P";
  }

  return enabled.has(family);
}

function isProfessionalConsumptionMapSyntheticAnchorRoute(route) {
  return Boolean(route?.search_anchor_route || route?.is_search_anchor_route);
}


/*
 * CARTO_UP010O_EXTRA_FLOWS_REQUIRE_PRO_FOCUS
 * Pour P→P/P→U, on ne rend les routes que si un professionnel est
 * explicitement survolé, cliqué ou recherché.
 */


/*
 * CARTO_UP010P_EXTRA_FOCUS_MATCH_KEYS
 * Identité complète du pro focus : ref Pxxxx + clés internes deck/map.
 */









/*
 * CARTO_UP011G_DEDUP_FOCUS_AND_PARTICLES
 * Source unique de vérité pour savoir quel professionnel est focus.
 */
function getProfessionalConsumptionMapFocusedProfessionalIdentity() {
  const refs = new Set();
  const keys = new Set();
  const labels = new Set();

  const addValue = (value) => {
    const text = String(value || "").trim();

    if (!text) {
      return;
    }

    const refMatches = text.match(/\bP[0-9]{4,}\b/g) || [];
    refMatches.forEach((ref) => refs.add(ref));

    keys.add(text);

    if (text.length >= 2 && text.length <= 180) {
      labels.add(text);
    }
  };

  const scan = (value, depth = 0, seen = new WeakSet()) => {
    if (value === null || value === undefined || depth > 6) {
      return;
    }

    if (typeof value === "string" || typeof value === "number") {
      addValue(value);
      return;
    }

    if (typeof value === "boolean" || typeof value === "function") {
      return;
    }

    if (Array.isArray(value)) {
      value.forEach((item) => scan(item, depth + 1, seen));
      return;
    }

    if (typeof value === "object") {
      if (seen.has(value)) {
        return;
      }

      seen.add(value);

      [
        "id",
        "key",
        "type",
        "sourceKey",
        "destinationKey",
        "source_key",
        "destination_key",
        "professional_ref",
        "professionalRef",
        "sourceProfessionalRef",
        "destinationProfessionalRef",
        "label",
        "name",
        "display_label",
        "professional_label",
        "source_label",
        "destination_label",
        "source_label_full",
        "destination_label_full"
      ].forEach((field) => {
        if (Object.prototype.hasOwnProperty.call(value, field)) {
          scan(value[field], depth + 1, seen);
        }
      });
    }
  };

  const searchRef = String(
    typeof getProfessionalConsumptionMapSelectedProfessionalRef === "function"
      ? getProfessionalConsumptionMapSelectedProfessionalRef()
      : ""
  ).trim();

  scan(searchRef);

  [
    typeof getProfessionalConsumptionMapLibreHighlight === "function"
      ? getProfessionalConsumptionMapLibreHighlight()
      : null,
    appState?.professionalConsumptionMapLibreHighlight,
    appState?.professionalConsumptionMapLibreLockedHighlight
  ].forEach((highlight) => scan(highlight));

  const data = appState?.professionalConsumptionMapLibreData || null;
  const points = [
    ...(Array.isArray(data?.destinations) ? data.destinations : []),
    ...(Array.isArray(data?.sources) ? data.sources : [])
  ];

  const highlight = typeof getProfessionalConsumptionMapLibreHighlight === "function"
    ? getProfessionalConsumptionMapLibreHighlight()
    : appState?.professionalConsumptionMapLibreHighlight;

  const highlightCenter = Array.isArray(highlight?.center)
    ? highlight.center
    : Array.isArray(highlight?.position)
      ? highlight.position
      : null;

  const pointMatchesFocus = (point) => {
    if (!point || typeof point !== "object") {
      return false;
    }

    const values = [
      point.id,
      point.key,
      point.sourceKey,
      point.destinationKey,
      point.source_key,
      point.destination_key,
      point.professional_ref,
      point.professionalRef,
      point.label,
      point.name,
      point.display_label,
      point.professional_label
    ].map((value) => String(value || "").trim()).filter(Boolean);

    for (const value of values) {
      if (keys.has(value) || labels.has(value)) {
        return true;
      }

      const ref = (value.match(/\bP[0-9]{4,}\b/) || [])[0];
      if (ref && refs.has(ref)) {
        return true;
      }
    }

    if (highlightCenter) {
      const lon = Number(point.longitude ?? point.lon ?? point.lng);
      const lat = Number(point.latitude ?? point.lat);
      const hLon = Number(highlightCenter[0]);
      const hLat = Number(highlightCenter[1]);

      if (
        Number.isFinite(lon)
        && Number.isFinite(lat)
        && Number.isFinite(hLon)
        && Number.isFinite(hLat)
        && Math.abs(lon - hLon) <= 0.00035
        && Math.abs(lat - hLat) <= 0.00035
      ) {
        return true;
      }
    }

    return false;
  };

  points.forEach((point) => {
    if (pointMatchesFocus(point)) {
      scan(point);
    }
  });

  return {
    ref: Array.from(refs)[0] || "",
    refs,
    keys,
    labels
  };
}

function getProfessionalConsumptionMapFocusedProfessionalRef() {
  const identity = getProfessionalConsumptionMapFocusedProfessionalIdentity();
  return identity.ref || "";
}

function doesProfessionalConsumptionMapRouteMatchFocusedProfessionalByKey(route, identity) {
  if (!route || !identity) {
    return false;
  }

  const values = [
    route.id,
    route.key,
    route.sourceKey,
    route.destinationKey,
    route.source_key,
    route.destination_key,
    route.base_route_id,
    route.professional_ref,
    route.professionalRef,
    route.sourceProfessionalRef,
    route.destinationProfessionalRef,
    route.source_label,
    route.destination_label,
    route.source_label_full,
    route.destination_label_full,
    route?.source?.id,
    route?.source?.key,
    route?.source?.sourceKey,
    route?.source?.destinationKey,
    route?.source?.source_key,
    route?.source?.destination_key,
    route?.source?.professional_ref,
    route?.source?.professionalRef,
    route?.source?.label,
    route?.source?.name,
    route?.source?.display_label,
    route?.source?.professional_label,
    route?.destination?.id,
    route?.destination?.key,
    route?.destination?.sourceKey,
    route?.destination?.destinationKey,
    route?.destination?.source_key,
    route?.destination?.destination_key,
    route?.destination?.professional_ref,
    route?.destination?.professionalRef,
    route?.destination?.label,
    route?.destination?.name,
    route?.destination?.display_label,
    route?.destination?.professional_label
  ].map((value) => String(value || "").trim()).filter(Boolean);

  for (const value of values) {
    if (identity.keys.has(value) || identity.labels.has(value)) {
      return true;
    }

    const refs = value.match(/\bP[0-9]{4,}\b/g) || [];
    if (refs.some((ref) => identity.refs.has(ref))) {
      return true;
    }
  }

  return false;
}

function doesProfessionalConsumptionMapRouteMatchFocusedProfessional(route) {
  /*
   * CARTO_UP011G_DEDUP_FOCUS_AND_PARTICLES
   * Matching unique pour recherche, survol et clic.
   */
  const selectedSearchRef =
    typeof getProfessionalConsumptionMapSelectedSearchProfessionalRefStrict === "function"
      ? getProfessionalConsumptionMapSelectedSearchProfessionalRefStrict()
      : "";

  if (selectedSearchRef) {
    if (
      typeof doesProfessionalConsumptionMapValueContainProfessionalRefLoose === "function"
      && doesProfessionalConsumptionMapValueContainProfessionalRefLoose(route, selectedSearchRef)
    ) {
      return true;
    }

    if (
      typeof doesProfessionalConsumptionMapObjectInvolveProfessional === "function"
      && doesProfessionalConsumptionMapObjectInvolveProfessional(route, selectedSearchRef)
    ) {
      return true;
    }
  }

  const identity = getProfessionalConsumptionMapFocusedProfessionalIdentity();

  if (!identity.ref && !identity.refs.size && !identity.keys.size && !identity.labels.size) {
    return false;
  }

  if (typeof doesProfessionalConsumptionMapObjectInvolveProfessional === "function") {
    for (const ref of identity.refs) {
      if (doesProfessionalConsumptionMapObjectInvolveProfessional(route, ref)) {
        return true;
      }
    }
  }

  if (typeof doesProfessionalConsumptionMapValueContainProfessionalRefLoose === "function") {
    for (const ref of identity.refs) {
      if (doesProfessionalConsumptionMapValueContainProfessionalRefLoose(route, ref)) {
        return true;
      }
    }
  }

  return doesProfessionalConsumptionMapRouteMatchFocusedProfessionalByKey(route, identity);
}


function isProfessionalConsumptionMapExtraFlowFamily(route) {
  const family = getProfessionalConsumptionMapRouteFlowFamily(route);
  return family === "P_TO_P" || family === "P_TO_U";
}

function shouldProfessionalConsumptionMapRenderExtraRoute(route) {
  if (!isProfessionalConsumptionMapExtraFlowFamily(route)) {
    return true;
  }

  return doesProfessionalConsumptionMapRouteMatchFocusedProfessional(route);
}


function shouldProfessionalConsumptionMapRenderRoute(route) {
  /*
   * CARTO_UP011G_DEDUP_FOCUS_AND_PARTICLES
   * U→P : vue globale.
   * P→P/P→U : seulement routes du pro focus.
   */
  if (!route || isProfessionalConsumptionMapSyntheticAnchorRoute(route)) {
    return false;
  }

  if (!isProfessionalConsumptionMapFlowFamilyEnabledForRoute(route)) {
    return false;
  }

  const path = Array.isArray(route.roadPath) && route.roadPath.length >= 2
    ? route.roadPath
    : Array.isArray(route.path) && route.path.length >= 2
      ? route.path
      : null;

  if (!path) {
    return false;
  }

  const family = getProfessionalConsumptionMapRouteFlowFamily(route);

  if (family === "U_TO_P") {
    return true;
  }

  return doesProfessionalConsumptionMapRouteMatchFocusedProfessional(route);
}

function getProfessionalConsumptionMapRouteFamilyColor(route, alpha = 190) {
  const family = getProfessionalConsumptionMapRouteFlowFamily(route);

  if (family === "P_TO_P") {
    return [14, 165, 233, alpha]; // bleu/cyan
  }

  if (family === "P_TO_U") {
    return [236, 72, 153, alpha]; // rose
  }

  if (family === "SEARCH") {
    return [148, 163, 184, alpha];
  }

  return [249, 115, 22, alpha]; // orange U→P
}

function getProfessionalConsumptionMapRouteFamilyGlowColor(route, alpha = 58) {
  const family = getProfessionalConsumptionMapRouteFlowFamily(route);

  if (family === "P_TO_P") {
    return [56, 189, 248, alpha];
  }

  if (family === "P_TO_U") {
    return [244, 114, 182, alpha];
  }

  if (family === "SEARCH") {
    return [148, 163, 184, alpha];
  }

  return [251, 146, 60, alpha];
}



/*
 * CARTO_UP011B_PP_KEEP_POINTS_FIX_PARTICLE_GATE
 * Une vue extra-flux seule conserve les points de contexte visibles.
 * Les routes/particules restent filtrées par focus ailleurs.
 */
function isProfessionalConsumptionMapExtraFlowOnlyView() {
  const enabled = getProfessionalConsumptionMapEnabledFlowFamilies();

  return Boolean(
    enabled
    && enabled.size > 0
    && !enabled.has("U_TO_P")
    && (enabled.has("P_TO_P") || enabled.has("P_TO_U"))
  );
}



/*
 * CARTO_UP011E_FIX_SEARCH_REF_HIGHLIGHT
 * La recherche pro doit matcher directement la ref Pxxxx dans les routes,
 * sans dépendre du highlightId MapLibre/Deck.gl.
 */
function getProfessionalConsumptionMapSelectedSearchProfessionalRefStrict() {
  const ref = String(
    typeof getProfessionalConsumptionMapSelectedProfessionalRef === "function"
      ? getProfessionalConsumptionMapSelectedProfessionalRef()
      : ""
  ).trim();

  return /^P[0-9]{4,}$/.test(ref) ? ref : "";
}

function doesProfessionalConsumptionMapValueContainProfessionalRefLoose(value, professionalRef, seen = new WeakSet(), depth = 0) {
  const ref = String(professionalRef || "").trim();

  if (!/^P[0-9]{4,}$/.test(ref)) {
    return false;
  }

  if (value === null || value === undefined || depth > 6) {
    return false;
  }

  if (typeof value === "string" || typeof value === "number") {
    return String(value).includes(ref);
  }

  if (typeof value === "boolean" || typeof value === "function") {
    return false;
  }

  if (Array.isArray(value)) {
    return value.some((item) => (
      doesProfessionalConsumptionMapValueContainProfessionalRefLoose(item, ref, seen, depth + 1)
    ));
  }

  if (typeof value === "object") {
    if (seen.has(value)) {
      return false;
    }

    seen.add(value);

    return Object.entries(value).some(([key, item]) => {
      // Évite de parcourir les grosses géométries GPS.
      if (
        key === "roadPath"
        || key === "path"
        || key === "coordinates"
        || key === "sourcePosition"
        || key === "targetPosition"
      ) {
        return false;
      }

      return doesProfessionalConsumptionMapValueContainProfessionalRefLoose(item, ref, seen, depth + 1);
    });
  }

  return false;
}



/* CARTO_CLUSTER_MAIN_PERF002B_FOCUS_MATCH_CACHE
 * Le profiler montre des dizaines de milliers d'appels à :
 * - getProfessionalConsumptionMapFocusedProfessionalIdentity()
 * - doesProfessionalConsumptionMapRouteMatchFocusedProfessional(route)
 *
 * Ces valeurs ne changent pas à chaque accessor deck.gl.
 * On les mémoïse par état de focus + période + familles de flux.
 */
const professionalConsumptionMapFocusMatchMemoCache = {
  key: "",
  identity: null,
  routeMatches: new Map()
};

function getProfessionalConsumptionMapFocusMatchMemoKey() {
  let selectedRef = "";
  let highlightKey = "";
  let lockedHighlightKey = "";
  let selectedSource = "";
  let periodKey = "";
  let flowKey = "";

  try {
    selectedRef = typeof getProfessionalConsumptionMapSelectedSearchProfessionalRefStrict === "function"
      ? String(getProfessionalConsumptionMapSelectedSearchProfessionalRefStrict() || "")
      : "";
  } catch (_err) {
    selectedRef = "";
  }

  try {
    highlightKey = typeof getProfessionalConsumptionMapLibreHighlightKey === "function"
      ? String(getProfessionalConsumptionMapLibreHighlightKey(getProfessionalConsumptionMapLibreHighlight()) || "")
      : "";
  } catch (_err) {
    highlightKey = "";
  }

  try {
    lockedHighlightKey = typeof getProfessionalConsumptionMapLibreHighlightKey === "function"
      ? String(getProfessionalConsumptionMapLibreHighlightKey(appState.professionalConsumptionMapLibreLockedHighlight) || "")
      : "";
  } catch (_err) {
    lockedHighlightKey = "";
  }

  try {
    selectedSource = String(appState.professionalConsumptionMapSelectedSourcePostalCode || "");
  } catch (_err) {
    selectedSource = "";
  }

  try {
    periodKey = String(appState.professionalConsumptionMapPeriodKey || "");
  } catch (_err) {
    periodKey = "";
  }

  try {
    const flowState = typeof getProfessionalConsumptionMapFlowFamilyState === "function"
      ? getProfessionalConsumptionMapFlowFamilyState()
      : {};

    flowKey = [
      flowState.U_TO_P === true ? "U1" : "U0",
      flowState.P_TO_P === true ? "PP1" : "PP0",
      flowState.P_TO_U === true ? "PU1" : "PU0"
    ].join("|");
  } catch (_err) {
    flowKey = "";
  }

  return [
    selectedRef,
    highlightKey,
    lockedHighlightKey,
    selectedSource,
    periodKey,
    flowKey
  ].join("§");
}

function clearProfessionalConsumptionMapFocusMatchMemoCache() {
  professionalConsumptionMapFocusMatchMemoCache.key = "";
  professionalConsumptionMapFocusMatchMemoCache.identity = null;
  professionalConsumptionMapFocusMatchMemoCache.routeMatches.clear();
}

function ensureProfessionalConsumptionMapFocusMatchMemoCache() {
  const key = getProfessionalConsumptionMapFocusMatchMemoKey();

  if (professionalConsumptionMapFocusMatchMemoCache.key !== key) {
    professionalConsumptionMapFocusMatchMemoCache.key = key;
    professionalConsumptionMapFocusMatchMemoCache.identity = null;
    professionalConsumptionMapFocusMatchMemoCache.routeMatches.clear();
  }

  return professionalConsumptionMapFocusMatchMemoCache;
}

function getProfessionalConsumptionMapRouteMatchMemoKey(route) {
  if (!route || typeof route !== "object") {
    return "null";
  }

  return [
    route.id,
    route.sourceKey,
    route.source_key,
    route.destinationKey,
    route.destination_key,
    route.professionalRef,
    route.professional_ref,
    route.flowFamily,
    route.flow_family,
    route.kind
  ].map((value) => String(value || "")).join("§");
}

if (
  typeof getProfessionalConsumptionMapFocusedProfessionalIdentity === "function"
  && !getProfessionalConsumptionMapFocusedProfessionalIdentity.__perf002bMemoized
) {
  const baseGetProfessionalConsumptionMapFocusedProfessionalIdentity =
    getProfessionalConsumptionMapFocusedProfessionalIdentity;

  getProfessionalConsumptionMapFocusedProfessionalIdentity = function(...args) {
    const cache = ensureProfessionalConsumptionMapFocusMatchMemoCache();

    if (cache.identity) {
      return cache.identity;
    }

    cache.identity = baseGetProfessionalConsumptionMapFocusedProfessionalIdentity.apply(this, args);
    return cache.identity;
  };

  getProfessionalConsumptionMapFocusedProfessionalIdentity.__perf002bMemoized = true;
}

if (
  typeof doesProfessionalConsumptionMapRouteMatchFocusedProfessional === "function"
  && !doesProfessionalConsumptionMapRouteMatchFocusedProfessional.__perf002bMemoized
) {
  const baseDoesProfessionalConsumptionMapRouteMatchFocusedProfessional =
    doesProfessionalConsumptionMapRouteMatchFocusedProfessional;

  doesProfessionalConsumptionMapRouteMatchFocusedProfessional = function(route, ...args) {
    const cache = ensureProfessionalConsumptionMapFocusMatchMemoCache();
    const routeKey = getProfessionalConsumptionMapRouteMatchMemoKey(route);

    if (cache.routeMatches.has(routeKey)) {
      return cache.routeMatches.get(routeKey);
    }

    const result = baseDoesProfessionalConsumptionMapRouteMatchFocusedProfessional.call(this, route, ...args);
    cache.routeMatches.set(routeKey, result);
    return result;
  };

  doesProfessionalConsumptionMapRouteMatchFocusedProfessional.__perf002bMemoized = true;
}

function buildProfessionalConsumptionMapLibreLayers(data) {
  /*
   * CARTO_UP005E_LOCKED_FOCUS_ALL
   *
   * Règle visuelle :
   * - sans focus : réseau complet visible ;
   * - hover ou clic source : seuls cette source, ses routes et ses pros restent visibles ;
   * - hover ou clic pro : seuls ce pro, ses routes et ses sources restent visibles ;
   * - les U/P non concernés disparaissent.
   */
  const {
    MapboxOverlay,
    PathLayer,
    ScatterplotLayer
  } = window.deck || {};

  if (!ScatterplotLayer || !PathLayer) {
    return null;
  }

  const highlight = getProfessionalConsumptionMapLibreHighlight();
  const highlightType = highlight?.type || "";
  const highlightId = highlight?.id || "";
  const hasActiveHighlight = Boolean(highlightType && highlightId);

  const maxRouteVolume = Math.max(
    1,
    ...data.routes.map((route) => Number(route.visual_volume || route.volume || 0))
  );

  const sourceRawScores = data.sources.map((source) => (
    Number(source.tx_count || 0) * Number(source.volume || 0)
  ));
  const sourceLogScores = sourceRawScores.map((value) => Math.log1p(value));
  const maxSourceLogScore = Math.max(1, ...sourceLogScores);

  const destinationVolumes = data.destinations.map((destination) => Number(destination.volume || 0));
  const destinationLogVolumes = destinationVolumes.map((value) => Math.log1p(value));
  const maxDestinationLogVolume = Math.max(1, ...destinationLogVolumes);

  /*
   * CARTO_UP006C_ROAD_ONLY_ROUTES
   * On ne dessine plus les lignes directes fallback.
   * Une route apparaît uniquement quand OSRM a fourni une vraie polyline routière.
   */
  /*
   * CARTO_UP010N2_PATCH_ROUTEPATHDATA_PP
   * routePathData doit respecter les familles cochées.
   * Sans ça, P→P/P→U peuvent être présents dans data.routes mais invisibles.
   */
  const routePathData = data.routes
    .filter((route) => shouldProfessionalConsumptionMapRenderRoute(route))
    .map((route) => {
      const roadPath = Array.isArray(route.roadPath) && route.roadPath.length >= 2
        ? route.roadPath
        : Array.isArray(route.path) && route.path.length >= 2
          ? route.path
          : null;

      return {
        ...route,
        type: "route",
        flowFamily: getProfessionalConsumptionMapRouteFlowFamily(route),
        flow_family: getProfessionalConsumptionMapRouteFlowFamily(route),
        path: roadPath,
        roadPath,
        isRoadRouted: Boolean(roadPath)
      };
    })
    .filter((route) => route.isRoadRouted && Array.isArray(route.path) && route.path.length >= 2);

  const routeById = new Map();
  const professionalRefsBySource = new Map();
  const sourceKeysByProfessional = new Map();

  // CARTO_UP010N2_PATCH_ROUTEPATHDATA_PP
  routePathData.forEach((route) => {
    routeById.set(String(route.id || ""), route);

    const routeSourceKey = getProfessionalConsumptionMapRenderedRouteSourceFocusId(route);
    const routeDestinationKey = getProfessionalConsumptionMapRenderedRouteDestinationFocusId(route);

    if (routeSourceKey && routeDestinationKey) {
      if (!professionalRefsBySource.has(routeSourceKey)) {
        professionalRefsBySource.set(routeSourceKey, new Set());
      }
      professionalRefsBySource.get(routeSourceKey).add(routeDestinationKey);

      if (!sourceKeysByProfessional.has(routeDestinationKey)) {
        sourceKeysByProfessional.set(routeDestinationKey, new Set());
      }
      sourceKeysByProfessional.get(routeDestinationKey).add(routeSourceKey);
    }
  });

  function clamp01(value) {
    return Math.max(0, Math.min(1, value));
  }

  function getSourceKey(source) {
    return String(source.source_key || source.postal_code || "").trim();
  }

  function getProfessionalRef(destination) {
    return String(destination.professional_ref || "").trim();
  }

  function getSourceIntensity(source) {
    const raw = Number(source.tx_count || 0) * Number(source.volume || 0);
    return clamp01(Math.log1p(raw) / maxSourceLogScore);
  }

  function getDestinationIntensity(destination) {
    return clamp01(Math.log1p(Number(destination.volume || 0)) / maxDestinationLogVolume);
  }

  function getRouteIntensity(route) {
    return clamp01(Math.sqrt(Number(route.visual_volume || route.volume || 0) / maxRouteVolume));
  }

  function isRouteHighlighted(route) {
    if (!hasActiveHighlight) return true;

    /*
     * CARTO_UP011E_FIX_SEARCH_REF_HIGHLIGHT
     * Priorité absolue : recherche pro active.
     * Si P0010 est recherché, toute route contenant P0010 est active.
     */
    const selectedSearchRef = getProfessionalConsumptionMapSelectedSearchProfessionalRefStrict();

    if (
      selectedSearchRef
      && doesProfessionalConsumptionMapValueContainProfessionalRefLoose(route, selectedSearchRef)
    ) {
      return true;
    }

    if (doesProfessionalConsumptionMapRouteMatchFocusedProfessional(route)) {
      return true;
    }

    if (highlightType === "source") {
      return getProfessionalConsumptionMapRenderedRouteSourceFocusId(route) === highlightId;
    }

    if (highlightType === "professional") {
      return getProfessionalConsumptionMapRenderedRouteDestinationFocusId(route) === highlightId;
    }

    if (highlightType === "route") {
      return String(route.id || "") === highlightId;
    }

    return true;
  }

  function isSourceHighlighted(source) {
    if (!hasActiveHighlight) return true;

    const sourceKey = getProfessionalConsumptionMapRenderedSourceFocusId(source)
      || getSourceKey(source);

    /*
     * CARTO_UP011E_FIX_SEARCH_REF_HIGHLIGHT
     * En recherche pro, garder visibles les sources des routes du pro.
     */
    const selectedSearchRef = getProfessionalConsumptionMapSelectedSearchProfessionalRefStrict();

    if (selectedSearchRef) {
      return routePathData.some((route) => {
        const routeSourceKey = String(
          route.sourceKey
          || route.source_key
          || route?.source?.key
          || route?.source?.id
          || ""
        );

        return (
          routeSourceKey === sourceKey
          && doesProfessionalConsumptionMapValueContainProfessionalRefLoose(route, selectedSearchRef)
        );
      });
    }

    if (highlightType === "source") {
      return sourceKey === highlightId;
    }

    if (highlightType === "professional") {
      return Boolean(sourceKeysByProfessional.get(highlightId)?.has(sourceKey));
    }

    if (highlightType === "route") {
      const route = routeById.get(highlightId);
      return route ? String(route.sourceKey || "") === sourceKey : false;
    }

    return true;
  }

  function isDestinationHighlighted(destination) {
    if (!hasActiveHighlight) return true;

    const professionalRef = getProfessionalConsumptionMapRenderedDestinationFocusId(destination)
      || getProfessionalRef(destination);

    /*
     * CARTO_UP011E_FIX_SEARCH_REF_HIGHLIGHT
     */
    const selectedSearchRef = getProfessionalConsumptionMapSelectedSearchProfessionalRefStrict();

    if (selectedSearchRef) {
      return (
        professionalRef === selectedSearchRef
        || doesProfessionalConsumptionMapValueContainProfessionalRefLoose(destination, selectedSearchRef)
      );
    }

    if (highlightType === "professional") {
      return professionalRef === highlightId;
    }

    if (highlightType === "source") {
      return Boolean(professionalRefsBySource.get(highlightId)?.has(professionalRef));
    }

    if (highlightType === "route") {
      const route = routeById.get(highlightId);
      return route ? String(route.professionalRef || "") === professionalRef : false;
    }

    return true;
  }

  function routeAlphaFactor(route) {
    if (!hasActiveHighlight) return 1;
    return isRouteHighlighted(route) ? 1 : 0.04;
  }

  function pointAlphaFactor(isHighlighted) {
    if (!hasActiveHighlight) return 1;

    // CARTO_UP011B_PP_KEEP_POINTS_FIX_PARTICLE_GATE
    // En P→P/P→U seul, les points hors focus restent visibles mais plus discrets.
    if (isProfessionalConsumptionMapExtraFlowOnlyView()) {
      return isHighlighted ? 1 : 0.42;
    }

    return isHighlighted ? 1 : 0;
  }

  /*
   * CARTO_UP005F_FILTER_POINT_LAYER_DATA
   * Plus robuste que radius=0/alpha=0 : on retire directement les points
   * non concernés des couches deck.gl quand un focus est actif.
   */
  /*
   * CARTO_UP011B_PP_KEEP_POINTS_FIX_PARTICLE_GATE
   * En P→P/P→U seul :
   * - les points restent tous visibles pour garder le contexte réseau ;
   * - seules les routes et particules sont filtrées par le focus.
   */
  const preserveAllPointsForExtraFlowFocus =
    hasActiveHighlight && isProfessionalConsumptionMapExtraFlowOnlyView();

  const visibleSourceData = hasActiveHighlight && !preserveAllPointsForExtraFlowFocus
    ? data.sources.filter((source) => isSourceHighlighted(source))
    : data.sources;

  const visibleDestinationData = hasActiveHighlight && !preserveAllPointsForExtraFlowFocus
    ? data.destinations.filter((destination) => isDestinationHighlighted(destination))
    : data.destinations;

  const routeGlowLayer = new PathLayer({
    id: "up-routes-road-glow",
    data: routePathData,
    pickable: false,
    getPath: (d) => d.path,
    getColor: (d) => {
      const t = getRouteIntensity(d);
      const f = routeAlphaFactor(d);
      if (isProfessionalConsumptionMapExtraFlowFamily(d)) {
        return getProfessionalConsumptionMapRouteFamilyGlowColor(
          d,
          Math.round((38 + t * 52) * f)
        );
      }

      return getProfessionalConsumptionMapRouteColor(
        d,
        Math.round((8 + t * 14) * f),
        "glow"
      );
    },
    widthUnits: "pixels",
    rounded: true,
    capRounded: true,
    jointRounded: true,
    getWidth: (d) => {
      const t = getRouteIntensity(d);
      return (1.15 + t * 1.45) * (hasActiveHighlight && isRouteHighlighted(d) ? 1.85 : 1);
    },
    widthMinPixels: 1.0,
    widthMaxPixels: 4.8
  });

  const routeCoreLayer = new PathLayer({
    id: "up-routes-road-core",
    data: routePathData,
    pickable: false,
    getPath: (d) => d.path,
    getColor: (d) => {
      const t = getRouteIntensity(d);
      const active = isRouteHighlighted(d);
      const f = routeAlphaFactor(d);
      if (isProfessionalConsumptionMapExtraFlowFamily(d)) {
        return active
          ? getProfessionalConsumptionMapRouteFamilyColor(d, 230)
          : getProfessionalConsumptionMapRouteFamilyColor(
              d,
              Math.round((82 + t * 76) * f)
            );
      }

      return active && hasActiveHighlight
        ? getProfessionalConsumptionMapRouteColor(d, 178, "core")
        : getProfessionalConsumptionMapRouteColor(
            d,
            Math.round((48 + t * 48) * f),
            "core"
          );
    },
    widthUnits: "pixels",
    rounded: true,
    capRounded: true,
    jointRounded: true,
    getWidth: (d) => {
      const t = getRouteIntensity(d);
      const extraFactor = isProfessionalConsumptionMapExtraFlowFamily(d) ? 1.35 : 1;
      return (0.55 + t * 0.85) * extraFactor * (hasActiveHighlight && isRouteHighlighted(d) ? 2.15 : 1);
    },
    widthMinPixels: 0.55,
    widthMaxPixels: 3.8
  });

  const particleData = buildProfessionalConsumptionMapParticleData(
    routePathData.filter((route) => !route.search_anchor_route && !route.is_search_anchor_route),
    isRouteHighlighted
  );

  const particleGlowLayer = new ScatterplotLayer({
    id: "up-flow-particles-glow",
    data: particleData,
    pickable: false,
    radiusUnits: "pixels",
    getPosition: (d) => d.position,
    getRadius: (d) => {
      const isDark = typeof isProfessionalConsumptionMapDarkTheme === "function"
        ? isProfessionalConsumptionMapDarkTheme()
        : true;
      const base = Number(d.radius || 3) * Number(d.glowRadiusFactor || 1.7);
      return base * (isDark ? 1.0 : 1.16);
    },
    stroked: false,
    filled: true,
    getFillColor: (d) => {
      const isDark = typeof isProfessionalConsumptionMapDarkTheme === "function"
        ? isProfessionalConsumptionMapDarkTheme()
        : true;

      return isDark
        ? [255, 224, 150, Number(d.glowAlpha || 18)]
        : [255, 174, 36, Number(d.glowAlpha || 28)];
    }
  });

  const particleCoreLayer = new ScatterplotLayer({
    id: "up-flow-particles-core",
    data: particleData,
    pickable: false,
    radiusUnits: "pixels",
    getPosition: (d) => d.position,
    getRadius: (d) => {
      const isDark = typeof isProfessionalConsumptionMapDarkTheme === "function"
        ? isProfessionalConsumptionMapDarkTheme()
        : true;
      return Number(d.radius || 3) * (isDark ? 1.0 : 1.20);
    },
    stroked: true,
    filled: true,
    getFillColor: (d) => {
      const isDark = typeof isProfessionalConsumptionMapDarkTheme === "function"
        ? isProfessionalConsumptionMapDarkTheme()
        : true;

      return isDark
        ? [255, 248, 220, Number(d.alpha || 140)]
        : [255, 151, 32, Number(d.alpha || 185)];
    },
    getLineColor: (d) => {
      const isDark = typeof isProfessionalConsumptionMapDarkTheme === "function"
        ? isProfessionalConsumptionMapDarkTheme()
        : true;

      return isDark
        ? [255, 205, 120, 190]
        : [120, 65, 0, 218];
    },
    getLineWidth: 1
  });

  const sourceGlowLayer = new ScatterplotLayer({
    id: "up-sources-glow",
    data: visibleSourceData,
    pickable: false,
    radiusUnits: "meters",
    getPosition: (d) => [Number(d.longitude), Number(d.latitude)],
    getRadius: (d) => {
      if (!isSourceHighlighted(d)) return 0;
      const t = getSourceIntensity(d);
      return (70 + t * 110) * (hasActiveHighlight ? 1.25 : 0.82);
    },
    radiusMinPixels: 0.0,
    radiusMaxPixels: 20.16,
    stroked: false,
    filled: true,
    getFillColor: (d) => {
      const t = getSourceIntensity(d);
      const f = pointAlphaFactor(isSourceHighlighted(d));
      return getProfessionalConsumptionMapActorPointColor(
        d,
        Math.round((10 + t * 22) * f),
        "glow"
      );
    }
  });

  const sourceLayer = new ScatterplotLayer({
    id: "up-sources",
    data: visibleSourceData,
    pickable: true,
    onHover: handleProfessionalConsumptionMapLibreHover,
    onClick: handleProfessionalConsumptionMapLibreClick,
    radiusUnits: "meters",
    getPosition: (d) => [Number(d.longitude), Number(d.latitude)],
    getRadius: (d) => {
      if (!isSourceHighlighted(d)) return 0;
      const t = getSourceIntensity(d);
      return (42 + t * 54) * (hasActiveHighlight ? 1.20 : 1);
    },
    radiusMinPixels: 0.0,
    radiusMaxPixels: 11.2,
    stroked: true,
    filled: true,
    getFillColor: (d) => {
      const t = getSourceIntensity(d);
      const f = pointAlphaFactor(isSourceHighlighted(d));
      return getProfessionalConsumptionMapActorPointColor(
        d,
        Math.round((100 + t * 82) * f),
        "core"
      );
    },
    getLineColor: (d) => {
      const t = getSourceIntensity(d);
      const f = pointAlphaFactor(isSourceHighlighted(d));
      return [
        255,
        Math.round(225 - t * 16),
        Math.round(225 - t * 36),
        Math.round(220 * f)
      ];
    },
    getLineWidth: (d) => hasActiveHighlight && isSourceHighlighted(d) ? 2.0 : 1.1
  });

  const destinationGlowLayer = new ScatterplotLayer({
    id: "up-destinations-glow",
    data: visibleDestinationData,
    pickable: false,
    radiusUnits: "meters",
    getPosition: (d) => [Number(d.longitude), Number(d.latitude)],
    getRadius: (d) => {
      if (!isDestinationHighlighted(d)) return 0;
      const t = getDestinationIntensity(d);
      return (92 + t * 138) * (hasActiveHighlight ? 1.24 : 0.82);
    },
    radiusMinPixels: 0.0,
    radiusMaxPixels: 24.64,
    stroked: false,
    filled: true,
    getFillColor: (d) => {
      const t = getDestinationIntensity(d);
      const f = pointAlphaFactor(isDestinationHighlighted(d));
      return getProfessionalConsumptionMapActorPointColor(
        d,
        Math.round((9 + t * 22) * f),
        "glow"
      );
    }
  });

  const destinationLayer = new ScatterplotLayer({
    id: "up-destinations",
    data: visibleDestinationData,
    pickable: true,
    onHover: handleProfessionalConsumptionMapLibreHover,
    onClick: handleProfessionalConsumptionMapLibreClick,
    radiusUnits: "meters",
    getPosition: (d) => [Number(d.longitude), Number(d.latitude)],
    getRadius: (d) => {
      if (!isDestinationHighlighted(d)) return 0;
      const t = getDestinationIntensity(d);
      return (60 + t * 88) * (hasActiveHighlight ? 1.18 : 1);
    },
    radiusMinPixels: 0.0,
    radiusMaxPixels: 15.68,
    stroked: true,
    filled: true,
    getFillColor: (d) => {
      const t = getDestinationIntensity(d);
      const f = pointAlphaFactor(isDestinationHighlighted(d));
      return getProfessionalConsumptionMapActorPointColor(
        d,
        Math.round((105 + t * 78) * f),
        "core"
      );
    },
    getLineColor: (d) => {
      const f = pointAlphaFactor(isDestinationHighlighted(d));
      return [236, 253, 245, Math.round(220 * f)];
    },
    getLineWidth: (d) => hasActiveHighlight && isDestinationHighlighted(d) ? 2.1 : 1.2
  });

  return {
    MapboxOverlay,
    layers: [
      routeGlowLayer,
      routeCoreLayer,
      particleGlowLayer,
      particleCoreLayer,
      sourceGlowLayer,
      destinationGlowLayer,
      sourceLayer,
      destinationLayer
    ]
  };
}


/*
 * CARTO_UP010D_RENDER_SEARCH_POINT_WITHOUT_ROUTES
 * Un rendu sans route peut être valide si la recherche pro ajoute un point.
 */
function hasProfessionalConsumptionMapRenderableObjects(data) {
  return Boolean(
    (Array.isArray(data?.routes) && data.routes.length)
    || (Array.isArray(data?.sources) && data.sources.length)
    || (Array.isArray(data?.destinations) && data.destinations.length)
  );
}

function getProfessionalConsumptionMapFirstRenderablePoint(data) {
  const candidates = [
    ...(Array.isArray(data?.destinations) ? data.destinations : []),
    ...(Array.isArray(data?.sources) ? data.sources : [])
  ];

  for (const item of candidates) {
    const longitude = Number(item.longitude ?? item.lon ?? item.lng);
    const latitude = Number(item.latitude ?? item.lat);

    if (
      Number.isFinite(longitude)
      && Number.isFinite(latitude)
      && longitude >= -180
      && longitude <= 180
      && latitude >= -90
      && latitude <= 90
    ) {
      return [longitude, latitude];
    }
  }

  return null;
}


function renderProfessionalConsumptionMapLibre() {
  // CARTO_UP009A_PRESERVE_MAP_VIEW_FOCUS_RENDER
  const preservedInteractiveState = captureProfessionalConsumptionMapLibreInteractiveState();
  const container = document.getElementById("professionalConsumptionMapLibre");
  if (!container) return;

  if (getProfessionalConsumptionMapViewMode() !== "static") {
    destroyProfessionalConsumptionMapLibre({ preserveInteractiveState: true });
    return;
  }

  if (
    !window.maplibregl
    || !window.deck
    || !window.deck.MapboxOverlay
    || !window.deck.ScatterplotLayer
    || (!window.deck.ArcLayer && !window.deck.LineLayer)
  ) {
    container.classList.remove("is-ready");
    return;
  }

  const rawPayload = appState.professionalConsumptionMapRenderPayload
    || appState.professionalConsumptionMap
    || null;

  const payload = buildProfessionalConsumptionMapVisualPayload(rawPayload);
  const data = buildProfessionalConsumptionMapLibreData(payload);

  // CARTO_UP010E3_ALLOW_SEARCH_POINT_NO_ROUTES_ROBUST
  if (!hasProfessionalConsumptionMapRenderableObjects(data)) {
    return;
  }

  destroyProfessionalConsumptionMapLibre();

  container.classList.add("is-ready");
  syncProfessionalConsumptionMapLibreThemeClass(container);
  bindProfessionalConsumptionMapThemeObserver();
  // CARTO_CLUSTER_MAIN_PERF001B_PARTICLE_TOGGLE
  ensureProfessionalConsumptionMapParticleControls();

  ensureProfessionalConsumptionMapFlowFamilyControls(payload);
  ensureProfessionalConsumptionMapProfessionalSearchControls(payload);

  const firstRoute = data.routes[0];
  const firstRenderablePoint = getProfessionalConsumptionMapFirstRenderablePoint(data);
  const center = firstRoute?.sourcePosition
    || firstRoute?.targetPosition
    || firstRenderablePoint
    || [3.8767, 43.6119];

  const map = new window.maplibregl.Map({
    container: "professionalConsumptionMapLibre",
    style: getProfessionalConsumptionMapLibreStyleUrl(),
    center,
    zoom: 10.5,
    pitch: 0,
    bearing: 0,
    attributionControl: true,
    dragRotate: false,
    pitchWithRotate: false
  });

  // CARTO_UP003D_ROUTE_READABILITY — garder une lecture cartographique simple.
  map.scrollZoom.disable();
  if (map.dragRotate) map.dragRotate.disable();
  if (map.touchZoomRotate && map.touchZoomRotate.disableRotation) {
    map.touchZoomRotate.disableRotation();
  }
  map.addControl(new window.maplibregl.NavigationControl(), "top-right");

  const mapCanvas = map.getCanvas?.();
  if (mapCanvas) {
    mapCanvas.addEventListener("mouseleave", clearProfessionalConsumptionMapLibreHighlight);
  }

  map.on("click", () => {
    window.setTimeout(() => {
      const lastObjectClickAt = Number(appState.professionalConsumptionMapLibreLastObjectClickAt || 0);
      if (Date.now() - lastObjectClickAt > 220) {
        clearProfessionalConsumptionMapLibreLockedHighlight();
        clearProfessionalConsumptionMapLibreHighlight();
      }
    }, 0);
  });

  map.on("load", () => {
    // CARTO_UP010I_SEARCH_USES_LOCKED_HIGHLIGHT
    const searchLockedHighlight = syncProfessionalConsumptionMapSearchLockedHighlight(data);

    const layerConfig = buildProfessionalConsumptionMapLibreLayers(data);

    if (!layerConfig) {
      container.classList.remove("is-ready");
      return;
    }

    const overlay = new layerConfig.MapboxOverlay({
      layers: layerConfig.layers,
      getTooltip: getProfessionalConsumptionMapLibreTooltip,
      onHover: handleProfessionalConsumptionMapLibreHover,
      onClick: handleProfessionalConsumptionMapLibreClick
    });

    map.addControl(overlay);

    appState.professionalConsumptionMapLibreMap = map;

    // CARTO_CLUSTER_MAIN_PERF003B_CANVAS_CAMERA_SYNC
    bindProfessionalConsumptionMapCanvasParticleCameraSync(map);

  // CARTO_UP010I_SEARCH_EASE_AFTER_MAP
  if (searchLockedHighlight) {
    easeProfessionalConsumptionMapToSearchLockedHighlightSoon();
  }
    appState.professionalConsumptionMapLibreOverlay = overlay;
    appState.professionalConsumptionMapLibreData = data;

    // CARTO_UP010K_SEARCH_FOCUS_STARTS_PARTICLES
    if (isProfessionalConsumptionMapSearchFocusActive()) {
      startProfessionalConsumptionMapParticleAnimationSoon();
    }

    if (hasProfessionalConsumptionMapLibrePreservedView(preservedInteractiveState)) {
      restoreProfessionalConsumptionMapLibreInteractiveState(map, preservedInteractiveState);
    } else {
      if (hasProfessionalConsumptionMapRenderableObjects(data)) {
        const firstPoint = getProfessionalConsumptionMapFirstRenderablePoint(data);

        if (!data.routes.length && firstPoint && typeof map.jumpTo === "function") {
          map.jumpTo({
            center: firstPoint,
            zoom: 13.8,
            bearing: 0,
            pitch: 0
          });
        } else {
          fitProfessionalConsumptionMapLibreToData(map, data);
        }
      } else {
        fitProfessionalConsumptionMapLibreToData(map, data);
      }
    }

    updateProfessionalConsumptionMapRoadRoutingStatus(data);

    // CARTO_UP006D_COMPLETE_ROUTING_STATUS_FIXED — chargement asynchrone complet des polylignes routières.
    loadProfessionalConsumptionMapRoadGeometries(data, overlay);

    window.setTimeout(() => {
      try {
        map.resize();
      } catch (_err) {
        // no-op
      }
    }, 120);
  });
}



/*
 * CARTO_UP004A_ROAD_ROUTING_TEST
 * Routage routier indicatif via OSRM public, côté navigateur.
 *
 * Important :
 * - les trajets ne sont PAS des déplacements individuels réels ;
 * - les sources sont des bassins agrégés / synthétiques ;
 * - le routage sert uniquement à rendre les faisceaux plus lisibles spatialement.
 */
function getProfessionalConsumptionMapRoadRoutingCache() {
  if (!appState.professionalConsumptionMapRoadRoutingCache) {
    appState.professionalConsumptionMapRoadRoutingCache = new Map();
  }

  return appState.professionalConsumptionMapRoadRoutingCache;
}

function getProfessionalConsumptionMapRoadRoutingKey(route) {
  const source = route?.sourcePosition || [];
  const target = route?.targetPosition || [];

  return [
    route?.sourceCode || "",
    route?.professionalRef || "",
    Number(source[0] || 0).toFixed(5),
    Number(source[1] || 0).toFixed(5),
    Number(target[0] || 0).toFixed(5),
    Number(target[1] || 0).toFixed(5)
  ].join("|");
}

function getProfessionalConsumptionMapRoadRoutingUrl(route) {
  const source = route?.sourcePosition || [];
  const target = route?.targetPosition || [];

  const sourceLongitude = Number(source[0]);
  const sourceLatitude = Number(source[1]);
  const targetLongitude = Number(target[0]);
  const targetLatitude = Number(target[1]);

  if (
    !Number.isFinite(sourceLongitude)
    || !Number.isFinite(sourceLatitude)
    || !Number.isFinite(targetLongitude)
    || !Number.isFinite(targetLatitude)
  ) {
    return null;
  }

  return [
    "https://router.project-osrm.org/route/v1/driving/",
    `${sourceLongitude},${sourceLatitude};${targetLongitude},${targetLatitude}`,
    "?overview=full&geometries=geojson&alternatives=false&steps=false"
  ].join("");
}


/*
 * CARTO_UP006D_COMPLETE_ROUTING_STATUS_FIXED
 * Routage complet progressif :
 * - toutes les routes visibles sont tentées ;
 * - retry léger ;
 * - cadence douce pour éviter les limites OSRM publiques ;
 * - compteur visible des géométries GPS.
 */
function waitProfessionalConsumptionMapRoadRouting(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function getProfessionalConsumptionMapRoadRoutingStats(data) {
  const routes = Array.isArray(data?.routes) ? data.routes : [];
  const total = routes.length;
  const routed = routes.filter((route) => Array.isArray(route.roadPath) && route.roadPath.length >= 2).length;
  const failed = routes.filter((route) => route.roadRoutingStatus === "failed").length;
  const pending = Math.max(0, total - routed - failed);

  return {
    total,
    routed,
    failed,
    pending
  };
}

function updateProfessionalConsumptionMapRoadRoutingStatus(data) {
  const container = document.getElementById("professionalConsumptionMapLibre");
  if (!container) return;

  let node = container.querySelector("[data-professional-consumption-map-routing-status]");

  if (!node) {
    node = document.createElement("div");
    node.className = "professional-consumption-maplibre-routing-status";
    node.setAttribute("data-professional-consumption-map-routing-status", "true");
    container.appendChild(node);
  }

  const stats = getProfessionalConsumptionMapRoadRoutingStats(data);

  const suffix = stats.failed
    ? ` · ${formatProfessionalSummaryInteger(stats.failed)} échec(s)`
    : "";

  node.textContent = [
    "GPS",
    `${formatProfessionalSummaryInteger(stats.routed)}/${formatProfessionalSummaryInteger(stats.total)} tracés`,
    stats.pending ? `${formatProfessionalSummaryInteger(stats.pending)} en attente` : "complet"
  ].join(" · ") + suffix;

  node.classList.toggle("is-complete", stats.total > 0 && stats.routed === stats.total);
  node.classList.toggle("has-failures", stats.failed > 0);
}


async function fetchProfessionalConsumptionMapRoadGeometry(route) {
  const cache = getProfessionalConsumptionMapRoadRoutingCache();
  const key = getProfessionalConsumptionMapRoadRoutingKey(route);

  if (cache.has(key)) {
    const cached = cache.get(key);
    return cached?.failed ? null : cached;
  }

  const url = getProfessionalConsumptionMapRoadRoutingUrl(route);

  if (!url) {
    cache.set(key, { failed: true, reason: "missing_coordinates" });
    return null;
  }

  const maxAttempts = 3;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        method: "GET",
        headers: {
          "Accept": "application/json"
        }
      });

      if (!response.ok) {
        if (attempt < maxAttempts) {
          await waitProfessionalConsumptionMapRoadRouting(220 * attempt); // CARTO_UP006E_ROUTE_QUEUE_PLUS_PARTICLES
          continue;
        }

        cache.set(key, { failed: true, reason: `http_${response.status}` });
        return null;
      }

      const json = await response.json();
      const coordinates = json?.routes?.[0]?.geometry?.coordinates || null;

      if (!Array.isArray(coordinates) || coordinates.length < 2) {
        if (attempt < maxAttempts) {
          await waitProfessionalConsumptionMapRoadRouting(180 * attempt); // CARTO_UP006E_ROUTE_QUEUE_PLUS_PARTICLES
          continue;
        }

        cache.set(key, { failed: true, reason: "no_geometry" });
        return null;
      }

      const validCoordinates = coordinates
        .map((point) => [Number(point?.[0]), Number(point?.[1])])
        .filter((point) => Number.isFinite(point[0]) && Number.isFinite(point[1]));

      const geometry = validCoordinates.length >= 2
        ? {
            path: validCoordinates,
            distance_m: Number(json?.routes?.[0]?.distance || 0),
            duration_s: Number(json?.routes?.[0]?.duration || 0),
            provider: "osrm_public"
          }
        : null;

      if (geometry) {
        cache.set(key, geometry);
        return geometry;
      }

      if (attempt < maxAttempts) {
        await waitProfessionalConsumptionMapRoadRouting(300 * attempt);
        continue;
      }

      cache.set(key, { failed: true, reason: "invalid_geometry" });
      return null;
    } catch (_err) {
      if (attempt < maxAttempts) {
        await waitProfessionalConsumptionMapRoadRouting(260 * attempt); // CARTO_UP006E_ROUTE_QUEUE_PLUS_PARTICLES
        continue;
      }

      cache.set(key, { failed: true, reason: "fetch_error" });
      return null;
    }
  }

  cache.set(key, { failed: true, reason: "unknown" });
  return null;
}


/*
 * CARTO_UP009B_REUSE_GPS_ROUTE_CACHE
 * Réhydrate immédiatement les routes depuis le cache OSRM déjà calculé.
 * Objectif : changement de filtre = zéro recalcul pour les couples déjà connus.
 */
function applyProfessionalConsumptionMapCachedRoadGeometry(route) {
  if (!route) {
    return false;
  }

  const cache = getProfessionalConsumptionMapRoadRoutingCache();
  const key = getProfessionalConsumptionMapRoadRoutingKey(route);

  if (!cache || !key || !cache.has(key)) {
    return false;
  }

  const cached = cache.get(key);

  route.roadPathChecked = true;

  if (cached?.path?.length >= 2) {
    route.roadPath = cached.path;
    route.road_distance_m = cached.distance_m;
    route.road_duration_s = cached.duration_s;
    route.road_provider = cached.provider || "osrm_public_cached";
    route.roadRoutingStatus = "routed";
    route.roadRoutingCacheHit = true;
    return true;
  }

  if (cached?.failed) {
    route.roadRoutingStatus = "failed";
    route.roadRoutingFailureReason = cached.reason || "cached_failure";
    route.roadRoutingCacheHit = true;
    return true;
  }

  return false;
}

function hydrateProfessionalConsumptionMapRoadGeometriesFromCache(data) {
  const routes = Array.isArray(data?.routes) ? data.routes : [];

  let cachedRouted = 0;
  let cachedFailed = 0;

  routes.forEach((route) => {
    const beforeStatus = route.roadRoutingStatus || "";
    const hydrated = applyProfessionalConsumptionMapCachedRoadGeometry(route);

    if (!hydrated) {
      return;
    }

    if (route.roadRoutingStatus === "routed") {
      cachedRouted += 1;
    } else if (route.roadRoutingStatus === "failed" && beforeStatus !== "failed") {
      cachedFailed += 1;
    }
  });

  data.roadRoutingCacheStats = {
    cached_routed: cachedRouted,
    cached_failed: cachedFailed
  };

  return data.roadRoutingCacheStats;
}


async function loadProfessionalConsumptionMapRoadGeometries(data, overlay) {
  /*
   * CARTO_UP009B_REUSE_GPS_ROUTE_CACHE
   * On réutilise les tracés déjà calculés avant de lancer la moindre requête.
   */
  if (!data?.routes?.length || !overlay) {
    return;
  }

  hydrateProfessionalConsumptionMapRoadGeometriesFromCache(data);

  data.routes.forEach((route) => {
    if (!route.roadRoutingStatus) {
      route.roadRoutingStatus = Array.isArray(route.roadPath) && route.roadPath.length >= 2
        ? "routed"
        : "pending";
    }
  });

  updateProfessionalConsumptionMapRoadRoutingStatus(data);

  const pendingRoutes = data.routes.filter((route) => (
    !route.roadPathChecked
    && !(Array.isArray(route.roadPath) && route.roadPath.length >= 2)
  ));

  if (!pendingRoutes.length) {
    const layerConfig = buildProfessionalConsumptionMapLibreLayers(data);
    if (layerConfig?.layers) {
      overlay.setProps({ layers: layerConfig.layers });
    }
    updateProfessionalConsumptionMapRoadRoutingStatus(data);
    return;
  }

  const concurrency = 4;
  let index = 0;
  let renderTick = 0;

  const refreshLayers = () => {
    const layerConfig = buildProfessionalConsumptionMapLibreLayers(data);
    if (layerConfig?.layers) {
      overlay.setProps({ layers: layerConfig.layers });
    }
    updateProfessionalConsumptionMapRoadRoutingStatus(data);
  };

  const runNext = async () => {
    const route = pendingRoutes[index];
    index += 1;

    if (!route) {
      return;
    }

    // Recheck juste avant fetch : un autre filtre/rendu a pu remplir le cache entre-temps.
    if (applyProfessionalConsumptionMapCachedRoadGeometry(route)) {
      renderTick += 1;
      if (renderTick % 8 === 0) {
        refreshLayers();
      } else {
        updateProfessionalConsumptionMapRoadRoutingStatus(data);
      }
      await runNext();
      return;
    }

    route.roadRoutingStatus = "pending";

    await waitProfessionalConsumptionMapRoadRouting(70);

    const geometry = await fetchProfessionalConsumptionMapRoadGeometry(route);

    route.roadPathChecked = true;

    if (geometry?.path?.length >= 2) {
      route.roadPath = geometry.path;
      route.road_distance_m = geometry.distance_m;
      route.road_duration_s = geometry.duration_s;
      route.road_provider = geometry.provider;
      route.roadRoutingStatus = "routed";
      route.roadRoutingCacheHit = false;
    } else {
      route.roadRoutingStatus = "failed";
      route.roadRoutingCacheHit = false;
    }

    renderTick += 1;

    if (renderTick % 3 === 0 || route.roadRoutingStatus === "routed") {
      refreshLayers();
    } else {
      updateProfessionalConsumptionMapRoadRoutingStatus(data);
    }

    await runNext();
  };

  await Promise.all(
    Array.from({ length: Math.min(concurrency, pendingRoutes.length) }, runNext)
  );

  refreshLayers();
}

function getProfessionalConsumptionMapRoutePath(route) {
  if (Array.isArray(route?.roadPath) && route.roadPath.length >= 2) {
    return route.roadPath;
  }

  return [
    route.sourcePosition,
    route.targetPosition
  ];
}


function getProfessionalConsumptionMapPayload(consumptionMapSummary) {
  return consumptionMapSummary || null;
}

/*
 * CARTO_UP001B_FIXED
 * Mode A : vue d’ensemble limitée aux principaux faisceaux.
 * Mode C : focus sur une zone source sélectionnée.
 *
 * Le payload API reste complet. On filtre seulement le payload de rendu canvas.
 */
function getProfessionalConsumptionMapOverviewLimit() {
  /*
   * CARTO_UP005E_LOCKED_FOCUS_ALL
   * null = tout voir dans le payload déjà filtré/confidentiel.
   */
  const raw = appState.professionalConsumptionMapOverviewLimit;

  if (raw === "all") {
    return null;
  }

  const value = Number(raw || 30);

  if (!Number.isFinite(value) || value <= 0) {
    return 30;
  }

  return Math.max(5, Math.min(500, Math.round(value)));
}

function getProfessionalConsumptionMapSelectedSourcePostalCode() {
  return String(appState.professionalConsumptionMapSelectedSourcePostalCode || "").trim();
}

function getProfessionalConsumptionMapRouteVolume(route) {
  return Number(route?.final_volume ?? route?.volume ?? 0);
}

function getProfessionalConsumptionMapRouteTxCount(route) {
  return Number(route?.final_tx_count ?? route?.tx_count ?? 0);
}

function getProfessionalConsumptionMapRouteSortValue(route) {
  return getProfessionalConsumptionMapRouteVolume(route);
}

function getProfessionalConsumptionMapSourceOptions(payload) {
  const routes = Array.isArray(payload?.routes) ? payload.routes : [];
  const buckets = new Map();

  routes.forEach((route) => {
    const postalCode = String(route?.source_postal_code || "").trim();
    if (!postalCode) return;

    const item = buckets.get(postalCode) || {
      postal_code: postalCode,
      city: route?.source_city || "",
      route_count: 0,
      tx_count: 0,
      volume: 0,
      professionals: new Set()
    };

    item.route_count += 1;
    item.tx_count += getProfessionalConsumptionMapRouteTxCount(route);
    item.volume += getProfessionalConsumptionMapRouteVolume(route);

    const professionalRef = String(route?.professional_ref || "").trim();
    if (professionalRef) {
      item.professionals.add(professionalRef);
    }

    buckets.set(postalCode, item);
  });

  return Array.from(buckets.values())
    .map((item) => ({
      ...item,
      professional_count: item.professionals.size
    }))
    .sort((a, b) => Number(b.volume || 0) - Number(a.volume || 0));
}

function getProfessionalConsumptionMapFilteredRoutes(payload) {
  /*
   * CARTO_UP005E_LOCKED_FOCUS_ALL
   * Le sélecteur limite le nombre de faisceaux en vue globale comme en focus.
   * limit === null signifie : tout voir.
   */
  const allRoutes = Array.isArray(payload?.routes) ? payload.routes : [];
  const selectedSource = getProfessionalConsumptionMapSelectedSourcePostalCode();
  const limit = getProfessionalConsumptionMapOverviewLimit();

  const sortRoutes = (routes) => [...routes].sort(
    (a, b) => getProfessionalConsumptionMapRouteSortValue(b)
      - getProfessionalConsumptionMapRouteSortValue(a)
  );

  const limitRoutes = (routes) => {
    const sorted = sortRoutes(routes);
    return limit === null ? sorted : sorted.slice(0, limit);
  };

  if (selectedSource) {
    const focusedRoutes = allRoutes.filter((route) => (
      String(route?.source_postal_code || "").trim() === selectedSource
    ));

    if (focusedRoutes.length) {
      return {
        mode: "source-focus",
        selectedSource,
        totalRoutesBeforeLimit: focusedRoutes.length,
        limit,
        routes: limitRoutes(focusedRoutes)
      };
    }
  }

  return {
    mode: "overview",
    selectedSource: "",
    totalRoutesBeforeLimit: allRoutes.length,
    limit,
    routes: limitRoutes(allRoutes)
  };
}

function buildProfessionalConsumptionMapVisualPayload(payload) {
  if (!payload || typeof payload !== "object") {
    return payload || null;
  }

  const result = getProfessionalConsumptionMapFilteredRoutes(payload);
  const routes = result.routes || [];

  const sourceCodes = new Set(
    routes
      .map((route) => String(route?.source_postal_code || "").trim())
      .filter(Boolean)
  );

  const destinationRefs = new Set(
    routes
      .map((route) => String(route?.professional_ref || "").trim())
      .filter(Boolean)
  );

  const sources = (payload.sources || []).filter((source) => (
    sourceCodes.has(String(source?.postal_code || "").trim())
  ));

  const destinations = (payload.destinations || []).filter((destination) => (
    destinationRefs.has(String(destination?.professional_ref || "").trim())
  ));

  const visibleTxCount = routes.reduce(
    (sum, route) => sum + getProfessionalConsumptionMapRouteTxCount(route),
    0
  );

  const visibleVolume = routes.reduce(
    (sum, route) => sum + getProfessionalConsumptionMapRouteVolume(route),
    0
  );

  const sourcePointStatusCounts = {};
  const professionalPointStatusCounts = {};
  const routeAreaStatusCounts = {};

  routes.forEach((route) => {
    const sourceStatus = String(route?.source_point_status || "unknown");
    const professionalStatus = String(route?.professional_point_status || "unknown");
    const areaStatus = route?.source_postal_code ? "available" : "missing_geometry";

    sourcePointStatusCounts[sourceStatus] = (sourcePointStatusCounts[sourceStatus] || 0) + 1;
    professionalPointStatusCounts[professionalStatus] = (professionalPointStatusCounts[professionalStatus] || 0) + 1;
    routeAreaStatusCounts[areaStatus] = (routeAreaStatusCounts[areaStatus] || 0) + 1;
  });

  const visibleSourceAreaGeojson = {};
  const sourceAreas = payload?.geometry?.visible_source_area_geojson || {};

  sourceCodes.forEach((postalCode) => {
    if (sourceAreas[postalCode]) {
      visibleSourceAreaGeojson[postalCode] = sourceAreas[postalCode];
    }
  });

  const cartographiableTxCount = Number(payload?.coverage?.cartographiable_tx_count || 0);
  const cartographiableVolume = Number(payload?.coverage?.cartographiable_volume || 0);

  const visualSource = result.selectedSource
    ? sources.find((source) => String(source?.postal_code || "").trim() === result.selectedSource)
    : null;

  return {
    ...payload,
    routes,
    sources,
    destinations,
    geometry: {
      ...(payload.geometry || {}),
      visible_source_area_geojson: visibleSourceAreaGeojson,
      source_point_status_counts: sourcePointStatusCounts,
      professional_point_status_counts: professionalPointStatusCounts,
      route_area_status_counts: routeAreaStatusCounts,
      visual_route_count: routes.length,
      visual_source_count: sources.length,
      visual_destination_count: destinations.length
    },
    coverage: {
      ...(payload.coverage || {}),
      total_visible_route_count: Number(payload?.coverage?.visible_route_count || 0),
      total_visible_tx_count: Number(payload?.coverage?.visible_tx_count || 0),
      total_visible_volume: Number(payload?.coverage?.visible_volume || 0),
      visible_route_count: routes.length,
      visible_tx_count: visibleTxCount,
      visible_volume: visibleVolume,
      visible_tx_share_of_cartographiable: cartographiableTxCount
        ? visibleTxCount / cartographiableTxCount
        : null,
      visible_volume_share_of_cartographiable: cartographiableVolume
        ? visibleVolume / cartographiableVolume
        : null,
      visual_mode: result.mode,
      visual_overview_limit: getProfessionalConsumptionMapOverviewLimit(),
      visual_source_postal_code: result.selectedSource || null,
      visual_source_city: visualSource?.city || null
    },
    summary: {
      ...(payload.summary || {}),
      route_count: routes.length,
      visible_route_count: routes.length,
      visible_tx_count: visibleTxCount,
      visible_volume: visibleVolume,
      source_postal_code_count: sources.length,
      destination_professional_count: destinations.length
    },
    visual: {
      mode: result.mode,
      overview_limit: getProfessionalConsumptionMapOverviewLimit(),
      visual_limit: result.limit,
      total_routes_before_limit: Number(result.totalRoutesBeforeLimit || routes.length),
      selected_source_postal_code: result.selectedSource || null,
      selected_source_city: visualSource?.city || null,
      route_count: routes.length,
      tx_count: visibleTxCount,
      volume: visibleVolume,
      source_count: sources.length,
      destination_count: destinations.length
    }
  };
}

function getProfessionalConsumptionMapVisualSummaryText(payload) {
  const visualPayload = buildProfessionalConsumptionMapVisualPayload(payload);
  const visual = visualPayload?.visual || {};
  const coverage = visualPayload?.coverage || {};

  if (visual.mode === "source-focus") {
    const sourceLabel = getProfessionalConsumptionMapSourceDisplayLabel({
      postal_code: visual.selected_source_postal_code,
      city: visual.selected_source_city
    });

    const limitLabel = visual.visual_limit === null
      ? "tout voir"
      : `top ${formatProfessionalSummaryInteger(visual.visual_limit || 30)}`;

    return [
      `Mode C · Focus zone source : ${sourceLabel || "zone sélectionnée"}`,
      limitLabel,
      `${formatProfessionalSummaryInteger(visual.route_count || 0)} faisceau(x)`,
      `${formatProfessionalSummaryInteger(visual.tx_count || 0)} paiement(s)`,
      euro(visual.volume || 0)
    ].join(" · ");
  }

  const overviewLabel = coverage.visual_overview_limit === null
    ? "tous les faisceaux"
    : `top ${formatProfessionalSummaryInteger(coverage.visual_overview_limit || 30)} faisceaux par volume`;

  return [
    `Mode A · Vue d’ensemble : ${overviewLabel}`,
    `${formatProfessionalSummaryInteger(visual.route_count || 0)} affiché(s)`,
    `${formatProfessionalSummaryInteger(visual.tx_count || 0)} paiement(s)`,
    euro(visual.volume || 0)
  ].join(" · ");
}


function normalizeProfessionalConsumptionMapCityDisplay(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";

  const normalized = raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();

  const cityAliases = {
    "montpellier": "Montpellier",
    "montpelier": "Montpellier",
    "monptellier": "Montpellier",
    "castelnau le lez": "Castelnau-le-Lez",
    "castelnau-le-lez": "Castelnau-le-Lez",
    "le cres": "Le Crès",
    "prades-le-lez": "Prades-le-Lez",
    "prades le lez": "Prades-le-Lez",
    "jacou": "Jacou",
    "sussargues": "Sussargues",
    "castries": "Castries",

    "lyon": "Lyon",
    "lyon01": "Lyon 1er",
    "lyon 1": "Lyon 1er",
    "lyon 01": "Lyon 1er",
    "lyon 1er arrondissement": "Lyon 1er",
    "villeurbanne": "Villeurbanne",
    "villeurbannne": "Villeurbanne",
    "vaux-en-velin": "Vaulx-en-Velin",
    "vaux en velin": "Vaulx-en-Velin"
  };

  if (cityAliases[normalized]) {
    return cityAliases[normalized];
  }

  return raw
    .toLowerCase()
    .split(/([\s-]+)/)
    .map((part) => /^[a-zà-ÿ]/i.test(part)
      ? part.charAt(0).toUpperCase() + part.slice(1)
      : part
    )
    .join("");
}

function getProfessionalConsumptionMapSourceSectorLabel(postalCode, city = "") {
  const code = String(postalCode || "").trim();

  const sectorLabels = {
    "34000": "Montpellier centre",
    "34070": "Montpellier ouest / sud-ouest",
    "34080": "Montpellier nord-ouest",
    "34090": "Montpellier nord / nord-est",
    "34160": "Sussargues / Castries",
    "34170": "Castelnau-le-Lez",
    "34920": "Le Crès",
    "34730": "Prades-le-Lez",
    "34830": "Jacou",

    "69001": "Lyon 1er",
    "69002": "Lyon 2e",
    "69003": "Lyon 3e",
    "69004": "Lyon 4e",
    "69005": "Lyon 5e",
    "69006": "Lyon 6e",
    "69007": "Lyon 7e",
    "69008": "Lyon 8e",
    "69009": "Lyon 9e",
    "69100": "Villeurbanne",
    "69120": "Vaulx-en-Velin",
    "69300": "Caluire-et-Cuire",
    "69160": "Tassin-la-Demi-Lune",
    "69230": "Saint-Genis-Laval",
    "69600": "Oullins",
    "69500": "Bron",
    "69150": "Décines-Charpieu",
    "69110": "Sainte-Foy-lès-Lyon"
  };

  return sectorLabels[code] || normalizeProfessionalConsumptionMapCityDisplay(city) || code || "Zone source";
}

function getProfessionalConsumptionMapSourceDisplayLabel(source) {
  const postalCode = String(source?.postal_code || source?.source_postal_code || "").trim();
  const city = source?.city || source?.source_city || "";
  const sectorLabel = getProfessionalConsumptionMapSourceSectorLabel(postalCode, city);

  if (!postalCode) {
    return sectorLabel;
  }

  return `${postalCode} · ${sectorLabel}`;
}


function renderProfessionalConsumptionMapVisualControlsHtml(payload) {
  const selectedSource = getProfessionalConsumptionMapSelectedSourcePostalCode();
  const overviewLimit = getProfessionalConsumptionMapOverviewLimit();
  const sourceOptions = getProfessionalConsumptionMapSourceOptions(payload);

  const sourceOptionsHtml = sourceOptions.map((source) => {
    const postalCode = String(source?.postal_code || "").trim();
    const label = [
      getProfessionalConsumptionMapSourceDisplayLabel(source),
      `${formatProfessionalSummaryInteger(source?.route_count || 0)} faisceau(x)`,
      euro(source?.volume || 0)
    ].filter(Boolean).join(" · ");

    return `
      <option
        value="${escapeHtml(postalCode)}"
        ${postalCode === selectedSource ? "selected" : ""}
      >
        ${escapeHtml(label)}
      </option>
    `;
  }).join("");

  return `
    <div class="professional-consumption-map-visual-controls">
      <div class="professional-consumption-map-visual-controls-row">
        <label class="professional-consumption-map-control">
          <span>Mode C · Focus zone source</span>
          <select data-professional-consumption-map-source-filter>
            <option value="">Mode A · Vue d’ensemble</option>
            ${sourceOptionsHtml}
          </select>
        </label>

        <label class="professional-consumption-map-control">
          <span>Nombre max. de faisceaux affichés</span>
          <select data-professional-consumption-map-overview-limit>
            <option value="all" ${overviewLimit === null ? "selected" : ""}>
              Tout voir
            </option>
            ${[5, 8, 12, 20, 30, 50, 80].map((value) => `
              <option value="${value}" ${Number(value) === overviewLimit ? "selected" : ""}>
                Top ${value}
              </option>
            `).join("")}
          </select>
        </label>

        <button
          type="button"
          class="professional-consumption-map-reset-btn"
          data-professional-consumption-map-reset-focus
        >
          Réinitialiser
        </button>
      </div>

      <div
        class="professional-consumption-map-visual-summary"
        data-professional-consumption-map-visual-summary
      >
        ${escapeHtml(getProfessionalConsumptionMapVisualSummaryText(payload))}
      </div>
    </div>
  `;
}


/*
 * CARTO_UP002C_DYNAMIC_NOTE
 * Synchronise le bloc “Lecture du rendu courant” avec le rendu réellement visible.
 */
function getProfessionalConsumptionMapCurrentRenderNoteHtml(payload) {
  const visualPayload = buildProfessionalConsumptionMapVisualPayload(payload);
  const visual = visualPayload?.visual || {};
  const coverage = visualPayload?.coverage || {};
  const geometry = visualPayload?.geometry || {};

  const modeLabel = visual.mode === "source-focus"
    ? `Mode C · Focus zone source${
        visual.selected_source_postal_code
          ? ` ${visual.selected_source_postal_code}`
          : ""
      }${
        visual.selected_source_city
          ? ` · ${visual.selected_source_city}`
          : ""
      }`
    : `Mode A · Vue d’ensemble${
        coverage.visual_overview_limit
          ? ` · top ${formatProfessionalSummaryInteger(coverage.visual_overview_limit)} faisceaux`
          : ""
      }`;

  const routeCount = Number(
    coverage.visible_route_count
    || visual.route_count
    || 0
  );

  const txCount = Number(
    coverage.visible_tx_count
    || visual.tx_count
    || 0
  );

  const volume = Number(
    coverage.visible_volume
    || visual.volume
    || 0
  );

  const sourceCount = Number(
    geometry?.visual_source_count
    || visual.source_count
    || 0
  );

  const destinationCount = Number(
    geometry?.visual_destination_count
    || visual.destination_count
    || 0
  );

  return `
    <strong>Lecture du rendu courant.</strong>
    ${escapeHtml(modeLabel)}.
    Les lignes illustrent des <strong>faisceaux de consommation</strong>,
    pas des trajets individuels réels.
    Le rendu affiche
    <strong>${formatProfessionalSummaryInteger(routeCount)} faisceau(x)</strong>,
    <strong>${formatProfessionalSummaryInteger(txCount)} paiement(s)</strong>
    et
    <strong>${euro(volume)}</strong>,
    retenus après un seuil minimal de
    <strong>2 particuliers distincts par faisceau</strong>.
    Le rendu conserve
    <strong>${formatProfessionalSummaryInteger(sourceCount)} bassin(s) source</strong>
    et
    <strong>${formatProfessionalSummaryInteger(destinationCount)} professionnel(s)</strong>.
  `;
}

function updateProfessionalConsumptionMapCurrentRenderNote() {
  const payload = appState.professionalConsumptionMap || null;

  document
    .querySelectorAll("[data-professional-consumption-map-current-note]")
    .forEach((node) => {
      node.innerHTML = getProfessionalConsumptionMapCurrentRenderNoteHtml(payload);
    });
}


function updateProfessionalConsumptionMapVisualControlsUi() {
  const payload = appState.professionalConsumptionMap || null;
  const selectedSource = getProfessionalConsumptionMapSelectedSourcePostalCode();
  const overviewLimit = getProfessionalConsumptionMapOverviewLimit();

  document
    .querySelectorAll("[data-professional-consumption-map-source-filter]")
    .forEach((select) => {
      select.value = selectedSource;
    });

  document
    .querySelectorAll("[data-professional-consumption-map-overview-limit]")
    .forEach((select) => {
      select.value = overviewLimit === null ? "all" : String(overviewLimit);
    });

  document
    .querySelectorAll("[data-professional-consumption-map-visual-summary]")
    .forEach((node) => {
      node.textContent = getProfessionalConsumptionMapVisualSummaryText(payload);
    });

  updateProfessionalConsumptionMapCurrentRenderNote();
}

function refreshProfessionalConsumptionMapVisualRender() {
  pauseProfessionalConsumptionMapPlayback();

  appState.professionalConsumptionMapViewMode = "static";
  appState.professionalConsumptionMapRenderPayload =
    getProfessionalConsumptionMapFinalRenderPayload(
      appState.professionalConsumptionMap
    );

  resetProfessionalConsumptionMapRenderCaches();
  renderProfessionalConsumptionMapCanvas();
  renderProfessionalConsumptionMapZoomCanvas();
  updateProfessionalConsumptionMapVisualControlsUi();
}

function setProfessionalConsumptionMapSourceFilter(value) {
  appState.professionalConsumptionMapSelectedSourcePostalCode =
    String(value || "").trim();

  refreshProfessionalConsumptionMapVisualRender();
}

function setProfessionalConsumptionMapOverviewLimit(value) {
  if (String(value || "").trim() === "all") {
    appState.professionalConsumptionMapOverviewLimit = "all";
  } else {
    const nextValue = Number(value || 30);
    appState.professionalConsumptionMapOverviewLimit =
      Number.isFinite(nextValue) && nextValue > 0
        ? Math.round(nextValue)
        : 30;
  }

  refreshProfessionalConsumptionMapVisualRender();
}


function collectProfessionalConsumptionMapCoordinates(payload) {
  const routes = payload?.routes || [];
  const sourceAreas = payload?.geometry?.visible_source_area_geojson || {};
  const points = [];

  routes.forEach((route) => {
    const destination = route?.destination || {};

    if (
      Number.isFinite(Number(destination.longitude))
      && Number.isFinite(Number(destination.latitude))
    ) {
      points.push([
        Number(destination.longitude),
        Number(destination.latitude)
      ]);
    }

    (route?.source_points || []).forEach((point) => {
      if (
        Number.isFinite(Number(point?.longitude))
        && Number.isFinite(Number(point?.latitude))
      ) {
        points.push([
          Number(point.longitude),
          Number(point.latitude)
        ]);
      }
    });
  });

  const pushGeoJsonCoordinates = (coords) => {
    if (!Array.isArray(coords)) {
      return;
    }

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

  Object.values(sourceAreas).forEach((featureCollection) => {
    (featureCollection?.features || []).forEach((feature) => {
      pushGeoJsonCoordinates(feature?.geometry?.coordinates || []);
    });
  });

  return points;
}

function buildProfessionalConsumptionMapProjection(payload, width, height) {
  const coords = collectProfessionalConsumptionMapCoordinates(payload);

  if (!coords.length) {
    return null;
  }

  const lons = coords.map((point) => point[0]);
  const lats = coords.map((point) => point[1]);

  let minLon;
  let maxLon;
  let minLat;
  let maxLat;

  /*
   * CARTO_UP002E_FOCUS_CENTER
   * En Mode C, on centre la projection sur le bassin source sélectionné.
   * Les destinations restent prises en compte dans l'étendue, mais de façon
   * symétrique autour de la source : le CP ne se retrouve plus repoussé
   * sur un bord par un professionnel éloigné.
   */
  const isSourceFocus =
    payload?.visual?.mode === "source-focus"
    && payload?.visual?.selected_source_postal_code;

  if (isSourceFocus) {
    const sourceCoords = [];

    (payload?.routes || []).forEach((route) => {
      const source = route?.source || {};

      if (
        Number.isFinite(Number(source.longitude))
        && Number.isFinite(Number(source.latitude))
      ) {
        sourceCoords.push([
          Number(source.longitude),
          Number(source.latitude)
        ]);
      }

      (route?.source_points || []).forEach((point) => {
        if (
          Number.isFinite(Number(point?.longitude))
          && Number.isFinite(Number(point?.latitude))
        ) {
          sourceCoords.push([
            Number(point.longitude),
            Number(point.latitude)
          ]);
        }
      });
    });

    const centerLon = sourceCoords.length
      ? sourceCoords.reduce((sum, point) => sum + point[0], 0) / sourceCoords.length
      : (Math.min(...lons) + Math.max(...lons)) / 2;

    const centerLat = sourceCoords.length
      ? sourceCoords.reduce((sum, point) => sum + point[1], 0) / sourceCoords.length
      : (Math.min(...lats) + Math.max(...lats)) / 2;

    const maxLonDelta = Math.max(
      0.018,
      ...lons.map((lon) => Math.abs(lon - centerLon))
    );

    const maxLatDelta = Math.max(
      0.014,
      ...lats.map((lat) => Math.abs(lat - centerLat))
    );

    const focusLonHalfSpan = maxLonDelta * 1.16;
    const focusLatHalfSpan = maxLatDelta * 1.16;

    minLon = centerLon - focusLonHalfSpan;
    maxLon = centerLon + focusLonHalfSpan;
    minLat = centerLat - focusLatHalfSpan;
    maxLat = centerLat + focusLatHalfSpan;
  } else {
    minLon = Math.min(...lons);
    maxLon = Math.max(...lons);
    minLat = Math.min(...lats);
    maxLat = Math.max(...lats);

    const lonSpan = Math.max(maxLon - minLon, 0.01);
    const latSpan = Math.max(maxLat - minLat, 0.01);

    minLon -= lonSpan * 0.06;
    maxLon += lonSpan * 0.06;
    minLat -= latSpan * 0.06;
    maxLat += latSpan * 0.06;
  }

  const margin = isSourceFocus
    ? {
        top: 52,
        right: 78,
        bottom: 58,
        left: 78
      }
    : {
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
    minLon,
    maxLon,
    minLat,
    maxLat,
    width,
    height,
    project(longitude, latitude) {
      const x = offsetX + (Number(longitude) - minLon) * scale;
      const y = offsetY + (maxLat - Number(latitude)) * scale;
      return { x, y };
    }
  };
}

function drawProfessionalConsumptionMapGeoJson(ctx, projection, featureCollection) {
  const drawRing = (ring) => {
    if (!Array.isArray(ring) || !ring.length) {
      return;
    }

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

  const drawGeometry = (geometry) => {
    if (!geometry) {
      return;
    }

    if (geometry.type === "Polygon") {
      (geometry.coordinates || []).forEach(drawRing);
    }

    if (geometry.type === "MultiPolygon") {
      (geometry.coordinates || []).forEach((polygon) => {
        (polygon || []).forEach(drawRing);
      });
    }
  };

  ctx.beginPath();

  (featureCollection?.features || []).forEach((feature) => {
    drawGeometry(feature?.geometry);
  });

  ctx.fill("evenodd");
  ctx.stroke();
}



function getProfessionalConsumptionMapThemePalette() {
  const computed = window.getComputedStyle(document.body);
  const isDark = document.body.classList.contains("dark-mode");

  const cardBg =
    computed.getPropertyValue("--card-bg")?.trim()
    || (isDark ? "#111827" : "#ffffff");

  return {
    isDark,
    cardBg,

    ambientCenter: isDark
      ? "rgba(14, 165, 233, 0.028)"
      : "rgba(37, 99, 235, 0.028)",

    ambientOuter: isDark
      ? "rgba(15, 23, 42, 0)"
      : "rgba(255, 255, 255, 0)",

    cartographicGuide: isDark
      ? "rgba(148, 163, 184, 0.060)"
      : "rgba(100, 116, 139, 0.050)",

    areaFill: isDark
      ? "rgba(148, 163, 184, 0.115)"
      : "rgba(15, 23, 42, 0.052)",

    areaStroke: isDark
      ? "rgba(226, 232, 240, 0.210)"
      : "rgba(71, 85, 105, 0.170)",

    areaGlow: isDark
      ? "rgba(148, 163, 184, 0.120)"
      : "rgba(15, 23, 42, 0.080)",

    territoryPlate: isDark
      ? "rgba(15, 23, 42, 0.18)"
      : "rgba(255, 255, 255, 0.20)"
  };
}


function drawProfessionalConsumptionMapBackdrop(ctx, projection, payload) {
  const width = projection.width;
  const height = projection.height;
  const palette = getProfessionalConsumptionMapThemePalette();

  /*
    En thème clair, on conserve un fond calé sur l'encart.
    En thème sombre, on laisse le canvas réellement transparent :
    le fond exact du bloc parent apparaît alors à travers la carte,
    ce qui évite toute dissonance de teinte et renforce l'effet flottant.
  */
  if (palette.isDark) {
    ctx.clearRect(0, 0, width, height);
  } else {
    ctx.fillStyle = palette.cardBg;
    ctx.fillRect(0, 0, width, height);
  }

  const destinations = payload?.destinations || [];
  const validDestinations = destinations.filter((item) => (
    Number.isFinite(Number(item?.longitude))
    && Number.isFinite(Number(item?.latitude))
  ));

  if (!validDestinations.length) {
    return;
  }

  let weightedX = 0;
  let weightedY = 0;
  let weightTotal = 0;

  validDestinations.forEach((destination) => {
    const point = projection.project(
      destination.longitude,
      destination.latitude
    );
    const weight = Math.max(1, Math.sqrt(Number(destination?.volume || 0)));

    weightedX += point.x * weight;
    weightedY += point.y * weight;
    weightTotal += weight;
  });

  const center = {
    x: weightedX / Math.max(1, weightTotal),
    y: weightedY / Math.max(1, weightTotal)
  };

  /*
    Une ambiance quasi invisible, juste assez pour éviter un vide trop plat.
    Elle ne doit plus reconstituer un panneau rectangulaire perceptible.
  */
  ctx.save();

  const centralGlow = ctx.createRadialGradient(
    center.x,
    center.y,
    0,
    center.x,
    center.y,
    Math.max(width, height) * 0.48
  );

  centralGlow.addColorStop(0, palette.ambientCenter);
  centralGlow.addColorStop(1, palette.ambientOuter);

  ctx.fillStyle = centralGlow;
  ctx.fillRect(0, 0, width, height);

  /*
    Les repères circulaires deviennent beaucoup plus discrets.
    Ils restent utiles comme texture cartographique légère,
    sans redessiner une scène autonome.
  */
  ctx.strokeStyle = palette.cartographicGuide;
  ctx.lineWidth = 1;

  const maxRadius = Math.max(width, height) * 0.72;
  [0.28, 0.56, 0.84].forEach((ratio) => {
    ctx.beginPath();
    ctx.arc(center.x, center.y, maxRadius * ratio, 0, Math.PI * 2);
    ctx.stroke();
  });

  ctx.restore();
}


function drawProfessionalConsumptionMapAreas(ctx, projection, payload) {
  const sourceAreas = payload?.geometry?.visible_source_area_geojson || {};
  const palette = getProfessionalConsumptionMapThemePalette();

  /*
    Première passe : une "plaque" territoriale légère, à peine visible,
    pour donner l’impression que la forme flotte sur la page.
  */
  ctx.save();
  ctx.fillStyle = palette.territoryPlate;
  ctx.strokeStyle = "transparent";
  ctx.shadowColor = palette.areaGlow;
  ctx.shadowBlur = palette.isDark ? 20 : 16;

  Object.values(sourceAreas).forEach((featureCollection) => {
    drawProfessionalConsumptionMapGeoJson(ctx, projection, featureCollection);
  });

  ctx.restore();

  /*
    Deuxième passe : la matière cartographique elle-même.
  */
  ctx.save();
  ctx.fillStyle = palette.areaFill;
  ctx.strokeStyle = palette.areaStroke;
  ctx.lineWidth = 1.15;
  ctx.shadowColor = palette.areaGlow;
  ctx.shadowBlur = palette.isDark ? 10 : 8;

  Object.values(sourceAreas).forEach((featureCollection) => {
    drawProfessionalConsumptionMapGeoJson(ctx, projection, featureCollection);
  });

  ctx.restore();
}

function professionalConsumptionMapHash(value) {
  const text = String(value || "");
  let hash = 0;

  for (let index = 0; index < text.length; index += 1) {
    hash = ((hash << 5) - hash) + text.charCodeAt(index);
    hash |= 0;
  }

  return Math.abs(hash);
}





function interpolateProfessionalConsumptionMapPoint(start, end, ratio) {
  const t = Math.max(0, Math.min(1, Number(ratio || 0)));

  return {
    x: start.x + (end.x - start.x) * t,
    y: start.y + (end.y - start.y) * t
  };
}

function getProfessionalConsumptionMapQuadraticPoint(
  source,
  control,
  destination,
  ratio
) {
  const t = Math.max(0, Math.min(1, Number(ratio || 0)));

  const ax = source.x + (control.x - source.x) * t;
  const ay = source.y + (control.y - source.y) * t;

  const bx = control.x + (destination.x - control.x) * t;
  const by = control.y + (destination.y - control.y) * t;

  return {
    x: ax + (bx - ax) * t,
    y: ay + (by - ay) * t
  };
}

function getProfessionalConsumptionMapPartialQuadraticCurve(
  source,
  control,
  destination,
  ratio
) {
  const t = Math.max(0, Math.min(1, Number(ratio || 0)));

  if (t >= 1) {
    return {
      control,
      destination
    };
  }

  const firstControl = interpolateProfessionalConsumptionMapPoint(
    source,
    control,
    t
  );

  const secondControl = interpolateProfessionalConsumptionMapPoint(
    control,
    destination,
    t
  );

  const partialDestination = interpolateProfessionalConsumptionMapPoint(
    firstControl,
    secondControl,
    t
  );

  return {
    control: firstControl,
    destination: partialDestination
  };
}

function drawProfessionalConsumptionMapRouteHeadParticle(
  ctx,
  point,
  {
    structuralWeight = 0,
    traffic = 0,
    appearance = 1
  } = {}
) {
  const safeAppearance = Math.max(0, Math.min(1, Number(appearance || 0)));
  const safeTraffic = Math.max(0, Math.min(1, Number(traffic || 0)));
  const safeStructure = Math.max(0, Math.min(1, Number(structuralWeight || 0)));

  const coreRadius =
    1.25
    + safeStructure * 1.35
    + safeTraffic * 0.80;

  const haloRadius =
    coreRadius * (3.2 + safeTraffic * 0.8);

  ctx.save();
  ctx.globalCompositeOperation = "lighter";

  const glow = ctx.createRadialGradient(
    point.x,
    point.y,
    0,
    point.x,
    point.y,
    haloRadius
  );

  glow.addColorStop(
    0,
    `rgba(255, 251, 235, ${0.52 + safeAppearance * 0.24})`
  );
  glow.addColorStop(
    0.34,
    `rgba(251, 191, 36, ${0.26 + safeAppearance * 0.20})`
  );
  glow.addColorStop(
    1,
    "rgba(251, 191, 36, 0)"
  );

  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(point.x, point.y, haloRadius, 0, Math.PI * 2);
  ctx.fill();

  ctx.beginPath();
  ctx.fillStyle =
    `rgba(255, 251, 235, ${0.78 + safeAppearance * 0.18})`;
  ctx.shadowBlur = 3.6 + safeTraffic * 7 + safeStructure * 4;
  ctx.shadowColor =
    `rgba(251, 191, 36, ${0.40 + safeTraffic * 0.24})`;
  ctx.arc(point.x, point.y, coreRadius, 0, Math.PI * 2);
  ctx.fill();

  ctx.restore();
}




function drawProfessionalConsumptionMapRoutes(ctx, surface, payload) {
  const routes = [...(payload?.routes || [])].sort(
    (a, b) => Number(a?.final_volume ?? a?.volume ?? 0)
      - Number(b?.final_volume ?? b?.volume ?? 0)
  );

  const referenceRoutes =
    appState.professionalConsumptionMap?.routes
    || routes;

  const maxFinalVolume = Math.max(
    1,
    ...referenceRoutes.map((route) => Number(route?.volume || 0))
  );

  const maxFinalTxCount = Math.max(
    1,
    ...referenceRoutes.map((route) => Number(route?.tx_count || 0))
  );

  const densityLightFactor =
    getProfessionalConsumptionMapDensityLightFactor(payload);

  const drawCurve = (
    source,
    controlX,
    controlY,
    destinationPoint,
    strokeStyle,
    lineWidth,
    shadowBlur,
    shadowColor,
    composite = "source-over",
    traceProgress = 1
  ) => {
    const curve = getProfessionalConsumptionMapPartialQuadraticCurve(
      source,
      { x: controlX, y: controlY },
      destinationPoint,
      traceProgress
    );

    ctx.save();
    ctx.globalCompositeOperation = composite;
    ctx.strokeStyle = strokeStyle;
    ctx.lineWidth = lineWidth;
    ctx.lineCap = "round";
    ctx.shadowBlur = shadowBlur;
    ctx.shadowColor = shadowColor;

    ctx.beginPath();
    ctx.moveTo(source.x, source.y);
    ctx.quadraticCurveTo(
      curve.control.x,
      curve.control.y,
      curve.destination.x,
      curve.destination.y
    );
    ctx.stroke();

    ctx.restore();
  };

  routes.forEach((route) => {
    const geometry =
      getProfessionalConsumptionMapProjectedRouteGeometry(route, surface);

    if (!geometry) {
      return;
    }

    const finalVolume = Number(route?.final_volume ?? route?.volume ?? 0);
    const finalTxCount = Number(route?.final_tx_count ?? route?.tx_count ?? 0);

    const structuralVolumeRatio = Math.sqrt(
      Math.max(0, finalVolume) / maxFinalVolume
    );

    const structuralFrequencyRatio = Math.sqrt(
      Math.max(0, finalTxCount) / maxFinalTxCount
    );

    const appearance = Math.max(
      0,
      Math.min(1, Number(route?.appearance_progress ?? 1))
    );

    const traffic = Math.max(
      0,
      Math.min(1, Number(route?.traffic_progress ?? 1))
    );

    const inactivityFade = Math.max(
      0,
      Math.min(1, Number(route?.inactivity_fade ?? 1))
    );

    if (appearance <= 0 || inactivityFade <= 0) {
      return;
    }

    const isStaticLightMap =
      getProfessionalConsumptionMapViewMode() === "static"
      && !document.body.classList.contains("dark-mode");

    const structuralWeight =
      structuralVolumeRatio * 0.68
      + structuralFrequencyRatio * 0.32;

    const trafficPresence = 0.18 + traffic * 0.82;
    const routeBirth = 0.22 + appearance * 0.78;

    const traceProgress =
      appearance < 0.999
        ? easeProfessionalConsumptionMapProgress(appearance)
        : 1;

    const staticLightWidthBoost = isStaticLightMap ? 1.10 : 1;
    const visualFade = inactivityFade;

    // CARTO_UP002A_SAFE — faisceaux plus fins : la relation doit guider, pas saturer.
    const coreWidth =
      (0.24 + structuralWeight * 1.62)
      * routeBirth
      * (0.58 + trafficPresence * 0.42)
      * staticLightWidthBoost
      * (0.42 + visualFade * 0.58);

    const haloWidth = coreWidth * (
      isStaticLightMap
        ? 1.55 + traffic * 0.45
        : 1.85 + traffic * 0.60
    );

    const bodyWidth = coreWidth * (
      isStaticLightMap
        ? 1.05 + traffic * 0.24
        : 1.10 + traffic * 0.26
    );

    const haloAlpha =
      (0.010 + structuralWeight * 0.060)
      * appearance
      * (0.24 + traffic * 0.76)
      * (isStaticLightMap ? 0.72 : 0.82)
      * visualFade
      * densityLightFactor;

    const bodyAlpha =
      (0.026 + structuralWeight * 0.130)
      * appearance
      * (0.26 + traffic * 0.74)
      * (isStaticLightMap ? 1.05 : 0.88)
      * visualFade
      * densityLightFactor;

    const coreAlpha =
      (0.075 + structuralWeight * 0.300)
      * appearance
      * (0.34 + traffic * 0.66)
      * (isStaticLightMap ? 1.00 : 0.88)
      * visualFade
      * (0.92 + densityLightFactor * 0.08);

    geometry.strands.forEach((strand) => {
      const {
        source,
        destinationPoint,
        controlX,
        controlY,
        strandIndex
      } = strand;

      const routeGradientPalette = isStaticLightMap
        ? {
            start: "220, 38, 38",
            middle: "217, 119, 6",
            end: "5, 150, 105"
          }
        : {
            start: "248, 113, 113",
            middle: "251, 191, 36",
            end: "52, 211, 153"
          };

      const buildGradient = (alpha) => {
        const gradient = ctx.createLinearGradient(
          source.x,
          source.y,
          destinationPoint.x,
          destinationPoint.y
        );

        gradient.addColorStop(
          0,
          `rgba(${routeGradientPalette.start}, ${alpha})`
        );
        gradient.addColorStop(
          0.48,
          `rgba(${routeGradientPalette.middle}, ${alpha * 0.96})`
        );
        gradient.addColorStop(
          1,
          `rgba(${routeGradientPalette.end}, ${alpha})`
        );

        return gradient;
      };

      if (isStaticLightMap) {
        const underlayAlpha = Math.min(
          0.18,
          0.035 + structuralWeight * 0.085 + traffic * 0.035
        ) * visualFade;

        drawCurve(
          source,
          controlX,
          controlY,
          destinationPoint,
          `rgba(51, 65, 85, ${underlayAlpha})`,
          coreWidth * 0.82,
          0,
          "rgba(51, 65, 85, 0)",
          "source-over",
          traceProgress
        );
      }

      drawCurve(
        source,
        controlX,
        controlY,
        destinationPoint,
        buildGradient(haloAlpha),
        haloWidth,
        (4 + traffic * 9 + structuralWeight * 4)
          * visualFade
          * densityLightFactor,
        `rgba(16, 185, 129, ${(0.03 + traffic * 0.18) * visualFade})`,
        isStaticLightMap ? "source-over" : "lighter",
        traceProgress
      );

      drawCurve(
        source,
        controlX,
        controlY,
        destinationPoint,
        buildGradient(bodyAlpha),
        bodyWidth,
        (2 + traffic * 5 + structuralWeight * 2)
          * visualFade
          * densityLightFactor,
        `rgba(245, 158, 11, ${(0.02 + traffic * 0.12) * visualFade})`,
        isStaticLightMap ? "source-over" : "lighter",
        traceProgress
      );

      drawCurve(
        source,
        controlX,
        controlY,
        destinationPoint,
        buildGradient(coreAlpha),
        coreWidth,
        (0.5 + traffic * 2.2)
          * visualFade
          * densityLightFactor,
        `rgba(255, 255, 255, ${(0.015 + traffic * 0.08) * visualFade})`,
        "source-over",
        traceProgress
      );

      if (traceProgress < 0.999 && visualFade > 0.15) {
        const headPoint = getProfessionalConsumptionMapQuadraticPoint(
          source,
          { x: controlX, y: controlY },
          destinationPoint,
          traceProgress
        );

        drawProfessionalConsumptionMapRouteHeadParticle(
          ctx,
          headPoint,
          {
            structuralWeight,
            traffic,
            appearance: appearance * visualFade
          }
        );
      }
    });
  });
}


function drawProfessionalConsumptionMapSourcePoints(ctx, surface, payload) {
  const pointsByKey = new Map();

  (payload?.routes || []).forEach((route) => {
    const appearance = Math.max(
      0,
      Math.min(1, Number(route?.appearance_progress ?? 1))
    );

    const inactivityFade = Math.max(
      0,
      Math.min(1, Number(route?.inactivity_fade ?? 1))
    );

    const pointIntensity = appearance * inactivityFade;

    if (pointIntensity <= 0) {
      return;
    }

    const geometry =
      getProfessionalConsumptionMapProjectedRouteGeometry(route, surface);

    if (!geometry) {
      return;
    }

    geometry.strands.forEach((strand) => {
      const key = `${strand.source.x}|${strand.source.y}`;
      const existing = pointsByKey.get(key);

      if (!existing || pointIntensity > existing.intensity) {
        pointsByKey.set(key, {
          point: strand.source,
          intensity: pointIntensity
        });
      }
    });
  });

  ctx.save();

  const densityLightFactor =
    getProfessionalConsumptionMapDensityLightFactor(payload);

  pointsByKey.forEach(({ point, intensity }) => {
    // CARTO_UP002A_SAFE — les sources sont des bassins, pas des points individuels.
    const outerRadius = 2.1 + 1.2 * intensity;
    const innerRadius = 0.75 + 0.55 * intensity;

    ctx.save();
    ctx.globalCompositeOperation = "lighter";

    ctx.beginPath();
    ctx.fillStyle = `rgba(248, 113, 113, ${(0.05 + 0.08 * intensity) * densityLightFactor})`;
    ctx.shadowBlur = (5 + 7 * intensity) * densityLightFactor;
    ctx.shadowColor = `rgba(248, 113, 113, ${(0.16 + 0.29 * intensity) * densityLightFactor})`;
    ctx.arc(point.x, point.y, outerRadius, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.fillStyle = `rgba(251, 113, 133, ${(0.24 + 0.54 * intensity) * densityLightFactor})`;
    ctx.shadowBlur = (2 + 3 * intensity) * densityLightFactor;
    ctx.shadowColor = `rgba(251, 113, 133, ${(0.18 + 0.32 * intensity) * densityLightFactor})`;
    ctx.arc(point.x, point.y, innerRadius, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  });

  ctx.restore();
}


function drawProfessionalConsumptionMapDestinations(ctx, surface, payload) {
  const destinations = payload?.destinations || [];

  const referenceDestinations =
    appState.professionalConsumptionMap?.destinations
    || destinations;

  const maxFinalVolume = Math.max(
    1,
    ...referenceDestinations.map((destination) => Number(destination?.volume || 0))
  );

  const maxFinalTxCount = Math.max(
    1,
    ...referenceDestinations.map((destination) => Number(destination?.tx_count || 0))
  );

  const densityLightFactor =
    getProfessionalConsumptionMapDensityLightFactor(payload);

  destinations.forEach((destination) => {
    const point =
      getProfessionalConsumptionMapProjectedDestinationPoint(
        destination,
        surface
      );

    if (!point) {
      return;
    }

    const finalVolume = Number(destination?.final_volume ?? destination?.volume ?? 0);
    const finalTxCount = Number(destination?.final_tx_count ?? destination?.tx_count ?? 0);

    const structuralVolumeRatio = Math.sqrt(
      Math.max(0, finalVolume) / maxFinalVolume
    );

    const structuralFrequencyRatio = Math.sqrt(
      Math.max(0, finalTxCount) / maxFinalTxCount
    );

    const structuralWeight =
      structuralVolumeRatio * 0.62
      + structuralFrequencyRatio * 0.38;

    const appearance = Math.max(
      0,
      Math.min(1, Number(destination?.appearance_progress ?? 1))
    );

    const traffic = Math.max(
      0,
      Math.min(1, Number(destination?.traffic_progress ?? 1))
    );

    const inactivityFade = Math.max(
      0,
      Math.min(1, Number(destination?.inactivity_fade ?? 1))
    );

    const visualFade = appearance * inactivityFade;

    if (visualFade <= 0) {
      return;
    }

    const nodeBirth = 0.36 + 0.64 * appearance;
    const trafficPresence = 0.24 + 0.76 * traffic;

    // CARTO_UP002A_SAFE — le pro devient le point d'arrivée lisible.
    const coreRadius =
      (3.1 + structuralWeight * 6.4)
      * nodeBirth
      * (0.68 + trafficPresence * 0.32)
      * (0.50 + inactivityFade * 0.50);

    const haloRadius =
      coreRadius * (1.15 + traffic * 0.50);

    const outerHaloRadius =
      coreRadius * (1.85 + traffic * 0.70);

    ctx.save();
    ctx.globalCompositeOperation = "lighter";

    const outerGlow = ctx.createRadialGradient(
      point.x,
      point.y,
      0,
      point.x,
      point.y,
      outerHaloRadius
    );
    outerGlow.addColorStop(
      0,
      `rgba(52, 211, 153, ${(0.040 + structuralWeight * 0.100) * visualFade * trafficPresence * densityLightFactor})`
    );
    outerGlow.addColorStop(
      0.56,
      `rgba(16, 185, 129, ${(0.018 + structuralWeight * 0.050) * visualFade * trafficPresence * densityLightFactor})`
    );
    outerGlow.addColorStop(1, "rgba(16, 185, 129, 0)");

    ctx.fillStyle = outerGlow;
    ctx.beginPath();
    ctx.arc(point.x, point.y, outerHaloRadius, 0, Math.PI * 2);
    ctx.fill();

    const innerGlow = ctx.createRadialGradient(
      point.x,
      point.y,
      0,
      point.x,
      point.y,
      haloRadius
    );
    innerGlow.addColorStop(
      0,
      `rgba(167, 243, 208, ${(0.095 + structuralWeight * 0.170) * visualFade * trafficPresence * densityLightFactor})`
    );
    innerGlow.addColorStop(1, "rgba(52, 211, 153, 0)");

    ctx.fillStyle = innerGlow;
    ctx.beginPath();
    ctx.arc(point.x, point.y, haloRadius, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();

    ctx.save();

    ctx.beginPath();
    ctx.fillStyle = `rgba(16, 185, 129, ${0.18 + 0.72 * visualFade * trafficPresence})`;
    ctx.shadowBlur =
      (6 + structuralWeight * 10 + traffic * 16)
      * visualFade
      * densityLightFactor;
    ctx.shadowColor =
      `rgba(52, 211, 153, ${0.16 + 0.42 * visualFade * trafficPresence})`;
    ctx.arc(point.x, point.y, coreRadius, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.strokeStyle =
      `rgba(236, 253, 245, ${0.22 + 0.70 * visualFade * trafficPresence})`;
    ctx.lineWidth = 1.25;
    ctx.arc(point.x, point.y, coreRadius, 0, Math.PI * 2);
    ctx.stroke();

    ctx.restore();
  });
}

function drawProfessionalConsumptionMapCaption(ctx, projection, payload) {
  const coverage = payload?.coverage || {};

  ctx.save();

  ctx.fillStyle = "rgba(2, 6, 23, 0.58)";
  ctx.beginPath();
  ctx.roundRect(18, 16, 430, 54, 14);
  ctx.fill();

  ctx.fillStyle = "rgba(241, 245, 249, 0.96)";
  ctx.font = "600 13px Inter, system-ui, sans-serif";
  ctx.fillText(
    "Rouge : origine agrégée  →  Vert : professionnel",
    32,
    37
  );

  ctx.fillStyle = "rgba(203, 213, 225, 0.92)";
  ctx.font = "500 12px Inter, system-ui, sans-serif";
  ctx.fillText(
    `${formatProfessionalSummaryInteger(coverage.visible_route_count || 0)} faisceaux visibles · ${euro(coverage.visible_volume || 0)} représentés`,
    32,
    56
  );

  ctx.restore();
}




function getCurrentMlcfluxTheme() {
  return document.body.classList.contains("dark-mode")
    ? "dark"
    : "light";
}

function enterProfessionalConsumptionMapDynamicTheme() {
  if (!appState.professionalConsumptionMapThemeOverrideActive) {
    appState.professionalConsumptionMapThemeBeforeDynamic =
      getCurrentMlcfluxTheme();

    appState.professionalConsumptionMapThemeOverrideActive = true;
  }

  // Thème forcé visuellement, sans écraser la préférence persistée.
  applyTheme("dark", false);
}

function restoreProfessionalConsumptionMapDynamicTheme() {
  if (!appState.professionalConsumptionMapThemeOverrideActive) {
    return;
  }

  const themeToRestore =
    appState.professionalConsumptionMapThemeBeforeDynamic
    || localStorage.getItem("mlcflux_theme")
    || "light";

  appState.professionalConsumptionMapThemeOverrideActive = false;
  appState.professionalConsumptionMapThemeBeforeDynamic = null;

  // Restauration visuelle, sans modifier la préférence déjà stockée.
  applyTheme(themeToRestore, false);
}


function buildProfessionalConsumptionMapHelpHtml() {
  return buildAnalyticHelpHtml(PROFESSIONAL_CONSUMPTION_MAP_HELP, {
    kicker: "Aide à la lecture",
    fallbackTitle: "Répartition territoriale des flux U→P",
    fallbackText: "Aucune aide détaillée n’est encore définie pour cette carte."
  });
}

function openProfessionalConsumptionMapHelp() {
  openStatsChartModal(
    buildProfessionalConsumptionMapHelpHtml(),
    "help"
  );
}


function buildProfessionalConsumptionMapZoomPlayerHtml() {
  const payload = appState.professionalConsumptionMap || null;

  if (!payload) {
    return "";
  }

  const state = getProfessionalConsumptionMapPlayerState(payload);
  const timeline = getProfessionalConsumptionMapTimeline(payload);
  const steps = timeline?.steps || [];
  const currentStep =
    steps[state.stepIndex]
    || steps[steps.length - 1]
    || null;

  const snapshot =
    appState.professionalConsumptionMapRenderPayload
    || payload;

  const coverage = snapshot?.coverage || {};
  const isDynamic = getProfessionalConsumptionMapViewMode() === "dynamic";

  return `
    <div
      class="professional-consumption-map-player professional-consumption-map-player-overlay professional-consumption-map-player-zoom-overlay"
      data-professional-consumption-map-player
      aria-hidden="${isDynamic ? "false" : "true"}"
      ${isDynamic ? "" : "hidden"}
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
            ${state.isPlaying ? "" : "disabled"}
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
            class="professional-consumption-map-duration-btn ${state.durationMs === 10000 ? "is-active" : ""}"
            data-consumption-map-duration="10000"
          >
            10 s
          </button>

          <button
            type="button"
            class="professional-consumption-map-duration-btn ${state.durationMs === 30000 ? "is-active" : ""}"
            data-consumption-map-duration="30000"
          >
            30 s
          </button>

          <button
            type="button"
            class="professional-consumption-map-duration-btn ${state.durationMs === 60000 ? "is-active" : ""}"
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
          max="${state.finalStep}"
          value="${state.stepIndex}"
          step="1"
          data-consumption-map-range
        />

        <div class="professional-consumption-map-player-readout">
          <strong data-consumption-map-current-label>
            ${currentStep?.label || "Fin de période"}
          </strong>

          <span data-consumption-map-current-metrics>
            ${formatProfessionalSummaryInteger(coverage.visible_route_count || 0)} faisceau(x)
            · ${formatProfessionalSummaryInteger(coverage.visible_tx_count || 0)} paiement(s)
            · ${euro(coverage.visible_volume || 0)}
          </span>
        </div>
      </div>
    </div>
  `;
}


function renderProfessionalConsumptionMapZoomCanvas() {
  const canvas = document.getElementById("professionalConsumptionMapZoomCanvas");
  const rawPayload = appState.professionalConsumptionMapRenderPayload
    || appState.professionalConsumptionMap
    || null;
  const payload = buildProfessionalConsumptionMapVisualPayload(rawPayload);

  if (!canvas || !payload) {
    return;
  }

  const frame = canvas.parentElement;
  const rect = frame?.getBoundingClientRect?.();

  const width = Math.max(960, Math.round(rect?.width || 1280));
  const height = Math.max(640, Math.round(rect?.height || 820));
  const dpr = window.devicePixelRatio || 1;

  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const basePayload = payload;
  const surface = getProfessionalConsumptionMapRenderSurface(
    "zoom",
    basePayload,
    width,
    height,
    dpr
  );

  if (!surface?.projection) {
    return;
  }

  drawProfessionalConsumptionMapCachedFixedLayer(ctx, surface);
  drawProfessionalConsumptionMapRoutes(ctx, surface, payload);
  drawProfessionalConsumptionMapSourcePoints(ctx, surface, payload);
  drawProfessionalConsumptionMapDestinations(ctx, surface, payload);
  drawProfessionalConsumptionMapCaption(ctx, surface.projection, payload);
}

function bindProfessionalConsumptionMapZoomModalControls() {
  const modal = document.getElementById("statsChartModal");
  if (!modal) {
    return;
  }

  const helpButton = modal.querySelector(
    "[data-professional-consumption-map-zoom-help]"
  );
  const helpPanel = modal.querySelector(
    "#professionalConsumptionMapZoomHelpPanel"
  );

  if (helpButton && helpPanel) {
    helpButton.addEventListener("click", () => {
      helpPanel.classList.toggle("hidden");
      helpButton.classList.toggle(
        "stats-chart-tool-btn-active",
        !helpPanel.classList.contains("hidden")
      );
    });
  }
}

function openProfessionalConsumptionMapZoom() {
  const payload = appState.professionalConsumptionMapRenderPayload
    || appState.professionalConsumptionMap
    || null;

  if (!payload) {
    return;
  }

  openStatsChartModal(`
    <div class="professional-consumption-map-zoom-shell">
      <p class="stats-chart-modal-kicker">Agrandissement</p>

      <div class="stats-chart-zoom-header">
        <div class="stats-chart-zoom-title-group">
          <h2>Répartition territoriale des flux U→P</h2>
          <p class="stats-chart-help-summary">
            Vue agrandie de la carte U→P. Elle reprend l’état actuellement affiché :
            carte statique complète ou séquence dynamique en cours.
          </p>
        </div>

        <div class="stats-chart-zoom-actions">
          <button
            type="button"
            class="stats-chart-tool-btn"
            data-professional-consumption-map-zoom-help
            aria-label="Afficher l’aide de lecture de la carte agrandie"
            title="Aide à la lecture"
          >
            ?
          </button>
        </div>
      </div>

      <aside
        id="professionalConsumptionMapZoomHelpPanel"
        class="stats-chart-zoom-help hidden"
      >
        ${buildProfessionalConsumptionMapHelpHtml()}
      </aside>

      <div class="professional-consumption-map-zoom-frame">
        <canvas id="professionalConsumptionMapZoomCanvas"></canvas>
        ${buildProfessionalConsumptionMapZoomPlayerHtml()}
      </div>

      <p class="professional-consumption-map-zoom-note">
        L’agrandissement reste synchronisé avec la carte principale :
        si la lecture dynamique est en cours, la visualisation agrandie évolue elle aussi.
      </p>
    </div>
  `, "consumption-map-zoom");

  window.requestAnimationFrame(() => {
    renderProfessionalConsumptionMapZoomCanvas();
    bindProfessionalConsumptionMapZoomModalControls();
    bindProfessionalConsumptionMapPlayerControls();
    updateProfessionalConsumptionMapPlayerUi();
  });
}

function bindProfessionalConsumptionMapTools() {
  document
    .querySelectorAll("[data-professional-consumption-map-help]")
    .forEach((button) => {
      if (button.dataset.bound === "true") {
        return;
      }

      button.addEventListener("click", () => {
        openProfessionalConsumptionMapHelp();
      });

      button.dataset.bound = "true";
    });

  document
    .querySelectorAll("[data-professional-consumption-map-zoom]")
    .forEach((button) => {
      if (button.dataset.bound === "true") {
        return;
      }

      button.addEventListener("click", () => {
        openProfessionalConsumptionMapZoom();
      });

      button.dataset.bound = "true";
    });

  document
    .querySelectorAll("[data-professional-consumption-map-source-filter]")
    .forEach((select) => {
      if (select.dataset.bound === "true") {
        return;
      }

      select.addEventListener("change", () => {
        setProfessionalConsumptionMapSourceFilter(select.value);
      });

      select.dataset.bound = "true";
    });

  document
    .querySelectorAll("[data-professional-consumption-map-overview-limit]")
    .forEach((select) => {
      if (select.dataset.bound === "true") {
        return;
      }

      select.addEventListener("change", () => {
        setProfessionalConsumptionMapOverviewLimit(select.value);
      });

      select.dataset.bound = "true";
    });

  document
    .querySelectorAll("[data-professional-consumption-map-reset-focus]")
    .forEach((button) => {
      if (button.dataset.bound === "true") {
        return;
      }

      button.addEventListener("click", () => {
        appState.professionalConsumptionMapSelectedSourcePostalCode = "";
        refreshProfessionalConsumptionMapVisualRender();
      });

      button.dataset.bound = "true";
    });

}
function getProfessionalConsumptionMapViewMode() {
  return appState.professionalConsumptionMapViewMode === "dynamic"
    ? "dynamic"
    : "static";
}

function applyProfessionalConsumptionMapViewModeUi() {
  const mode = getProfessionalConsumptionMapViewMode();

  const toggleRoot = document.querySelector(
    "[data-professional-consumption-map-mode-toggle]"
  );
  const playerRoots = document.querySelectorAll(
    "[data-professional-consumption-map-player]"
  );

  toggleRoot
    ?.querySelectorAll("[data-consumption-map-view-mode]")
    .forEach((button) => {
      const isActive = button.dataset.consumptionMapViewMode === mode;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });

  playerRoots.forEach((playerRoot) => {
    const shouldHidePlayer = mode !== "dynamic";
    playerRoot.hidden = shouldHidePlayer;
    playerRoot.setAttribute(
      "aria-hidden",
      shouldHidePlayer ? "true" : "false"
    );
  });
}

function setProfessionalConsumptionMapViewMode(mode) {
  const nextMode = mode === "dynamic" ? "dynamic" : "static";
  const payload = appState.professionalConsumptionMap || null;

  appState.professionalConsumptionMapViewMode = nextMode;

  if (nextMode === "static") {
    pauseProfessionalConsumptionMapPlayback();
    restoreProfessionalConsumptionMapDynamicTheme();

    appState.professionalConsumptionMapRenderPayload =
      getProfessionalConsumptionMapFinalRenderPayload(payload);

    if (payload) {
      const state = getProfessionalConsumptionMapPlayerState(payload);
      state.stepIndex = state.finalStep;
      state.frameStep = state.finalStep;
      state.isPlaying = false;
    }
  } else {
    pauseProfessionalConsumptionMapPlayback();
    enterProfessionalConsumptionMapDynamicTheme();

    // On ouvre le mode dynamique sur la carte complète.
    // Le clic sur Lecture ou Rejouer relancera depuis le début.
    appState.professionalConsumptionMapRenderPayload =
      getProfessionalConsumptionMapFinalRenderPayload(payload);

    if (payload) {
      const state = getProfessionalConsumptionMapPlayerState(payload);
      state.stepIndex = state.finalStep;
      state.frameStep = state.finalStep;
      state.isPlaying = false;
    }
  }

  applyProfessionalConsumptionMapViewModeUi();
  renderProfessionalConsumptionMapCanvas();
  updateProfessionalConsumptionMapPlayerUi();
}

function bindProfessionalConsumptionMapModeToggleControls() {
  const root = document.querySelector(
    "[data-professional-consumption-map-mode-toggle]"
  );

  if (!root) {
    return;
  }

  if (root.dataset.bound === "true") {
    applyProfessionalConsumptionMapViewModeUi();
    return;
  }

  root.dataset.bound = "true";

  root
    .querySelectorAll("[data-consumption-map-view-mode]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        setProfessionalConsumptionMapViewMode(
          button.dataset.consumptionMapViewMode
        );
      });
    });

  applyProfessionalConsumptionMapViewModeUi();
}

function getProfessionalConsumptionMapTimeline(payload) {
  return payload?.timeline || {
    step_count: 0,
    steps: []
  };
}

function getProfessionalConsumptionMapFinalStepIndex(payload) {
  const timeline = getProfessionalConsumptionMapTimeline(payload);
  const steps = timeline?.steps || [];
  return Math.max(0, steps.length - 1);
}

function getProfessionalConsumptionMapDefaultDurationMs() {
  return 30000;
}

function getProfessionalConsumptionMapPlayerState(payload) {
  const finalStep = getProfessionalConsumptionMapFinalStepIndex(payload);
  const periodKey = appState.professionalConsumptionMapPeriodKey || "";

  const existing = appState.professionalConsumptionMapPlayer || null;

  if (
    !existing
    || existing.periodKey !== periodKey
    || existing.finalStep !== finalStep
  ) {
    appState.professionalConsumptionMapPlayer = {
      periodKey,
      finalStep,
      stepIndex: finalStep,
      frameStep: finalStep,
      durationMs: getProfessionalConsumptionMapDefaultDurationMs(),
      isPlaying: false,
      animationFrameId: null,
      playbackStartTime: null,
      playbackStartStep: finalStep,
      playbackDurationMs: 0
    };
  }

  return appState.professionalConsumptionMapPlayer;
}


function getProfessionalConsumptionMapRouteStateAtStep(route, stepIndex) {
  const entries = route?.timeline || [];
  let selected = null;

  for (const entry of entries) {
    if (Number(entry?.step) <= Number(stepIndex)) {
      selected = entry;
    } else {
      break;
    }
  }

  return selected;
}


function easeProfessionalConsumptionMapProgress(progress) {
  const value = Math.max(0, Math.min(1, Number(progress || 0)));

  // Smoothstep : début et fin plus doux qu'une interpolation linéaire.
  return value * value * (3 - 2 * value);
}

function getProfessionalConsumptionMapRouteRevealStartStep(route, minUsers) {
  const entries = route?.timeline || [];

  for (const entry of entries) {
    if (Number(entry?.cumulative_distinct_users || 0) >= Number(minUsers || 5)) {
      return Number(entry.step || 0);
    }
  }

  return null;
}

function getProfessionalConsumptionMapRouteRevealProgress(
  route,
  frameStep,
  minUsers
) {
  const revealStartStep = getProfessionalConsumptionMapRouteRevealStartStep(
    route,
    minUsers
  );

  if (revealStartStep === null) {
    return 0;
  }

  const current = Number(frameStep || 0);

  if (current < revealStartStep) {
    return 0;
  }

  /*
    Apparition progressive sur un peu moins d'un pas temporel.
    Sur l'historique complet :
    - 30 s ≈ ~350 ms de fade par mois
    - 60 s ≈ ~700 ms
    - 10 s ≈ ~115 ms
  */
  const fadeWindowSteps = 0.90;
  const raw = Math.min(
    1,
    Math.max(0, (current - revealStartStep) / fadeWindowSteps)
  );

  return easeProfessionalConsumptionMapProgress(raw);
}


function interpolateProfessionalConsumptionMapNumber(
  startValue,
  endValue,
  progress
) {
  const start = Number(startValue || 0);
  const end = Number(endValue || 0);
  const ratio = easeProfessionalConsumptionMapProgress(progress);

  return start + (end - start) * ratio;
}

function getProfessionalConsumptionMapInterpolatedRouteState(
  route,
  frameStep
) {
  const safeFrameStep = Math.max(0, Number(frameStep || 0));
  const baseStep = Math.floor(safeFrameStep);
  const nextStep = baseStep + 1;
  const progress = safeFrameStep - baseStep;

  const baseState = getProfessionalConsumptionMapRouteStateAtStep(
    route,
    baseStep
  );

  const nextState = getProfessionalConsumptionMapRouteStateAtStep(
    route,
    nextStep
  );

  if (!baseState) {
    return null;
  }

  if (
    !nextState
    || Number(nextState.step) === Number(baseState.step)
    || progress <= 0
  ) {
    return {
      cumulative_tx_count: Number(baseState.cumulative_tx_count || 0),
      cumulative_volume: Number(baseState.cumulative_volume || 0),
      cumulative_distinct_users: Number(baseState.cumulative_distinct_users || 0),
      interpolated: false
    };
  }

  return {
    cumulative_tx_count: interpolateProfessionalConsumptionMapNumber(
      baseState.cumulative_tx_count,
      nextState.cumulative_tx_count,
      progress
    ),
    cumulative_volume: interpolateProfessionalConsumptionMapNumber(
      baseState.cumulative_volume,
      nextState.cumulative_volume,
      progress
    ),
    cumulative_distinct_users: interpolateProfessionalConsumptionMapNumber(
      baseState.cumulative_distinct_users,
      nextState.cumulative_distinct_users,
      progress
    ),
    interpolated: true
  };
}

function getProfessionalConsumptionMapTimelineEntryAtStep(route, stepIndex) {
  const entries = route?.timeline || [];
  let selected = null;

  for (const entry of entries) {
    if (Number(entry?.step) <= stepIndex) {
      selected = entry;
    } else {
      break;
    }
  }

  return selected;
}

function getProfessionalConsumptionMapAnimatedStrandCount(route, entry) {
  const fullPoints = route?.source_points || [];
  const fullCount = fullPoints.length;

  if (!fullCount) {
    return 0;
  }

  const fullVolume = Math.max(1, Number(route?.volume || 0));
  const currentVolume = Math.max(0, Number(entry?.cumulative_volume || 0));
  const ratio = Math.min(1, currentVolume / fullVolume);

  return Math.max(
    1,
    Math.min(
      fullCount,
      Math.ceil(fullCount * Math.sqrt(ratio))
    )
  );
}





function getProfessionalConsumptionMapInactivityWindows(payload) {
  const granularity = payload?.timeline?.granularity || "month";

  if (granularity === "day") {
    return {
      fadeStartSteps: 183,
      fadeEndSteps: 365
    };
  }

  if (granularity === "week") {
    return {
      fadeStartSteps: 26,
      fadeEndSteps: 52
    };
  }

  return {
    fadeStartSteps: 6,
    fadeEndSteps: 12
  };
}

function getProfessionalConsumptionMapLastActivityStep(route, frameStep) {
  const entries = route?.timeline || [];
  const current = Number(frameStep || 0);
  let lastStep = null;

  for (const entry of entries) {
    const step = Number(entry?.step);

    if (Number.isFinite(step) && step <= current) {
      lastStep = step;
    } else {
      break;
    }
  }

  return lastStep;
}

function getProfessionalConsumptionMapInactivityFade(route, frameStep, payload) {
  const lastActivityStep = getProfessionalConsumptionMapLastActivityStep(
    route,
    frameStep
  );

  if (lastActivityStep === null) {
    return {
      last_activity_step: null,
      inactive_steps: null,
      inactivity_fade: 0
    };
  }

  const { fadeStartSteps, fadeEndSteps } =
    getProfessionalConsumptionMapInactivityWindows(payload);

  const inactiveSteps = Math.max(
    0,
    Number(frameStep || 0) - Number(lastActivityStep || 0)
  );

  if (inactiveSteps <= fadeStartSteps) {
    return {
      last_activity_step: lastActivityStep,
      inactive_steps: inactiveSteps,
      inactivity_fade: 1
    };
  }

  if (inactiveSteps >= fadeEndSteps) {
    return {
      last_activity_step: lastActivityStep,
      inactive_steps: inactiveSteps,
      inactivity_fade: 0
    };
  }

  const raw =
    1
    - ((inactiveSteps - fadeStartSteps) / (fadeEndSteps - fadeStartSteps));

  return {
    last_activity_step: lastActivityStep,
    inactive_steps: inactiveSteps,
    inactivity_fade: easeProfessionalConsumptionMapProgress(raw)
  };
}

function getProfessionalConsumptionMapFinalRenderPayload(payload) {
  if (!payload) {
    return null;
  }

  const timeline = getProfessionalConsumptionMapTimeline(payload);
  const steps = Array.isArray(timeline?.steps) ? timeline.steps : [];

  /*
    Compat POSTAL002D :
    La nouvelle API /api/user-to-professional-map expose déjà un payload
    statique complet pour la période entière : routes, source_points,
    destinations, coverage et géométrie sont directement dessinables.

    L'ancien moteur dynamique reconstruit un snapshot à partir d'une timeline
    multi-pas. Sur une timeline neutre "all_period" à un seul pas, cette
    reconstruction peut produire un snapshot vide alors que le payload brut
    est valide. On court-circuite donc le snapshot dynamique dans ce cas.
  */
  if (
    timeline?.granularity === "all_period"
    || steps.length <= 1
  ) {
    return payload;
  }

  return buildProfessionalConsumptionMapSnapshotPayload(
    payload,
    getProfessionalConsumptionMapFinalStepIndex(payload)
  );
}

function clampProfessionalConsumptionMapRatio(value) {
  return Math.max(0, Math.min(1, Number(value || 0)));
}

function getProfessionalConsumptionMapTrafficProgress({
  cumulativeTxCount,
  finalTxCount,
  cumulativeVolume,
  finalVolume
}) {
  const frequencyProgress = finalTxCount
    ? clampProfessionalConsumptionMapRatio(
        Number(cumulativeTxCount || 0) / Number(finalTxCount || 1)
      )
    : 0;

  const volumeProgress = finalVolume
    ? clampProfessionalConsumptionMapRatio(
        Number(cumulativeVolume || 0) / Number(finalVolume || 1)
      )
    : 0;

  /*
    Le phénomène que l’on veut surtout faire sentir ici,
    c’est la route qui devient "empruntée" de manière répétée.
    On donne donc davantage de poids à la fréquence qu'au volume.
  */
  const blendedProgress =
    frequencyProgress * 0.72
    + volumeProgress * 0.28;

  return {
    frequency_progress: frequencyProgress,
    volume_progress: volumeProgress,
    traffic_progress: easeProfessionalConsumptionMapProgress(blendedProgress)
  };
}



function buildProfessionalConsumptionMapSnapshotPayload(payload, frameStep) {
  if (!payload) {
    return null;
  }

  const timeline = getProfessionalConsumptionMapTimeline(payload);
  const finalStep = getProfessionalConsumptionMapFinalStepIndex(payload);
  const safeFrameStep = Math.max(0, Number(frameStep || 0));

  if (!timeline?.steps?.length) {
    return payload;
  }

  const minUsers = Number(payload?.privacy?.min_distinct_users_per_route || 5);
  const activeRoutes = [];

  const destinationsByRef = new Map();
  const baseDestinationsByRef = new Map(
    (payload?.destinations || []).map((destination) => [
      destination.professional_ref,
      destination
    ])
  );

  let visibleTxCount = 0;
  let visibleVolume = 0;

  (payload?.routes || []).forEach((route) => {
    const state = getProfessionalConsumptionMapInterpolatedRouteState(
      route,
      safeFrameStep
    );

    if (!state) {
      return;
    }

    const cumulativeUsers = Number(state?.cumulative_distinct_users || 0);
    const cumulativeVolume = Number(state?.cumulative_volume || 0);
    const cumulativeTxCount = Number(state?.cumulative_tx_count || 0);

    const finalTxCount = Number(route?.tx_count || 0);
    const finalVolume = Number(route?.volume || 0);

    const appearanceProgress = getProfessionalConsumptionMapRouteRevealProgress(
      route,
      safeFrameStep,
      minUsers
    );

    if (
      cumulativeUsers < minUsers
      || cumulativeVolume <= 0
      || appearanceProgress <= 0
    ) {
      return;
    }

    const traffic = getProfessionalConsumptionMapTrafficProgress({
      cumulativeTxCount,
      finalTxCount,
      cumulativeVolume,
      finalVolume
    });

    const inactivity = getProfessionalConsumptionMapInactivityFade(
      route,
      safeFrameStep,
      payload
    );

    const activeRoute = {
      ...route,

      volume: cumulativeVolume,
      tx_count: cumulativeTxCount,
      distinct_users: cumulativeUsers,

      final_volume: finalVolume,
      final_tx_count: finalTxCount,

      appearance_progress: appearanceProgress,
      frequency_progress: traffic.frequency_progress,
      volume_progress: traffic.volume_progress,
      traffic_progress: traffic.traffic_progress,

      last_activity_step: inactivity.last_activity_step,
      inactive_steps: inactivity.inactive_steps,
      inactivity_fade: inactivity.inactivity_fade,

      strand_count: (route?.source_points || []).length,
      source_points: route?.source_points || []
    };

    activeRoutes.push(activeRoute);

    visibleTxCount += cumulativeTxCount;
    visibleVolume += cumulativeVolume;

    const professionalRef = route?.professional_ref;
    const baseDestination = baseDestinationsByRef.get(professionalRef) || {};

    if (!destinationsByRef.has(professionalRef)) {
      destinationsByRef.set(professionalRef, {
        ...baseDestination,
        professional_ref: professionalRef,
        professional_label: route?.professional_label,
        professional_city: route?.professional_city,
        professional_zip: route?.professional_zip,
        industry_name: route?.industry_name,
        latitude: route?.destination?.latitude,
        longitude: route?.destination?.longitude,

        route_count: 0,
        tx_count: 0,
        volume: 0,

        final_tx_count: Number(baseDestination?.tx_count || 0),
        final_volume: Number(baseDestination?.volume || 0),

        appearance_progress: 0,
        traffic_progress: 0,
        inactivity_fade: 0,
        source_postal_codes: new Set()
      });
    }

    const destination = destinationsByRef.get(professionalRef);
    destination.route_count += 1;
    destination.tx_count += cumulativeTxCount;
    destination.volume += cumulativeVolume;

    destination.appearance_progress = Math.max(
      Number(destination.appearance_progress || 0),
      appearanceProgress
    );

    destination.traffic_progress = Math.max(
      Number(destination.traffic_progress || 0),
      Number(traffic.traffic_progress || 0)
    );

    destination.inactivity_fade = Math.max(
      Number(destination.inactivity_fade || 0),
      Number(inactivity.inactivity_fade || 0)
    );

    destination.source_postal_codes.add(route?.source_postal_code);
  });

  const destinations = [...destinationsByRef.values()].map((destination) => ({
    ...destination,
    volume: Number(destination.volume || 0),
    distinct_source_postal_codes: destination.source_postal_codes.size
  }));

  destinations.sort((a, b) => Number(b.volume || 0) - Number(a.volume || 0));

  const cartographiableTx = Number(payload?.coverage?.cartographiable_tx_count || 0);
  const cartographiableVolume = Number(payload?.coverage?.cartographiable_volume || 0);

  return {
    ...payload,
    routes: activeRoutes,
    destinations,
    coverage: {
      ...(payload?.coverage || {}),
      visible_route_count: activeRoutes.length,
      visible_tx_count: visibleTxCount,
      visible_tx_share_of_cartographiable: cartographiableTx
        ? visibleTxCount / cartographiableTx
        : null,
      visible_volume: visibleVolume,
      visible_volume_share_of_cartographiable: cartographiableVolume
        ? visibleVolume / cartographiableVolume
        : null
    }
  };
}

function pauseProfessionalConsumptionMapPlayback() {
  const payload = appState.professionalConsumptionMap || null;
  const state = getProfessionalConsumptionMapPlayerState(payload);

  state.isPlaying = false;

  if (state.animationFrameId) {
    window.cancelAnimationFrame(state.animationFrameId);
    state.animationFrameId = null;
  }

  updateProfessionalConsumptionMapPlayerUi();
}

function setProfessionalConsumptionMapPlaybackStep(stepIndex) {
  const payload = appState.professionalConsumptionMap || null;
  const state = getProfessionalConsumptionMapPlayerState(payload);
  const finalStep = state.finalStep;

  const bounded = Math.max(
    0,
    Math.min(finalStep, Number(stepIndex || 0))
  );

  state.stepIndex = bounded;
  state.frameStep = bounded;
  appState.professionalConsumptionMapRenderPayload =
    buildProfessionalConsumptionMapSnapshotPayload(payload, bounded);

  renderProfessionalConsumptionMapCanvas();
  updateProfessionalConsumptionMapPlayerUi();
}

function startProfessionalConsumptionMapPlayback({ restart = false } = {}) {
  const payload = appState.professionalConsumptionMap || null;
  const state = getProfessionalConsumptionMapPlayerState(payload);
  const finalStep = state.finalStep;

  if (!payload?.timeline?.steps?.length || finalStep <= 0) {
    return;
  }

  if (state.animationFrameId) {
    window.cancelAnimationFrame(state.animationFrameId);
    state.animationFrameId = null;
  }

  if (restart || state.stepIndex >= finalStep) {
    state.stepIndex = 0;
    state.frameStep = 0;
    appState.professionalConsumptionMapRenderPayload =
      buildProfessionalConsumptionMapSnapshotPayload(payload, 0);
    renderProfessionalConsumptionMapCanvas();
  }

  if (state.stepIndex >= finalStep) {
    updateProfessionalConsumptionMapPlayerUi();
    return;
  }

  state.isPlaying = true;
  state.playbackStartTime = performance.now();
  state.playbackStartStep = Number(
    state.frameStep ?? state.stepIndex ?? 0
  );

  const remainingSteps = Math.max(1, finalStep - state.stepIndex);
  const totalSteps = Math.max(1, finalStep);
  state.playbackDurationMs = Math.max(
    400,
    state.durationMs * (remainingSteps / totalSteps)
  );

  const animate = (timestamp) => {
    if (!state.isPlaying) {
      return;
    }

    const elapsed = timestamp - state.playbackStartTime;
    const progress = Math.min(1, elapsed / state.playbackDurationMs);

    const rawFrameStep = state.playbackStartStep
      + progress * (finalStep - state.playbackStartStep);

    const nextStep = Math.min(
      finalStep,
      Math.floor(rawFrameStep + 1e-9)
    );

    state.stepIndex = nextStep;
    state.frameStep = Math.min(finalStep, rawFrameStep);

    appState.professionalConsumptionMapRenderPayload =
      buildProfessionalConsumptionMapSnapshotPayload(
        payload,
        state.frameStep
      );

    renderProfessionalConsumptionMapCanvas();
    updateProfessionalConsumptionMapPlayerUi();

    if (progress >= 1) {
      state.isPlaying = false;
      state.animationFrameId = null;
      state.stepIndex = finalStep;
      state.frameStep = finalStep;
      appState.professionalConsumptionMapRenderPayload =
      getProfessionalConsumptionMapFinalRenderPayload(payload);
      renderProfessionalConsumptionMapCanvas();
      updateProfessionalConsumptionMapPlayerUi();
      return;
    }

    state.animationFrameId = window.requestAnimationFrame(animate);
  };

  state.animationFrameId = window.requestAnimationFrame(animate);
  updateProfessionalConsumptionMapPlayerUi();
}

function updateProfessionalConsumptionMapPlayerUi() {
  const roots = document.querySelectorAll("[data-professional-consumption-map-player]");
  const payload = appState.professionalConsumptionMap || null;

  if (!roots.length || !payload) {
    return;
  }

  const state = getProfessionalConsumptionMapPlayerState(payload);
  const timeline = getProfessionalConsumptionMapTimeline(payload);
  const steps = timeline?.steps || [];
  const currentStep = steps[state.stepIndex] || steps[steps.length - 1] || null;
  const snapshot = appState.professionalConsumptionMapRenderPayload || payload;
  const coverage = snapshot?.coverage || {};

  roots.forEach((root) => {
    const range = root.querySelector("[data-consumption-map-range]");
    const label = root.querySelector("[data-consumption-map-current-label]");
    const metrics = root.querySelector("[data-consumption-map-current-metrics]");
    const pauseButton = root.querySelector("[data-consumption-map-pause]");

    if (range) {
      range.max = String(state.finalStep);
      range.value = String(state.stepIndex);
    }

    if (label) {
      label.textContent = currentStep?.label || "Fin de période";
    }

    if (metrics) {
      metrics.textContent =
        `${formatProfessionalSummaryInteger(coverage.visible_route_count || 0)} faisceau(x) · `
        + `${formatProfessionalSummaryInteger(coverage.visible_tx_count || 0)} paiement(s) · `
        + `${euro(coverage.visible_volume || 0)}`;
    }

    if (pauseButton) {
      pauseButton.disabled = !state.isPlaying;
    }

    root.querySelectorAll("[data-consumption-map-duration]").forEach((button) => {
      const duration = Number(button.dataset.consumptionMapDuration || 0);
      button.classList.toggle("is-active", duration === state.durationMs);
    });
  });
}

function bindProfessionalConsumptionMapPlayerControls() {
  const roots = document.querySelectorAll("[data-professional-consumption-map-player]");
  const payload = appState.professionalConsumptionMap || null;

  if (!roots.length || !payload) {
    return;
  }

  getProfessionalConsumptionMapPlayerState(payload);

  roots.forEach((root) => {
    if (root.dataset.bound === "true") {
      return;
    }

    root.dataset.bound = "true";

    const playButton = root.querySelector("[data-consumption-map-play]");
    const pauseButton = root.querySelector("[data-consumption-map-pause]");
    const replayButton = root.querySelector("[data-consumption-map-replay]");
    const range = root.querySelector("[data-consumption-map-range]");

    playButton?.addEventListener("click", () => {
      const state = getProfessionalConsumptionMapPlayerState(payload);
      startProfessionalConsumptionMapPlayback({
        restart: state.stepIndex >= state.finalStep
      });
    });

    pauseButton?.addEventListener("click", () => {
      pauseProfessionalConsumptionMapPlayback();
    });

    replayButton?.addEventListener("click", () => {
      startProfessionalConsumptionMapPlayback({
        restart: true
      });
    });

    range?.addEventListener("input", (event) => {
      pauseProfessionalConsumptionMapPlayback();
      setProfessionalConsumptionMapPlaybackStep(
        Number(event.target.value || 0)
      );
    });

    root.querySelectorAll("[data-consumption-map-duration]").forEach((button) => {
      button.addEventListener("click", () => {
        const state = getProfessionalConsumptionMapPlayerState(payload);
        const duration = Number(button.dataset.consumptionMapDuration || 0);

        if (![10000, 30000, 60000].includes(duration)) {
          return;
        }

        const wasPlaying = state.isPlaying;

        if (wasPlaying) {
          pauseProfessionalConsumptionMapPlayback();
        }

        state.durationMs = duration;
        updateProfessionalConsumptionMapPlayerUi();

        if (wasPlaying) {
          startProfessionalConsumptionMapPlayback({
            restart: false
          });
        }
      });
    });
  });

  updateProfessionalConsumptionMapPlayerUi();
}



function resetProfessionalConsumptionMapRenderCaches() {
  appState.professionalConsumptionMapRenderSurfaces = new Map();
}

function getProfessionalConsumptionMapRenderSurfaceKey(
  surfaceKind,
  width,
  height
) {
  const periodKey =
    appState.professionalConsumptionMapPeriodKey
    || "period:none";

  const themeKey =
    document.body.classList.contains("dark-mode")
      ? "theme:dark"
      : "theme:light";

  return [
    surfaceKind,
    periodKey,
    themeKey,
    `${width}x${height}`
  ].join("|");
}

function createProfessionalConsumptionMapBufferCanvas(
  width,
  height,
  dpr
) {
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);

  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  return {
    canvas,
    ctx
  };
}

function buildProfessionalConsumptionMapProjectionPayload(basePayload) {
  if (!basePayload || typeof basePayload !== "object") {
    return basePayload;
  }

  return {
    ...basePayload,
    geometry: {
      ...(basePayload.geometry || {}),

      /*
        Les périmètres postaux restent dessinés ensuite dans la carte,
        mais ils ne doivent pas forcer le zoom-out de la projection.
        Le cadrage se fait donc sur les éléments actifs du réseau :
        routes, sources synthétiques et professionnels atteints.
      */
      visible_source_area_geojson: {}
    }
  };
}

function getProfessionalConsumptionMapDensityLightFactor(payload) {
  const routeCount = Number(payload?.routes?.length || 0);

  /*
    Référence historique de la première version :
    ~190 routes visibles.
    Avec k≥2, on dépasse 450 routes visibles.
    On amortit doucement l’intensité lumineuse à mesure que la carte se densifie.
  */
  if (routeCount <= 200) {
    return 1;
  }

  const excess = routeCount - 200;
  const reduction = Math.min(0.20, excess / 1300);

  return 1 - reduction;
}

function getProfessionalConsumptionMapRenderSurface(
  surfaceKind,
  basePayload,
  width,
  height,
  dpr
) {
  if (!basePayload) {
    return null;
  }

  if (!(appState.professionalConsumptionMapRenderSurfaces instanceof Map)) {
    resetProfessionalConsumptionMapRenderCaches();
  }

  const key = getProfessionalConsumptionMapRenderSurfaceKey(
    surfaceKind,
    width,
    height
  );

  const existing =
    appState.professionalConsumptionMapRenderSurfaces.get(key);

  if (existing) {
    return existing;
  }

  const projectionPayload =
    buildProfessionalConsumptionMapProjectionPayload(basePayload);

  const projection = buildProfessionalConsumptionMapProjection(
    projectionPayload,
    width,
    height
  );

  if (!projection) {
    return null;
  }

  const buffer = createProfessionalConsumptionMapBufferCanvas(
    width,
    height,
    dpr
  );

  if (buffer.ctx) {
    drawProfessionalConsumptionMapBackdrop(
      buffer.ctx,
      projection,
      basePayload
    );

    drawProfessionalConsumptionMapAreas(
      buffer.ctx,
      projection,
      basePayload
    );
  }

  const surface = {
    key,
    surfaceKind,
    width,
    height,
    dpr,
    projection,
    fixedLayerCanvas: buffer.canvas,
    routeGeometryCache: new Map(),
    destinationGeometryCache: new Map()
  };

  appState.professionalConsumptionMapRenderSurfaces.set(key, surface);

  return surface;
}

function drawProfessionalConsumptionMapCachedFixedLayer(
  ctx,
  surface
) {
  if (!surface?.fixedLayerCanvas) {
    return;
  }

  ctx.save();
  ctx.globalCompositeOperation = "source-over";
  ctx.shadowBlur = 2;
  ctx.shadowColor = "transparent";
  ctx.drawImage(
    surface.fixedLayerCanvas,
    0,
    0,
    surface.width,
    surface.height
  );
  ctx.restore();
}

function getProfessionalConsumptionMapRouteGeometryKey(route) {
  const sourcePostalCode = String(route?.source_postal_code || "");
  const professionalRef = String(route?.professional_ref || "");
  const pointCount = Number(route?.source_points?.length || 0);

  return `${sourcePostalCode}|${professionalRef}|points:${pointCount}`;
}

function getProfessionalConsumptionMapProjectedRouteGeometry(
  route,
  surface
) {
  if (!route || !surface?.projection) {
    return null;
  }

  const key = getProfessionalConsumptionMapRouteGeometryKey(route);
  const cached = surface.routeGeometryCache.get(key);

  if (cached) {
    return cached;
  }

  const projection = surface.projection;
  const destination = route?.destination || {};

  const destinationPoint = projection.project(
    destination.longitude,
    destination.latitude
  );

  const strands = (route?.source_points || []).map(
    (sourcePoint, strandIndex) => {
      const source = projection.project(
        sourcePoint.longitude,
        sourcePoint.latitude
      );

      const dx = destinationPoint.x - source.x;
      const dy = destinationPoint.y - source.y;
      const distance = Math.max(1, Math.hypot(dx, dy));

      const midpointX = (source.x + destinationPoint.x) / 2;
      const midpointY = (source.y + destinationPoint.y) / 2;

      const normalX = -dy / distance;
      const normalY = dx / distance;

      const hash = professionalConsumptionMapHash(
        `${route?.source_postal_code}|${route?.professional_ref}|${strandIndex}`
      );

      const sign = hash % 2 === 0 ? 1 : -1;
      const strandOffset = ((strandIndex % 7) - 3) * 0.055;
      const curvature =
        sign * Math.min(128, distance * (0.17 + strandOffset));

      const controlX = midpointX + normalX * curvature;
      const controlY = midpointY + normalY * curvature;

      return {
        strandIndex,
        source,
        destinationPoint,
        controlX,
        controlY
      };
    }
  );

  const geometry = {
    destinationPoint,
    strands
  };

  surface.routeGeometryCache.set(key, geometry);
  return geometry;
}

function getProfessionalConsumptionMapProjectedDestinationPoint(
  destination,
  surface
) {
  if (!destination || !surface?.projection) {
    return null;
  }

  const key = String(
    destination?.professional_ref
    || `${destination.longitude}|${destination.latitude}`
  );

  const cached = surface.destinationGeometryCache.get(key);
  if (cached) {
    return cached;
  }

  const point = surface.projection.project(
    destination.longitude,
    destination.latitude
  );

  surface.destinationGeometryCache.set(key, point);
  return point;
}


function renderProfessionalConsumptionMapCanvas() {
  const canvas = document.getElementById("professionalConsumptionMapCanvas");
  const rawPayload = appState.professionalConsumptionMapRenderPayload
    || appState.professionalConsumptionMap
    || null;
  const payload = buildProfessionalConsumptionMapVisualPayload(rawPayload);

  if (!canvas || !payload) {
    bindProfessionalConsumptionMapTools();
    bindProfessionalConsumptionMapModeToggleControls();
    bindProfessionalConsumptionMapPlayerControls();
    return;
  }

  const frame = canvas.parentElement;
  const rect = frame?.getBoundingClientRect?.();

  const width = Math.max(720, Math.round(rect?.width || 1080));
  const height = Math.max(520, Math.round(rect?.height || 680));
  const dpr = window.devicePixelRatio || 1;

  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    bindProfessionalConsumptionMapTools();
    bindProfessionalConsumptionMapModeToggleControls();
    bindProfessionalConsumptionMapPlayerControls();
    return;
  }

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const basePayload = payload;
  const surface = getProfessionalConsumptionMapRenderSurface(
    "main",
    basePayload,
    width,
    height,
    dpr
  );

  if (!surface?.projection) {
    bindProfessionalConsumptionMapTools();
    bindProfessionalConsumptionMapModeToggleControls();
    bindProfessionalConsumptionMapPlayerControls();
    return;
  }

  drawProfessionalConsumptionMapCachedFixedLayer(ctx, surface);
  drawProfessionalConsumptionMapRoutes(ctx, surface, payload);
  drawProfessionalConsumptionMapSourcePoints(ctx, surface, payload);
  drawProfessionalConsumptionMapDestinations(ctx, surface, payload);
  drawProfessionalConsumptionMapCaption(ctx, surface.projection, payload);

  bindProfessionalConsumptionMapTools();
  bindProfessionalConsumptionMapModeToggleControls();
  bindProfessionalConsumptionMapPlayerControls();
  renderProfessionalConsumptionMapZoomCanvas();

  bindProfessionalConsumptionMapCanvasHover();
  renderProfessionalConsumptionMapLibre();
}


function refreshProfessionalConsumptionMapThemeRendering() {
  if (typeof resetProfessionalConsumptionMapRenderCaches === "function") {
    resetProfessionalConsumptionMapRenderCaches();
  }

  /*
    Si la carte est présente dans le DOM, on la redessine immédiatement.
    Cela couvre :
    - la carte principale ;
    - le modal agrandi s'il est ouvert.
  */
  if (
    typeof renderProfessionalConsumptionMapCanvas === "function"
    && document.getElementById("professionalConsumptionMapCanvas")
  ) {
    renderProfessionalConsumptionMapCanvas();
  }

  if (
    typeof renderProfessionalConsumptionMapZoomCanvas === "function"
    && document.getElementById("professionalConsumptionMapZoomCanvas")
  ) {
    renderProfessionalConsumptionMapZoomCanvas();
  }
}


/* CARTO_CLUSTER_MAIN_PERF_AUDIT001_INTEGRATED_PROFILER
 * Micro-profiler intégré, désactivé par défaut.
 *
 * Activation navigateur :
 *   __mlcFluxMapPerf.enable()
 *
 * Puis après reload :
 *   __mlcFluxMapPerf.reset()
 *   // tester animation / hover / recherche
 *   __mlcFluxMapPerf.report(80)
 *
 * Désactivation :
 *   __mlcFluxMapPerf.disable()
 */
(function installMlcFluxCartoIntegratedPerfProfiler() {
  if (typeof window === "undefined") {
    return;
  }

  const STORAGE_KEY = "mlcflux_carto_perf_audit";
  const URL_FLAG = "carto_perf_audit";

  function isProfilerEnabled() {
    try {
      const params = new URLSearchParams(window.location.search || "");
      return (
        params.get(URL_FLAG) === "1"
        || window.localStorage?.getItem(STORAGE_KEY) === "1"
      );
    } catch (_err) {
      return false;
    }
  }

  function exposeDisabledController() {
    window.__mlcFluxMapPerf = {
      enabled: false,
      enable() {
        try {
          window.localStorage?.setItem(STORAGE_KEY, "1");
        } catch (_err) {}
        window.location.reload();
      },
      disable() {
        try {
          window.localStorage?.removeItem(STORAGE_KEY);
        } catch (_err) {}
        window.location.reload();
      },
      status() {
        return {
          enabled: false,
          reason: "Profiler désactivé. Lance __mlcFluxMapPerf.enable() pour l’activer puis recharger."
        };
      }
    };
  }

  if (!isProfilerEnabled()) {
    exposeDisabledController();
    return;
  }

  if (window.__mlcFluxMapPerf?.enabled) {
    return;
  }

  const stats = new Map();
  const originals = [];
  const wrapped = [];

  function now() {
    return performance.now();
  }

  function record(name, duration) {
    const row = stats.get(name) || {
      name,
      calls: 0,
      totalMs: 0,
      maxMs: 0,
      over1ms: 0,
      over4ms: 0,
      over16ms: 0
    };

    row.calls += 1;
    row.totalMs += duration;
    row.maxMs = Math.max(row.maxMs, duration);
    if (duration >= 1) row.over1ms += 1;
    if (duration >= 4) row.over4ms += 1;
    if (duration >= 16) row.over16ms += 1;

    stats.set(name, row);
  }

  function getAppStateSafe() {
    try {
      if (typeof appState !== "undefined") {
        return appState;
      }
    } catch (_err) {}

    return window.appState || null;
  }

  function wrapNamedFunction(name) {
    let original = null;

    try {
      original = eval(name);
    } catch (_err) {
      return false;
    }

    if (typeof original !== "function" || original.__mlcFluxPerfWrapped) {
      return false;
    }

    const measured = function(...args) {
      const startedAt = now();
      try {
        return original.apply(this, args);
      } finally {
        record(`fn:${name}`, now() - startedAt);
      }
    };

    measured.__mlcFluxPerfWrapped = true;
    measured.__mlcFluxPerfOriginal = original;

    try {
      eval(`${name} = measured`);
    } catch (_err) {
      return false;
    }

    originals.push(() => {
      try {
        eval(`${name} = original`);
      } catch (_err) {}
    });

    wrapped.push(name);
    return true;
  }

  function wrapLayerProps(layerType, props) {
    if (!props || typeof props !== "object") {
      return;
    }

    const layerId = String(props.id || "unknown-layer");

    [
      "getPath",
      "getPosition",
      "getColor",
      "getFillColor",
      "getLineColor",
      "getWidth",
      "getLineWidth",
      "getRadius",
      "getFilterValue",
      "filter",
      "onHover",
      "onClick"
    ].forEach((key) => {
      if (typeof props[key] !== "function" || props[key].__mlcFluxPerfWrapped) {
        return;
      }

      const original = props[key];

      props[key] = function(...args) {
        const startedAt = now();
        try {
          return original.apply(this, args);
        } finally {
          record(`accessor:${layerType}:${layerId}.${key}`, now() - startedAt);
        }
      };

      props[key].__mlcFluxPerfWrapped = true;
    });
  }

  function wrapOverlaySetProps() {
    const state = getAppStateSafe();
    const overlay = state?.professionalConsumptionMapLibreOverlay;

    if (!overlay || typeof overlay.setProps !== "function" || overlay.setProps.__mlcFluxPerfWrapped) {
      return false;
    }

    const original = overlay.setProps;

    overlay.setProps = function(props = {}) {
      if (Array.isArray(props.layers)) {
        props.layers.forEach((layer) => {
          if (!layer?.props) return;
          wrapLayerProps(layer.constructor?.name || "Layer", layer.props);
        });
      }

      const startedAt = now();
      try {
        return original.call(this, props);
      } finally {
        record("deck:overlay.setProps", now() - startedAt);
      }
    };

    overlay.setProps.__mlcFluxPerfWrapped = true;

    originals.push(() => {
      overlay.setProps = original;
    });

    return true;
  }

  [
    "renderProfessionalConsumptionMapLibre",
    "buildProfessionalConsumptionMapLibreData",
    "buildProfessionalConsumptionMapLibreLayers",
    "buildProfessionalConsumptionMapParticleData",
    "startProfessionalConsumptionMapParticleAnimation",
    "stopProfessionalConsumptionMapParticleAnimation",
    "getProfessionalConsumptionMapFocusedProfessionalIdentity",
    "doesProfessionalConsumptionMapRouteMatchFocusedProfessional",
    "doesProfessionalConsumptionMapValueContainProfessionalRefLoose",
    "doesProfessionalConsumptionMapObjectInvolveProfessional",
    "getProfessionalConsumptionMapRouteFlowFamily",
    "shouldProfessionalConsumptionMapRenderRoute",
    "getProfessionalConsumptionMapRoutePaymentDayCount",
    "getProfessionalConsumptionMapRouteAveragePayment",
    "getProfessionalConsumptionMapPointAlongPath",
    "getProfessionalConsumptionMapLibreHighlight",
    "getProfessionalConsumptionMapLibreHighlightKey"
  ].forEach(wrapNamedFunction);

  wrapOverlaySetProps();

  window.addEventListener("webglcontextlost", () => {
    record("event:webglcontextlost", 1);
  }, true);

  window.__mlcFluxMapPerf = {
    enabled: true,
    reset() {
      stats.clear();
      wrapOverlaySetProps();
      console.log("MLCFlux carto perf reset OK");
    },
    report(limit = 80) {
      wrapOverlaySetProps();

      const rows = [...stats.values()]
        .map((row) => ({
          name: row.name,
          calls: row.calls,
          totalMs: Number(row.totalMs.toFixed(2)),
          avgMs: Number((row.totalMs / Math.max(1, row.calls)).toFixed(4)),
          maxMs: Number(row.maxMs.toFixed(2)),
          over1ms: row.over1ms,
          over4ms: row.over4ms,
          over16ms: row.over16ms
        }))
        .sort((a, b) => b.totalMs - a.totalMs)
        .slice(0, limit);

      const state = getAppStateSafe();

      console.table(rows);
      console.log("MLCFlux carto perf status", {
        enabled: true,
        wrapped,
        particlesEnabled: state?.professionalConsumptionMapParticlesEnabled,
        hasMap: Boolean(state?.professionalConsumptionMapLibreMap),
        hasOverlay: Boolean(state?.professionalConsumptionMapLibreOverlay),
        hasData: Boolean(state?.professionalConsumptionMapLibreData),
        routes: state?.professionalConsumptionMapLibreData?.routes?.length,
        sources: state?.professionalConsumptionMapLibreData?.sources?.length,
        destinations: state?.professionalConsumptionMapLibreData?.destinations?.length,
        animationFrame: state?.professionalConsumptionMapParticleAnimationFrame,
        animationTimeout: state?.professionalConsumptionMapParticleAnimationTimeout
      });

      return rows;
    },
    status() {
      const state = getAppStateSafe();
      return {
        enabled: true,
        wrapped,
        statsCount: stats.size,
        particlesEnabled: state?.professionalConsumptionMapParticlesEnabled,
        hasMap: Boolean(state?.professionalConsumptionMapLibreMap),
        hasOverlay: Boolean(state?.professionalConsumptionMapLibreOverlay),
        hasData: Boolean(state?.professionalConsumptionMapLibreData),
        routes: state?.professionalConsumptionMapLibreData?.routes?.length,
        sources: state?.professionalConsumptionMapLibreData?.sources?.length,
        destinations: state?.professionalConsumptionMapLibreData?.destinations?.length
      };
    },
    uninstall() {
      while (originals.length) {
        try {
          originals.pop()();
        } catch (_err) {}
      }
      stats.clear();
      console.log("MLCFlux carto perf wrappers retirés. Recharge conseillée.");
    },
    disable() {
      try {
        window.localStorage?.removeItem(STORAGE_KEY);
      } catch (_err) {}
      window.location.reload();
    }
  };

  console.log("MLCFlux carto perf profiler actif.", window.__mlcFluxMapPerf.status());
})();

