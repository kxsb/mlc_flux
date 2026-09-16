(() => {
  const rowsContainer = document.getElementById("dataControlRows");
  const searchInput = document.getElementById("dataControlSearch");
  const emptyState = document.getElementById("dataControlEmpty");

  const statusButtons = Array.from(
    document.querySelectorAll("[data-filter-status]")
  );

  if (!rowsContainer || !searchInput || !emptyState) {
    return;
  }

  const rows = Array.from(
    rowsContainer.querySelectorAll("tr[data-status]")
  );

  const rawButtons = Array.from(
    document.querySelectorAll("[data-raw-key]")
  );

  let activeStatus = null;

  function normalize(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function getPreviewRow(key) {
    return Array.from(
      rowsContainer.querySelectorAll(".raw-preview-row")
    ).find(row => row.dataset.rawFor === key) || null;
  }

  function applyFilters() {
    const query = normalize(searchInput.value);
    let visibleCount = 0;

    rows.forEach(row => {
      const statusMatches =
        !activeStatus ||
        row.dataset.status === activeStatus;

      const haystack = normalize(row.dataset.search);
      const searchMatches =
        !query ||
        haystack.includes(query);

      const visible =
        statusMatches &&
        searchMatches;

      row.hidden = !visible;

      if (!visible) {
        const key = row.dataset.key;
        const previewRow = getPreviewRow(key);

        if (previewRow) {
          previewRow.hidden = true;
        }

        const button = document.querySelector(
          `[data-raw-key="${CSS.escape(key)}"]`
        );

        if (button) {
          button.setAttribute(
            "aria-expanded",
            "false"
          );
        }
      }

      if (visible) {
        visibleCount += 1;
      }
    });

    emptyState.hidden = visibleCount !== 0;
  }

  searchInput.addEventListener(
    "input",
    applyFilters
  );

  statusButtons.forEach(button => {
    button.addEventListener("click", () => {
      const requested =
        button.dataset.filterStatus || null;

      activeStatus =
        activeStatus === requested
          ? null
          : requested;

      statusButtons.forEach(other => {
        other.setAttribute(
          "aria-pressed",
          String(
            other.dataset.filterStatus ===
            activeStatus
          )
        );
      });

      applyFilters();
    });
  });

  function stringifyValue(value) {
    if (value === null || value === undefined) {
      return "NULL";
    }

    if (typeof value === "object") {
      return JSON.stringify(value);
    }

    return String(value);
  }

  function buildRawTable(target, payload) {
    target.replaceChildren();

    const meta = document.createElement("div");
    meta.className = "raw-preview-meta";

    const source = document.createElement("div");
    source.className = "raw-preview-source";

    const sourceKind = document.createElement("strong");
    sourceKind.textContent =
      payload.source_kind ||
      "PostgreSQL";

    const sourceName = document.createElement("code");
    sourceName.textContent =
      payload.source ||
      "source inconnue";

    source.append(
      sourceKind,
      document.createTextNode(" · "),
      sourceName
    );

    const count = document.createElement("div");
    count.className = "raw-preview-count";
    count.textContent =
      `${payload.rows.length} ligne(s) affichée(s)` +
      ` · limite ${payload.limit}`;

    meta.append(source, count);
    target.append(meta);

    if (!payload.rows.length) {
      const empty = document.createElement("div");
      empty.className = "raw-preview-empty";
      empty.textContent =
        "La requête PostgreSQL n’a retourné aucune ligne.";
      target.append(empty);
      return;
    }

    const scroll = document.createElement("div");
    scroll.className = "raw-preview-scroll";

    const table = document.createElement("table");
    table.className = "raw-data-table";

    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");

    payload.columns.forEach(column => {
      const th = document.createElement("th");
      th.textContent = column;
      headRow.append(th);
    });

    thead.append(headRow);
    table.append(thead);

    const tbody = document.createElement("tbody");

    payload.rows.forEach(row => {
      const tr = document.createElement("tr");

      payload.columns.forEach(column => {
        const td = document.createElement("td");
        const value = row[column];

        td.textContent = stringifyValue(value);

        if (value === null || value === undefined) {
          td.classList.add("raw-null");
        }

        tr.append(td);
      });

      tbody.append(tr);
    });

    table.append(tbody);
    scroll.append(table);
    target.append(scroll);
  }

  async function loadRawData(
    key,
    target
  ) {
    target.replaceChildren();

    const loading = document.createElement("div");
    loading.className = "raw-preview-loading";
    loading.textContent =
      "Lecture PostgreSQL en cours…";

    target.append(loading);

    const response = await fetch(
      `/api/dev/data-control/raw/${encodeURIComponent(key)}`,
      {
        headers: {
          Accept: "application/json"
        }
      }
    );

    const contentType =
      response.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) {
      throw new Error(
        "La session semble expirée ou la réponse n’est pas JSON."
      );
    }

    const payload = await response.json();

    if (!response.ok || !payload.available) {
      throw new Error(
        payload.error ||
        `Erreur HTTP ${response.status}`
      );
    }

    buildRawTable(target, payload);
    target.dataset.loaded = "true";
  }

  rawButtons.forEach(button => {
    button.addEventListener("click", async () => {
      const key = button.dataset.rawKey;
      const previewRow = getPreviewRow(key);

      if (!previewRow) {
        return;
      }

      const target = previewRow.querySelector(
        "[data-raw-preview]"
      );

      if (!target) {
        return;
      }

      const isOpen =
        button.getAttribute("aria-expanded") ===
        "true";

      if (isOpen) {
        button.setAttribute(
          "aria-expanded",
          "false"
        );

        button.textContent =
          "▸ Voir les données brutes PostgreSQL";

        previewRow.hidden = true;
        return;
      }

      button.setAttribute(
        "aria-expanded",
        "true"
      );

      button.textContent =
        "▾ Masquer les données brutes PostgreSQL";

      previewRow.hidden = false;

      if (target.dataset.loaded === "true") {
        return;
      }

      try {
        await loadRawData(
          key,
          target
        );
      } catch (error) {
        target.replaceChildren();

        const errorBox =
          document.createElement("div");

        errorBox.className =
          "raw-preview-error";

        errorBox.textContent =
          error instanceof Error
            ? error.message
            : "Lecture PostgreSQL impossible.";

        target.append(errorBox);
      }
    });
  });
})();
