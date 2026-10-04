// Turns simulation events into visible office moments: speech bubbles, influence lines, confetti.

import type { HistoryEvent, StateView } from "../api/types";

export interface Shout {
  actorId: string;
  text: string;
  color: string;
  born: number;
}

export interface Link {
  from: string;
  to: string;
  born: number;
  kind: "influence" | "clash" | "friends";
}

export interface Burst {
  actorId: string;
  born: number;
  seed: number;
}

export const SHOUT_MS = 4200;
export const LINK_MS = 5200;
export const BURST_MS = 1800;

const GOOD = "#2f7a4b";
const BAD = "#a3333d";
const DRAMA = "#7a4bb0";
const NEUTRAL = "#3d3054";

function shoutFor(e: HistoryEvent): { text: string; color: string } | null {
  switch (e.kind) {
    case "fire":
      return { text: "Fired…", color: BAD };
    case "hire":
      return { text: "First day!", color: GOOD };
    case "promotion":
      return { text: "Promoted!", color: GOOD };
    case "warning":
      return { text: "Under review…", color: BAD };
    case "resignation":
      return { text: "I quit.", color: DRAMA };
    case "refusal":
      return { text: "Not using that.", color: DRAMA };
    case "big_swing":
      return { text: "All in!", color: DRAMA };
    case "strategy_deployed":
      return { text: "New strategy!", color: NEUTRAL };
    case "transfer":
      return { text: "New desk!", color: NEUTRAL };
    case "memo":
      return { text: "Memo for everyone!", color: NEUTRAL };
    case "poach_offer":
      return { text: "A rival wants me…", color: DRAMA };
    case "counter_offer":
      return { text: "Raise to stay!", color: GOOD };
    case "poached":
      return { text: `Off to ${String(e.data.rival ?? "a rival")}!`, color: BAD };
    case "loyal":
      return { text: "Staying loyal.", color: GOOD };
    case "raise_demand":
      return { text: "I deserve more.", color: DRAMA };
    case "raise_granted":
      return { text: "Raise!", color: GOOD };
    case "raise_refused":
      return { text: "Unbelievable…", color: BAD };
    case "book_limit":
      return { text: `${String(e.data.book ?? "They")} limited us!`, color: BAD };
    case "book_limit_lifted":
      return { text: "Limits back up!", color: GOOD };
    case "board_fires_ceo":
      return { text: "…the board?!", color: BAD };
    case "new_ceo":
      return { text: "A new era!", color: DRAMA };
    case "season_awards":
      return { text: "MVP!", color: GOOD };
    case "big_win": {
      const m = e.title.match(/\(\+€([\d,]+)\)/);
      return { text: m ? `+€${m[1]}!` : "Winner!", color: GOOD };
    }
    default:
      return null;
  }
}

export class Drama {
  shouts: Shout[] = [];
  links: Link[] = [];
  bursts: Burst[] = [];
  private seenEvents = new Set<string>();
  private seenBets = new Set<string>();
  private primed = false;

  ingest(state: StateView, now: number): void {
    if (!this.primed) {
      // don't replay old news when the page loads
      state.events.forEach((e) => this.seenEvents.add(e.id));
      state.ticker.forEach((b) => this.seenBets.add(b.id));
      this.primed = true;
      return;
    }
    for (const e of state.events) {
      if (this.seenEvents.has(e.id)) continue;
      this.seenEvents.add(e.id);
      const who = e.employee_ids[0];
      const lines = e.data.lines as Record<string, string> | undefined;
      if (lines) {
        // two-person scenes: each says their own line
        const color = e.kind === "argument" ? BAD : GOOD;
        for (const [id, text] of Object.entries(lines)) {
          this.shouts = this.shouts.filter((x) => x.actorId !== id);
          this.shouts.push({ actorId: id, text, color, born: now });
        }
        if (e.employee_ids.length >= 2) {
          this.links.push({ from: e.employee_ids[0], to: e.employee_ids[1], born: now,
                            kind: e.kind === "argument" ? "clash" : "friends" });
        }
      } else {
        const s = shoutFor(e);
        if (s && who) {
          this.shouts = this.shouts.filter((x) => x.actorId !== who);
          this.shouts.push({ actorId: who, ...s, born: now });
        }
      }
      if (who && ["big_win", "promotion", "season_awards", "counter_offer"].includes(e.kind)) {
        this.bursts.push({ actorId: who, born: now, seed: Math.random() * 1000 });
      }
    }
    const idByName = new Map(state.employees.map((x) => [x.name, x.id]));
    for (const b of state.ticker) {
      if (this.seenBets.has(b.id)) continue;
      this.seenBets.add(b.id);
      for (const name of b.influenced_by) {
        const to = idByName.get(name);
        if (to) this.links.push({ from: b.employee_id, to, born: now, kind: "influence" });
      }
    }
    if (this.seenEvents.size > 2000) this.seenEvents = new Set(state.events.map((e) => e.id));
    if (this.seenBets.size > 2000) this.seenBets = new Set(state.ticker.map((b) => b.id));
  }

  expire(now: number): void {
    this.shouts = this.shouts.filter((s) => now - s.born < SHOUT_MS);
    this.links = this.links.filter((l) => now - l.born < LINK_MS);
    this.bursts = this.bursts.filter((b) => now - b.born < BURST_MS);
  }
}
