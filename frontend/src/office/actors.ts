// Client-side "body" of each employee: where they should be (from their status) and how they get there.

import type { EmployeeCard, StateView } from "../api/types";
import type { Pt } from "./iso";
import type { Face, Layout, Spot } from "./layout";
import { findPath } from "./pathfind";
import { lookFor, type Look } from "./sprites";

export interface Floater {
  text: string;
  color: string;
  born: number;
}

export interface Actor {
  id: string;
  emp: EmployeeCard;
  x: number;
  y: number;
  path: Pt[];
  spot: Spot | null;
  targetKey: string;
  face: Face;
  flip: boolean;
  moving: boolean;
  walkClock: number;
  alpha: number;
  leaving: boolean;
  gone: boolean;
  lastFlash: number;
  floaters: Floater[];
  seed: number;
  look: Look;
  lookKey: string;
  celebrateUntil: number;
  speed: number; // tiles per second for the current walk
}

const WORK_STATUSES = new Set(["analyzing", "working", "watching", "celebrating", "frustrated", "stressed", "arriving"]);

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

const WALK_SPEED = 3; // tiles per second when there is time to stroll

export class ActorWorld {
  actors = new Map<string, Actor>();
  private initialized = false;
  private lastStateRef: StateView | null = null;
  private assignments = new Map<string, Spot>();

  constructor(public layout: Layout) {}

  setLayout(layout: Layout): void {
    this.layout = layout;
    for (const a of this.actors.values()) {
      a.targetKey = "";
      a.path = [];
    }
  }

  /** Recompute who goes where when a new snapshot arrives. */
  private assign(state: StateView): void {
    const L = this.layout;
    const deptById = new Map(state.departments.map((d) => [d.id, d]));
    const out = new Map<string, Spot>();
    const emps = [...state.employees].sort((a, b) => a.id.localeCompare(b.id));
    const meeting = emps.filter((e) => e.active && e.status === "meeting" && e.role !== "ceo");
    meeting.forEach((e, i) => out.set(e.id, L.meetingSeats[i % L.meetingSeats.length]));
    const researchers = emps.filter((e) => e.role === "researcher" && e.active);
    const idle: EmployeeCard[] = [];
    const bucket = Math.floor(Date.now() / 12000);
    for (const e of emps) {
      if (out.has(e.id)) continue;
      if (!e.active || e.status === "leaving") {
        out.set(e.id, L.entrance);
        continue;
      }
      if (e.role === "ceo") {
        out.set(e.id, e.status === "meeting" ? L.meetingHead : L.ceoSeat);
        continue;
      }
      if (e.role === "researcher") {
        const i = researchers.findIndex((r) => r.id === e.id);
        if (e.status === "researching") {
          const atBoard = e.task.startsWith("Designing") || (hash(e.id) + bucket) % 3 === 0;
          out.set(e.id, atBoard ? L.labBoards[i % L.labBoards.length] : L.labDesks[i % L.labDesks.length]);
        } else {
          idle.push(e);
        }
        continue;
      }
      const dept = e.department_id ? deptById.get(e.department_id) : undefined;
      const desk = dept && L.activeSlots.has(dept.room_slot) ? L.deskSeats[dept.room_slot][e.desk_index % 5] : null;
      if (desk && WORK_STATUSES.has(e.status)) out.set(e.id, desk);
      else idle.push(e);
    }
    // idle people drift to the Bench, overflow into corridors; stable per person
    const pool = [...L.benchSpots, ...L.corridorSpots];
    const used = new Set<string>();
    for (const e of idle) {
      let k = hash(e.id) % L.benchSpots.length;
      let tries = 0;
      while (used.has(pool[k].key) && tries < pool.length) {
        k = (k + 1) % pool.length;
        tries++;
      }
      used.add(pool[k].key);
      out.set(e.id, pool[k]);
    }
    this.assignments = out;
  }

  update(state: StateView, dt: number, now: number): void {
    if (state !== this.lastStateRef) {
      this.assign(state);
      this.lastStateRef = state;
    }
    // Walks must finish within the current phase, so at high simulation speeds people hurry
    // (and at 64x/max they simply appear where they need to be).
    const phase = state.runner.running ? state.runner.phase_seconds ?? 1.5 : 6;
    const deptColor = new Map(state.departments.map((d) => [d.id, d.color]));
    const seen = new Set<string>();
    for (const emp of state.employees) {
      seen.add(emp.id);
      let a = this.actors.get(emp.id);
      const target = this.assignments.get(emp.id) ?? this.layout.entrance;
      const color = emp.role === "researcher" ? "#0e9aa7" : deptColor.get(emp.department_id ?? "") ?? "#8a7f96";
      if (!a) {
        const spawnAtDoor = this.initialized && emp.active;
        const start = spawnAtDoor ? this.layout.entrance : target;
        const look = lookFor(emp.appearance, color, emp.role);
        a = {
          id: emp.id, emp, x: start.x, y: start.y, path: [], spot: spawnAtDoor ? null : target,
          targetKey: spawnAtDoor ? "" : target.key, face: target.face, flip: target.flip, moving: false,
          walkClock: 0, alpha: spawnAtDoor ? 0 : 1, leaving: false, gone: false, lastFlash: emp.pnl_flash_seq,
          floaters: [], seed: hash(emp.id) % 1000, look, lookKey: JSON.stringify(look), celebrateUntil: 0,
          speed: WALK_SPEED,
        };
        this.actors.set(emp.id, a);
      }
      a.emp = emp;
      const look = lookFor(emp.appearance, color, emp.role);
      const lk = JSON.stringify(look);
      if (lk !== a.lookKey) {
        a.look = look;
        a.lookKey = lk;
      }
      if (emp.pnl_flash_seq !== a.lastFlash) {
        a.lastFlash = emp.pnl_flash_seq;
        if (emp.day_profit) {
          const pos = emp.day_profit > 0;
          a.floaters.push({
            text: `${pos ? "+" : "-"}€${Math.abs(emp.day_profit).toFixed(2)}`,
            color: pos ? "#7cf0a0" : "#ff7a7a",
            born: now,
          });
          if (pos) a.celebrateUntil = now + 2200;
        }
      }
      a.leaving = !emp.active || emp.status === "leaving";
      if (target.key !== a.targetKey) {
        a.targetKey = target.key;
        a.spot = null;
        const path = findPath(this.layout, { x: a.x, y: a.y }, target);
        if (path === null || phase < 0.1) {
          a.x = target.x;
          a.y = target.y;
          a.path = [];
          a.spot = target;
        } else {
          a.path = [...path.slice(0, -1), { x: target.x, y: target.y }];
          if (path.length === 0) a.path = [{ x: target.x, y: target.y }];
          a.speed = Math.max(WALK_SPEED, (a.path.length + 1) / Math.max(0.05, phase * 0.7));
        }
      }
      this.move(a, a.speed * dt, target);
      if (a.alpha < 1 && !a.leaving) a.alpha = Math.min(1, a.alpha + dt * 2);
      if (a.leaving && !a.moving && a.spot?.key === "entrance") {
        a.alpha -= dt * 1.5;
        if (a.alpha <= 0) a.gone = true;
      }
      a.floaters = a.floaters.filter((f) => now - f.born < 2600);
    }
    for (const [id, a] of this.actors) {
      if (!seen.has(id)) {
        a.alpha -= dt * 2;
        if (a.alpha <= 0) this.actors.delete(id);
      } else if (a.gone) {
        a.alpha = 0;
      }
    }
    this.initialized = true;
  }

  private move(a: Actor, step: number, target: Spot): void {
    if (!a.path.length) {
      a.moving = false;
      if (!a.spot && Math.hypot(a.x - target.x, a.y - target.y) < 0.05) a.spot = target;
      if (a.spot) {
        a.face = a.spot.face;
        a.flip = a.spot.flip;
      }
      return;
    }
    a.moving = true;
    let remaining = step;
    while (remaining > 0 && a.path.length) {
      const next = a.path[0];
      const dx = next.x - a.x;
      const dy = next.y - a.y;
      const dist = Math.hypot(dx, dy);
      if (dist > 1e-6) {
        const sx = dx - dy; // screen-space direction
        const sy = dx + dy;
        a.flip = sx < 0;
        a.face = sy < 0 ? "back" : "front";
      }
      if (dist <= remaining) {
        a.x = next.x;
        a.y = next.y;
        a.path.shift();
        remaining -= dist;
      } else {
        a.x += (dx / dist) * remaining;
        a.y += (dy / dist) * remaining;
        remaining = 0;
      }
    }
    a.walkClock += step;
    if (!a.path.length) {
      a.spot = target;
      a.moving = false;
    }
  }
}
