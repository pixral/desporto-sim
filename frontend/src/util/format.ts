import { currentLang, t } from "../i18n";

/** en: 1,234.5 · es: 1.234,5 (grouping always on, so 4-digit amounts read the same way in both). */
function num(v: number, digits: number): string {
  const s = v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return currentLang() === "es" ? s.replace(/[.,]/g, (c) => (c === "," ? "." : ",")) : s;
}

function money(abs: number, digits: number, sign: string): string {
  return currentLang() === "es" ? `${sign}${num(abs, digits)} €` : `${sign}€${num(abs, digits)}`;
}

export function eur(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return money(Math.abs(v), digits, v < 0 ? "-" : "");
}

export function signedEur(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return money(Math.abs(v), digits, v > 0 ? "+" : v < 0 ? "-" : "±");
}

export function pct(v: number | null | undefined, digits = 1, signed = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const s = num(v * 100, digits);
  return `${signed && v > 0 ? "+" : ""}${s}%`;
}

/** A plain number in the current language's style. */
export function fmtNum(v: number, digits = 0): string {
  return num(v, digits);
}

export function tone(v: number | null | undefined): "pos" | "neg" | "flat" {
  if (!v) return "flat";
  return v > 0 ? "pos" : "neg";
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

function month(i: number): string {
  return currentLang() === "es" ? MESES[i] : MONTHS[i];
}

export function shortDate(iso: string): string {
  const d = new Date(iso.length <= 10 ? `${iso}T12:00:00` : iso);
  return `${d.getDate()} ${month(d.getMonth())} ${d.getFullYear()}`;
}

export function dayMonth(iso: string): string {
  const d = new Date(iso.length <= 10 ? `${iso}T12:00:00` : iso);
  return `${d.getDate()} ${month(d.getMonth())}`;
}

export function monthLabel(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return `${month(m - 1)} ${String(y).slice(2)}`;
}

const WEEKDAYS: Record<string, string> = {
  Monday: "Lunes",
  Tuesday: "Martes",
  Wednesday: "Miércoles",
  Thursday: "Jueves",
  Friday: "Viernes",
  Saturday: "Sábado",
  Sunday: "Domingo",
};

/** The backend sends English weekday names. */
export function weekday(name: string): string {
  return currentLang() === "es" ? (WEEKDAYS[name] ?? name) : name;
}

export const MARKET_LABEL: Record<string, string> = {
  get home_win() {
    return t("Home");
  },
  get draw() {
    return t("Draw");
  },
  get away_win() {
    return t("Away|market");
  },
  get over_2_5() {
    return t("Over 2.5");
  },
  get under_2_5() {
    return t("Under 2.5");
  },
};

export const STATUS_LABEL: Record<string, string> = {
  get thriving() {
    return t("Thriving");
  },
  get stable() {
    return t("Stable");
  },
  get strained() {
    return t("Strained");
  },
  get distress() {
    return t("Distress");
  },
  get bankrupt() {
    return t("Bankrupt");
  },
};

export const PHASE_LABEL: Record<string, string> = {
  get morning() {
    return t("Morning briefing");
  },
  get analysis() {
    return t("Analysis & betting");
  },
  get matches() {
    return t("Matches live");
  },
  get settlement() {
    return t("Settlement");
  },
};
