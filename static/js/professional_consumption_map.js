/*
 * MLCFlux — Carte de consommation U→P
 * Extraction MAPJS001 depuis static/js/app.js
 *
 * Objectif :
 * - isoler la grosse cartographie transactionnelle dans un fichier dédié ;
 * - conserver strictement les noms de fonctions existants ;
 * - ne modifier ni les API, ni les comportements, ni les dépendances globales.
 */

function getProfessionalConsumptionMapPayload(consumptionMapSummary) {
  return consumptionMapSummary || null;
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

  let minLon = Math.min(...lons);
  let maxLon = Math.max(...lons);
  let minLat = Math.min(...lats);
  let maxLat = Math.max(...lats);

  const lonSpan = Math.max(maxLon - minLon, 0.01);
  const latSpan = Math.max(maxLat - minLat, 0.01);

  minLon -= lonSpan * 0.06;
  maxLon += lonSpan * 0.06;
  minLat -= latSpan * 0.06;
  maxLat += latSpan * 0.06;

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
  ctx.shadowBlur = 5 + safeTraffic * 7 + safeStructure * 4;
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

    const coreWidth =
      (0.42 + structuralWeight * 3.05)
      * routeBirth
      * (0.58 + trafficPresence * 0.42)
      * staticLightWidthBoost
      * (0.42 + visualFade * 0.58);

    const haloWidth = coreWidth * (
      isStaticLightMap
        ? 3.25 + traffic * 1.05
        : 3.9 + traffic * 1.45
    );

    const bodyWidth = coreWidth * (
      isStaticLightMap
        ? 1.95 + traffic * 0.50
        : 1.85 + traffic * 0.55
    );

    const haloAlpha =
      (0.018 + structuralWeight * 0.13)
      * appearance
      * (0.24 + traffic * 0.76)
      * (isStaticLightMap ? 0.82 : 1)
      * visualFade
      * densityLightFactor;

    const bodyAlpha =
      (0.045 + structuralWeight * 0.24)
      * appearance
      * (0.26 + traffic * 0.74)
      * (isStaticLightMap ? 1.34 : 1)
      * visualFade
      * densityLightFactor;

    const coreAlpha =
      (0.12 + structuralWeight * 0.52)
      * appearance
      * (0.34 + traffic * 0.66)
      * (isStaticLightMap ? 1.22 : 1)
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
          coreWidth * 1.58,
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
        (12 + traffic * 28 + structuralWeight * 10)
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
        (5 + traffic * 14 + structuralWeight * 5)
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
        (1 + traffic * 6)
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
    const outerRadius = 3.2 + 2.0 * intensity;
    const innerRadius = 0.9 + 0.85 * intensity;

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

    const coreRadius =
      (2.7 + structuralWeight * 7.1)
      * nodeBirth
      * (0.68 + trafficPresence * 0.32)
      * (0.50 + inactivityFade * 0.50);

    const haloRadius =
      coreRadius * (1.9 + traffic * 1.35);

    const outerHaloRadius =
      coreRadius * (3.25 + traffic * 2.25);

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
      `rgba(52, 211, 153, ${(0.08 + structuralWeight * 0.22) * visualFade * trafficPresence * densityLightFactor})`
    );
    outerGlow.addColorStop(
      0.56,
      `rgba(16, 185, 129, ${(0.03 + structuralWeight * 0.11) * visualFade * trafficPresence * densityLightFactor})`
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
      `rgba(167, 243, 208, ${(0.16 + structuralWeight * 0.32) * visualFade * trafficPresence * densityLightFactor})`
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
    "Rouge : origine postale synthétique  →  Vert : professionnel",
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
    fallbackTitle: "Bassins de consommation Gonette",
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
  const payload = appState.professionalConsumptionMapRenderPayload
    || appState.professionalConsumptionMap
    || null;

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

  const basePayload = appState.professionalConsumptionMap || payload;
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
          <h2>Bassins de consommation Gonette</h2>
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
  ctx.shadowBlur = 0;
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
  const payload = appState.professionalConsumptionMapRenderPayload
    || appState.professionalConsumptionMap
    || null;

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

  const basePayload = appState.professionalConsumptionMap || payload;
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
