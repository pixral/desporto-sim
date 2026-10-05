import type { CeoAction, ReviewView } from "../api/types";
import { t } from "../i18n";
import { eur, pct } from "./format";

/** Looks up display names for the ids inside an action. */
export interface Namer {
  emp: (id?: string) => string;
  desk: (id?: string) => string;
  cand: (id?: string) => string;
  exp: (id?: string) => string;
  kind: (k?: string) => string;
  facility: (k?: string) => string;
  /** current setting, for "old → new" labels */
  stake: (deskId?: string) => number | null;
  labBudget: number | null;
  marketing: number | null;
}

/** Desk, kind and facility names stay in English here (as the server sends them); describe() translates them. */
export function reviewNamer(r: ReviewView): Namer {
  const by = <T extends { id: string; name: string }>(rows: T[]) => (id?: string) => rows.find((x) => x.id === id)?.name ?? t("someone");
  return {
    emp: by(r.people),
    desk: (id) => r.desks.find((d) => d.id === id)?.name ?? (id && id === r.lab.department_id ? "LAB" : "a desk"),
    cand: by(r.candidates),
    exp: by(r.lab.ready),
    kind: (k) => r.available_department_kinds.find((x) => x.kind === k)?.name ?? "new desk",
    facility: (k) => (r.office.facilities.find((f) => f.key === k)?.name ?? "space").replace(/^The /, ""),
    stake: (id) => r.desks.find((d) => d.id === id)?.stake_limit_pct ?? null,
    labBudget: r.company.lab_budget,
    marketing: r.company.marketing_budget,
  };
}

/** "the Germany Desk" / "the LAB" (Spanish needs the article to agree). `name` is the English desk name. */
export function theDesk(name: string): string {
  return name === "LAB" ? t("the LAB") : t("the {desk}", { desk: t(name) });
}

/** "the Canteen": `name` is the English facility name without its leading "The" (see "Canteen|facility" in i18n/es/people.ts). */
function theFacility(name: string): string {
  return t("the {facility}", { facility: t(`${name}|facility`) });
}

/** Same wording as the backend's `player.describe`, so edited decisions read like the advisor's. */
export function describe(a: CeoAction, n: Namer): string {
  const who = n.emp(a.employee_id);
  const deskName = n.desk(a.department_id);
  const desk = theDesk(deskName);
  const amount = eur(a.amount ?? 0);
  switch (a.type) {
    case "FIRE":
      return t("Fire {who}", { who });
    case "HIRE":
      return t("Hire {name} into {desk}", { name: n.cand(a.candidate_id), desk });
    case "PROMOTE":
      return t("Promote {who}", { who });
    case "WARN":
      return t("Warn {who}", { who });
    case "CLEAR_REVIEW":
      return t("Lift {who}'s review", { who });
    case "TRANSFER_EMPLOYEE":
      return t("Move {who} to {desk}", { who, desk });
    case "GIVE_TIME_OFF":
      return t("Give {who} {n} day(s) off", { who, n: a.value ?? 3 });
    case "TALK":
      return t("Talk with {who}", { who });
    case "TEAM_EVENT":
      return t("Team night out");
    case "SET_STAKE_LIMIT": {
      const now = n.stake(a.department_id);
      const params = { desk: t(deskName), new: pct(a.pct ?? 0) };
      return now === null
        ? t("{desk}: max stake {new} of bankroll", params)
        : t("{desk}: max stake {old} → {new} of bankroll", { ...params, old: pct(now) });
    }
    case "FUND_DEPARTMENT":
      return t("Move {amount} into {desk}", { amount, desk });
    case "WITHDRAW_BANKROLL":
      return t("Withdraw {amount} from {desk}", { amount, desk });
    case "CREATE_DEPARTMENT":
      return t("Open {desk} with {amount}", { desk: theDesk(n.kind(a.department_kind)), amount });
    case "CLOSE_DEPARTMENT":
      return t("Close {desk}", { desk });
    case "SET_LAB_BUDGET":
      return n.labBudget === null
        ? t("LAB budget {new}/month", { new: amount })
        : t("LAB budget {old} → {new}/month", { old: eur(n.labBudget), new: amount });
    case "SET_MARKETING_BUDGET":
      return n.marketing === null
        ? t("Marketing {new}/month", { new: amount })
        : t("Marketing {old} → {new}/month", { old: eur(n.marketing), new: amount });
    case "DEPLOY_STRATEGY":
      return t("Roll out '{strategy}' to {who}", { strategy: n.exp(a.experiment_id), who });
    case "ADJUST_STRATEGY":
      return t("{who}: set {field} to {value}", { who, field: String(a.field), value: String(a.value) });
    case "FREEZE_HIRING":
      return t("Freeze hiring");
    case "UNFREEZE_HIRING":
      return t("Lift the hiring freeze");
    case "CUT_SALARIES":
      return t("Cut every salary by {pct}", { pct: pct(a.pct ?? 0.1, 0) });
    case "TAKE_LOAN":
      return t("Borrow {amount}", { amount });
    case "REPAY_LOAN":
      return t("Repay {amount} of debt", { amount });
    case "SET_LAB_BRIEF":
      return t("LAB brief: {brief}", { brief: briefText(a, n) });
    case "TEST_CANDIDATE":
      return t("LAB: test {name}'s method", { name: n.cand(a.candidate_id) });
    case "SHELVE_STRATEGY":
      return t("Shelve '{strategy}'", { strategy: n.exp(a.experiment_id) });
    case "LEASE_SPACE":
      return t("Lease {facility}", { facility: theFacility(n.facility(a.facility)) });
    case "RELEASE_SPACE":
      return t("Give up {facility}", { facility: theFacility(n.facility(a.facility)) });
  }
}

/** Competition names by code (getters, so they follow the current language). */
export const COMP_NAMES: Record<string, string> = {
  get BL1() {
    return t("Bundesliga");
  },
  get PL() {
    return t("Premier League");
  },
  get LL() {
    return t("La Liga");
  },
  get SA() {
    return t("Serie A");
  },
  get UCL() {
    return t("Champions League");
  },
};
export const BRIEF_MARKETS: Record<string, string> = {
  get home_win() {
    return t("home wins");
  },
  get draw() {
    return t("draws");
  },
  get away_win() {
    return t("away wins");
  },
  get over_2_5() {
    return t("over 2.5 goals");
  },
  get under_2_5() {
    return t("under 2.5 goals");
  },
};

/** What a research brief points the LAB at. `deskName` is the English name of the desk (for "desk" briefs). */
export function briefLabel(kind: string, value: string, deskName: string): string {
  if (kind === "competition") return COMP_NAMES[value] ?? value;
  if (kind === "market") return BRIEF_MARKETS[value] ?? value;
  if (kind === "underdogs") return t("underdogs at longer odds");
  if (kind === "desk") return t("ideas for {desk}", { desk: theDesk(deskName) });
  return t("researchers' own ideas");
}

function briefText(a: CeoAction, n: Namer): string {
  const [kind, value] = (a.field ?? "").split(":");
  return briefLabel(kind, value, kind === "desk" ? n.desk(a.department_id) : "");
}

const KEYS = ["employee_id", "candidate_id", "department_id", "experiment_id", "facility", "department_kind"] as const;
const ONE_PER_REVIEW: CeoAction["type"][] = ["SET_LAB_BRIEF", "SET_LAB_BUDGET", "SET_MARKETING_BUDGET", "CUT_SALARIES"];

/** Two actions are "the same decision" when type and targets match (amounts may differ). */
export function sameDecision(a: CeoAction, b: CeoAction): boolean {
  if (a.type === b.type && ONE_PER_REVIEW.includes(a.type)) return true; // a new choice replaces the old one
  return a.type === b.type && KEYS.every((k) => (a[k] ?? null) === (b[k] ?? null));
}

/** Exactly this decision (same targets and numbers): drives the "already taken" state of buttons. */
export function exactDecision(a: CeoAction, b: CeoAction): boolean {
  return (
    a.type === b.type &&
    KEYS.every((k) => (a[k] ?? null) === (b[k] ?? null)) &&
    (a.field ?? null) === (b.field ?? null) &&
    (a.pct ?? null) === (b.pct ?? null) &&
    (a.amount ?? null) === (b.amount ?? null) &&
    (a.value ?? null) === (b.value ?? null)
  );
}

/** Which numeric field of an action the player can edit before signing off. */
export function editableField(a: CeoAction): { key: "amount" | "pct" | "value"; min: number; max: number; step: number; unit: string } | null {
  switch (a.type) {
    case "SET_STAKE_LIMIT":
      return { key: "pct", min: 0.005, max: 0.1, step: 0.005, unit: "share" };
    case "CUT_SALARIES":
      return { key: "pct", min: 0.05, max: 0.3, step: 0.05, unit: "share" };
    case "GIVE_TIME_OFF":
      return { key: "value", min: 1, max: 7, step: 1, unit: "days" };
    case "SET_LAB_BUDGET":
      return { key: "amount", min: 0, max: 400, step: 10, unit: "€" };
    case "SET_MARKETING_BUDGET":
      return { key: "amount", min: 0, max: 600, step: 10, unit: "€" };
    case "FUND_DEPARTMENT":
    case "WITHDRAW_BANKROLL":
    case "CREATE_DEPARTMENT":
    case "TAKE_LOAN":
    case "REPAY_LOAN":
      return { key: "amount", min: 0, max: 1_000_000, step: 100, unit: "€" };
    default:
      return null;
  }
}

/** Proposal areas (getters, so they follow the current language). */
export const AREA_LABEL: Record<string, string> = {
  get people() {
    return t("People");
  },
  get hiring() {
    return t("Hiring");
  },
  get desks() {
    return t("Desks");
  },
  get money() {
    return t("Money");
  },
  lab: "LAB",
  get office() {
    return t("Office");
  },
};
