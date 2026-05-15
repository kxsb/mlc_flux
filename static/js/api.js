export async function fetchTransactions() {
  const response = await fetch("/api/v2/transactions", {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Erreur API: ${response.status}`);
  }

  const data = await response.json();

  if (Array.isArray(data)) {
    return data;
  }

  if (data && Array.isArray(data.transactions)) {
    return data.transactions;
  }

  return [];
}
