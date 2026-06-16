import { fetchTransactions } from "./api.js";
import { state } from "./state.js";
import { normalizeTransactions } from "./normalize.js";
import { applyFilters, getUniqueValues } from "./filters.js";
import {
  renderApp,
  renderLoading,
  renderError,
  populateSelect,
} from "./render.js";

function syncFiltersFromDom() {
  state.filters.search = document.getElementById("searchInput").value.trim();
  state.filters.from = document.getElementById("fromFilter").value;
  state.filters.to = document.getElementById("toFilter").value;
  state.filters.dateFrom = document.getElementById("dateFrom").value;
  state.filters.dateTo = document.getElementById("dateTo").value;
}

function syncFiltersToDom() {
  document.getElementById("searchInput").value = state.filters.search;
  document.getElementById("fromFilter").value = state.filters.from;
  document.getElementById("toFilter").value = state.filters.to;
  document.getElementById("dateFrom").value = state.filters.dateFrom;
  document.getElementById("dateTo").value = state.filters.dateTo;
}

function refreshSelectOptions() {
  const fromValues = getUniqueValues(state.transactions, "from");
  const toValues = getUniqueValues(state.transactions, "to");

  populateSelect("fromFilter", fromValues, "Tous");
  populateSelect("toFilter", toValues, "Tous");

  syncFiltersToDom();
}

function refreshView() {
  syncFiltersFromDom();
  state.filteredTransactions = applyFilters(state.transactions, state.filters);
  renderApp(state.filteredTransactions);
}

async function loadTransactions() {
  renderLoading();

  const rawTransactions = await fetchTransactions();
  const normalizedTransactions = normalizeTransactions(rawTransactions);

  normalizedTransactions.sort((a, b) => {
    if (!a.date && !b.date) return 0;
    if (!a.date) return 1;
    if (!b.date) return -1;
    return b.date - a.date;
  });

  state.transactions = normalizedTransactions;

  refreshSelectOptions();
  refreshView();
}

function resetFilters() {
  state.filters = {
    search: "",
    from: "",
    to: "",
    dateFrom: "",
    dateTo: "",
  };

  syncFiltersToDom();
  refreshView();
}

function bindEvents() {
  document.getElementById("reloadButton").addEventListener("click", async () => {
    try {
      await loadTransactions();
    } catch (error) {
      renderError(error);
    }
  });

  document.getElementById("searchInput").addEventListener("input", refreshView);
  document.getElementById("fromFilter").addEventListener("change", refreshView);
  document.getElementById("toFilter").addEventListener("change", refreshView);
  document.getElementById("dateFrom").addEventListener("change", refreshView);
  document.getElementById("dateTo").addEventListener("change", refreshView);

  document
    .getElementById("resetFiltersButton")
    .addEventListener("click", resetFilters);

  const themeToggleBtn = document.getElementById("themeToggleBtn");
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", () => {
      document.body.classList.toggle("dark-mode");
    });
  }
}

async function init() {
  bindEvents();

  try {
    await loadTransactions();
  } catch (error) {
    renderError(error);
  }
}

init();
