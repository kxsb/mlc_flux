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

  const rows = Array.from(rowsContainer.querySelectorAll("tr[data-status]"));
  let activeStatus = null;

  function normalize(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function applyFilters() {
    const query = normalize(searchInput.value);
    let visibleCount = 0;

    rows.forEach(row => {
      const statusMatches = !activeStatus || row.dataset.status === activeStatus;
      const haystack = normalize(row.dataset.search);
      const searchMatches = !query || haystack.includes(query);
      const visible = statusMatches && searchMatches;

      row.hidden = !visible;
      if (visible) {
        visibleCount += 1;
      }
    });

    emptyState.hidden = visibleCount !== 0;
  }

  searchInput.addEventListener("input", applyFilters);

  statusButtons.forEach(button => {
    button.addEventListener("click", () => {
      const requested = button.dataset.filterStatus || null;
      activeStatus = activeStatus === requested ? null : requested;

      statusButtons.forEach(other => {
        other.setAttribute(
          "aria-pressed",
          String(other.dataset.filterStatus === activeStatus)
        );
      });

      applyFilters();
    });
  });
})();
