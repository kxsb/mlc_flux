/* LANDING_POLISH002 — restructuration robuste de la page principale */
(function () {
  "use strict";

  function normalizeText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[’']/g, "'")
      .replace(/\s+/g, " ")
      .toLowerCase()
      .trim();
  }

  function directText(node) {
    return Array.from(node.childNodes || [])
      .filter((child) => child.nodeType === Node.TEXT_NODE)
      .map((child) => child.textContent || "")
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function findHeadingContaining(fragment) {
    const wanted = normalizeText(fragment);
    return Array.from(document.querySelectorAll("h1,h2,h3")).find((node) =>
      normalizeText(node.textContent).includes(wanted)
    );
  }

  function findSmallestElement(predicate) {
    const nodes = Array.from(document.body.querySelectorAll("*"))
      .filter((node) => !["SCRIPT", "STYLE", "LINK", "META"].includes(node.tagName));

    return nodes
      .filter(predicate)
      .sort((a, b) => a.querySelectorAll("*").length - b.querySelectorAll("*").length)[0] || null;
  }

  function findVersionBadge() {
    return findSmallestElement((node) => {
      const own = normalizeText(directText(node));
      const full = normalizeText(node.textContent);
      return (
        own.startsWith("version :") ||
        full.startsWith("version : mlcflux beta") ||
        full.startsWith("version : mlcflux bêta")
      );
    });
  }

  function markIntroCard(title, introTitle) {
    if (!title || !introTitle) {
      return null;
    }

    let node = title.parentElement;
    while (node && node !== document.body) {
      if (node.contains(introTitle)) {
        node.classList.add("mlcflux-intro-card");
        return node;
      }
      node = node.parentElement;
    }

    return null;
  }

  function polishTitleAndMeta() {
    const title = findHeadingContaining("MLCFlux");
    const introTitle = findHeadingContaining("Qu'est-ce que c'est");

    if (title) {
      const cleaned = String(title.textContent || "").replace(/^#\s*/, "").trim();
      if (cleaned) {
        title.textContent = cleaned;
      }
      title.classList.add("mlcflux-landing-title");
    }

    markIntroCard(title, introTitle);

    const versionBadge = findVersionBadge();
    const releaseButton = document.querySelector(".mlcflux-release-note-trigger");

    if (!title || (!versionBadge && !releaseButton)) {
      return;
    }

    let row = document.querySelector(".mlcflux-landing-meta-row");
    if (!row) {
      row = document.createElement("div");
      row.className = "mlcflux-landing-meta-row";
      title.insertAdjacentElement("afterend", row);
    }

    if (versionBadge && versionBadge.parentElement !== row) {
      row.appendChild(versionBadge);
    }

    if (releaseButton && releaseButton.parentElement !== row) {
      row.appendChild(releaseButton);
    }

    document.querySelectorAll(".mlcflux-release-note-row").forEach((oldRow) => {
      if (!oldRow.children.length || !oldRow.textContent.trim()) {
        oldRow.remove();
      }
    });
  }

  function compactIntro() {
    const introTitle = findHeadingContaining("Qu'est-ce que c'est");
    const instanceTitle = findHeadingContaining("Ouvrir une instance");

    if (!introTitle || document.querySelector(".mlcflux-intro-copy")) {
      return;
    }

    introTitle.classList.add("mlcflux-intro-title");

    const paragraphs = [];
    let node = introTitle.nextElementSibling;

    while (node && node !== instanceTitle) {
      const next = node.nextElementSibling;

      if (node.tagName === "HR") {
        node.classList.add("mlcflux-intro-separator");
      }

      if (node.tagName === "P") {
        paragraphs.push(node);
      }

      node = next;
    }

    if (!paragraphs.length) {
      return;
    }

    const copy = document.createElement("div");
    copy.className = "mlcflux-intro-copy";
    paragraphs[0].parentNode.insertBefore(copy, paragraphs[0]);

    paragraphs.forEach((paragraph) => {
      paragraph.classList.add("mlcflux-intro-paragraph");
      copy.appendChild(paragraph);
    });
  }

  function headingTextEquals(node, text) {
    return normalizeText(node.textContent) === normalizeText(text);
  }

  function closestCardForHeading(heading) {
    let node = heading.parentElement;
    let best = node;

    while (node && node !== document.body) {
      const text = normalizeText(node.textContent);

      if (
        text.includes("plage des donnees") ||
        text.includes("masse monetaire suivie") ||
        text.includes("entrer dans l'instance")
      ) {
        best = node;
      }

      node = node.parentElement;
    }

    return best || heading.parentElement;
  }

  function commonAncestor(a, b) {
    if (!a || !b) {
      return null;
    }

    const ancestors = new Set();
    let node = a;

    while (node) {
      ancestors.add(node);
      node = node.parentElement;
    }

    node = b;
    while (node) {
      if (ancestors.has(node)) {
        return node;
      }
      node = node.parentElement;
    }

    return null;
  }

  function findCardsContainer() {
    const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4"));

    const gonette = headings.find((node) => headingTextEquals(node, "La Gonette"));
    const graine = headings.find((node) => headingTextEquals(node, "La Graine"));

    if (!gonette || !graine) {
      return null;
    }

    const gonetteCard = closestCardForHeading(gonette);
    const graineCard = closestCardForHeading(graine);
    const ancestor = commonAncestor(gonetteCard, graineCard);

    if (!ancestor || ancestor === document.body) {
      return gonetteCard.parentElement || graineCard.parentElement || null;
    }

    return ancestor;
  }

  function moveInstanceHeader() {
    document.querySelectorAll(".mlcflux-instance-header").forEach((header) => {
      header.remove();
    });

    const instanceTitle = findHeadingContaining("Ouvrir une instance");

    if (!instanceTitle) {
      return true;
    }

    const paragraph =
      instanceTitle.nextElementSibling &&
      instanceTitle.nextElementSibling.tagName === "P"
        ? instanceTitle.nextElementSibling
        : null;

    const previous = instanceTitle.previousElementSibling;
    if (previous && previous.tagName === "HR") {
      previous.classList.add("mlcflux-intro-separator");
    }

    if (paragraph) {
      paragraph.remove();
    }

    instanceTitle.remove();

    return true;
  }

  function polishLanding() {
    document.documentElement.classList.add("mlcflux-landing-polished");
    polishTitleAndMeta();
    compactIntro();
    moveInstanceHeader();
  }

  function runWithRetries() {
    polishLanding();

    let attempts = 0;
    const timer = window.setInterval(function () {
      attempts += 1;
      polishLanding();

      const hasMeta = Boolean(document.querySelector(".mlcflux-landing-meta-row .mlcflux-release-note-trigger"));
      const hasInstanceHeader = Boolean(document.querySelector(".mlcflux-instance-header"));

      if (attempts >= 12 || (hasMeta && hasInstanceHeader)) {
        window.clearInterval(timer);
      }
    }, 250);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", runWithRetries);
  } else {
    runWithRetries();
  }
})();
