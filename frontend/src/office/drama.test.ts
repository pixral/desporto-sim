import { describe, expect, it } from "vitest";
import type { StateView } from "../api/types";
import { Drama } from "./drama";

const ev = (id: string, kind: string, who: string, title = "") =>
  ({ id, time: "", kind, title, text: "", importance: 2, tone: "neutral", employee_ids: [who], department_id: null, data: {} });
const bet = (id: string, by: string, influenced: string[] = []) => ({ id, employee_id: by, influenced_by: influenced });

function state(events: unknown[], ticker: unknown[]): StateView {
  return {
    events,
    ticker,
    employees: [{ id: "e1", name: "Ana" }, { id: "e2", name: "Rui" }],
  } as unknown as StateView;
}

describe("drama", () => {
  it("does not replay old news on load, then reacts to new events", () => {
    const d = new Drama();
    d.ingest(state([ev("ev1", "fire", "e1")], []), 0);
    expect(d.shouts).toHaveLength(0);
    d.ingest(state([ev("ev1", "fire", "e1"), ev("ev2", "promotion", "e2"), ev("ev3", "big_win", "e1", "Ana lands X @ 5.0 (+€884)")], []), 10);
    expect(d.shouts.map((s) => s.text).sort()).toEqual(["+€884!", "Promoted!"]);
    expect(d.bursts).toHaveLength(2);
  });

  it("draws a link when a bet followed a colleague, and everything expires", () => {
    const d = new Drama();
    d.ingest(state([], [bet("b1", "e1")]), 0);
    d.ingest(state([], [bet("b1", "e1"), bet("b2", "e1", ["Rui"])]), 5);
    expect(d.links).toEqual([{ from: "e1", to: "e2", born: 5 }]);
    d.expire(60_000);
    expect(d.links).toHaveLength(0);
  });
});
