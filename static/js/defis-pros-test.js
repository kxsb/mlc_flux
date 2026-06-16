(function () {
  const $ = (id) => document.getElementById(id);

  let rawRows = [];
  let lastResultRows = [];
  let lastPublicationRows = [];
  let svgTemplateText = "";
  let currentSvgTemplateId = "";

  const SVG_TEMPLATE_STORAGE_KEY = "mlcflux:defis-pros:svg-templates:v1";

  const sectorsOrder = [
    "alimentation",
    "immobilier / bâtiment / artisanat",
    "mode / habillement / beauté",
    "loisirs / culture / sport",
    "services aux entreprises et aux particuliers",
    "santé",
    "collectivités et institutions"
  ];

  function sectorKey(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[’']/g, "'")
      .replace(/&/g, " et ")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function normalizeSimplifiedSector(value) {
    const key = sectorKey(value);
    const found = sectorsOrder.find((sector) => sectorKey(sector) === key);
    return found || "secteur non renseigné";
  }

  const rawSectorAliases = {
    "Administratifs": "services aux entreprises et aux particuliers",
    "Administration publique": "collectivités et institutions",
    "Agriculture": "alimentation",
    "Alcools et spiritueux": "alimentation",
    "Alcools & Spiritueux": "alimentation",
    "Alimentation": "alimentation",
    "Approvisionnement en eau": "services aux entreprises et aux particuliers",
    "Approvisionnement en énergie": "services aux entreprises et aux particuliers",
    "Artisanat et métiers d'art": "immobilier / bâtiment / artisanat",
    "Artisanat & Métiers d'Art": "immobilier / bâtiment / artisanat",
    "Audiovisuel information et communication": "loisirs / culture / sport",
    "Autre Commerce Alimentaire": "alimentation",
    "Autres commerces alimentaires": "alimentation",
    "Autres services": "services aux entreprises et aux particuliers",
    "Collectivité & Réseaux": "collectivités et institutions",
    "Collectivités et réseaux": "collectivités et institutions",
    "Construction": "immobilier / bâtiment / artisanat",
    "Divertissement": "loisirs / culture / sport",
    "Edition impression papeterie et librairie": "loisirs / culture / sport",
    "Édition Impression Papeterie et Librairie": "loisirs / culture / sport",
    "Éducation": "loisirs / culture / sport",
    "Education": "loisirs / culture / sport",
    "Éducation Et Formation": "services aux entreprises et aux particuliers",
    "Éducation et formation": "services aux entreprises et aux particuliers",
    "Entretien Mécanique Et Bâtiment": "immobilier / bâtiment / artisanat",
    "Entretien mécanique et bâtiment": "immobilier / bâtiment / artisanat",
    "Épiceries": "alimentation",
    "Epiceries": "alimentation",
    "Fabrication": "immobilier / bâtiment / artisanat",
    "Finance/Assurance": "services aux entreprises et aux particuliers",
    "Gestion et conseil aux entreprises": "services aux entreprises et aux particuliers",
    "Habillement beauté et accessoires": "mode / habillement / beauté",
    "Immobilier": "immobilier / bâtiment / artisanat",
    "Immobilier et espaces de location": "immobilier / bâtiment / artisanat",
    "Informatique et web": "services aux entreprises et aux particuliers",
    "Informatique/Communication": "services aux entreprises et aux particuliers",
    "Initiatives solidaires et services à la personne": "services aux entreprises et aux particuliers",
    "Maison et jardin": "immobilier / bâtiment / artisanat",
    "Ménages": "immobilier / bâtiment / artisanat",
    "Produits de l'agriculture et de l'élevage": "alimentation",
    "Restaurants bars et traiteurs": "alimentation",
    "Santé et bien-être": "santé",
    "Santé/Social": "santé",
    "Scientifique": "services aux entreprises et aux particuliers",
    "Sorties culturelles et tourisme": "loisirs / culture / sport",
    "Sports loisirs et jeux": "loisirs / culture / sport",
    "Transition écologique et économie circulaire": "services aux entreprises et aux particuliers",
    "Transport": "services aux entreprises et aux particuliers"
  };

  const sectorAliases = Object.fromEntries(
    Object.entries(rawSectorAliases).map(([raw, simplified]) => [
      sectorKey(raw),
      normalizeSimplifiedSector(simplified)
    ])
  );

  function simplifySector(value) {
    const raw = String(value || "").replace(/\s+/g, " ").trim();

    if (!raw) {
      return "secteur non renseigné";
    }

    const alreadySimplified = sectorsOrder.find((sector) => sectorKey(sector) === sectorKey(raw));
    if (alreadySimplified) {
      return alreadySimplified;
    }

    const mapped = sectorAliases[sectorKey(raw)];
    if (mapped) {
      return mapped;
    }

    return "à mapper : " + raw;
  }

  function get(row, names, fallback = null) {
    for (const name of names) {
      if (row && Object.prototype.hasOwnProperty.call(row, name) && row[name] !== null && row[name] !== undefined && row[name] !== "") {
        return row[name];
      }
    }
    return fallback;
  }

  function asNumber(value) {
    if (typeof value === "number") return Number.isFinite(value) ? value : 0;
    if (value === null || value === undefined) return 0;
    const text = String(value)
      .replace(/\u00a0/g, "")
      .replace(/\s/g, "")
      .replace(/€/g, "")
      .replace(/G/g, "")
      .replace(/%/g, "")
      .replace(",", ".");
    const n = Number.parseFloat(text);
    return Number.isFinite(n) ? n : 0;
  }

  function formatG(value) {
    return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(value) + " G";
  }

  function formatPct(value) {
    return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(value * 100) + " %";
  }

  function publicProfessionalName(value) {
    return String(value || "")
      .replace(/^P\d{4}\s*-\s*/i, "")
      .replace(/\s*\([^)]*anciennement[^)]*\)/ig, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function sectorPublicTitle(value) {
    const key = sectorKey(value);

    const titles = {
      "alimentation": "SECTEUR ALIMENTAIRE",
      "immobilier / batiment / artisanat": "SECTEUR IMMOBILIER · BÂTIMENT · ARTISANAT",
      "mode / habillement / beaute": "SECTEUR MODE · HABILLEMENT · BEAUTÉ",
      "loisirs / culture / sport": "SECTEUR LOISIRS · CULTURE · SPORT",
      "services aux entreprises et aux particuliers": "SECTEUR SERVICES",
      "sante": "SECTEUR SANTÉ",
      "collectivites et institutions": "SECTEUR COLLECTIVITÉS · INSTITUTIONS"
    };

    return titles[key] || `SECTEUR ${String(value || "").toUpperCase()}`;
  }

  function sectorIntro(value) {
    const key = sectorKey(value);

    const intros = {
      "alimentation": "Restaurants, bars, épiceries, producteurs, brasseurs, torréfacteurs, etc. Qui encaisse le plus de gonettes ? Qui en dépense le plus ? Qui en réutilise le plus ?",
      "immobilier / batiment / artisanat": "Artisanat, bâtiment, entretien, lieux et services liés à l’habitat. Qui fait circuler la Gonette dans ces métiers ?",
      "mode / habillement / beaute": "Habillement, accessoires, beauté et soin de soi. Qui reçoit, dépense et réutilise le plus de gonettes ?",
      "loisirs / culture / sport": "Culture, sport, loisirs, librairies, sorties et pratiques collectives. Qui fait vivre la Gonette dans ces activités ?",
      "services aux entreprises et aux particuliers": "Services, conseil, informatique, communication, accompagnement et prestations. Qui remet les gonettes en circulation ?",
      "sante": "Santé, soin, bien-être et accompagnement. Qui reçoit et réutilise le plus la Gonette dans ce secteur ?",
      "collectivites et institutions": "Collectivités, réseaux et institutions partenaires. Suivi spécifique des structures publiques ou assimilées."
    };

    return intros[key] || "Classement trimestriel des professionnel·les qui font circuler la Gonette dans le réseau.";
  }

  function replaceSvgTextContent(doc, pattern, replacement) {
    const nodes = doc.querySelectorAll("text, tspan");

    nodes.forEach((node) => {
      const current = String(node.textContent || "");

      if (pattern.test(current)) {
        node.textContent = replacement;
      }
    });
  }

  function cleanSector(value) {
    return simplifySector(value);
  }

  function normalizeRow(row) {
    const name = String(get(row, [
      "Professionnel", "professional", "name", "label", "Nom", "nom", "pro_name", "professional_name"
    ], "")).trim();

    const rawSector = get(row, [
      "Secteur simplifié", "secteur simplifié", "secteur_simplifie", "simplified_sector", "sector_simplified"
    ], "") || get(row, [
      "Secteur d’activité", "Secteur d'activité", "Secteur d'activite", "activity_sector", "sector", "secteur"
    ], "");

    const sector = cleanSector(rawSector);

    const activity = String(get(row, [
      "Secteur d’activité", "Secteur d'activité", "Secteur d'activite", "activity_sector", "activity", "secteur_activite"
    ], "") || "").trim();

    const zip = String(get(row, [
      "Code postal", "code_postal", "zip", "zipcode", "postal_code"
    ], "") || "").trim();

    const receivedFromP = asNumber(get(row, [
      "Reçu des professionnels", "Recu des professionnels", "B2B Reçu", "B2B Recu", "B2B Received", "recu_des_professionnels", "received_from_professionals"
    ], 0));

    const receivedFromU = asNumber(get(row, [
      "Reçu des particuliers", "Recu des particuliers", "B2C", "recu_des_particuliers", "received_from_users"
    ], 0));

    const received = asNumber(get(row, [
      "Total reçu", "Total Reçu", "Total Recu", "Paiements Reçu B+C", "Paiements Recu B+C", "total_recu", "total_received", "received_total", "total_received_amount"
    ], receivedFromP + receivedFromU));

    const emittedToP = asNumber(get(row, [
      "Émis vers les professionnels", "Emis vers les professionnels", "B2B Emis", "B2B Émis", "emis_vers_les_professionnels", "emitted_to_professionals"
    ], 0));

    const emittedToU = asNumber(get(row, [
      "Émis vers les particuliers", "Emis vers les particuliers", "Rémunération", "Remuneration", "emis_vers_les_particuliers", "emitted_to_users"
    ], 0));

    const emitted = asNumber(get(row, [
      "Total émis", "Total emis", "Total Émis", "Total Emis", "total_emis", "total_emitted", "emitted_total", "total_sent"
    ], emittedToP + emittedToU));

    const converted = asNumber(get(row, [
      "Total converti", "total_converti", "converted_total", "total_converted"
    ], 0));

    const reconverted = asNumber(get(row, [
      "Total reconverti", "total_reconverti", "reconverted_total", "total_reconverted"
    ], 0));

    let rate = asNumber(get(row, [
      "Taux de réutilisation", "Taux de reutilisation", "taux_reutilisation", "reuse_rate", "reutilisation_rate"
    ], NaN));

    if (!Number.isFinite(rate) || Number.isNaN(rate)) rate = received > 0 ? emitted / received : 0;
    if (rate > 10) rate = rate / 100;

    const idMatch = name.match(/^(P\d{4})/);
    const proId = idMatch ? idMatch[1] : "";

    return {
      source: row,
      name,
      proId,
      sector,
      activity,
      zip,
      received,
      emitted,
      receivedFromP,
      receivedFromU,
      emittedToP,
      emittedToU,
      converted,
      reconverted,
      rate
    };
  }

  function isInternal(row) {
    return row.proId === "P0000" || row.proId === "P9999" || /P0000|P9999/.test(row.name);
  }

  function sortRows(rows, key) {
    return [...rows].sort((a, b) => {
      const d = b[key] - a[key];
      if (d !== 0) return d;
      return b.received - a.received;
    });
  }

  function topRows(rows, key, n, predicate = null) {
    const filtered = predicate ? rows.filter(predicate) : rows;
    return sortRows(filtered, key).slice(0, n);
  }

  function rowHTML(row, index, key) {
    const value = key === "rate" ? formatPct(row.rate) : formatG(row[key]);
    const displayName = publicProfessionalName(row.name);
    const metaBits = [];
    if (row.zip) metaBits.push(row.zip);
    if (row.activity) metaBits.push(row.activity);
    const meta = metaBits.join(" · ");
    return `
      <div class="rank-row">
        <div class="rank">${index + 1}</div>
        <div>
          <div class="pro-name" title="${escapeHTML(row.name)}">${escapeHTML(displayName)}</div>
          <div class="pro-meta">${escapeHTML(meta || "—")}</div>
        </div>
        <div class="amount">${value}</div>
      </div>
    `;
  }

  function blockHTML(title, rows, key) {
    return `
      <div class="ranking-block">
        <div class="ranking-title">
          <span>${escapeHTML(title)}</span>
          <span>${rows.length ? rows.length + " résultat(s)" : ""}</span>
        </div>
        ${rows.length ? rows.map((r, i) => rowHTML(r, i, key)).join("") : `<div class="empty">Aucun résultat éligible.</div>`}
      </div>
    `;
  }

  function escapeHTML(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function buildAudit(rows, allRows) {
    const topN = Number.parseInt($("topN").value, 10) || 3;
    const minReceived = asNumber($("minReceived").value);
    const minEmittedForRate = asNumber($("minEmittedForRate") ? $("minEmittedForRate").value : 0);
    const includeInternal = $("internalAccounts").value === "include";

    const by = (items, keyFn) => {
      const map = new Map();

      for (const item of items) {
        const key = keyFn(item) || "—";
        if (!map.has(key)) {
          map.set(key, { key, count: 0, examples: [] });
        }

        const bucket = map.get(key);
        bucket.count += 1;

        if (bucket.examples.length < 5 && item.name) {
          bucket.examples.push(item.name);
        }
      }

      return [...map.values()].sort((a, b) => b.count - a.count || a.key.localeCompare(b.key, "fr"));
    };

    const shortList = (items, labelFn) => {
      if (!items.length) return "";

      const visible = items.slice(0, 8);
      const rest = items.length - visible.length;

      return `
        <details style="margin-top:8px;">
          <summary style="cursor:pointer;color:var(--accent);font-weight:850;">Voir le détail</summary>
          <ul style="margin:8px 0 0 0;padding-left:18px;color:var(--muted);font-size:.78rem;line-height:1.35;">
            ${visible.map((item) => `<li>${escapeHTML(labelFn(item))}</li>`).join("")}
            ${rest > 0 ? `<li>… ${rest} autre(s)</li>` : ""}
          </ul>
        </details>
      `;
    };

    const bucketList = (buckets) => {
      if (!buckets.length) return "";

      const visible = buckets.slice(0, 8);
      const rest = buckets.length - visible.length;

      return `
        <details style="margin-top:8px;">
          <summary style="cursor:pointer;color:var(--accent);font-weight:850;">Voir le détail</summary>
          <ul style="margin:8px 0 0 0;padding-left:18px;color:var(--muted);font-size:.78rem;line-height:1.35;">
            ${visible.map((bucket) => `
              <li>
                <strong>${escapeHTML(bucket.key)}</strong> — ${bucket.count}
                ${bucket.examples.length ? `<br><span>${escapeHTML(bucket.examples.join(" · "))}</span>` : ""}
              </li>
            `).join("")}
            ${rest > 0 ? `<li>… ${rest} autre(s)</li>` : ""}
          </ul>
        </details>
      `;
    };

    const missingSector = allRows.filter((r) => !r.sector || r.sector === "secteur non renseigné");
    const unmappedSectorRows = allRows.filter((r) => String(r.sector || "").startsWith("à mapper : "));
    const unmappedBuckets = by(unmappedSectorRows, (r) => String(r.sector || "").replace(/^à mapper : /, ""));

    const internalAll = allRows.filter(isInternal);
    const internalVisible = rows.filter(isInternal);

    const lowVolumeHighRate = rows.filter((r) => r.received > 0 && r.received < minReceived && r.rate >= 1);
    const lowSpentHighRate = rows.filter((r) => r.received >= minReceived && r.emitted > 0 && r.emitted < minEmittedForRate && r.rate >= 1);
    const extremeRate = rows.filter((r) => r.received > 0 && r.rate >= 3);
    const missingZip = rows.filter((r) => !r.zip);

    const sectorCompleteness = sectorsOrder.map((sector) => {
      const sectorRows = rows.filter((r) => r.sector === sector);
      const receivedCount = sectorRows.filter((r) => r.received > 0).length;
      const emittedCount = sectorRows.filter((r) => r.emitted > 0).length;
      const rateCount = sectorRows.filter((r) => r.received >= minReceived && r.emitted >= minEmittedForRate && r.rate > 0).length;

      return {
        sector,
        total: sectorRows.length,
        receivedCount,
        emittedCount,
        rateCount,
        missing: [
          receivedCount < topN ? `encaissées ${receivedCount}/${topN}` : "",
          emittedCount < topN ? `dépensées ${emittedCount}/${topN}` : "",
          rateCount < topN ? `ratio ${rateCount}/${topN}` : ""
        ].filter(Boolean)
      };
    }).filter((item) => item.total > 0 && item.missing.length);

    const items = [
      {
        level: missingSector.length ? "bad" : "ok",
        title: missingSector.length ? `${missingSector.length} pro(s) sans secteur` : "Secteurs renseignés",
        text: missingSector.length ? "Ces professionnels ne peuvent pas être classés correctement par grande famille." : "Aucun professionnel sans secteur détecté.",
        detail: shortList(missingSector, (r) => r.name)
      },
      {
        level: unmappedBuckets.length ? "bad" : "ok",
        title: unmappedBuckets.length ? `${unmappedBuckets.length} secteur(s) à mapper` : "Mapping secteurs complet",
        text: unmappedBuckets.length ? "Ces secteurs Odoo n’entrent pas encore dans les 7 familles Défis des pros." : "Aucun secteur hors nomenclature détecté.",
        detail: bucketList(unmappedBuckets)
      },
      {
        level: internalVisible.length ? "warn" : "ok",
        title: includeInternal
          ? `${internalVisible.length} compte(s) interne(s) visible(s)`
          : `${internalAll.length} compte(s) interne(s) neutralisé(s)`,
        text: includeInternal
          ? "P0000/P9999 sont inclus dans les résultats : utile pour audit, risqué pour publication."
          : "P0000/P9999 sont détectés dans les données mais exclus des classements publics.",
        detail: shortList(internalAll, (r) => `${r.name} — reçu ${formatG(r.received)}, émis ${formatG(r.emitted)}`)
      },
      {
        level: lowVolumeHighRate.length ? "warn" : "ok",
        title: lowVolumeHighRate.length ? `${lowVolumeHighRate.length} ratio(s) élevé(s) sur faible volume` : "Seuil de ratio cohérent",
        text: `Seuil actuel : ${formatG(minReceived)} reçues minimum et ${formatG(minEmittedForRate)} dépensées minimum pour le classement au ratio.`,
        detail: shortList(lowVolumeHighRate, (r) => `${publicProfessionalName(r.name)} — reçu ${formatG(r.received)}, ratio ${formatPct(r.rate)}`)
      },
      {
        level: lowSpentHighRate.length ? "warn" : "ok",
        title: lowSpentHighRate.length ? `${lowSpentHighRate.length} ratio(s) élevé(s) mais peu dépensés` : "Volumes dépensés suffisants pour le ratio",
        text: `Les pros sous ${formatG(minEmittedForRate)} dépensées sont exclus du top ratio public.`,
        detail: shortList(lowSpentHighRate, (r) => `${publicProfessionalName(r.name)} — dépensé ${formatG(r.emitted)}, ratio ${formatPct(r.rate)}`)
      },
      {
        level: extremeRate.length ? "warn" : "ok",
        title: extremeRate.length ? `${extremeRate.length} taux extrême(s)` : "Pas de taux extrême",
        text: extremeRate.length ? "À vérifier : effet d’acompte, paiement groupé, correction, faible encaissement ou cas métier particulier." : "Aucun ratio supérieur à 300 % sur le filtre courant.",
        detail: shortList(extremeRate, (r) => `${r.name} — reçu ${formatG(r.received)}, émis ${formatG(r.emitted)}, ratio ${formatPct(r.rate)}`)
      },
      {
        level: missingZip.length ? "warn" : "ok",
        title: missingZip.length ? `${missingZip.length} code(s) postal(aux) manquant(s)` : "Localisation disponible",
        text: missingZip.length ? "Peut gêner la production des affiches : arrondissement ou ville attendus." : "Les pros visibles ont un code postal.",
        detail: shortList(missingZip, (r) => r.name)
      },
      {
        level: sectorCompleteness.length ? "warn" : "ok",
        title: sectorCompleteness.length ? `${sectorCompleteness.length} secteur(s) incomplet(s)` : "Tous les tops sont complets",
        text: sectorCompleteness.length ? `Certains secteurs n’ont pas assez de candidats pour remplir un top ${topN} sur tous les indicateurs.` : `Chaque secteur visible peut produire ses tops ${topN}.`,
        detail: shortList(sectorCompleteness, (s) => `${s.sector} — ${s.missing.join(", ")}`)
      }
    ];

    $("audit").innerHTML = items.map((item) => `
      <div class="audit-item">
        <div class="dot ${item.level === "warn" ? "warn" : item.level === "bad" ? "bad" : ""}"></div>
        <div>
          <strong>${escapeHTML(item.title)}</strong>
          <span>${escapeHTML(item.text)}</span>
          ${item.detail || ""}
        </div>
      </div>
    `).join("");
  }

  function buildPack(resultsBySector, periodLabel, topN) {
    const lines = [];
    lines.push(`Défis des pros — résultats ${periodLabel}`);
    lines.push("");
    lines.push(`Top ${topN} par secteur`);
    lines.push("");

    for (const sector of Object.keys(resultsBySector)) {
      const res = resultsBySector[sector];
      lines.push(`## ${sector}`);
      lines.push("");

      lines.push("Gonettes encaissées");
      res.received.forEach((r, i) => lines.push(`${i + 1}. ${r.name} — ${formatG(r.received)}`));
      if (!res.received.length) lines.push("Aucun résultat éligible.");
      lines.push("");

      lines.push("Gonettes réutilisées");
      res.emitted.forEach((r, i) => lines.push(`${i + 1}. ${r.name} — ${formatG(r.emitted)}`));
      if (!res.emitted.length) lines.push("Aucun résultat éligible.");
      lines.push("");

      lines.push("Taux de réutilisation");
      res.rate.forEach((r, i) => lines.push(`${i + 1}. ${r.name} — ${formatPct(r.rate)}`));
      if (!res.rate.length) lines.push("Aucun résultat éligible.");
      lines.push("");
    }

    if ($("mode").value === "interne") {
      lines.push("---");
      lines.push("Indicateurs internes à ne pas publier tels quels");
      lines.push("");
      const topReconversions = sortRows(lastResultRows, "reconverted").slice(0, 10);
      lines.push("Top reconversions");
      topReconversions.forEach((r, i) => lines.push(`${i + 1}. ${r.name} — ${formatG(r.reconverted)}`));
      lines.push("");
    }

    $("pack").value = lines.join("\n");
  }

  function render() {
    const topN = Number.parseInt($("topN").value, 10) || 3;
    const minReceived = asNumber($("minReceived").value);
    const minEmittedForRate = asNumber($("minEmittedForRate") ? $("minEmittedForRate").value : 0);
    const selectedSector = $("sectorFilter").value;
    const includeInternal = $("internalAccounts").value === "include";
    const mode = $("mode").value;

    const normalized = rawRows.map(normalizeRow).filter(r => r.name);
    const rows = normalized
      .filter(r => includeInternal || !isInternal(r))
      .filter(r => !selectedSector || r.sector === selectedSector);

    lastResultRows = rows;

    const sectorSet = new Set(normalized.map(r => r.sector).filter(Boolean));
    hydrateSectorFilter([...sectorSet]);

    const sectors = [...new Set(rows.map(r => r.sector))]
      .sort((a, b) => {
        const ia = sectorsOrder.indexOf(a);
        const ib = sectorsOrder.indexOf(b);
        if (ia !== -1 || ib !== -1) return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
        return a.localeCompare(b, "fr");
      });

    const totalReceived = rows.reduce((s, r) => s + r.received, 0);
    const totalEmitted = rows.reduce((s, r) => s + r.emitted, 0);

    $("kpiPros").textContent = new Intl.NumberFormat("fr-FR").format(rows.length);
    $("kpiReceived").textContent = formatG(totalReceived);
    $("kpiEmitted").textContent = formatG(totalEmitted);
    $("kpiRate").textContent = totalReceived > 0 ? formatPct(totalEmitted / totalReceived) : "—";
    $("kpiSectors").textContent = new Intl.NumberFormat("fr-FR").format(sectors.length);

    const resultsBySector = {};
    const publicationRows = [];

    const cards = sectors.map(sector => {
      const sectorRows = rows.filter(r => r.sector === sector);
      const received = topRows(sectorRows, "received", topN, r => r.received > 0);
      const emitted = topRows(sectorRows, "emitted", topN, r => r.emitted > 0);
      const rate = topRows(sectorRows, "rate", topN, r => r.received >= minReceived && r.emitted >= minEmittedForRate && r.rate > 0);
      resultsBySector[sector] = { received, emitted, rate };

      received.forEach((r, i) => publicationRows.push({
        sector,
        indicator: "Gonettes encaissées",
        rank: i + 1,
        professional: publicProfessionalName(r.name),
        rawProfessional: r.name,
        zip: r.zip,
        activity: r.activity,
        value: r.received,
        readableValue: formatG(r.received),
        received: r.received,
        emitted: r.emitted,
        rate: r.rate
      }));

      emitted.forEach((r, i) => publicationRows.push({
        sector,
        indicator: "Gonettes réutilisées",
        rank: i + 1,
        professional: publicProfessionalName(r.name),
        rawProfessional: r.name,
        zip: r.zip,
        activity: r.activity,
        value: r.emitted,
        readableValue: formatG(r.emitted),
        received: r.received,
        emitted: r.emitted,
        rate: r.rate
      }));

      rate.forEach((r, i) => publicationRows.push({
        sector,
        indicator: "Taux de réutilisation",
        rank: i + 1,
        professional: publicProfessionalName(r.name),
        rawProfessional: r.name,
        zip: r.zip,
        activity: r.activity,
        value: r.rate,
        readableValue: formatPct(r.rate),
        received: r.received,
        emitted: r.emitted,
        rate: r.rate
      }));

      const internal = mode === "interne"
        ? blockHTML("Top reconversions · interne", topRows(sectorRows, "reconverted", Math.min(topN, 5), r => r.reconverted > 0), "reconverted")
        : "";

      return `
        <article class="sector-card">
          <div class="sector-title">
            <strong>${escapeHTML(sector)}</strong>
            <span>${sectorRows.length} pro(s)</span>
          </div>
          ${blockHTML("Gonettes encaissées", received, "received")}
          ${blockHTML("Gonettes réutilisées", emitted, "emitted")}
          ${blockHTML("Taux de réutilisation", rate, "rate")}
          ${internal}
        </article>
      `;
    });

    $("rankings").innerHTML = cards.length ? cards.join("") : `<div class="loading">Aucun professionnel ne correspond aux filtres.</div>`;

    lastPublicationRows = publicationRows;

    syncExportManager();
    syncSvgTemplateSelector();

    buildAudit(rows, normalized);
    buildPack(resultsBySector, `${$("startDate").value} → ${$("endDate").value}`, topN);

    $("status").textContent = `Vue calculée sur ${rows.length} pro(s). Pack publication : ${publicationRows.length} ligne(s). Source : /api/pros?start/end.`;
  }

  function hydrateSectorFilter(sectors) {
    const select = $("sectorFilter");
    const current = select.value;
    const ordered = sectors
      .sort((a, b) => {
        const ia = sectorsOrder.indexOf(a);
        const ib = sectorsOrder.indexOf(b);
        if (ia !== -1 || ib !== -1) return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
        return a.localeCompare(b, "fr");
      });

    select.innerHTML = `<option value="">Tous les secteurs</option>` + ordered.map(s => (
      `<option value="${escapeHTML(s)}">${escapeHTML(s)}</option>`
    )).join("");

    if ([...select.options].some(o => o.value === current)) select.value = current;
  }

  async function fetchPros() {
    const start = $("startDate").value;
    const end = $("endDate").value;

    const urls = [
      `/api/pros?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
    ];

    let lastError = null;

    for (const url of urls) {
      try {
        const response = await fetch(url, { headers: { "Accept": "application/json" } });
        if (!response.ok) {
          lastError = `${url} → HTTP ${response.status}`;
          continue;
        }

        const data = await response.json();
        const rows = Array.isArray(data)
          ? data
          : Array.isArray(data.pros)
            ? data.pros
            : Array.isArray(data.data)
              ? data.data
              : Array.isArray(data.rows)
                ? data.rows
                : [];

        if (!rows.length) {
          lastError = `${url} → aucune ligne exploitable`;
          continue;
        }

        rawRows = rows;
        $("error").style.display = "none";
        $("status").textContent = `Données périodées chargées depuis ${url}`;
        render();
        return;
      } catch (error) {
        lastError = `${url} → ${error.message}`;
      }
    }

    $("error").style.display = "block";
    $("error").textContent = `Impossible de charger les données professionnelles. Dernière erreur : ${lastError || "inconnue"}`;
    $("rankings").innerHTML = `<div class="loading">Erreur de chargement.</div>`;
  }

  function buildPublicationPayload() {
    const sectors = {};

    for (const row of lastPublicationRows) {
      if (!sectors[row.sector]) {
        sectors[row.sector] = {
          sector: row.sector,
          rankings: {
            "Gonettes encaissées": [],
            "Gonettes réutilisées": [],
            "Taux de réutilisation": []
          }
        };
      }

      if (!sectors[row.sector].rankings[row.indicator]) {
        sectors[row.sector].rankings[row.indicator] = [];
      }

      sectors[row.sector].rankings[row.indicator].push({
        rank: row.rank,
        professional: row.professional,
        zip: row.zip,
        activity: row.activity,
        value: row.value,
        readableValue: row.readableValue,
        received: row.received,
        emitted: row.emitted,
        rate: row.rate
      });
    }

    return {
      type: "defis-pros-publication-pack",
      schemaVersion: 1,
      generatedAt: new Date().toISOString(),
      period: {
        start: $("startDate").value,
        end: $("endDate").value
      },
      topN: Number.parseInt($("topN").value, 10) || 3,
      mode: $("mode").value,
      minReceivedForRate: asNumber($("minReceived").value),
      minEmittedForRate: asNumber($("minEmittedForRate") ? $("minEmittedForRate").value : 0),
      sectors: Object.values(sectors)
    };
  }

  function periodReadableLabel() {
    const start = $("startDate").value;
    const end = $("endDate").value;

    const quarterLabels = {
      "01-01:03-31": "1er trimestre",
      "04-01:06-30": "2e trimestre",
      "07-01:09-30": "3e trimestre",
      "10-01:12-31": "4e trimestre"
    };

    if (/^\d{4}-\d{2}-\d{2}$/.test(start) && /^\d{4}-\d{2}-\d{2}$/.test(end)) {
      const year = start.slice(0, 4);
      const key = `${start.slice(5)}:${end.slice(5)}`;

      if (start.slice(0, 4) === end.slice(0, 4) && quarterLabels[key]) {
        return `${quarterLabels[key]} ${year}`;
      }
    }

    return `${start} → ${end}`;
  }

  function slugify(value) {
    return String(value || "secteur")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .toLowerCase() || "secteur";
  }

  function setSvgText(doc, id, value) {
    const el = doc.getElementById(id);

    if (!el) {
      return;
    }

    el.textContent = String(value ?? "—");
  }

  function downloadTextFile(filename, content, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");

    a.href = url;
    a.download = filename;
    a.click();

    URL.revokeObjectURL(url);
  }

  function buildSectorSvg(templateText, sectorPayload) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(templateText, "image/svg+xml");
    const errorNode = doc.querySelector("parsererror");

    if (errorNode) {
      throw new Error("Le modèle SVG n’est pas lisible par le navigateur.");
    }

    const period = periodReadableLabel();
    const sectorTitle = sectorPublicTitle(sectorPayload.sector);

    setSvgText(doc, "period_label", period);
    setSvgText(doc, "text12", sectorTitle);
    setSvgText(doc, "text13", sectorIntro(sectorPayload.sector));

    replaceSvgTextContent(doc, /RATIO\s+R[ÉE]UTILISATION.*$/i, "TOP 3 · TAUX DE RÉUTILISATION");
    replaceSvgTextContent(doc, /ENCAISS[ÉE]ES\s*\/\s*D[ÉE]PENS[ÉE]ES/i, "DÉPENSÉES / ENCAISSÉES");

    const received = sectorPayload.rankings["Gonettes encaissées"] || [];
    const spent = sectorPayload.rankings["Gonettes réutilisées"] || [];
    const ratio = sectorPayload.rankings["Taux de réutilisation"] || [];

    for (let i = 1; i <= 3; i += 1) {
      const r = received[i - 1];
      setSvgText(doc, `received_${i}_rank`, r ? String(i) : "—");
      setSvgText(doc, `received_${i}_name`, r ? r.professional : "—");
      setSvgText(doc, `received_${i}_value`, r ? r.readableValue : "—");

      const s = spent[i - 1];
      setSvgText(doc, `spent_${i}_rank`, s ? String(i) : "—");
      setSvgText(doc, `spent_${i}_name`, s ? s.professional : "—");
      setSvgText(doc, `spent_${i}_value`, s ? s.readableValue : "—");

      const q = ratio[i - 1];
      setSvgText(doc, `ratio_${i}_rank`, q ? String(i) : "—");
      setSvgText(doc, `ratio_${i}_name`, q ? q.professional : "—");
      setSvgText(doc, `ratio_${i}_received`, q ? formatG(q.emitted || 0) : "—");
      setSvgText(doc, `ratio_${i}_value`, q ? q.readableValue : "—");
    }

    setSvgText(
      doc,
      "text_ratio_note",
      `Données limitées aux pros ayant encaissé au moins ${formatG(asNumber($("minReceived").value))} et dépensé au moins ${formatG(asNumber($("minEmittedForRate") ? $("minEmittedForRate").value : 0))} sur la période. Les taux supérieurs à 100 % peuvent correspondre à des gonettes reçues sur des périodes précédentes.`
    );

    return new XMLSerializer().serializeToString(doc);
  }

  function emptySvgTemplateStore() {
    return {
      selectedId: "",
      templates: []
    };
  }

  function loadSvgTemplateStore() {
    try {
      const raw = localStorage.getItem(SVG_TEMPLATE_STORAGE_KEY);

      if (!raw) {
        return emptySvgTemplateStore();
      }

      const parsed = JSON.parse(raw);
      const templates = Array.isArray(parsed.templates) ? parsed.templates : [];

      return {
        selectedId: String(parsed.selectedId || ""),
        templates: templates
          .filter((template) => template && template.id && template.text)
          .map((template) => ({
            id: String(template.id),
            name: String(template.name || template.filename || "Modèle SVG"),
            filename: String(template.filename || ""),
            text: String(template.text || ""),
            size: Number(template.size || String(template.text || "").length),
            createdAt: String(template.createdAt || ""),
            updatedAt: String(template.updatedAt || template.createdAt || "")
          }))
      };
    } catch (error) {
      console.warn("Impossible de lire les modèles SVG mémorisés", error);
      return emptySvgTemplateStore();
    }
  }

  function saveSvgTemplateStore(store) {
    localStorage.setItem(SVG_TEMPLATE_STORAGE_KEY, JSON.stringify(store));
  }

  function getStoredSvgTemplate(templateId) {
    const store = loadSvgTemplateStore();
    return store.templates.find((template) => template.id === templateId) || null;
  }

  function syncSvgTemplateSelector() {
    const select = $("svgTemplateSelect");
    const summary = $("svgTemplateSummary");

    if (!select) {
      return;
    }

    const store = loadSvgTemplateStore();
    const preferred = currentSvgTemplateId || store.selectedId || select.value;

    select.innerHTML = `<option value="">Aucun modèle enregistré</option>` + store.templates.map((template) => {
      const label = `${template.name}${template.size ? ` · ${Math.round(template.size / 1024)} Ko` : ""}`;
      return `<option value="${escapeHTML(template.id)}">${escapeHTML(label)}</option>`;
    }).join("");

    if ([...select.options].some((option) => option.value === preferred)) {
      select.value = preferred;
    }

    if (summary) {
      const active = select.value ? getStoredSvgTemplate(select.value) : null;

      summary.textContent = active
        ? `Modèle actif : ${active.name} — mémorisé dans ce navigateur.`
        : store.templates.length
          ? `${store.templates.length} modèle(s) mémorisé(s). Sélectionne un modèle avant export SVG/PDF.`
          : "Aucun modèle SVG mémorisé. Ajoute un modèle pour exporter des affiches.";
    }
  }

  function activateStoredSvgTemplate(templateId) {
    const store = loadSvgTemplateStore();
    const template = store.templates.find((item) => item.id === templateId);

    if (!template) {
      currentSvgTemplateId = "";
      svgTemplateText = "";
      store.selectedId = "";
      saveSvgTemplateStore(store);
      syncSvgTemplateSelector();
      $("status").textContent = "Aucun modèle SVG actif.";
      return;
    }

    currentSvgTemplateId = template.id;
    svgTemplateText = template.text;
    store.selectedId = template.id;
    saveSvgTemplateStore(store);
    syncSvgTemplateSelector();
    $("status").textContent = `Modèle SVG actif : ${template.name}`;
  }

  async function importSvgTemplateFile(file) {
    if (!file) {
      return;
    }

    const text = await file.text();

    if (!/<svg[\s>]/i.test(text)) {
      $("status").textContent = "Le fichier sélectionné ne ressemble pas à un SVG.";
      return;
    }

    const now = new Date().toISOString();
    const baseName = String(file.name || "modele.svg").replace(/\.svg$/i, "");
    const store = loadSvgTemplateStore();
    const existing = store.templates.find((template) => template.filename === file.name || template.name === baseName);

    let templateId;

    if (existing) {
      existing.name = baseName;
      existing.filename = file.name || existing.filename;
      existing.text = text;
      existing.size = text.length;
      existing.updatedAt = now;
      templateId = existing.id;
    } else {
      templateId = `svg_${Date.now()}_${Math.random().toString(16).slice(2)}`;
      store.templates.push({
        id: templateId,
        name: baseName,
        filename: file.name || "",
        text,
        size: text.length,
        createdAt: now,
        updatedAt: now
      });
    }

    store.selectedId = templateId;

    try {
      saveSvgTemplateStore(store);
    } catch (error) {
      $("status").textContent = "Impossible de mémoriser le SVG : stockage navigateur probablement plein.";
      return;
    }

    activateStoredSvgTemplate(templateId);
  }

  function deleteSelectedSvgTemplate() {
    const select = $("svgTemplateSelect");
    const templateId = select ? select.value : currentSvgTemplateId;

    if (!templateId) {
      $("status").textContent = "Aucun modèle sélectionné à supprimer.";
      return;
    }

    const store = loadSvgTemplateStore();
    const template = store.templates.find((item) => item.id === templateId);

    if (!template) {
      $("status").textContent = "Modèle introuvable.";
      return;
    }

    if (!window.confirm(`Supprimer le modèle SVG « ${template.name} » de ce navigateur ?`)) {
      return;
    }

    store.templates = store.templates.filter((item) => item.id !== templateId);
    store.selectedId = store.templates[0] ? store.templates[0].id : "";

    saveSvgTemplateStore(store);

    if (store.selectedId) {
      activateStoredSvgTemplate(store.selectedId);
    } else {
      currentSvgTemplateId = "";
      svgTemplateText = "";
      syncSvgTemplateSelector();
      $("status").textContent = "Modèle SVG supprimé. Aucun modèle actif.";
    }
  }

  function restoreStoredSvgTemplate() {
    const store = loadSvgTemplateStore();

    if (store.selectedId && store.templates.some((template) => template.id === store.selectedId)) {
      activateStoredSvgTemplate(store.selectedId);
      return;
    }

    syncSvgTemplateSelector();
  }

  function buildManagedPayload(allVisible) {
    const payload = buildPublicationPayload();
    const selectedSector = $("exportSector") ? $("exportSector").value : "";

    if (!allVisible && selectedSector) {
      payload.sectors = payload.sectors.filter((sector) => sector.sector === selectedSector);
    }

    return payload;
  }

  function publicationRowsForPayload(payload) {
    const allowedSectors = new Set(payload.sectors.map((sector) => sector.sector));
    return lastPublicationRows.filter((row) => allowedSectors.has(row.sector));
  }

  function downloadManagedCSV(payload) {
    const rows = publicationRowsForPayload(payload);

    const header = [
      "secteur",
      "indicateur",
      "rang",
      "professionnel",
      "code_postal",
      "secteur_activite",
      "valeur",
      "valeur_lisible"
    ];

    const csvCell = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
    const formatRawNumber = (value) => {
      if (typeof value !== "number" || !Number.isFinite(value)) return value;
      return String(Math.round(value * 10000) / 10000).replace(".", ",");
    };

    const lines = [header.join(";")];

    for (const row of rows) {
      lines.push([
        row.sector,
        row.indicator,
        row.rank,
        row.professional,
        row.zip,
        row.activity,
        formatRawNumber(row.value),
        row.readableValue
      ].map(csvCell).join(";"));
    }

    const suffix = payload.sectors.length === 1 ? slugify(payload.sectors[0].sector) : "tous-secteurs";
    downloadTextFile(
      `defis-pros-classements-${$("startDate").value}-${$("endDate").value}-${suffix}.csv`,
      lines.join("\n"),
      "text/csv;charset=utf-8"
    );

    $("status").textContent = `CSV exporté : ${rows.length} ligne(s), ${payload.sectors.length} secteur(s).`;
  }

  function downloadManagedJSON(payload) {
    const suffix = payload.sectors.length === 1 ? slugify(payload.sectors[0].sector) : "tous-secteurs";

    downloadTextFile(
      `defis-pros-pack-affiches-${$("startDate").value}-${$("endDate").value}-${suffix}.json`,
      JSON.stringify(payload, null, 2),
      "application/json;charset=utf-8"
    );

    $("status").textContent = `JSON exporté : ${payload.sectors.length} secteur(s).`;
  }

  function escapeForHTMLDocument(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function openManagedPDF(payload) {
    if (!svgTemplateText) {
      $("status").textContent = "Charge d’abord un modèle SVG avant de préparer le PDF.";
      return;
    }

    if (!payload.sectors.length) {
      $("status").textContent = "Aucun secteur à exporter en PDF.";
      return;
    }

    const titleSuffix = payload.sectors.length === 1
      ? payload.sectors[0].sector
      : "tous les secteurs visibles";

    const pages = [];

    for (const sectorPayload of payload.sectors) {
      try {
        const svg = buildSectorSvg(svgTemplateText, sectorPayload);
        pages.push(`
          <section class="pdf-page">
            ${svg}
          </section>
        `);
      } catch (error) {
        $("status").textContent = `Erreur préparation PDF : ${error.message}`;
        return;
      }
    }

    const printHTML = `<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Défis des pros — ${escapeForHTMLDocument(titleSuffix)}</title>
  <style>
    @page {
      size: A4 portrait;
      margin: 0;
    }

    * {
      box-sizing: border-box;
    }

    html,
    body {
      margin: 0;
      padding: 0;
      background: #ece7df;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .toolbar {
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px;
      background: #241a12;
      color: white;
      font-size: 14px;
    }

    .toolbar strong {
      display: block;
      font-size: 15px;
    }

    .toolbar span {
      opacity: .82;
    }

    .toolbar-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .toolbar button {
      border: 0;
      border-radius: 10px;
      padding: 9px 12px;
      font-weight: 800;
      cursor: pointer;
      background: white;
      color: #241a12;
    }

    .pdf-page {
      width: 210mm;
      min-height: 297mm;
      margin: 14px auto;
      background: white;
      page-break-after: always;
      break-after: page;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }

    .pdf-page:last-child {
      page-break-after: auto;
      break-after: auto;
    }

    .pdf-page svg {
      width: 210mm;
      height: auto;
      max-height: 297mm;
      display: block;
    }

    @media print {
      html,
      body {
        background: white;
      }

      .toolbar {
        display: none;
      }

      .pdf-page {
        margin: 0;
        box-shadow: none;
      }
    }
  </style>
</head>
<body>
  <div class="toolbar">
    <div>
      <strong>Défis des pros — ${escapeForHTMLDocument(titleSuffix)}</strong>
      <span>${payload.sectors.length} affiche(s). Utiliser “Enregistrer en PDF” dans la fenêtre d’impression.</span>
    </div>
    <div class="toolbar-actions">
      <button onclick="window.print()">Imprimer / enregistrer en PDF</button>
      <button onclick="window.close()">Fermer</button>
    </div>
  </div>

  ${pages.join("\n")}
</body>
</html>`;

    const preview = window.open("", "_blank");

    if (!preview) {
      downloadTextFile(
        `defis-pros-print-${$("startDate").value}-${$("endDate").value}-${slugify(titleSuffix)}.html`,
        printHTML,
        "text/html;charset=utf-8"
      );

      $("status").textContent = "Popup bloquée : fichier HTML d’impression téléchargé. Ouvre-le puis fais Ctrl+P → Enregistrer en PDF.";
      return;
    }

    preview.document.open();
    preview.document.write(printHTML);
    preview.document.close();
    preview.focus();

    $("status").textContent = payload.sectors.length === 1
      ? `Prévisualisation PDF ouverte : ${payload.sectors[0].sector}.`
      : `Prévisualisation PDF ouverte : ${payload.sectors.length} affiche(s).`;
  }

  function downloadManagedSVG(payload) {
    if (!svgTemplateText) {
      $("status").textContent = "Charge d’abord un modèle SVG.";
      return;
    }

    if (!payload.sectors.length) {
      $("status").textContent = "Aucun secteur à exporter.";
      return;
    }

    payload.sectors.forEach((sectorPayload, index) => {
      window.setTimeout(() => {
        try {
          const svg = buildSectorSvg(svgTemplateText, sectorPayload);
          const filename = `defis-pros-${$("startDate").value}-${$("endDate").value}-${slugify(sectorPayload.sector)}.svg`;
          downloadTextFile(filename, svg, "image/svg+xml;charset=utf-8");
        } catch (error) {
          $("status").textContent = `Erreur export SVG : ${error.message}`;
        }
      }, index * 300);
    });

    $("status").textContent = payload.sectors.length === 1
      ? `SVG exporté : ${payload.sectors[0].sector}.`
      : `Export SVG lancé : ${payload.sectors.length} fichiers pour les secteurs filtrés.`;
  }

  function runManagedExport(allVisible) {
    const payload = buildManagedPayload(allVisible);
    const format = $("exportFormat") ? $("exportFormat").value : "svg";

    if (!payload.sectors.length) {
      $("status").textContent = "Aucun secteur disponible pour l’export.";
      return;
    }

    if (format === "csv") {
      downloadManagedCSV(payload);
      return;
    }

    if (format === "json") {
      downloadManagedJSON(payload);
      return;
    }

    if (format === "pdf") {
      openManagedPDF(payload);
      return;
    }

    downloadManagedSVG(payload);
  }

  function syncExportManager() {
    const select = $("exportSector");
    const summary = $("exportSummary");

    if (!select) {
      return;
    }

    const payload = buildPublicationPayload();
    const previous = select.value;

    select.innerHTML = payload.sectors.map((sector) => (
      `<option value="${escapeHTML(sector.sector)}">${escapeHTML(sector.sector)}</option>`
    )).join("");

    if ([...select.options].some((option) => option.value === previous)) {
      select.value = previous;
    }

    if (!select.value && select.options.length) {
      select.value = select.options[0].value;
    }

    if (summary) {
      summary.textContent = payload.sectors.length
        ? `${payload.sectors.length} secteur(s) disponible(s). Le bouton principal exporte uniquement le secteur cible sélectionné.`
        : "Aucun secteur disponible avec les filtres actuels.";
    }
  }

  function exportSVGPack() {
    if (!svgTemplateText) {
      $("status").textContent = "Charge d’abord un modèle SVG avec le bouton « Charger modèle SVG ».";
      return;
    }

    const payload = buildPublicationPayload();

    if (!payload.sectors.length) {
      $("status").textContent = "Aucun secteur à exporter. Vérifie les filtres, les seuils et le secteur cible.";
      return;
    }

    payload.sectors.forEach((sectorPayload, index) => {
      window.setTimeout(() => {
        try {
          const svg = buildSectorSvg(svgTemplateText, sectorPayload);
          const filename = `defis-pros-${$("startDate").value}-${$("endDate").value}-${slugify(sectorPayload.sector)}.svg`;

          downloadTextFile(filename, svg, "image/svg+xml;charset=utf-8");
        } catch (error) {
          $("status").textContent = `Erreur export SVG : ${error.message}`;
        }
      }, index * 250);
    });

    $("status").textContent = `Export SVG visible lancé : ${payload.sectors.length} affiche(s), selon les filtres affichés.`;
  }

  function exportJSON() {
    const payload = buildPublicationPayload();
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");

    a.href = url;
    a.download = `defis-pros-pack-affiches-${$("startDate").value}-${$("endDate").value}.json`;
    a.click();

    URL.revokeObjectURL(url);

    $("status").textContent = `JSON visible exporté : ${payload.sectors.length} secteur(s), ${lastPublicationRows.length} ligne(s), selon les filtres affichés.`;
  }

  function exportCSV() {
    const header = [
      "secteur",
      "indicateur",
      "rang",
      "professionnel",
      "code_postal",
      "secteur_activite",
      "valeur",
      "valeur_lisible"
    ];

    const csvCell = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
    const formatRawNumber = (value) => {
      if (typeof value !== "number" || !Number.isFinite(value)) return value;
      return String(Math.round(value * 10000) / 10000).replace(".", ",");
    };

    const lines = [header.join(";")];

    for (const r of lastPublicationRows) {
      lines.push([
        r.sector,
        r.indicator,
        r.rank,
        r.professional,
        r.zip,
        r.activity,
        formatRawNumber(r.value),
        r.readableValue
      ].map(csvCell).join(";"));
    }

    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `defis-pros-pack-publication-${$("startDate").value}-${$("endDate").value}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    $("status").textContent = `CSV visible exporté : ${lastPublicationRows.length} ligne(s) de classement selon les filtres affichés.`;
  }

  async function copyPack() {
    await navigator.clipboard.writeText($("pack").value);
    $("status").textContent = "Pack de publication copié dans le presse-papiers.";
  }

  $("refreshBtn").addEventListener("click", fetchPros);
  $("csvBtn").addEventListener("click", exportCSV);
  if ($("jsonBtn")) $("jsonBtn").addEventListener("click", exportJSON);
  if ($("svgBtn")) $("svgBtn").addEventListener("click", exportSVGPack);
  if ($("exportSelectedBtn")) $("exportSelectedBtn").addEventListener("click", () => runManagedExport(false));
  if ($("exportAllVisibleBtn")) $("exportAllVisibleBtn").addEventListener("click", () => runManagedExport(true));

  function bindSvgTemplateInput(inputId) {
    const input = $(inputId);

    if (!input) {
      return;
    }

    input.addEventListener("change", async (event) => {
      const file = event.target.files && event.target.files[0];

      if (!file) {
        return;
      }

      await importSvgTemplateFile(file);
      input.value = "";
    });
  }

  bindSvgTemplateInput("svgTemplateInput");
  bindSvgTemplateInput("svgTemplateStoreInput");

  if ($("svgTemplateSelect")) {
    $("svgTemplateSelect").addEventListener("change", (event) => {
      activateStoredSvgTemplate(event.target.value);
    });
  }

  if ($("deleteSvgTemplateBtn")) {
    $("deleteSvgTemplateBtn").addEventListener("click", deleteSelectedSvgTemplate);
  }

  $("copyBtn").addEventListener("click", copyPack);

  ["startDate", "endDate"].forEach(id => $(id).addEventListener("change", fetchPros));
  ["topN", "mode", "minReceived", "minEmittedForRate", "sectorFilter", "internalAccounts"].forEach(id => $(id).addEventListener("change", render));

  restoreStoredSvgTemplate();
  fetchPros();
})();
