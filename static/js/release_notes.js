/* RELEASE_NOTES_CONTENT002 — modale Notes de version page principale */
(function () {
  "use strict";

  const TRIGGER_CLASS = "mlcflux-release-note-trigger";
  const OVERLAY_ID = "mlcflux-release-note-overlay";

  function findVersionBadge() {
    const selectors = [
      ".version",
      ".version-badge",
      ".mlcflux-version",
      "[data-mlcflux-version]",
      "span",
      "small",
      "strong",
      "p",
      "div"
    ];

    const nodes = Array.from(document.querySelectorAll(selectors.join(",")));

    return nodes.find((node) => {
      const text = String(node.textContent || "").trim();
      return (
        /^version\s*:/i.test(text) ||
        /MLCFlux\s+b[êe]ta/i.test(text)
      );
    });
  }

  function createOverlay() {
    const overlay = document.createElement("div");
    overlay.id = OVERLAY_ID;
    overlay.className = "mlcflux-release-note-overlay";
    overlay.hidden = true;

    overlay.innerHTML = `
      <section class="mlcflux-release-note-modal" role="dialog" aria-modal="true" aria-labelledby="mlcflux-release-note-title">
        <header class="mlcflux-release-note-header">
          <div>
            <h2 class="mlcflux-release-note-title" id="mlcflux-release-note-title">Notes de version</h2>
            <p class="mlcflux-release-note-subtitle">MLCFlux bêta v1.0.4 multi — juin 2026</p>
          </div>
          <button class="mlcflux-release-note-close" type="button" aria-label="Fermer les notes de version">×</button>
        </header>

        <div class="mlcflux-release-note-body">
          <section class="mlcflux-release-note-current">
            <p class="mlcflux-release-note-kicker">Version actuelle</p>
            <h3>MLCFlux bêta v1.0.4 multi</h3>
            <p>
              Cette version marque le passage vers une exploitation plus autonome :
              synchronisation automatique quotidienne, orchestration multi-instance
              et documentation intégrée des évolutions.
            </p>
          </section>

          <section class="mlcflux-release-note-version">
            <h3>v1.0.4 — 20/06/2026</h3>
            <ul>
              <li><strong>Activation de la synchronisation automatique quotidienne</strong> : les instances peuvent désormais être mises à jour par tâche planifiée, sans relance manuelle systématique.</li>
              <li><strong>Ajout d’un orchestrateur de synchronisation multi-instance</strong> pour traiter les monnaies locales configurées dans un même flux technique.</li>
              <li><strong>Ajout des notes de version</strong> directement sur la page d’entrée.</li>
              <li>Professionnalisation de la page d’accueil publique : présentation plus sobre, introduction resserrée, chargement plus lisible des instances.</li>
            </ul>
          </section>

          <section class="mlcflux-release-note-version">
            <h3>v1.0.3 — 17/06/2026</h3>
            <ul>
              <li><strong>Stabilisation des fiches professionnelles</strong> : meilleure cohérence des onglets, des noms affichés et des libellés professionnels.</li>
              <li><strong>Consolidation des vues liées aux professionnels</strong>, notamment les perspectives de réemploi et les informations utiles à l’analyse d’un acteur.</li>
              <li>Préparation d’une lecture plus robuste des données professionnelles entre La Gonette et La Graine.</li>
            </ul>
          </section>

          <section class="mlcflux-release-note-version">
            <h3>v1.0.2 — 16/06/2026</h3>
            <ul>
              <li><strong>Durcissement de la sécurité d’authentification</strong> et nettoyage des artefacts runtime avant déploiement.</li>
              <li><strong>Stabilisation de la page publique multi-instance</strong> et de la navigation entre sélection, connexion et espace d’analyse.</li>
              <li><strong>Stabilisation du guide Markdown</strong> et de la section “Info & méthodologie”.</li>
              <li>Ouverture de la section “Info & méthodologie” aux utilisateurs non administrateurs.</li>
              <li>Correction de la navigation d’administration.</li>
            </ul>
          </section>

          <section class="mlcflux-release-note-version">
            <h3>v1.0.1 — 16/06/2026</h3>
            <ul>
              <li><strong>Premier socle bêta multi-instance de MLCFlux.</strong></li>
              <li>Mise en place de la sélection publique des monnaies locales.</li>
              <li>Première intégration des instances La Gonette et La Graine.</li>
              <li>Séparation entre page publique de sélection et espaces d’analyse protégés.</li>
              <li>Mise en place des premiers indicateurs comparables multi-MLC.</li>
            </ul>
          </section>
        </div>
      </section>
    `;

    return overlay;
  }

  function mountReleaseNotes() {
    if (document.querySelector("." + TRIGGER_CLASS)) {
      return;
    }

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = TRIGGER_CLASS;
    trigger.textContent = "Notes de version";
    trigger.setAttribute("aria-haspopup", "dialog");
    trigger.setAttribute("aria-controls", OVERLAY_ID);

    const versionBadge = findVersionBadge();

    if (versionBadge && versionBadge.parentNode) {
      const row = document.createElement("div");
      row.className = "mlcflux-release-note-row";

      versionBadge.parentNode.insertBefore(row, versionBadge);
      row.appendChild(versionBadge);
      row.appendChild(trigger);
    } else {
      const title = document.querySelector("h1");
      const row = document.createElement("div");
      row.className = "mlcflux-release-note-row";
      row.appendChild(trigger);

      if (title) {
        title.insertAdjacentElement("afterend", row);
      } else {
        document.body.prepend(row);
      }
    }

    const overlay = createOverlay();
    document.body.appendChild(overlay);

    const closeButton = overlay.querySelector(".mlcflux-release-note-close");
    const modal = overlay.querySelector(".mlcflux-release-note-modal");

    function openModal() {
      overlay.hidden = false;
      document.documentElement.classList.add("mlcflux-release-note-open");
      if (closeButton) {
        closeButton.focus();
      }
    }

    function closeModal() {
      overlay.hidden = true;
      document.documentElement.classList.remove("mlcflux-release-note-open");
      trigger.focus();
    }

    trigger.addEventListener("click", openModal);

    if (closeButton) {
      closeButton.addEventListener("click", closeModal);
    }

    overlay.addEventListener("click", function (event) {
      if (!modal || !modal.contains(event.target)) {
        closeModal();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !overlay.hidden) {
        closeModal();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountReleaseNotes);
  } else {
    mountReleaseNotes();
  }
})();
