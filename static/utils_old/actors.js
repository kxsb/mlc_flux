export function isPro(value) {
  return /^P\d{4}\b/.test(String(value || "").trim());
}

export function isUser(value) {
  return /^U(?:\d{4}|_[A-Za-z0-9_-]+)\b/.test(String(value || "").trim());
}

export function isConversion(value) {
  return String(value || "").toLowerCase().includes("conversion");
}

export function extractActorCode(value) {
  const text = String(value || "").trim();

  const proMatch = text.match(/P\d{4}/);
  if (proMatch) return proMatch[0];

  const userMatch = text.match(/U(?:\d{4}|_[A-Za-z0-9_-]+)/);
  if (userMatch) return userMatch[0];

  return null;
}