export function eur(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const sign = v < 0 ? "-" : "";
  return `${sign}€${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

export function signedEur(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v > 0 ? "+" : v < 0 ? "-" : "±"}€${Math.abs(v).toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

export function pct(v: number | null | undefined, digits = 1, signed = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const s = (v * 100).toFixed(digits);
  return `${signed && v > 0 ? "+" : ""}${s}%`;
}

export function tone(v: number | null | undefined): "pos" | "neg" | "flat" {
  if (!v) return "flat";
  return v > 0 ? "pos" : "neg";
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function shortDate(iso: string): string {
  const d = new Date(iso.length <= 10 ? `${iso}T12:00:00` : iso);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function dayMonth(iso: string): string {
  const d = new Date(iso.length <= 10 ? `${iso}T12:00:00` : iso);
  return `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

export function monthLabel(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return `${MONTHS[m - 1]} ${String(y).slice(2)}`;
}

export const MARKET_LABEL: Record<string, string> = {
  home_win: "Home",
  draw: "Draw",
  away_win: "Away",
  over_2_5: "Over 2.5",
  under_2_5: "Under 2.5",
};

export const STATUS_LABEL: Record<string, string> = {
  thriving: "Thriving",
  stable: "Stable",
  strained: "Strained",
  distress: "Distress",
  bankrupt: "Bankrupt",
};

export const PHASE_LABEL: Record<string, string> = {
  morning: "Morning briefing",
  analysis: "Analysis & betting",
  matches: "Matches live",
  settlement: "Settlement",
};
