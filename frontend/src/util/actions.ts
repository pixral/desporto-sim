import type { CeoAction, ReviewView } from "../api/types";
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

export function reviewNamer(r: ReviewView): Namer {
  const by = <T extends { id: string; name: string }>(rows: T[]) => (id?: string) => rows.find((x) => x.id === id)?.name ?? "someone";
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

/** Same wording as the backend's `player.describe`, so edited decisions read like the advisor's. */
export function describe(a: CeoAction, n: Namer): string {
  const who = n.emp(a.employee_id);
  const desk = n.desk(a.department_id);
  const amount = a.amount ?? 0;
  switch (a.type) {
    case "FIRE":
      return `Fire ${who}`;
    case "HIRE":
      return `Hire ${n.cand(a.candidate_id)} into the ${desk}`;
    case "PROMOTE":
      return `Promote ${who}`;
    case "WARN":
      return `Warn ${who}`;
    case "CLEAR_REVIEW":
      return `Lift ${who}'s review`;
    case "TRANSFER_EMPLOYEE":
      return `Move ${who} to the ${desk}`;
    case "GIVE_TIME_OFF":
      return `Give ${who} ${a.value ?? 3} day(s) off`;
    case "TALK":
      return `Talk with ${who}`;
    case "TEAM_EVENT":
      return "Team night out";
    case "SET_STAKE_LIMIT": {
      const now = n.stake(a.department_id);
      return `${desk}: max stake ${now === null ? "" : `${pct(now)} → `}${pct(a.pct ?? 0)} of bankroll`;
    }
    case "FUND_DEPARTMENT":
      return `Move ${eur(amount)} into the ${desk}`;
    case "WITHDRAW_BANKROLL":
      return `Withdraw ${eur(amount)} from the ${desk}`;
    case "CREATE_DEPARTMENT":
      return `Open the ${n.kind(a.department_kind)} with ${eur(amount)}`;
    case "CLOSE_DEPARTMENT":
      return `Close the ${desk}`;
    case "SET_LAB_BUDGET":
      return `LAB budget ${n.labBudget === null ? "" : `${eur(n.labBudget)} → `}${eur(amount)}/month`;
    case "SET_MARKETING_BUDGET":
      return `Marketing ${n.marketing === null ? "" : `${eur(n.marketing)} → `}${eur(amount)}/month`;
    case "DEPLOY_STRATEGY":
      return `Roll out '${n.exp(a.experiment_id)}' to ${who}`;
    case "ADJUST_STRATEGY":
      return `${who}: set ${a.field} to ${a.value}`;
    case "FREEZE_HIRING":
      return "Freeze hiring";
    case "UNFREEZE_HIRING":
      return "Lift the hiring freeze";
    case "CUT_SALARIES":
      return `Cut every salary by ${pct(a.pct ?? 0.1, 0)}`;
    case "TAKE_LOAN":
      return `Borrow ${eur(amount)}`;
    case "REPAY_LOAN":
      return `Repay ${eur(amount)} of debt`;
    case "SET_LAB_BRIEF":
      return `LAB brief: ${briefText(a, n)}`;
    case "TEST_CANDIDATE":
      return `LAB: test ${n.cand(a.candidate_id)}'s method`;
    case "SHELVE_STRATEGY":
      return `Shelve '${n.exp(a.experiment_id)}'`;
    case "LEASE_SPACE":
      return `Lease the ${n.facility(a.facility)}`;
    case "RELEASE_SPACE":
      return `Give up the ${n.facility(a.facility)}`;
  }
}

export const COMP_NAMES: Record<string, string> = {
  BL1: "Bundesliga",
  PL: "Premier League",
  LL: "La Liga",
  SA: "Serie A",
  UCL: "Champions League",
};
export const BRIEF_MARKETS: Record<string, string> = {
  home_win: "home wins",
  draw: "draws",
  away_win: "away wins",
  over_2_5: "over 2.5 goals",
  under_2_5: "under 2.5 goals",
};

function briefText(a: CeoAction, n: Namer): string {
  const [kind, value] = (a.field ?? "").split(":");
  if (kind === "competition") return COMP_NAMES[value] ?? value;
  if (kind === "market") return BRIEF_MARKETS[value] ?? value;
  if (kind === "underdogs") return "underdogs at longer odds";
  if (kind === "desk") return `ideas for the ${n.desk(a.department_id)}`;
  return "researchers' own ideas";
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

export const AREA_LABEL: Record<string, string> = {
  people: "People",
  hiring: "Hiring",
  desks: "Desks",
  money: "Money",
  lab: "LAB",
  office: "Office",
};
