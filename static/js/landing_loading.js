/* LANDING_LOADING002 — loader autonome des cartes instances */
(function () {
  "use strict";

  const LOADER_ID = "mlcflux-instance-loading";

  function normalizeText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[’']/g, "'")
      .replace(/\s+/g, " ")
      .toLowerCase()
      .trim();
  }

  function headingTextEquals(node, text) {
    return normalizeText(node.textContent) === normalizeText(text);
  }

  function instanceCardsAreVisible() {
    const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4"));
    const hasGonette = headings.some((node) => headingTextEquals(node, "La Gonette"));
    const hasGraine = headings.some((node) => headingTextEquals(node, "La Graine"));

    return hasGonette && hasGraine;
  }

  function findIntroCard() {
    const introTitle = Array.from(document.querySelectorAll("h1,h2,h3")).find((node) =>
      normalizeText(node.textContent).includes("qu'est-ce que c'est")
    );

    if (!introTitle) {
      return null;
    }

    let node = introTitle.parentElement;
    let best = node;

    while (node && node !== document.body) {
      const text = normalizeText(node.textContent);

      if (
        text.includes("mlcflux") &&
        text.includes("qu'est-ce que c'est")
      ) {
        best = node;
      }

      node = node.parentElement;
    }

    return best;
  }

  function createLoader() {
    const wrapper = document.createElement("div");
    wrapper.id = LOADER_ID;
    wrapper.className = "mlcflux-instance-loading";
    wrapper.setAttribute("aria-live", "polite");
    wrapper.setAttribute("aria-label", "Chargement des instances");

    wrapper.innerHTML = `
      <p class="mlcflux-instance-loading-caption">Chargement des instances disponibles…</p>
      <div class="mlcflux-instance-loading-card" aria-hidden="true">
        <span class="mlcflux-instance-loading-line title"></span>
        <span class="mlcflux-instance-loading-line short"></span>
        <span class="mlcflux-instance-loading-line long"></span>
        <span class="mlcflux-instance-loading-line medium"></span>
        <span class="mlcflux-instance-loading-line long"></span>
      </div>
      <div class="mlcflux-instance-loading-card" aria-hidden="true">
        <span class="mlcflux-instance-loading-line title"></span>
        <span class="mlcflux-instance-loading-line short"></span>
        <span class="mlcflux-instance-loading-line long"></span>
        <span class="mlcflux-instance-loading-line medium"></span>
        <span class="mlcflux-instance-loading-line long"></span>
      </div>
    `;

    return wrapper;
  }

  function removeLoader() {
    const loader = document.getElementById(LOADER_ID);
    if (loader) {
      loader.remove();
    }
  }

  function mountLoader() {
    if (instanceCardsAreVisible()) {
      removeLoader();
      return;
    }

    if (document.getElementById(LOADER_ID)) {
      return;
    }

    const introCard = findIntroCard();

    if (introCard && introCard.parentNode) {
      introCard.insertAdjacentElement("afterend", createLoader());
      return;
    }

    document.body.appendChild(createLoader());
  }

  function watchCards() {
    mountLoader();

    const observer = new MutationObserver(function () {
      if (instanceCardsAreVisible()) {
        removeLoader();
        observer.disconnect();
        return;
      }

      mountLoader();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    window.setTimeout(function () {
      if (instanceCardsAreVisible()) {
        removeLoader();
      }
      observer.disconnect();
    }, 12000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", watchCards);
  } else {
    watchCards();
  }
})();
