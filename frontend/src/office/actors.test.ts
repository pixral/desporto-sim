import { describe, expect, it } from "vitest";
import type { EmployeeCard, StateView } from "../api/types";
import { ActorWorld } from "./actors";
import { buildLayout } from "./layout";

function emp(id: string, status: string, department_id: string | null, desk_index = 0, role: EmployeeCard["role"] = "tipster"): EmployeeCard {
  return {
    id, name: id, role, title: "Tipster", level: 1, specialty: "form", specialty_label: "Form analyst",
    department_id, desk_index, active: true, status, task: "", thought: "", mood: "calm", stress: 0.2,
    confidence: 0.5, reputation: 50, risk_tolerance: 0.4, day_profit: 0, month_profit: 0, profit: 0, roi: 0,
    bets: 0, streak: 0, under_review: false,
    appearance: { skin: 0, hair_style: 0, hair_color: 0, shirt: 0, pants: 0, accessory: 0 },
    pnl_flash_seq: 0, tenure_days: 10, left: null,
  };
}

function state(employees: EmployeeCard[], phaseSeconds = 6, phase = "analysis"): StateView {
  return {
    clock: { phase, date: "2026-08-14", time: phase === "settlement" ? "23:30" : "11:00" },
    run: { ended: false },
    departments: [
      { id: "d1", name: "Germany Desk", kind: "germany", color: "#d8232a", room_slot: 0, active: true },
      { id: "d2", name: "Premier League Desk", kind: "england", color: "#6a2c91", room_slot: 1, active: true },
    ],
    employees,
    runner: { running: true, speed: "1x", speeds: [], phase_seconds: phaseSeconds },
  } as unknown as StateView;
}

function run(world: ActorWorld, s: StateView, seconds: number) {
  for (let t = 0; t < seconds; t += 0.05) world.update(s, 0.05, t * 1000);
}

describe("actors", () => {
  it("working tipsters walk from the lounge to their own desk within a phase", () => {
    const world = new ActorWorld(buildLayout(new Set([0, 1])));
    const idle = state([emp("a", "idle", "d1", 0), emp("b", "idle", "d2", 3)]);
    run(world, idle, 1);
    const a0 = world.actors.get("a")!;
    expect(a0.targetKey.startsWith("sofa") || a0.targetKey.startsWith("bean") || a0.targetKey.length > 0).toBe(true);
    const working = state([emp("a", "working", "d1", 0), emp("b", "watching", "d2", 3)]);
    run(world, working, 4.5);
    const a = world.actors.get("a")!;
    const b = world.actors.get("b")!;
    expect(a.targetKey).toBe("desk0-0");
    expect(b.targetKey).toBe("desk1-3");
    expect(a.moving).toBe(false);
    expect(b.moving).toBe(false);
    expect(a.spot?.key).toBe("desk0-0");
  });

  it("people hurry at high speeds and appear instantly at max speed", () => {
    const world = new ActorWorld(buildLayout(new Set([0, 1])));
    run(world, state([emp("a", "idle", "d1")], 0.35), 0.5);
    run(world, state([emp("a", "working", "d1")], 0.35), 0.3);
    expect(world.actors.get("a")!.spot?.key).toBe("desk0-0");
    run(world, state([emp("a", "idle", "d1")], 0), 0.06);
    expect(world.actors.get("a")!.moving).toBe(false);
  });

  it("the CEO meets one or two people in the office and a group in the meeting room", () => {
    const world = new ActorWorld(buildLayout(new Set([0])));
    const ceo = (status: string) => emp("c", status, null, 0, "ceo");
    run(world, state([ceo("ceo_office")]), 0.2);
    expect(world.actors.get("c")!.targetKey).toBe("ceo");
    run(world, state([ceo("meeting")]), 0.2); // nobody to meet: stays at the desk
    expect(world.actors.get("c")!.targetKey).toBe("ceo");
    run(world, state([ceo("meeting"), emp("a", "meeting", "d1")]), 0.2);
    expect(world.actors.get("c")!.targetKey).toBe("ceo");
    expect(world.actors.get("a")!.targetKey).toBe("ceo-v0");
    const group = ["a", "b", "d"].map((id) => emp(id, "meeting", "d1"));
    run(world, state([ceo("meeting"), ...group]), 0.2);
    expect(world.actors.get("c")!.targetKey).toBe("meet-head");
    expect(world.actors.get("a")!.targetKey.startsWith("meet-")).toBe(true);
  });

  it("everyone goes home at night and walks back in the next morning", () => {
    const world = new ActorWorld(buildLayout(new Set([0])));
    run(world, state([emp("a", "working", "d1"), emp("c", "ceo_office", null, 0, "ceo")]), 3);
    run(world, state([emp("a", "celebrating", "d1"), emp("c", "ceo_office", null, 0, "ceo")], 6, "settlement"), 8);
    const a = world.actors.get("a")!;
    expect(a.targetKey).toBe("home");
    expect(a.away).toBe(true);
    expect(a.alpha).toBe(0);
    expect(world.actors.get("c")!.away).toBe(true);
    run(world, state([emp("a", "idle", "d1"), emp("c", "ceo_office", null, 0, "ceo")], 6, "morning"), 0.05);
    expect(a.away).toBe(false);
    expect(Math.abs(a.x - 34.5) + Math.abs(a.y - 24.5)).toBeLessThan(1.5); // came in through the front door
    run(world, state([emp("a", "idle", "d1"), emp("c", "ceo_office", null, 0, "ceo")], 6, "morning"), 6);
    expect(a.alpha).toBe(1);
    expect(a.moving).toBe(false);
  });

  it("people off sick or on leave stay home", () => {
    const world = new ActorWorld(buildLayout(new Set([0])));
    run(world, state([emp("a", "away", "d1"), emp("b", "idle", "d1")]), 3);
    expect(world.actors.get("a")!.away).toBe(true);
    expect(world.actors.get("a")!.alpha).toBe(0);
    expect(world.actors.get("b")!.away).toBe(false);
  });

  it("fired people walk to the exit and fade out", () => {
    const world = new ActorWorld(buildLayout(new Set([0])));
    run(world, state([emp("a", "working", "d1")]), 3);
    const leaver = { ...emp("a", "leaving", "d1"), active: false };
    run(world, state([leaver]), 8);
    const a = world.actors.get("a")!;
    expect(a.targetKey).toBe("entrance");
    expect(a.gone).toBe(true);
  });
});
