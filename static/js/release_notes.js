/* VERSION_UI002F_RELEASE_NOTES_PRODUCT_HISTORY — page d'entrée */

(function () {
  "use strict";

  const FALLBACK_LABEL = "MLCFlux bêta v1.0.6 multi — juin 2026";
  const BUTTON_ID = "mlcfluxReleaseNotesButton";
  const OVERLAY_ID = "mlcflux-release-note-overlay";

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function labelWithoutMonth(label) {
    return String(label || FALLBACK_LABEL).replace(/\s+—\s+juin\s+2026\s*$/i, "");
  }

  function renderInlineMarkdown(value) {
    return escapeHtml(value)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/[“”]/g, '"');
  }

  function extractLead(markdown) {
    const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;
      if (line.startsWith("#")) continue;
      if (line.startsWith("- ")) continue;
      return line;
    }

    return "";
  }

  function stripLeadFromMarkdown(markdown) {
    const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
    let removed = false;

    return lines.filter((rawLine) => {
      const line = rawLine.trim();

      if (removed) return true;
      if (!line) return true;
      if (line.startsWith("#")) return true;
      if (line.startsWith("- ")) return true;

      removed = true;
      return false;
    }).join("\n").trim();
  }

  function renderReleaseMarkdown(markdown) {
    const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
    const html = [];

    for (const rawLine of lines) {
      const line = rawLine.trim();

      if (!line) {
        html.push('<div class="mlcflux-release-note-gap"></div>');
        continue;
      }

      if (line.startsWith("### ")) {
        html.push(`<h4>${renderInlineMarkdown(line.slice(4))}</h4>`);
        continue;
      }

      if (line.startsWith("## ")) {
        html.push(`<h3>${renderInlineMarkdown(line.slice(3))}</h3>`);
        continue;
      }

      if (line.startsWith("# ")) {
        html.push(`<h2>${renderInlineMarkdown(line.slice(2))}</h2>`);
        continue;
      }

      if (line.startsWith("- ")) {
        html.push(`<li>${renderInlineMarkdown(line.slice(2))}</li>`);
        continue;
      }

      html.push(`<p>${renderInlineMarkdown(line)}</p>`);
    }

    return html.join("")
      .replace(/(<li>.*?<\/li>)(?!\s*<li>)/gs, "<ul>$1</ul>")
      .replace(/<\/ul>\s*<ul>/g, "");
  }

  function renderReleaseHistory(payload) {
    const label = payload.label || FALLBACK_LABEL;
    const sections = Array.isArray(payload.sections) ? payload.sections : [];
    const current = payload.current || sections[0] || {};
    const lead = extractLead(current.markdown || "");
    const currentVersion = payload.version || current.version || "";

    const history = sections.map((section) => {
      const markdown = section && section.markdown ? section.markdown : "";
      const normalized = section && section.version === currentVersion
        ? stripLeadFromMarkdown(markdown)
        : markdown;

      return normalized ? renderReleaseMarkdown(normalized) : "";
    }).filter(Boolean).join("");

    return `
      <div class="mlcflux-release-current">
        <p class="mlcflux-release-current-kicker">Version actuelle</p>
        <h3>${escapeHtml(labelWithoutMonth(label))}</h3>
        ${lead ? `<p>${renderInlineMarkdown(lead)}</p>` : ""}
      </div>
      <div class="mlcflux-release-history">
        ${history || "<p>Aucune note de version disponible.</p>"}
      </div>
    `;
  }

  function ensureFallbackStyles() {
    if (document.getElementById("mlcflux-release-notes-fallback-style")) return;

    const style = document.createElement("style");
    style.id = "mlcflux-release-notes-fallback-style";
    style.textContent = `
      .mlcflux-release-note-trigger {
        width: auto !important;
        display: inline-flex !important;
        align-items: center;
        justify-content: center;
        gap: 0.3rem;
        border-radius: 999px;
        border: 1px solid rgba(232, 73, 38, 0.32);
        padding: 0.55rem 0.95rem;
        background: rgba(255, 255, 255, 0.42);
        color: #c64527;
        font-weight: 800;
        cursor: pointer;
      }

      .mlcflux-release-note-trigger:hover {
        background: rgba(255, 255, 255, 0.68);
      }

      .mlcflux-release-note-overlay {
        position: fixed;
        inset: 0;
        z-index: 100000;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 1.25rem;
        background: rgba(15, 23, 42, 0.54);
        backdrop-filter: blur(4px);
      }

      .mlcflux-release-note-modal {
        width: min(760px, calc(100vw - 2rem));
        max-height: min(760px, calc(100vh - 2rem));
        overflow: hidden;
        display: flex;
        flex-direction: column;
        border-radius: 24px;
        background: #fffaf3;
        color: #1f2933;
        border: 1px solid rgba(15, 23, 42, 0.12);
        box-shadow: 0 24px 70px rgba(15, 23, 42, 0.28);
      }

      .mlcflux-release-note-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        padding: 1.15rem 1.25rem 0.85rem;
        border-bottom: 1px solid rgba(15, 23, 42, 0.10);
      }

      .mlcflux-release-note-title {
        margin: 0.1rem 0 0.25rem;
        font-size: 1.18rem;
        line-height: 1.25;
      }

      .mlcflux-release-note-subtitle {
        margin: 0;
        color: rgba(31, 41, 51, 0.72);
        font-size: 0.92rem;
      }

      .mlcflux-release-note-close {
        border: 0;
        border-radius: 999px;
        width: 2rem;
        height: 2rem;
        cursor: pointer;
        font-size: 1.2rem;
        line-height: 1;
        background: rgba(15, 23, 42, 0.08);
        color: #1f2933;
      }

      .mlcflux-release-note-body {
        padding: 1.15rem 1.45rem 1.35rem;
        overflow: auto;
        line-height: 1.55;
      }

      .mlcflux-release-current {
        margin-bottom: 1.35rem;
      }

      .mlcflux-release-current-kicker {
        margin: 0 0 0.65rem;
        color: rgba(31, 41, 51, 0.78);
      }

      .mlcflux-release-current h3,
      .mlcflux-release-history h3 {
        margin: 0.9rem 0 0.6rem;
        font-size: 1.02rem;
        line-height: 1.25;
      }

      .mlcflux-release-current h3 {
        font-size: 1.12rem;
      }

      .mlcflux-release-history ul {
        margin: 0.45rem 0 1.15rem 1.4rem;
        padding: 0;
      }

      .mlcflux-release-history li {
        margin: 0.25rem 0;
      }

      .mlcflux-release-note-body code {
        padding: 0.08rem 0.28rem;
        border-radius: 0.35rem;
        background: rgba(15, 23, 42, 0.08);
        font-size: 0.92em;
      }
    `;

    document.head.appendChild(style);
  }

  async function fetchVersionPayload() {
    const response = await fetch("/api/version", {
      method: "GET",
      credentials: "same-origin",
      headers: { "Accept": "application/json" }
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  function findVersionBadge() {
    return (
      document.getElementById("mlcfluxLandingVersionBadge")
      || document.querySelector("[data-mlcflux-version-badge='landing']")
      || Array.from(document.querySelectorAll(".version-badge")).find((node) => {
        const text = String(node.textContent || "").trim().toLowerCase();
        return text.startsWith("version :");
      })
      || null
    );
  }

  function ensureReleaseNotesButton() {
    const badge = findVersionBadge();
    let button = document.getElementById(BUTTON_ID);

    if (!button) {
      button = document.createElement("button");
      button.id = BUTTON_ID;
      button.type = "button";
      button.textContent = "Notes de version ↗";
      button.setAttribute("aria-label", "Afficher les notes de version");

      if (badge && badge.parentElement) {
        badge.insertAdjacentElement("afterend", button);
      } else {
        document.body.appendChild(button);
      }
    }

    button.classList.add("mlcflux-release-note-trigger");
    button.dataset.mlcfluxReleaseNotesTrigger = "1";
    button.type = "button";
    button.style.width = "auto";
    button.style.display = "inline-flex";

    return button;
  }

  function closeReleaseNotesModal() {
    const overlay = document.getElementById(OVERLAY_ID);
    if (overlay) overlay.remove();
  }

  async function openReleaseNotesModal() {
    ensureFallbackStyles();
    closeReleaseNotesModal();

    const overlay = document.createElement("div");
    overlay.id = OVERLAY_ID;
    overlay.className = "mlcflux-release-note-overlay";
    overlay.innerHTML = `
      <section class="mlcflux-release-note-modal" role="dialog" aria-modal="true" aria-labelledby="mlcflux-release-note-title">
        <header class="mlcflux-release-note-header">
          <div>
            <h2 class="mlcflux-release-note-title" id="mlcflux-release-note-title">Notes de version</h2>
            <p class="mlcflux-release-note-subtitle">${escapeHtml(FALLBACK_LABEL)}</p>
          </div>
          <button type="button" class="mlcflux-release-note-close" aria-label="Fermer">×</button>
        </header>
        <div class="mlcflux-release-note-body">
          <p>Chargement des notes de version…</p>
        </div>
      </section>
    `;

    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) closeReleaseNotesModal();
    });

    const closeButton = overlay.querySelector(".mlcflux-release-note-close");
    if (closeButton) closeButton.addEventListener("click", closeReleaseNotesModal);

    document.body.appendChild(overlay);

    try {
      const payload = await fetchVersionPayload();
      const label = payload.label || FALLBACK_LABEL;

      overlay.querySelector(".mlcflux-release-note-subtitle").textContent = label;
      overlay.querySelector(".mlcflux-release-note-body").innerHTML = renderReleaseHistory(payload);
    } catch (error) {
      overlay.querySelector(".mlcflux-release-note-body").innerHTML =
        `<p>Impossible de charger les notes de version : ${escapeHtml(error.message || error)}</p>`;
    }
  }

  async function refreshLandingVersionBadge() {
    const badge = findVersionBadge();

    try {
      const payload = await fetchVersionPayload();
      const label = payload.label || FALLBACK_LABEL;

      if (badge) {
        badge.textContent = `version : ${label}`;
        badge.setAttribute("data-mlcflux-version", payload.version || "");
        badge.setAttribute("aria-label", label);
      }

      const meta = document.querySelector('meta[name="mlcflux-version"]');
      if (meta) meta.setAttribute("content", label);
    } catch (_error) {
      if (badge) badge.textContent = `version : ${FALLBACK_LABEL}`;
    }
  }

  function isReleaseNotesTrigger(target) {
    if (!target || !target.closest) return null;
    return target.closest(`#${BUTTON_ID}, [data-mlcflux-release-notes-trigger="1"], .mlcflux-release-note-trigger`);
  }

  function initReleaseNotes() {
    ensureFallbackStyles();
    ensureReleaseNotesButton();

    document.addEventListener("click", (event) => {
      const trigger = isReleaseNotesTrigger(event.target);
      if (!trigger) return;

      event.preventDefault();
      event.stopPropagation();
      openReleaseNotesModal();
    }, true);

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeReleaseNotesModal();
        return;
      }

      const trigger = isReleaseNotesTrigger(event.target);
      if (!trigger) return;
      if (event.key !== "Enter" && event.key !== " ") return;

      event.preventDefault();
      openReleaseNotesModal();
    }, true);

    refreshLandingVersionBadge();
  }

  window.openMlcFluxReleaseNotesModal = openReleaseNotesModal;
  window.closeMlcFluxReleaseNotesModal = closeReleaseNotesModal;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initReleaseNotes, { once: true });
  } else {
    initReleaseNotes();
  }
})();
