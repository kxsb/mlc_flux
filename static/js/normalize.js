function parseAmount(value) {
  if (value === null || value === undefined || value === "") {
    return 0;
  }

  const amount = Number.parseFloat(value);
  return Number.isFinite(amount) ? amount : 0;
}

function parseDate(value) {
  if (!value) return null;

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function normalizeTransactions(rows) {
  return rows.map((tx, index) => {
    const date = parseDate(tx.date);

    return {
      id: tx.id ?? `tx-${index}`,
      transactionNumber: tx.transactionNumber ?? "",
      dateRaw: tx.date ?? "",
      date,
      amount: parseAmount(tx.amount),
      description: String(tx.description ?? "").trim(),
      from: String(tx.from ?? "").trim(),
      to: String(tx.to ?? "").trim(),
      group: String(tx.group ?? "").trim(),
      type: String(tx.type ?? "").trim(),
    };
  });
}
