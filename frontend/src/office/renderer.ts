// Draws the living office: floor, walls, furniture and people, depth-sorted, with day/night light.
// The scene is rendered at native pixel scale into an offscreen canvas, then scaled up crisply.

import type { EmployeeCard, StateView } from "../api/types";
import { t } from "../i18n";
import { eur } from "../util/format";
import { ActorWorld, type Actor } from "./actors";
import { BURST_MS, Drama, LINK_MS, SHOUT_MS } from "./drama";
import {
  INNER_WALL_H,
  iso,
  MAP_H,
  MAP_W,
  MARGIN,
  ORIGIN_X,
  ORIGIN_Y,
  OUTER_WALL_H,
  SCENE_H,
  SCENE_W,
  unIso,
  type Pt,
} from "./iso";
import { ANNEX_X, buildLayout, LOTS, roomAt, SLOT_ORIGINS, SLOT_W, type Furniture, type Layout } from "./layout";
import { fillPoly, isoBox, makeCanvas, mix, shade, tileDiamond, type Ctx } from "./pixel";
import { characterFrames, icon, prerenderFurniture, type IconKind, type Prerendered } from "./sprites";

interface Drawable {
  depth: number;
  draw: (ctx: Ctx) => void;
}

interface StaticPiece {
  pre: Prerendered;
  depth: number;
  f?: Furniture;
}

export interface PickResult {
  actorId?: string;
  departmentId?: string;
}

const FLOORS: Record<string, [string, string]> = {
  ceo: ["#6b4632", "#734c37"],
  meeting: ["#4f6378", "#546a80"],
  lab: ["#78a3a0", "#6e9996"],
  bench: ["#5f7d4d", "#668654"],
  corridor: ["#5a4e60", "#61556a"],
  desk: ["#a87a52", "#9f7249"],
  vacant: ["#3f3846", "#443c4b"],
  canteen: ["#e6dfcf", "#ddd4c1"],
  studio: ["#2b2838", "#312d40"],
  lot: ["#3a3540", "#35313b"],
};

const WALL = { cap: "#efe3cf", faceX: "#cdb89a", faceY: "#b5a083", end: "#a38e72", outerX: "#d9c6a6", outerY: "#bfa985" };

const STATUS_ICON: Record<string, IconKind> = {
  analyzing: "question",
  working: "euro",
  watching: "ball",
  celebrating: "star",
  frustrated: "cloud",
  stressed: "alert",
  meeting: "dots",
  researching: "bulb",
  ceo_office: "chart",
  studio: "mic",
};

const GLOW: Record<string, string> = {
  analyzing: "#6cc4ff",
  working: "#7cf0a0",
  watching: "#7cf0a0",
  celebrating: "#ffd25a",
  frustrated: "#ff6b6b",
  stressed: "#ff6b6b",
  researching: "#9ff0e6",
};

/** Plate name of an east-wing lot that is still for lease (layout.ts keeps the English ones). */
function lotLabel(key: string, fallback: string): string {
  switch (key) {
    case "canteen":
      return t("CANTEEN");
    case "desk_wing":
      return t("DESK WING");
    case "studio":
      return t("STUDIO");
    default:
      return fallback;
  }
}

/** Ambient light target by simulated clock time. */
function tintFor(time: string): [number, number, number, number] {
  const [h, m] = time.split(":").map(Number);
  const t = h + m / 60;
  if (t >= 21 || t < 6) return [18, 22, 64, 0.42];
  if (t < 9) return [255, 186, 120, 0.1];
  if (t < 14) return [0, 0, 0, 0];
  if (t < 19) return [255, 160, 90, 0.1];
  return [80, 60, 120, 0.25];
}

function skyFor(time: string): string {
  const [h] = time.split(":").map(Number);
  if (h >= 21 || h < 6) return "#1b2550";
  if (h < 9) return "#f3c99a";
  if (h < 14) return "#a6dbf1";
  if (h < 19) return "#f0b27e";
  return "#5a4a8a";
}

export class OfficeRenderer {
  private ctx: CanvasRenderingContext2D;
  private scene = makeCanvas(SCENE_W, SCENE_H);
  private sctx = this.scene.getContext("2d")!;
  private floor: HTMLCanvasElement | null = null;
  layout: Layout = buildLayout(new Set([0, 1, 2, 3]));
  private layoutKey = "";
  private statics: StaticPiece[] = [];
  private windows: Pt[][] = [];
  private tvScreen: Pt[] = [];
  actors = new ActorWorld(this.layout);
  private drama = new Drama();
  camera = { zoom: 2, x: 0, y: 0 };
  private userMoved = false;
  private cssW = 800;
  private cssH = 600;
  private dpr = 1;
  private tint: [number, number, number, number] = [0, 0, 0, 0];
  private last = 0;
  private valueHistory: { date: string; v: number }[] = [];
  hoveredId: string | null = null;
  selectedId: string | null = null;
  showNames = false;

  constructor(private canvas: HTMLCanvasElement) {
    this.ctx = canvas.getContext("2d")!;
  }

  // ------------------------------------------------------------------ camera
  resize(w: number, h: number, dpr: number): void {
    this.cssW = w;
    this.cssH = h;
    this.dpr = dpr;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    if (!this.userMoved) this.fit();
  }

  /** Size of the part of the scene the building occupies (it grows when the east wing is leased). */
  private sceneSize(): { w: number; h: number } {
    const width = this.layout.width;
    return { w: ORIGIN_X + width * 16 + MARGIN, h: ORIGIN_Y + (width + MAP_H) * 8 + MARGIN };
  }

  fit(): void {
    const { w, h } = this.sceneSize();
    const z = Math.min(this.cssW / w, this.cssH / h);
    this.camera.zoom = Math.max(0.5, Math.floor(z * 8) / 8);
    this.camera.x = Math.round((this.cssW - w * this.camera.zoom) / 2);
    this.camera.y = Math.round((this.cssH - h * this.camera.zoom) / 2);
    this.userMoved = false;
  }

  zoomAt(factor: number, mx: number, my: number): void {
    const old = this.camera.zoom;
    const next = Math.max(0.5, Math.min(5, Math.round(old * factor * 4) / 4));
    if (next === old) return;
    this.userMoved = true;
    const sx = (mx - this.camera.x) / old;
    const sy = (my - this.camera.y) / old;
    this.camera.zoom = next;
    this.camera.x = Math.round(mx - sx * next);
    this.camera.y = Math.round(my - sy * next);
  }

  /** Centre the camera on a tile at the given zoom. */
  focusTile(x: number, y: number, zoom: number): void {
    const p = iso(x, y);
    this.userMoved = true;
    this.camera.zoom = zoom;
    this.camera.x = Math.round(this.cssW / 2 - p.x * zoom);
    this.camera.y = Math.round(this.cssH / 2 - (p.y - 10) * zoom);
  }

  pan(dx: number, dy: number): void {
    this.userMoved = true;
    this.camera.x += dx;
    this.camera.y += dy;
  }

  toScene(mx: number, my: number): Pt {
    return { x: (mx - this.camera.x) / this.camera.zoom, y: (my - this.camera.y) / this.camera.zoom };
  }

  toScreen(p: Pt): Pt {
    return { x: p.x * this.camera.zoom + this.camera.x, y: p.y * this.camera.zoom + this.camera.y };
  }

  pick(mx: number, my: number, state: StateView | null): PickResult {
    const p = this.toScene(mx, my);
    const sorted = [...this.actors.actors.values()].filter((a) => a.alpha > 0.3).sort((a, b) => b.x + b.y - (a.x + a.y));
    for (const a of sorted) {
      const f = iso(a.x, a.y);
      if (p.x >= f.x - 8 && p.x <= f.x + 8 && p.y >= f.y - 26 && p.y <= f.y + 2) return { actorId: a.id };
    }
    const t = unIso(p.x, p.y);
    const room = roomAt(this.layout, t.x, t.y);
    if (room?.kind === "desk" && state) {
      const dept = state.departments.find((d) => d.room_slot === room.slot && d.kind !== "lab");
      if (dept) return { departmentId: dept.id };
    }
    if (room?.kind === "lab" && state) {
      const lab = state.departments.find((d) => d.kind === "lab");
      if (lab) return { departmentId: lab.id };
    }
    return {};
  }

  // ------------------------------------------------------------------ static layers
  private ensureLayout(state: StateView): void {
    const desks = state.departments.filter((d) => d.kind !== "lab" && d.active);
    const leased = Object.keys(state.office?.leased ?? {}).sort();
    const key = desks.map((d) => `${d.room_slot}:${d.color}`).sort().join("|") + "#" + leased.join(",");
    if (key === this.layoutKey && this.floor) return;
    this.layoutKey = key;
    const widthBefore = this.layout.width;
    this.layout = buildLayout(new Set(desks.map((d) => d.room_slot)), new Set(leased));
    if (this.layout.width !== widthBefore && !this.userMoved) this.fit();
    this.actors.setLayout(this.layout);
    const colorBySlot = new Map(desks.map((d) => [d.room_slot, d.color]));
    this.buildFloor(colorBySlot);
    this.statics = [];
    for (const f of this.layout.furniture) {
      const depth = f.depthBias !== undefined ? f.x + f.y + 1 + f.depthBias : f.x + f.w / 2 + f.y + f.d / 2;
      this.statics.push({ pre: prerenderFurniture(f), depth, f });
    }
    for (const w of this.layout.walls) {
      if (w.outer) continue;
      const a = roomAt(this.layout, w.side === "N" ? w.x : w.x - 1, w.side === "N" ? w.y - 1 : w.y);
      const b = roomAt(this.layout, w.x, w.y);
      if (a?.kind === "corridor" && b?.kind === "corridor") continue;
      this.statics.push({ pre: this.prerenderWall(w.x, w.y, w.side), depth: w.x + w.y + 0.5 });
    }
  }

  private prerenderWall(x: number, y: number, side: "N" | "W"): Prerendered {
    const left = iso(x, y + 1).x - 4;
    const right = iso(x + 1, y).x + 4;
    const top = iso(x, y).y - INNER_WALL_H - 6;
    const bottom = iso(x + 1, y + 1).y;
    const canvas = makeCanvas(Math.ceil(right - left), Math.ceil(bottom - top));
    const ctx = canvas.getContext("2d")!;
    ctx.translate(-Math.floor(left), -Math.floor(top));
    if (side === "N") isoBox(ctx, x, y - 0.07, 1, 0.14, INNER_WALL_H, { top: WALL.cap, left: WALL.faceX, right: WALL.end });
    else isoBox(ctx, x - 0.07, y, 0.14, 1, INNER_WALL_H, { top: WALL.cap, left: WALL.end, right: WALL.faceY });
    return { canvas, ox: Math.floor(left), oy: Math.floor(top) };
  }

  private buildFloor(colorBySlot: Map<number, string>): void {
    const c = makeCanvas(SCENE_W, SCENE_H);
    const ctx = c.getContext("2d")!;
    for (let y = 0; y < MAP_H; y++) {
      for (let x = 0; x < this.layout.width; x++) {
        const room = this.layout.roomGrid[y * MAP_W + x];
        if (!room) continue;
        let pal = FLOORS[room.kind];
        if (room.kind === "desk") {
          const col = colorBySlot.get(room.slot ?? -1);
          pal = col ? [mix(FLOORS.desk[0], col, 0.12), mix(FLOORS.desk[1], col, 0.12)] : FLOORS.vacant;
        }
        const plank = room.kind === "desk" || room.kind === "ceo" ? x % 2 : (x + y) % 2;
        tileDiamond(ctx, x, y, pal[plank]);
        if (room.kind === "lab") tileDiamond(ctx, x, y, shade(pal[0], 0.08), 0.42);
        if (room.kind === "canteen" && plank) tileDiamond(ctx, x, y, "#c9734f", 0.38);
        if (room.kind === "lot" && (x * 7 + y * 3) % 5 === 0) tileDiamond(ctx, x, y, "#423c48", 0.35); // dust
      }
    }
    // a doormat just inside each desk room's door, in the desk's colour
    for (const [slot, col] of colorBySlot) {
      const o = SLOT_ORIGINS[slot];
      this.doormat(ctx, o.x + 9, o.y, 2, 1, "#2f2735", shade(col, -0.3), shade(col, -0.05));
    }
    this.doormat(ctx, 33, 24, 3, 1, "#2f2735", "#6e3a30", "#9a5a44"); // street entrance
    this.drawOuterWalls(ctx);
    this.floor = c;
  }

  private doormat(ctx: Ctx, x: number, y: number, w: number, d: number, edge: string, inner: string, stripe: string): void {
    const quad = (u0: number, v0: number, u1: number, v1: number) => [iso(u0, v0), iso(u1, v0), iso(u1, v1), iso(u0, v1)];
    fillPoly(ctx, quad(x + 0.12, y + 0.18, x + w - 0.12, y + d - 0.12), edge);
    fillPoly(ctx, quad(x + 0.24, y + 0.3, x + w - 0.24, y + d - 0.24), inner);
    fillPoly(ctx, quad(x + 0.24, y + 0.47, x + w - 0.24, y + 0.53), stripe);
  }

  private wallN(u0: number, u1: number, v0: number, v1: number): Pt[] {
    const a = iso(u0, 0);
    const b = iso(u1, 0);
    return [
      { x: a.x, y: a.y - v0 },
      { x: b.x, y: b.y - v0 },
      { x: b.x, y: b.y - v1 },
      { x: a.x, y: a.y - v1 },
    ];
  }

  private wallW(u0: number, u1: number, v0: number, v1: number): Pt[] {
    const a = iso(0, u0);
    const b = iso(0, u1);
    return [
      { x: a.x, y: a.y - v0 },
      { x: b.x, y: b.y - v0 },
      { x: b.x, y: b.y - v1 },
      { x: a.x, y: a.y - v1 },
    ];
  }

  private drawOuterWalls(ctx: Ctx): void {
    const H = OUTER_WALL_H;
    const width = this.layout.width;
    for (let x = 0; x < width; x++) isoBox(ctx, x, -0.15, 1, 0.15, H, { top: WALL.cap, left: WALL.outerX, right: WALL.end });
    for (let y = 0; y < MAP_H; y++) isoBox(ctx, -0.15, y, 0.15, 1, H, { top: WALL.cap, left: WALL.end, right: WALL.outerY });
    isoBox(ctx, -0.15, -0.15, 0.15, 0.15, H, { top: WALL.cap, left: WALL.end, right: WALL.end });
    // baseboards
    fillPoly(ctx, this.wallN(0, width, 0, 3), "#8a7258");
    fillPoly(ctx, this.wallW(0, MAP_H, 0, 3), "#76614a");
    // windows (glass painted every frame)
    this.windows = [];
    const winN = [[2.2, 4.8], [27.2, 28.8], [30.2, 31.8], [33.2, 34.8]];
    if (width > ANNEX_X) winN.push([42.2, 43.8], [45.2, 46.6]);
    for (const [a, b] of winN) {
      fillPoly(ctx, this.wallN(a - 0.08, b + 0.08, 12, 38), "#6e5a44");
      this.windows.push(this.wallN(a, b, 14, 36));
    }
    for (const y of [10, 12.6, 19, 21.6]) {
      fillPoly(ctx, this.wallW(y - 0.08, y + 1.48, 12, 38), "#5e4c39");
      this.windows.push(this.wallW(y, y + 1.4, 14, 36));
    }
    // meeting-room screen
    fillPoly(ctx, this.wallN(9.8, 12.9, 13, 37), "#2a2633");
    this.tvScreen = this.wallN(10, 12.7, 15, 35);
    // LAB whiteboards with scribbles
    for (const [a, b] of [[17, 19.6], [21, 23.6]]) {
      fillPoly(ctx, this.wallN(a - 0.06, b + 0.06, 11, 37), "#9aa3ad");
      fillPoly(ctx, this.wallN(a, b, 13, 35), "#f4f6f7");
      for (let i = 0; i < 4; i++) {
        const u = a + 0.3 + i * 0.5;
        fillPoly(ctx, this.wallN(u, u + 0.35, 28 - i * 3, 29 - i * 3), i % 2 ? "#3d6fb5" : "#c23b3b");
        fillPoly(ctx, this.wallN(u, u + 0.2, 20 + i, 21 + i), "#2b2130");
      }
    }
    // bench clock and posters
    fillPoly(ctx, this.wallN(35.2, 35.8, 22, 32), "#f4f6f7");
    fillPoly(ctx, this.wallW(4.4, 5.6, 16, 34), "#2f6fb0"); // CEO painting
    fillPoly(ctx, this.wallW(4.55, 5.45, 19, 31), "#f2a541");
    fillPoly(ctx, this.wallW(7.2, 8.8, 18, 32), "#1b1426"); // company sign
    fillPoly(ctx, this.wallW(7.35, 8.65, 21, 29), "#f2a541");
    fillPoly(ctx, this.wallW(16.3, 17.7, 16, 34), "#c25b9a"); // poster
    fillPoly(ctx, this.wallW(16.5, 17.5, 20, 30), "#fdf6e3");
    if (this.layout.leased.has("canteen")) {
      // the menu board above the counter
      fillPoly(ctx, this.wallN(37.2, 41.6, 16, 36), "#2b2633");
      for (let i = 0; i < 4; i++) fillPoly(ctx, this.wallN(37.6, 39.4 + (i % 2) * 1.2, 30 - i * 4, 31 - i * 4), "#efe9dc");
      fillPoly(ctx, this.wallN(40.3, 41.2, 18, 33), "#d4573a");
    }
  }

  // ------------------------------------------------------------------ frame
  frame(state: StateView | null, now: number): void {
    const dt = this.last ? Math.min(0.1, (now - this.last) / 1000) : 0;
    this.last = now;
    const ctx = this.ctx;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = "#151020";
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    if (!state) return;
    this.ensureLayout(state);
    this.actors.update(state, dt, now);
    this.drama.ingest(state, now);
    this.drama.expire(now);
    const last = this.valueHistory[this.valueHistory.length - 1];
    if (!last || last.date !== state.clock.date) {
      this.valueHistory.push({ date: state.clock.date, v: state.kpis.valuation });
      if (this.valueHistory.length > 60) this.valueHistory.shift();
    } else last.v = state.kpis.valuation;

    const target = tintFor(state.clock.time);
    for (let i = 0; i < 4; i++) this.tint[i] += (target[i] - this.tint[i]) * Math.min(1, dt * 2);

    this.renderScene(state, now);

    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.scene, this.camera.x, this.camera.y, SCENE_W * this.camera.zoom, SCENE_H * this.camera.zoom);
    this.renderOverlay(state, now);
  }

  private renderScene(state: StateView, now: number): void {
    const ctx = this.sctx;
    ctx.clearRect(0, 0, SCENE_W, SCENE_H);
    if (this.floor) ctx.drawImage(this.floor, 0, 0);
    // dynamic wall bits
    const sky = skyFor(state.clock.time);
    for (const w of this.windows) {
      fillPoly(ctx, w, sky);
      if (sky === "#1b2550") {
        ctx.fillStyle = "#e8e4ff";
        const p = w[3];
        ctx.fillRect(Math.round(p.x + 6), Math.round(p.y + 5), 1, 1);
        ctx.fillRect(Math.round(p.x + 13), Math.round(p.y + 11), 1, 1);
      }
    }
    this.drawTv(ctx, state);

    const list: Drawable[] = [];
    for (const s of this.statics) {
      list.push({ depth: s.depth, draw: (c) => c.drawImage(s.pre.canvas, s.pre.ox, s.pre.oy) });
    }
    const occupied = new Map<string, Actor>();
    for (const a of this.actors.actors.values()) {
      if (a.spot && !a.moving) occupied.set(a.spot.key, a);
      list.push({ depth: a.x + a.y, draw: (c) => this.drawActor(c, a, now, state) });
    }
    for (const s of this.statics) {
      const f = s.f;
      if (!f) continue;
      if (f.kind === "desk" || f.kind === "lab_desk") {
        const key = f.kind === "desk" ? `desk${f.slot}-${f.index}` : `lab${f.index}`;
        const a = occupied.get(key);
        if (a) list.push({ depth: s.depth + 0.01, draw: (c) => this.drawMonitorGlow(c, f, a, now) });
      } else if (f.kind === "server") {
        list.push({ depth: s.depth + 0.01, draw: (c) => this.drawLeds(c, f, now) });
      } else if (f.kind === "arcade") {
        list.push({ depth: s.depth + 0.01, draw: (c) => this.drawArcade(c, f, now) });
      }
    }
    list.sort((a, b) => a.depth - b.depth);
    for (const d of list) d.draw(ctx);

    // ambient light
    const [r, g, b, alpha] = this.tint;
    if (alpha > 0.01) {
      ctx.save();
      ctx.globalCompositeOperation = "source-atop";
      ctx.fillStyle = `rgba(${r | 0},${g | 0},${b | 0},${alpha.toFixed(3)})`;
      ctx.fillRect(0, 0, SCENE_W, SCENE_H);
      ctx.restore();
      if (alpha > 0.2) this.drawLamps(ctx, occupied, alpha);
    }
    this.drawDrama(ctx, now);
  }

  /** Influence lines between colleagues and confetti bursts (scene space, above the lighting). */
  private drawDrama(ctx: Ctx, now: number): void {
    const head = (id: string) => {
      const a = this.actors.actors.get(id);
      if (!a || a.alpha < 0.3) return null;
      const p = iso(a.x, a.y);
      return { x: p.x, y: p.y - 16 };
    };
    for (const l of this.drama.links) {
      const a = head(l.from);
      const b = head(l.to);
      if (!a || !b) continue;
      const t = (now - l.born) / LINK_MS;
      const len = Math.hypot(b.x - a.x, b.y - a.y);
      const steps = Math.max(2, Math.floor(len / 3));
      const crawl = Math.floor(now / 120) % 2;
      ctx.save();
      ctx.globalAlpha = Math.min(1, 2 * (1 - t));
      if (l.kind === "clash") {
        // a jittering red zig-zag: these two are not getting along
        ctx.fillStyle = "#ff5a5a";
        for (let i = 0; i <= steps; i++) {
          const f = i / steps;
          const zig = (i % 4 < 2 ? 1 : -1) * 2 + (Math.floor(now / 90) % 2);
          ctx.fillRect(Math.round(a.x + (b.x - a.x) * f), Math.round(a.y + (b.y - a.y) * f + zig - 4), 1, 1);
        }
      } else {
        ctx.fillStyle = l.kind === "friends" ? "#7cf0a0" : "#ffd25a";
        for (let i = crawl; i <= steps; i += 2) {
          const f = i / steps;
          ctx.fillRect(Math.round(a.x + (b.x - a.x) * f), Math.round(a.y + (b.y - a.y) * f - Math.sin(f * Math.PI) * 10), 1, 1);
        }
        ctx.fillRect(Math.round(b.x) - 1, Math.round(b.y) - 1, 3, 3);
      }
      ctx.restore();
    }
    const colors = ["#ffd25a", "#7cf0a0", "#ff6bd1", "#6cc4ff", "#fdf6e3"];
    for (const burst of this.drama.bursts) {
      const h = head(burst.actorId);
      if (!h) continue;
      const t = (now - burst.born) / 1000;
      ctx.save();
      ctx.globalAlpha = Math.max(0, 1 - (now - burst.born) / BURST_MS);
      for (let i = 0; i < 14; i++) {
        const ang = burst.seed + i * 2.399;
        const v = 18 + (i % 4) * 7;
        const x = h.x + Math.cos(ang) * v * t;
        const y = h.y - 6 - Math.abs(Math.sin(ang)) * v * t + 40 * t * t;
        ctx.fillStyle = colors[i % colors.length];
        ctx.fillRect(Math.round(x), Math.round(y), i % 3 === 0 ? 2 : 1, 1);
      }
      ctx.restore();
    }
  }

  private drawTv(ctx: Ctx, state: StateView): void {
    fillPoly(ctx, this.tvScreen, "#10241c");
    const pts = this.valueHistory;
    if (pts.length < 2) return;
    const vals = pts.map((p) => p.v);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const up = vals[vals.length - 1] >= vals[0];
    ctx.fillStyle = up ? "#5fe08a" : "#ff6b6b";
    for (let i = 0; i < vals.length; i++) {
      const u = 10.1 + (i / (vals.length - 1)) * 2.5;
      const v = 17 + ((vals[i] - lo) / Math.max(1, hi - lo)) * 15;
      const p = iso(u, 0);
      ctx.fillRect(Math.round(p.x), Math.round(p.y - v), 1, 1);
    }
    void state;
  }

  private drawActor(ctx: Ctx, a: Actor, now: number, state: StateView): void {
    if (a.alpha <= 0) return;
    const p = iso(a.x, a.y);
    const e = a.emp;
    const frames = characterFrames(a.look);
    const seated = !a.moving && a.spot?.pose === "sit";
    let sprite: HTMLCanvasElement;
    let bob = 0;
    if (a.moving) {
      const f = Math.floor(a.walkClock * 3.2) % 4;
      sprite = a.face === "back" ? frames.backWalk[f] : frames.frontWalk[f];
    } else if (seated) {
      const typing = e.status === "analyzing" || e.status === "working" || e.status === "researching";
      sprite = a.face === "back" ? frames.backSit[0] : frames.frontSit[typing ? Math.floor(now / 170 + a.seed) % 2 : 0];
    } else {
      sprite = a.face === "back" ? frames.backWalk[0] : frames.frontWalk[0];
      bob = Math.floor(now / 650 + a.seed) % 2;
    }
    let jx = 0;
    if (e.status === "stressed" && Math.sin(now * 0.04 + a.seed) > 0.55) jx = Math.sin(now * 0.9) > 0 ? 1 : -1;
    let hop = 0;
    if (now < a.celebrateUntil) hop = Math.round(Math.abs(Math.sin(now * 0.012)) * 4);
    ctx.save();
    ctx.globalAlpha = Math.max(0, Math.min(1, a.alpha));
    // shadow (and selection ring)
    const sel = a.id === this.selectedId;
    const hov = a.id === this.hoveredId;
    if (sel || hov) {
      ctx.fillStyle = sel ? "#ffd25a" : "rgba(255,255,255,0.6)";
      ctx.fillRect(Math.round(p.x) - 7, Math.round(p.y) - 1, 15, 3);
      ctx.fillRect(Math.round(p.x) - 5, Math.round(p.y) - 2, 11, 5);
    }
    ctx.fillStyle = "rgba(10,6,20,0.35)";
    ctx.fillRect(Math.round(p.x) - 5, Math.round(p.y) - 1, 11, 2);
    ctx.fillRect(Math.round(p.x) - 3, Math.round(p.y) - 2, 7, 4);
    const sx = Math.round(p.x) - 8 + jx;
    const sy = Math.round(p.y) - 23 - bob - hop + (seated ? 1 : 0);
    if (a.flip) {
      ctx.translate(sx + 16, sy);
      ctx.scale(-1, 1);
      ctx.drawImage(sprite, 0, 0);
      ctx.setTransform(1, 0, 0, 1, 0, 0);
    } else {
      ctx.drawImage(sprite, sx, sy);
    }
    if (a.leaving) ctx.drawImage(icon("box"), sx + 2, sy + 10);
    if (e.status === "stressed" && Math.floor(now / 400 + a.seed) % 3 === 0) {
      ctx.fillStyle = "#7cc8ff";
      ctx.fillRect(sx + 12, sy + 3, 1, 2);
    }
    if (e.under_review && e.active) {
      ctx.fillStyle = "#ff9f1c";
      ctx.fillRect(sx + 14, sy - 1, 2, 4);
      ctx.fillRect(sx + 14, sy + 4, 2, 1);
    }
    // status bubble
    const iconKind = this.iconFor(e, state);
    const visibleFor = e.status === "stressed" ? 6 : e.status === "idle" ? 1.4 : 3.2;
    const cycle = ((now / 1000 + a.seed * 0.37) % (e.status === "idle" ? 12 : 9)) < visibleFor;
    if (iconKind && (sel || hov || cycle) && !a.leaving) {
      ctx.drawImage(icon(iconKind), Math.round(p.x) - 6, sy - 13);
    }
    if (sel) {
      const ay = sy - 20 + (Math.floor(now / 300) % 2);
      ctx.fillStyle = "#ffd25a";
      ctx.fillRect(Math.round(p.x) - 2, ay, 5, 1);
      ctx.fillRect(Math.round(p.x) - 1, ay + 1, 3, 1);
      ctx.fillRect(Math.round(p.x), ay + 2, 1, 1);
    }
    ctx.restore();
  }

  private iconFor(e: EmployeeCard, state: StateView): IconKind | null {
    if (e.status === "idle") {
      const h = Number(state.clock.time.split(":")[0]);
      return h >= 21 || h < 6 ? "zzz" : "coffee";
    }
    return STATUS_ICON[e.status] ?? null;
  }

  private drawMonitorGlow(ctx: Ctx, f: Furniture, a: Actor, now: number): void {
    const col = GLOW[a.emp.status] ?? "#9ab0c8";
    const p = f.kind === "desk" ? iso(f.x + 1.0, f.y + 0.24) : iso(f.x + 0.95, f.y + 0.23);
    const flicker = Math.floor(now / 250 + a.seed) % 7 === 0 ? 0.5 : 1;
    ctx.save();
    ctx.globalAlpha = 0.22 * flicker;
    ctx.fillStyle = col;
    ctx.fillRect(Math.round(p.x) - 6, Math.round(p.y) - 22, 13, 10);
    ctx.globalAlpha = 0.9 * flicker;
    ctx.fillRect(Math.round(p.x) - 3, Math.round(p.y) - 19, 7, 1);
    ctx.restore();
  }

  private drawLeds(ctx: Ctx, f: Furniture, now: number): void {
    const p = iso(f.x + 0.9, f.y + 0.5);
    const cols = ["#5fe08a", "#ffd25a", "#6cc4ff", "#ff6b6b"];
    for (let i = 0; i < 6; i++) {
      const on = Math.floor(now / (180 + i * 70) + f.y * 3 + i) % 3 !== 0;
      if (!on) continue;
      ctx.fillStyle = cols[(i + f.y) % cols.length];
      ctx.fillRect(Math.round(p.x) + 1 + (i % 2) * 3, Math.round(p.y) - 30 + i * 4, 1, 1);
    }
  }

  private drawArcade(ctx: Ctx, f: Furniture, now: number): void {
    const p = iso(f.x + 0.85, f.y + 0.5);
    const cols = ["#ff5ad1", "#5ad1ff", "#ffd25a", "#7cf0a0"];
    ctx.fillStyle = cols[Math.floor(now / 400) % cols.length];
    ctx.fillRect(Math.round(p.x) - 5, Math.round(p.y) - 26, 5, 5);
  }

  private drawLamps(ctx: Ctx, occupied: Map<string, Actor>, alpha: number): void {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    const glow = (p: Pt, r: number, col: string, a: number) => {
      const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r);
      g.addColorStop(0, col.replace("A", (a * alpha).toFixed(3)));
      g.addColorStop(1, col.replace("A", "0"));
      ctx.fillStyle = g;
      ctx.fillRect(p.x - r, p.y - r, r * 2, r * 2);
    };
    for (const [key] of occupied) {
      if (!key.startsWith("desk") && !key.startsWith("lab") && key !== "ceo") continue;
      const a = occupied.get(key)!;
      glow(iso(a.x + 0.5, a.y + 0.6), 26, "rgba(255,200,120,A)", 0.45);
    }
    const lamps = [iso(6, 8), iso(17, 8), iso(28, 8), iso(6, 17), iso(17, 17), iso(28, 17), iso(34.5, 12), iso(34.5, 21)];
    if (this.layout.leased.has("desk_wing")) lamps.push(iso(41, 8));
    if (this.layout.leased.has("studio")) lamps.push(iso(41, 17));
    for (const p of lamps) glow(p, 34, "rgba(255,214,150,A)", 0.3);
    ctx.restore();
  }

  // ------------------------------------------------------------------ screen-space labels
  private renderOverlay(state: StateView, now: number): void {
    const ctx = this.ctx;
    const z = this.camera.zoom;
    const plateFont = Math.round(Math.max(9, Math.min(15, 5.5 * z)));
    ctx.textBaseline = "middle";
    ctx.textAlign = "center";
    const plate = (p: Pt, title: string, sub: string | null, bg: string, subColor = "#fdf6e3") => {
      const s = this.toScreen(p);
      ctx.font = `${plateFont}px Silkscreen, monospace`;
      const w = Math.max(ctx.measureText(title).width, sub ? ctx.measureText(sub).width : 0) + 14;
      const h = sub ? plateFont * 2.6 : plateFont * 1.7;
      ctx.fillStyle = "#1b1426";
      ctx.fillRect(Math.round(s.x - w / 2) - 2, Math.round(s.y - h) - 2, Math.round(w) + 4, Math.round(h) + 4);
      ctx.fillStyle = bg;
      ctx.fillRect(Math.round(s.x - w / 2), Math.round(s.y - h), Math.round(w), Math.round(h));
      ctx.fillStyle = "#fdf6e3";
      ctx.fillText(title, s.x, s.y - h + plateFont * 0.85);
      if (sub) {
        ctx.font = `${Math.round(plateFont * 1.15)}px VT323, monospace`;
        ctx.fillStyle = subColor;
        ctx.fillText(sub, s.x, s.y - h + plateFont * 1.95);
      }
    };
    // fixed rooms on the back wall
    const roomPlates: [number, string, string][] = [
      [4, t("CEO OFFICE"), "#5b2d3a"],
      [12, t("MEETING ROOM"), "#33475c"],
      [21, t("LAB"), "#0b6e77"],
      [31, t("THE BENCH"), "#3f5c33"],
    ];
    if (this.layout.leased.has("canteen")) roomPlates.push([41.5, t("THE CANTEEN"), "#8a3b2a"]);
    for (const [u, label, col] of roomPlates) {
      const base = iso(u, 0);
      plate({ x: base.x, y: base.y - OUTER_WALL_H - 3 }, label, null, col);
    }
    // east wing: the studio and the lots still for lease
    if (this.layout.width > ANNEX_X) {
      const facilities = state.office?.facilities ?? [];
      for (const [key, lot] of Object.entries(LOTS)) {
        if (this.layout.leased.has(key)) continue;
        const base = iso(ANNEX_X + 5.5, (lot.y0 + lot.y1) / 2);
        const f = facilities.find((x) => x.key === key);
        const sub = f ? t("{name} · {cost}/mo", { name: t(f.name), cost: eur(f.monthly_cost) }) : lotLabel(key, lot.label);
        plate({ x: base.x, y: base.y }, t("FOR LEASE"), sub, "#3a3344", "#b6abc4");
      }
      if (this.layout.leased.has("studio")) {
        const base = iso(ANNEX_X + 5.5, 18);
        plate({ x: base.x, y: base.y - INNER_WALL_H - 4 }, t("MEDIA STUDIO"), t("on air every morning"), "#4b2d63", "#ff8ad8");
      }
    }
    // desk rooms
    SLOT_ORIGINS.forEach((o, slot) => {
      if (slot === 6 && !this.layout.leased.has("desk_wing")) return;
      const dept = state.departments.find((d) => d.room_slot === slot && d.kind !== "lab" && d.active);
      const base = iso(o.x + SLOT_W / 2, o.y);
      const at = { x: base.x, y: base.y - INNER_WALL_H - 4 };
      if (dept) {
        const m = dept.month_profit;
        const sub = t("month {amount}", { amount: `${m >= 0 ? "+" : "-"}${eur(Math.abs(m))}` });
        plate(at, t(dept.name).toUpperCase(), sub, shade(dept.color, -0.35), m >= 0 ? "#7cf0a0" : "#ff8a8a");
      } else {
        plate(at, t("EMPTY ROOM"), t("no desk yet"), "#3a3344", "#b6abc4");
      }
    });
    // speech bubbles for events
    const shoutFont = Math.round(Math.max(13, Math.min(22, 7.5 * z)));
    ctx.font = `${shoutFont}px VT323, monospace`;
    for (const s of this.drama.shouts) {
      const a = this.actors.actors.get(s.actorId);
      if (!a || a.alpha < 0.3) continue;
      const feet = this.toScreen(iso(a.x, a.y));
      const t = (now - s.born) / SHOUT_MS;
      const w = ctx.measureText(s.text).width + 12;
      const h = shoutFont + 6;
      const x = Math.round(feet.x - w / 2);
      const y = Math.round(feet.y - 42 * z - h - (t < 0.1 ? (0.1 - t) * 40 : 0));
      ctx.globalAlpha = t > 0.85 ? (1 - t) / 0.15 : 1;
      ctx.fillStyle = "#1b1426";
      ctx.fillRect(x - 2, y - 2, Math.round(w) + 4, h + 4);
      ctx.fillStyle = "#fdf6e3";
      ctx.fillRect(x, y, Math.round(w), h);
      ctx.fillStyle = s.color;
      ctx.fillRect(x, y, 3, h);
      ctx.fillStyle = "#fdf6e3";
      ctx.fillRect(Math.round(feet.x) - 3, y + h, 6, 3);
      ctx.fillRect(Math.round(feet.x) - 1, y + h + 3, 2, 2);
      ctx.fillStyle = "#2b2130";
      ctx.fillText(s.text, feet.x + 1, y + h / 2 + 1);
      ctx.globalAlpha = 1;
    }
    // names & floaters
    const nameFont = Math.round(Math.max(10, Math.min(16, 6 * z)));
    const floatFont = Math.round(Math.max(13, Math.min(26, 9 * z)));
    for (const a of this.actors.actors.values()) {
      for (const f of a.floaters) {
        // the day's P/L floats up from where the person was when the results came in
        const t = (now - f.born) / 2600;
        const at = this.toScreen(iso(f.x, f.y));
        const y = at.y - 30 * z - t * 22 * z;
        ctx.globalAlpha = Math.max(0, 1 - t * t);
        ctx.font = `${floatFont}px VT323, monospace`;
        ctx.lineWidth = 3;
        ctx.strokeStyle = "#1b1426";
        ctx.strokeText(f.text, at.x, y);
        ctx.fillStyle = f.color;
        ctx.fillText(f.text, at.x, y);
        ctx.globalAlpha = 1;
      }
      if (a.alpha <= 0.05) continue;
      const feet = this.toScreen(iso(a.x, a.y));
      const show = this.showNames || z >= 2.75 || a.id === this.hoveredId || a.id === this.selectedId;
      if (show) {
        ctx.font = `${nameFont}px VT323, monospace`;
        const text = a.emp.name;
        const w = ctx.measureText(text).width + 6;
        ctx.globalAlpha = a.alpha;
        ctx.fillStyle = "rgba(27,20,38,0.8)";
        ctx.fillRect(Math.round(feet.x - w / 2), Math.round(feet.y + 3), Math.round(w), nameFont);
        ctx.fillStyle = a.emp.role === "ceo" ? "#ffd25a" : "#fdf6e3";
        ctx.fillText(text, feet.x, feet.y + 3 + nameFont / 2);
        ctx.globalAlpha = 1;
      }
    }
  }
}
