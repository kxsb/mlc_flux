function matchesSearch(tx, search) {
  if (!search) return true;

  const haystack = [
    tx.transactionNumber,
    tx.description,
    tx.from,
    tx.to,
    tx.group,
    tx.type,
  ]
    .join(" ")
    .toLowerCase();

  return haystack.includes(search.toLowerCase());
}

function matchesDateRange(tx, dateFrom, dateTo) {
  if (!tx.date) return false;

  if (dateFrom) {
    const start = new Date(`${dateFrom}T00:00:00`);
    if (tx.date < start) return false;
  }

  if (dateTo) {
    const end = new Date(`${dateTo}T23:59:59`);
    if (tx.date > end) return false;
  }

  return true;
}

export function applyFilters(transactions, filters) {
  return transactions.filter((tx) => {
    if (filters.from && tx.from !== filters.from) return false;
    if (filters.to && tx.to !== filters.to) return false;
    if (!matchesSearch(tx, filters.search)) return false;
    if (!matchesDateRange(tx, filters.dateFrom, filters.dateTo)) return false;
    return true;
  });
}

export function getUniqueValues(transactions, key) {
  return [...new Set(transactions.map((tx) => tx[key]).filter(Boolean))].sort(
    (a, b) => a.localeCompare(b, "fr")
  );
}
