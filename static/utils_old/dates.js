export function parseFrDate(str) {
  if (!str) return new Date("invalid");

  const value = String(str).trim();

  // YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return new Date(`${value}T00:00:00`);
  }

  // DD-MM-YYYY
  if (/^\d{2}-\d{2}-\d{4}$/.test(value)) {
    const [d, m, y] = value.split("-");
    return new Date(`${y}-${m}-${d}T00:00:00`);
  }

  // DD/MM/YYYY
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(value)) {
    const [d, m, y] = value.split("/");
    return new Date(`${y}-${m}-${d}T00:00:00`);
  }

  const parsed = new Date(value);
  return parsed;
}

export function uniqueSortedDates(rows) {
  const dates = [...new Set((rows || []).map(r => r.Date).filter(Boolean))];
  dates.sort((a, b) => parseFrDate(a) - parseFrDate(b));
  return dates;
}

export function getPeriodBounds(rows) {
  const dates = uniqueSortedDates(rows);
  if (!dates.length) {
    return {
      dates: [],
      minDate: null,
      maxDate: null
    };
  }

  return {
    dates,
    minDate: dates[0],
    maxDate: dates[dates.length - 1]
  };
}

export function getFilteredTransactionsByPeriod(rows, periodState) {
  const safeRows = rows || [];
  const { dates } = getPeriodBounds(safeRows);

  if (!dates.length) return safeRows;

  const minIndex = Math.max(0, periodState?.minIndex ?? 0);
  const maxIndex = Math.min(dates.length - 1, periodState?.maxIndex ?? dates.length - 1);

  const minDate = dates[Math.min(minIndex, maxIndex)];
  const maxDate = dates[Math.max(minIndex, maxIndex)];

  return safeRows.filter(row => {
    const d = parseFrDate(row.Date);
    return d >= parseFrDate(minDate) && d <= parseFrDate(maxDate);
  });
}