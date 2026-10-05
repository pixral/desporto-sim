import { describe as suite, expect, it } from "vitest";
import type { CeoAction } from "../api/types";
import { describe, editableField, exactDecision, type Namer, sameDecision } from "./actions";

const namer: Namer = {
  emp: (id) => ({ e2: "Cosmo", e3: "Bastian" })[id ?? ""] ?? "someone",
  desk: (id) => ({ d1: "Germany Desk" })[id ?? ""] ?? "a desk",
  cand: () => "Chiara",
  exp: () => "PL Sniper v2",
  kind: () => "Spain Desk",
  facility: (k) => (k === "canteen" ? "Canteen" : "space"),
  stake: (id) => (id === "d1" ? 0.05 : null),
  labBudget: 60,
  marketing: null,
};

suite("decision labels", () => {
  it("reads like the advisor's", () => {
    expect(describe({ type: "FIRE", employee_id: "e2" }, namer)).toBe("Fire Cosmo");
    expect(describe({ type: "HIRE", candidate_id: "c1", department_id: "d1" }, namer)).toBe("Hire Chiara into the Germany Desk");
    expect(describe({ type: "LEASE_SPACE", facility: "canteen" }, namer)).toBe("Lease the Canteen");
    expect(describe({ type: "SET_LAB_BRIEF", field: "competition:PL" }, namer)).toBe("LAB brief: Premier League");
    expect(describe({ type: "SET_LAB_BRIEF", field: "desk", department_id: "d1" }, namer)).toBe("LAB brief: ideas for the Germany Desk");
  });

  it("shows the current value next to the new one", () => {
    expect(describe({ type: "SET_STAKE_LIMIT", department_id: "d1", pct: 0.03 }, namer)).toBe("Germany Desk: max stake 5.0% → 3.0% of bankroll");
    expect(describe({ type: "SET_LAB_BUDGET", amount: 110 }, namer)).toBe("LAB budget €60 → €110/month");
    expect(describe({ type: "SET_MARKETING_BUDGET", amount: 90 }, namer)).toBe("Marketing €90/month");
  });
});

suite("matching decisions", () => {
  const talkA: CeoAction = { type: "TALK", employee_id: "e2" };
  const talkB: CeoAction = { type: "TALK", employee_id: "e3" };
  it("treats different targets as different decisions", () => {
    expect(sameDecision(talkA, talkB)).toBe(false);
    expect(sameDecision(talkA, { ...talkA, reason: "x" })).toBe(true);
  });

  it("replaces a desk's stake limit but knows the numbers changed", () => {
    const a: CeoAction = { type: "SET_STAKE_LIMIT", department_id: "d1", pct: 0.03 };
    const b: CeoAction = { type: "SET_STAKE_LIMIT", department_id: "d1", pct: 0.04 };
    expect(sameDecision(a, b)).toBe(true);
    expect(exactDecision(a, b)).toBe(false);
  });

  it("keeps one research brief and one budget per review", () => {
    expect(sameDecision({ type: "SET_LAB_BRIEF", field: "market:draw" }, { type: "SET_LAB_BRIEF", field: "underdogs" })).toBe(true);
    expect(exactDecision({ type: "SET_LAB_BRIEF", field: "market:draw" }, { type: "SET_LAB_BRIEF", field: "underdogs" })).toBe(false);
    expect(sameDecision({ type: "SET_LAB_BUDGET", amount: 80 }, { type: "SET_LAB_BUDGET", amount: 120 })).toBe(true);
  });

  it("knows which numbers can be edited before sign-off", () => {
    expect(editableField({ type: "SET_STAKE_LIMIT", department_id: "d1", pct: 0.03 })?.key).toBe("pct");
    expect(editableField({ type: "GIVE_TIME_OFF", employee_id: "e2", value: 3 })?.max).toBe(7);
    expect(editableField({ type: "FIRE", employee_id: "e2" })).toBeNull();
  });
});
