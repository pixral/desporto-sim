import { describe, expect, it } from "vitest";
import type { StateView } from "../api/types";
import { fortuneFrom, VACANT } from "./fortune";

function state(over: { day?: number; value?: number; peak?: number; status?: string; ended?: boolean; end?: StateView["run"]["end_kind"]; leased?: string[] } = {}): StateView {
  return {
    run: { starting_capital: 20000, ended: over.ended ?? false, end_kind: over.end ?? null },
    clock: { day_index: over.day ?? 200 },
    kpis: { valuation: over.value ?? 20000, peak_value: over.peak ?? over.value ?? 20000, status: over.status ?? "stable" },
    office: { leased: Object.fromEntries((over.leased ?? []).map((k) => [k, "2026-09-01"])) },
    employees: [{ active: true }, { active: true }, { active: false }],
  } as unknown as StateView;
}

describe("the title-screen building", () => {
  it("is an empty building without a company", () => {
    expect(fortuneFrom(null)).toEqual(VACANT);
  });

  it("starts as a small first office in the first month", () => {
    expect(fortuneFrom(state({ day: 10, value: 90000 })).tier).toBe(0);
  });

  it("grows with company value", () => {
    expect(fortuneFrom(state({ value: 21000 })).tier).toBe(1);
    expect(fortuneFrom(state({ value: 26000 })).tier).toBe(2);
    expect(fortuneFrom(state({ value: 40000 })).tier).toBe(3);
    expect(fortuneFrom(state({ value: 70000 })).tier).toBe(4);
  });

  it("dims and empties when things go badly", () => {
    expect(fortuneFrom(state({ value: 21000 })).mood).toBe("bright");
    expect(fortuneFrom(state({ value: 15000 })).mood).toBe("dim");
    expect(fortuneFrom(state({ value: 21000, status: "strained" })).mood).toBe("dim");
    expect(fortuneFrom(state({ value: 9000 })).mood).toBe("dark");
    expect(fortuneFrom(state({ value: 21000, status: "distress" })).mood).toBe("dark");
  });

  it("burns the building it had grown into when the company goes bankrupt", () => {
    const f = fortuneFrom(state({ value: 0, peak: 45000, ended: true, end: "bankrupt" }));
    expect(f).toMatchObject({ mood: "ruin", ending: "bankrupt", tier: 3, staff: 0 });
  });

  it("shows the player's ending and the leased spaces", () => {
    expect(fortuneFrom(state({ value: 30000, ended: true, end: "retired" }))).toMatchObject({ ending: "retired", mood: "bright" });
    expect(fortuneFrom(state({ value: 8000, ended: true, end: "fired" }))).toMatchObject({ ending: "fired" });
    const f = fortuneFrom(state({ leased: ["studio", "desk_wing"] }));
    expect([f.studio, f.deskWing, f.canteen, f.staff]).toEqual([true, true, false, 2]);
  });
});
