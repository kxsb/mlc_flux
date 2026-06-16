import { formatAmount, formatDateTime, escapeHtml } from "./utils.js";

function renderSummary(transactions) {
  const summaryEl = document.getElementById("summary");
  const subtitleEl = document.getElementById("pageSubtitle");

  const count = transactions.length;
  const totalAmount = transactions.reduce((sum, tx) => sum + tx.amount, 0);

  summaryEl.innerHTML = `
    <div class="card">
      <h3>Résumé</h3>
      <p><strong>Transactions affichées :</strong> ${count}</p>
      <p><strong>Montant cumulé :</strong> ${formatAmount(totalAmount)}</p>
    </div>
  `;

  subtitleEl.textContent = `${count} transaction(s) affichée(s)`;
}

function renderTable(transactions) {
  const contentEl = document.getElementById("content");

  if (!transactions.length) {
    contentEl.innerHTML = `
      <div class="card">
        <p>Aucune transaction à afficher.</p>
      </div>
    `;
    return;
  }

  const rows = transactions
    .map(
      (tx) => `
        <tr>
          <td>${escapeHtml(formatDateTime(tx.date))}</td>
          <td>${escapeHtml(tx.transactionNumber)}</td>
          <td>${escapeHtml(tx.from)}</td>
          <td>${escapeHtml(tx.to)}</td>
          <td>${escapeHtml(tx.description)}</td>
          <td>${escapeHtml(formatAmount(tx.amount))}</td>
        </tr>
      `
    )
    .join("");

  contentEl.innerHTML = `
    <div class="card">
      <h3>Transactions</h3>
      <div class="table-wrapper">
        <table class="transactions-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>N°</th>
              <th>De</th>
              <th>Vers</th>
              <th>Description</th>
              <th>Montant</th>
            </tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

export function renderApp(transactions) {
  renderSummary(transactions);
  renderTable(transactions);
}

export function renderLoading() {
  document.getElementById("pageSubtitle").textContent = "Chargement des données...";
  document.getElementById("summary").innerHTML = "";
  document.getElementById("content").innerHTML = `
    <div class="card">
      <p>Chargement…</p>
    </div>
  `;
}

export function renderError(error) {
  console.error(error);

  document.getElementById("pageSubtitle").textContent = "Erreur de chargement";
  document.getElementById("summary").innerHTML = "";
  document.getElementById("content").innerHTML = `
    <div class="card">
      <h3>Erreur</h3>
      <p>Impossible de charger les transactions.</p>
      <p>${escapeHtml(error.message ?? "Erreur inconnue")}</p>
    </div>
  `;
}

export function populateSelect(selectId, values, placeholder = "Tous") {
  const select = document.getElementById(selectId);
  const currentValue = select.value;

  select.innerHTML = `<option value="">${placeholder}</option>`;

  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }

  if (values.includes(currentValue)) {
    select.value = currentValue;
  }
}
