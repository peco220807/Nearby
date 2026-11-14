// Деньги — только целые центы. Разбираем строку без float.
export function parseCents(input) {
  const s = String(input).trim().replace(",", ".");
  const m = /^(\d+)(?:\.(\d{1,2}))?$/.exec(s);
  if (!m) return null;
  return Number(m[1]) * 100 + Number((m[2] || "").padEnd(2, "0"));
}

export function formatCents(cents) {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}
