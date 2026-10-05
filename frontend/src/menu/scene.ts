import { drawText, textWidth } from "./font";
import type { Fortune } from "./fortune";

/**
 * The title screen: the company's building on a city street, drawn at 180 px high and scaled up.
 * Day turns to night (CYCLE seconds), cars and people come and go, and the building shows how the company is
 * doing (see fortune.ts). Everything is procedural; there are no image assets.
 */

export interface SceneLabels {
  name: string;
  forLease: string;
  closed: string;
  onAir: string;
  newBoss: string;
  thanks: string;
}

const H = 180;
const BASE = 146; // where the buildings meet the pavement
const ROAD_TOP = 153;
const ROAD_BOTTOM = 169;
const FH = 13; // storey height
const GH = 27; // ground floor height (name board, awning, door)
const CYCLE = 120; // seconds for a whole day and night

type RGB = [number, number, number];
const hex = (h: string): RGB => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
const css = (c: RGB, a = 1) => `rgba(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])},${a})`;
const mix = (a: RGB, b: RGB, t: number): RGB => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const clamp = (v: number, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));

/** Deterministic noise in [0, 1). */
function hash(a: number, b: number, c = 0): number {
  let h = (a * 374761393 + b * 668265263 + c * 2147483647) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

function rng(seed: number) {
  let t = seed >>> 0;
  return () => {
    t = (t + 0x6d2b79f5) | 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

const SKY = {
  nightTop: hex("#0a0a1e"),
  nightLow: hex("#1f1942"),
  dayTop: hex("#4b9be0"),
  dayLow: hex("#bfe4ff"),
  warmLow: hex("#f39a64"),
  warmTop: hex("#5a3d7a"),
};
const FACADE = ["#9a5a45", "#a8705a", "#c4aa8c", "#d6cfc2", "#4c78a6"];
const TRIM = ["#6e3b2d", "#7a4a3a", "#8f7a60", "#9a9388", "#2e4f73"];
const CAR_COLORS = ["#c94f4f", "#3f6fb5", "#e8e2d4", "#2f2f3a", "#5aa06a", "#8a5cb8", "#d98b3a", "#7d8a99"];
const SHIRTS = ["#d95f4b", "#4b7bd9", "#e8c547", "#5fb37a", "#b35fb3", "#e8e2d4", "#3b3b4f", "#e08a3a"];
const SKINS = ["#f1c9a0", "#d9a77c", "#a8704a", "#7a4e33", "#f5d6b8"];

interface Win {
  x: number;
  y: number;
  floor: number;
  col: number;
}
interface Block {
  x0: number;
  bw: number;
  floors: number;
  top: number;
  wins: Win[];
}
interface Layout {
  main: Block;
  annex: Block | null;
  doorX: number;
  fireFloor: number;
}
interface Car {
  x: number;
  lane: 0 | 1;
  speed: number;
  kind: "car" | "van" | "bus" | "taxi";
  color: string;
}
interface Walker {
  x: number;
  y: number;
  dir: 1 | -1;
  speed: number;
  shirt: string;
  skin: string;
  phase: number;
  target: number | null; // a door to walk into
  alpha: number;
  still?: boolean;
}
interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  max: number;
  color: string;
  size: number;
  gravity: number;
}

const TIERS: { floors: number; bw: number }[] = [
  { floors: 2, bw: 72 },
  { floors: 3, bw: 86 },
  { floors: 4, bw: 94 },
  { floors: 5, bw: 102 },
  { floors: 7, bw: 92 },
];

function block(x0: number, bw: number, floors: number): Block {
  const top = BASE - GH - floors * FH;
  const cols = Math.floor((bw - 6) / 12);
  const total = cols * 12 - 5;
  const start = x0 + Math.round((bw - total) / 2);
  const wins: Win[] = [];
  for (let f = 1; f <= floors; f++) {
    for (let c = 0; c < cols; c++) wins.push({ x: start + c * 12, y: BASE - GH - f * FH + 3, floor: f, col: c });
  }
  return { x0, bw, floors, top, wins };
}

export class CityScene {
  private ctx: CanvasRenderingContext2D;
  private fg: HTMLCanvasElement;
  private fgx: CanvasRenderingContext2D;
  private W = 320;
  private fortune: Fortune | null = null;
  private labels: SceneLabels = { name: "DESPORTO & CIA.", forLease: "FOR LEASE", closed: "CLOSED", onAir: "ON AIR", newBoss: "UNDER NEW MANAGEMENT", thanks: "THANK YOU, BOSS!" };
  private layout: Layout | null = null;
  private skyline: { x: number; w: number; h: number; far: boolean }[] = [];
  private stars: { x: number; y: number; s: number }[] = [];
  private clouds: { x: number; y: number; w: number }[] = [];
  private cars: Car[] = [];
  private walkers: Walker[] = [];
  private smoke: Particle[] = [];
  private sparks: Particle[] = [];
  private nextCar = [0, 0];
  private nextWalker = 0;
  private nextFirework = 0;
  private last = 0;
  private clock = CYCLE * 0.55; // start in the afternoon
  private rand = rng(7);

  constructor(private canvas: HTMLCanvasElement) {
    this.ctx = canvas.getContext("2d")!;
    this.fg = document.createElement("canvas");
    this.fgx = this.fg.getContext("2d")!;
    this.resize(canvas.clientWidth || 1280, canvas.clientHeight || 720);
  }

  /** The canvas is H px tall and as wide as the screen's aspect needs; CSS scales it up. */
  resize(cssW: number, cssH: number) {
    this.W = Math.max(320, Math.round((H * cssW) / Math.max(1, cssH)));
    for (const c of [this.canvas, this.fg]) {
      c.width = this.W;
      c.height = H;
    }
    this.ctx.imageSmoothingEnabled = false;
    this.buildBackdrop();
    this.relayout();
  }

  setFortune(f: Fortune, labels: SceneLabels) {
    const fresh = !this.fortune;
    this.fortune = f;
    this.labels = labels;
    this.relayout();
    if (fresh) {
      const clock = this.clock;
      for (let i = 0; i < 400; i++) this.update(0.1); // start with a lived-in street
      this.clock = clock;
    }
    if (f.mood === "ruin" || f.mood === "vacant" || f.mood === "dark") this.walkers = this.walkers.filter((w) => w.target === null);
    if (f.mood === "ruin") this.cars = this.cars.filter((c) => c.lane === 1); // the fire engine blocks the far lane
  }

  /** 0 = midnight, 0.25 = dawn, 0.5 = noon, 0.75 = dusk */
  get dayPhase(): number {
    return (this.clock / CYCLE) % 1;
  }

  /** The company's name, shortened to fit the board over the door. */
  private boardName(): string {
    const max = Math.floor(((this.layout?.main.bw ?? 72) - 6) / 4);
    const name = this.labels.name;
    return name.length > max ? name.slice(0, max - 1).trimEnd() + "." : name;
  }

  private relayout() {
    const f = this.fortune;
    if (!f) return;
    const t = TIERS[f.tier];
    const annexW = f.deskWing ? 44 : 0;
    const x0 = Math.round(this.W / 2 - (t.bw + annexW) / 2);
    const main = block(x0, t.bw, t.floors);
    const annex = f.deskWing ? block(x0 + t.bw, annexW, Math.min(3, t.floors)) : null;
    this.layout = { main, annex, doorX: x0 + Math.round(t.bw / 2), fireFloor: Math.min(t.floors, Math.max(1, Math.ceil(t.floors / 2))) };
  }

  private buildBackdrop() {
    const r = rng(42);
    this.skyline = [];
    for (const far of [true, false]) {
      let x = -10;
      while (x < this.W + 10) {
        const w = 14 + Math.floor(r() * 22);
        this.skyline.push({ x, w, h: (far ? 40 : 22) + Math.floor(r() * (far ? 55 : 40)), far });
        x += w + (far ? 0 : Math.floor(r() * 6));
      }
    }
    this.stars = Array.from({ length: 70 }, () => ({ x: Math.floor(r() * this.W), y: Math.floor(r() * 100), s: r() }));
    this.clouds = Array.from({ length: 5 }, () => ({ x: r() * this.W, y: 12 + r() * 50, w: 14 + Math.floor(r() * 18) }));
  }

  // ------------------------------------------------------------------ simulation of the street
  private busy(): number {
    const f = this.fortune;
    if (!f || f.mood === "ruin" || f.mood === "vacant") return 0;
    return f.mood === "dark" ? 0.2 : f.mood === "dim" ? 0.5 : 1;
  }

  private update(dt: number) {
    this.clock += dt;
    const night = this.night();
    const W = this.W;
    const r = this.rand;
    // traffic: two lanes, the far one drives left
    for (const lane of [0, 1] as const) {
      this.nextCar[lane] -= dt;
      const blocked = lane === 0 && this.fortune?.mood === "ruin"; // the fire engine is parked there
      if (this.nextCar[lane] <= 0 && !blocked) {
        const roll = r();
        const kind: Car["kind"] = roll < 0.07 ? "bus" : roll < 0.24 ? "van" : roll < 0.34 ? "taxi" : "car";
        const speed = (lane === 0 ? -1 : 1) * (18 + r() * 14) * (kind === "bus" ? 0.75 : 1);
        this.cars.push({ x: lane === 0 ? W + 34 : -34, lane, speed, kind, color: CAR_COLORS[Math.floor(r() * CAR_COLORS.length)] });
        this.nextCar[lane] = (0.8 + r() * 2.2) * (1 + 1.6 * night);
      }
    }
    // keep a gap behind the car in front (lanes don't overtake)
    for (const lane of [0, 1] as const) {
      const dir = lane === 0 ? -1 : 1;
      const row = this.cars.filter((c) => c.lane === lane).sort((a, b) => dir * (b.x - a.x));
      for (let i = 1; i < row.length; i++) {
        const ahead = row[i - 1];
        const me = row[i];
        const len = (k: Car["kind"]) => (k === "bus" ? 30 : k === "van" ? 18 : 14);
        const gap = dir > 0 ? ahead.x - (me.x + len(me.kind)) : me.x - (ahead.x + len(ahead.kind));
        if (gap < 6) me.speed = dir * Math.min(Math.abs(me.speed), Math.abs(ahead.speed));
      }
    }
    for (const c of this.cars) c.x += c.speed * dt;
    this.cars = this.cars.filter((c) => c.x > -40 && c.x < W + 40);
    // people
    const L = this.layout;
    this.nextWalker -= dt;
    if (this.nextWalker <= 0 && L) {
      const near = r() < 0.6;
      const dir: 1 | -1 = r() < 0.5 ? 1 : -1;
      const busy = this.busy();
      const toDoor = near && busy > 0 && night < 0.6 && r() < 0.4 * busy;
      const fromDoor = near && busy > 0 && !toDoor && r() < 0.25 * busy;
      this.walkers.push({
        x: fromDoor ? L.doorX : dir === 1 ? -6 : W + 6,
        y: near ? 151 : 178,
        dir,
        speed: 7 + r() * 6,
        shirt: SHIRTS[Math.floor(r() * SHIRTS.length)],
        skin: SKINS[Math.floor(r() * SKINS.length)],
        phase: r() * 2,
        target: toDoor ? L.doorX : null,
        alpha: fromDoor ? 0 : 1,
      });
      this.nextWalker = (0.6 + r() * 1.4) * (1 + 3 * night);
    }
    for (const w of this.walkers) {
      if (w.still) continue;
      if (w.target !== null) {
        w.dir = w.target > w.x ? 1 : -1;
        if (Math.abs(w.target - w.x) < 1) {
          w.alpha -= dt * 2.5; // through the door
          continue;
        }
      } else if (w.alpha < 1) {
        w.alpha = Math.min(1, w.alpha + dt * 2.5);
      }
      w.x += w.dir * w.speed * dt;
      w.phase += dt * w.speed * 0.35;
    }
    this.walkers = this.walkers.filter((w) => w.alpha > 0 && w.x > -10 && w.x < W + 10);
    // smoke from a fire, fireworks for a retirement
    const f = this.fortune;
    if (f?.mood === "ruin" && L) {
      for (const win of L.main.wins.filter((x) => x.floor === L.fireFloor)) {
        if (r() < dt * 2.2) {
          this.smoke.push({ x: win.x + 3 + r() * 2, y: win.y - 4, vx: 2 + r() * 4, vy: -(7 + r() * 5), life: 0, max: 4 + r() * 3, color: "#4d4752", size: 2, gravity: 0 });
        }
      }
    }
    for (const p of this.smoke) {
      p.life += dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.size = 2 + (p.life / p.max) * 4;
    }
    this.smoke = this.smoke.filter((p) => p.life < p.max);
    if (f?.ending === "retired" && night > 0.4 && L) {
      this.nextFirework -= dt;
      if (this.nextFirework <= 0) {
        const cx = L.main.x0 - 30 + r() * (L.main.bw + 60);
        const cy = 20 + r() * Math.max(10, L.main.top - 30);
        const color = ["#ff6b8a", "#ffd34a", "#6cc0ff", "#7cf0a0", "#c792ea"][Math.floor(r() * 5)];
        for (let i = 0; i < 26; i++) {
          const a = (i / 26) * Math.PI * 2;
          const v = 14 + r() * 10;
          this.sparks.push({ x: cx, y: cy, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: 0, max: 1.4 + r() * 0.6, color, size: 1, gravity: 14 });
        }
        this.nextFirework = 0.9 + r() * 1.4;
      }
    }
    for (const p of this.sparks) {
      p.life += dt;
      p.vy += p.gravity * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
    }
    this.sparks = this.sparks.filter((p) => p.life < p.max);
  }

  /** 0 at midday … 1 in the dead of night */
  private night(): number {
    const elev = Math.sin(2 * Math.PI * (this.dayPhase - 0.25));
    return 1 - clamp((elev + 0.12) / 0.38);
  }

  // ------------------------------------------------------------------ drawing
  frame(nowMs: number) {
    const dt = this.last ? Math.min(0.1, (nowMs - this.last) / 1000) : 0;
    this.last = nowMs;
    if (dt) this.update(dt);
    const t = nowMs / 1000;
    const ctx = this.ctx;
    const night = this.night();
    const elev = Math.sin(2 * Math.PI * (this.dayPhase - 0.25));
    const warm = clamp(1 - Math.abs(elev) / 0.32) * (1 - night * 0.5);
    this.drawSky(ctx, night, warm, elev, t);
    // ground objects go on their own layer so night can darken them without touching the sky
    const g = this.fgx;
    g.clearRect(0, 0, this.W, H);
    this.drawSkyline(g, night);
    this.drawStreet(g);
    if (this.layout && this.fortune) this.drawBuilding(g, this.fortune, this.layout, t);
    this.drawProps(g, t);
    this.drawTraffic(g, 0);
    this.drawWalkers(g);
    this.drawTraffic(g, 1);
    g.globalCompositeOperation = "source-atop";
    g.fillStyle = `rgba(12,9,32,${0.64 * night})`;
    g.fillRect(0, 0, this.W, H);
    if (warm > 0) {
      g.fillStyle = `rgba(255,140,80,${0.13 * warm})`;
      g.fillRect(0, 0, this.W, H);
    }
    g.globalCompositeOperation = "source-over";
    ctx.drawImage(this.fg, 0, 0);
    this.drawLights(ctx, night, t);
  }

  private drawSky(ctx: CanvasRenderingContext2D, night: number, warm: number, elev: number, t: number) {
    const top = mix(mix(SKY.dayTop, SKY.nightTop, night), SKY.warmTop, warm * 0.6);
    const low = mix(mix(SKY.dayLow, SKY.nightLow, night), SKY.warmLow, warm * 0.8);
    for (let y = 0; y < BASE; y += 2) {
      ctx.fillStyle = css(mix(top, low, y / BASE));
      ctx.fillRect(0, y, this.W, 2);
    }
    // stars
    if (night > 0.3) {
      for (const s of this.stars) {
        const tw = 0.5 + 0.5 * Math.sin(t * (1 + s.s * 2) + s.x);
        ctx.fillStyle = `rgba(255,248,220,${(night - 0.3) * 1.3 * (0.4 + 0.6 * tw) * (0.4 + s.s * 0.6)})`;
        ctx.fillRect(s.x, s.y, 1, 1);
      }
    }
    // sun by day, moon by night, on an arc over the street
    const phase = this.dayPhase;
    const arc = (p: number) => ({ x: this.W * (0.08 + 0.84 * p), y: 120 - Math.sin(p * Math.PI) * 100 });
    if (elev > -0.15) {
      const p = clamp((phase - 0.25 + 0.03) / 0.56);
      const s = arc(p);
      ctx.fillStyle = `rgba(255,236,170,${0.25})`;
      ctx.fillRect(s.x - 5, s.y - 5, 11, 11);
      ctx.fillStyle = warm > 0.4 ? "#ffb070" : "#fff2b8";
      ctx.fillRect(s.x - 3, s.y - 3, 7, 7);
      ctx.fillRect(s.x - 4, s.y - 2, 9, 5);
      ctx.fillRect(s.x - 2, s.y - 4, 5, 9);
    } else {
      const p = clamp((((phase + 0.25) % 1) - 0.0) / 0.5);
      const m = arc(p);
      ctx.fillStyle = "#e9e4d0";
      ctx.fillRect(m.x - 2, m.y - 3, 5, 7);
      ctx.fillRect(m.x - 3, m.y - 2, 7, 5);
      ctx.fillStyle = "#c9c2ad";
      ctx.fillRect(m.x, m.y - 1, 1, 1);
      ctx.fillRect(m.x - 1, m.y + 1, 2, 1);
    }
    // clouds drift slowly
    const cloud = css(mix(hex("#ffffff"), hex("#3b3560"), night), 0.85 - night * 0.35);
    for (const c of this.clouds) {
      const x = ((c.x + t * 2.5) % (this.W + 60)) - 40;
      ctx.fillStyle = cloud;
      ctx.fillRect(x, c.y, c.w, 3);
      ctx.fillRect(x + 3, c.y - 2, c.w - 8, 2);
      ctx.fillRect(x + 6, c.y - 4, Math.max(4, c.w - 16), 2);
    }
  }

  private drawSkyline(g: CanvasRenderingContext2D, night: number) {
    for (const b of this.skyline) {
      g.fillStyle = b.far ? "#7d86ad" : "#5d6386";
      g.fillRect(b.x, BASE - b.h, b.w, b.h);
      if (!b.far) {
        g.fillStyle = "#4f557a";
        g.fillRect(b.x, BASE - b.h, b.w, 2);
      }
    }
    // distant windows are lit later, in drawLights
    void night;
  }

  private drawStreet(g: CanvasRenderingContext2D) {
    const W = this.W;
    g.fillStyle = "#a39cb0"; // pavement
    g.fillRect(0, BASE, W, ROAD_TOP - BASE);
    g.fillStyle = "#8d8699";
    for (let x = 0; x < W; x += 9) g.fillRect(x, BASE, 1, ROAD_TOP - BASE);
    g.fillStyle = "#cfc8d8"; // kerb
    g.fillRect(0, ROAD_TOP - 1, W, 1);
    g.fillStyle = "#3d3b48"; // road
    g.fillRect(0, ROAD_TOP, W, ROAD_BOTTOM - ROAD_TOP);
    g.fillStyle = "#d9d2b8";
    for (let x = 0; x < W; x += 16) g.fillRect(x, 161, 8, 1);
    g.fillStyle = "#cfc8d8";
    g.fillRect(0, ROAD_BOTTOM, W, 1);
    g.fillStyle = "#958ea2"; // near pavement
    g.fillRect(0, ROAD_BOTTOM + 1, W, H - ROAD_BOTTOM - 1);
    g.fillStyle = "#847d91";
    for (let x = 4; x < W; x += 9) g.fillRect(x, ROAD_BOTTOM + 1, 1, H - ROAD_BOTTOM - 1);
  }

  private lampXs(): number[] {
    const out: number[] = [];
    const door = this.layout?.doorX ?? -99;
    for (let x = 18; x < this.W; x += 62) if (Math.abs(x - door) > 16) out.push(x);
    return out;
  }

  private drawProps(g: CanvasRenderingContext2D, t: number) {
    for (const x of this.lampXs()) {
      g.fillStyle = "#3b3846";
      g.fillRect(x, BASE - 24, 1, 26);
      g.fillRect(x, BASE - 24, 4, 1);
      g.fillStyle = "#57536a";
      g.fillRect(x + 3, BASE - 24, 3, 2);
    }
    // a tree at each end of the block
    const L = this.layout;
    if (L) {
      const left = L.main.x0 - 16;
      const right = (L.annex ? L.annex.x0 + L.annex.bw : L.main.x0 + L.main.bw) + 10;
      for (const x of [left, right]) {
        g.fillStyle = "#6b4a35";
        g.fillRect(x + 3, BASE - 8, 2, 9);
        g.fillStyle = "#3f7a4a";
        g.fillRect(x, BASE - 16, 8, 8);
        g.fillRect(x + 1, BASE - 18, 6, 2);
        g.fillStyle = "#58985f";
        g.fillRect(x + 1, BASE - 15, 3, 3);
      }
      if (this.fortune?.mood === "ruin") this.drawFireEngine(g, L.doorX - 20, t);
    }
  }

  private drawFireEngine(g: CanvasRenderingContext2D, x: number, t: number) {
    const y = 158;
    g.fillStyle = "#c7302b";
    g.fillRect(x, y - 7, 30, 6);
    g.fillRect(x + 22, y - 10, 8, 3);
    g.fillStyle = "#e9e2d0";
    g.fillRect(x + 2, y - 9, 18, 1); // ladder
    for (let i = 3; i < 20; i += 3) g.fillRect(x + i, y - 10, 1, 1);
    g.fillStyle = "#9fd3f0";
    g.fillRect(x + 24, y - 9, 4, 2);
    g.fillStyle = "#1c1b22";
    g.fillRect(x + 3, y - 1, 3, 2);
    g.fillRect(x + 23, y - 1, 3, 2);
    g.fillStyle = Math.floor(t * 3) % 2 ? "#ff4040" : "#4080ff";
    g.fillRect(x + 25, y - 11, 2, 1);
  }

  private drawBuilding(g: CanvasRenderingContext2D, f: Fortune, L: Layout, t: number) {
    const tier = f.tier;
    const ruin = f.mood === "ruin";
    for (const b of [L.main, ...(L.annex ? [L.annex] : [])]) {
      const isAnnex = b !== L.main;
      g.fillStyle = isAnnex ? TRIM[Math.min(tier, 3)] : FACADE[tier];
      g.fillRect(b.x0, b.top, b.bw, BASE - b.top);
      if (isAnnex) {
        g.fillStyle = FACADE[Math.min(tier, 3)];
        g.fillRect(b.x0 + 1, b.top + 1, b.bw - 2, BASE - b.top - 1);
      }
      // texture: brick specks or glass mullions
      if (tier === 4 && !isAnnex) {
        g.fillStyle = "#6f9bc8";
        for (let x = b.x0 + 3; x < b.x0 + b.bw - 2; x += 6) g.fillRect(x, b.top, 1, BASE - GH - b.top);
      } else if (tier <= 1) {
        g.fillStyle = TRIM[tier];
        for (let y = b.top + 2; y < BASE - GH; y += 3) {
          for (let x = b.x0 + ((y / 3) % 2 ? 2 : 5); x < b.x0 + b.bw - 1; x += 6) {
            if (hash(x, y) < 0.5) g.fillRect(x, y, 2, 1);
          }
        }
      }
      // storey bands
      g.fillStyle = TRIM[tier];
      for (let fl = 1; fl <= b.floors; fl++) g.fillRect(b.x0, BASE - GH - fl * FH + FH - 1, b.bw, 1);
      g.fillRect(b.x0 - 1, b.top - 2, b.bw + 2, 2); // parapet
      // windows
      for (const w of b.wins) {
        g.fillStyle = TRIM[tier];
        g.fillRect(w.x - 1, w.y - 1, 9, 9);
        if (ruin) {
          g.fillStyle = "#1b1820";
          g.fillRect(w.x, w.y, 7, 7);
          if (hash(w.floor, w.col, 3) < 0.45) {
            g.fillStyle = "#4a4652";
            for (let i = 0; i < 4; i++) g.fillRect(w.x + 1 + i, w.y + 1 + i + (i % 2), 1, 1);
          }
        } else {
          g.fillStyle = tier === 4 && !isAnnex ? "#7fb6dd" : "#86bde0";
          g.fillRect(w.x, w.y, 7, 7);
          g.fillStyle = "#b9dcf2";
          g.fillRect(w.x + 1, w.y + 1, 2, 1);
          g.fillRect(w.x + 1, w.y + 2, 1, 1);
          const roll = hash(w.floor + (isAnnex ? 40 : 0), w.col, 21);
          if ((f.mood === "dark" || f.mood === "vacant") && roll < 0.4) {
            g.fillStyle = "#d8cbb0"; // papered over
            g.fillRect(w.x, w.y, 7, 7);
            g.fillStyle = "#b8a98c";
            for (let i = 0; i < 6; i++) g.fillRect(w.x + i, w.y + 6 - i, 1, 1);
          } else if ((f.mood === "dim" || f.mood === "dark") && roll < 0.7) {
            g.fillStyle = "#9a97a6"; // blinds down
            for (let i = 0; i < 7; i += 2) g.fillRect(w.x, w.y + i, 7, 1);
          }
        }
      }
    }
    const m = L.main;
    if (L.annex) {
      const a = L.annex;
      g.fillStyle = TRIM[Math.min(tier, 3)];
      g.fillRect(a.x0 + 9, BASE - GH + 12, 26, 11);
      g.fillStyle = ruin ? "#1b1820" : "#86bde0";
      g.fillRect(a.x0 + 10, BASE - GH + 13, 24, 9);
    }
    // soot above the burning floor
    if (ruin) {
      g.fillStyle = "rgba(20,14,14,0.55)";
      g.fillRect(m.x0, BASE - GH - (L.fireFloor + 1) * FH, m.bw, FH + 4);
    }
    // balconies with plants
    const balconyFloors = tier === 2 ? [2] : tier === 3 ? [2, 4] : [];
    for (const fl of balconyFloors) {
      const row = m.wins.filter((w) => w.floor === fl);
      if (row.length < 4) continue;
      for (const [a, z] of [
        [row[0], row[1]],
        [row[row.length - 2], row[row.length - 1]],
      ]) {
        const x = a.x - 3;
        const w = z.x + 10 - x;
        const y = a.y + 8;
        g.fillStyle = TRIM[tier];
        g.fillRect(x, y, w, 2);
        g.fillStyle = "#e9e4d8";
        g.fillRect(x, y - 4, w, 1);
        for (let i = x; i < x + w; i += 2) g.fillRect(i, y - 4, 1, 4);
        g.fillStyle = "#8a5a3a";
        g.fillRect(x + 1, y - 2, 3, 2);
        g.fillStyle = "#4f9a5a";
        g.fillRect(x, y - 5, 5, 3);
      }
    }
    this.drawGroundFloor(g, f, L, t);
    this.drawRoof(g, f, L, t);
    // the café tables of the canteen
    if (f.canteen && !ruin) {
      for (const dx of [6, 20]) {
        const x = m.x0 + dx;
        g.fillStyle = dx === 6 ? "#d4553f" : "#3f8fd4";
        g.fillRect(x - 3, BASE - 9, 9, 2);
        g.fillRect(x - 1, BASE - 10, 5, 1);
        g.fillStyle = "#e9e2d0";
        g.fillRect(x + 1, BASE - 7, 1, 6);
        g.fillStyle = "#6b5a4a";
        g.fillRect(x - 1, BASE - 3, 5, 1);
      }
    }
  }

  private drawGroundFloor(g: CanvasRenderingContext2D, f: Fortune, L: Layout, t: number) {
    const m = L.main;
    const tier = f.tier;
    const gy = BASE - GH;
    const ruin = f.mood === "ruin";
    g.fillStyle = TRIM[tier];
    g.fillRect(m.x0, gy, m.bw, 2);
    // shop windows (or a glass lobby on the big buildings)
    if (tier >= 3) {
      g.fillStyle = ruin ? "#1b1820" : "#6fa9cf";
      g.fillRect(m.x0 + 3, gy + 4, m.bw - 6, GH - 4);
      g.fillStyle = TRIM[tier];
      for (let x = m.x0 + 3; x < m.x0 + m.bw - 3; x += 8) g.fillRect(x, gy + 4, 1, GH - 4);
      g.fillRect(m.x0 + 3, gy + 11, m.bw - 6, 1);
    } else {
      for (const side of [-1, 1]) {
        const x = side < 0 ? m.x0 + 4 : m.x0 + m.bw - 4 - 16;
        g.fillStyle = TRIM[tier];
        g.fillRect(x - 1, gy + 12, 18, 11);
        g.fillStyle = ruin ? "#1b1820" : "#86bde0";
        g.fillRect(x, gy + 13, 16, 9);
        g.fillStyle = "#b9dcf2";
        g.fillRect(x + 1, gy + 14, 3, 1);
      }
    }
    // the door
    const dx = L.doorX;
    g.fillStyle = "#2b2533";
    g.fillRect(dx - 6, BASE - 14, 12, 14);
    if (ruin) {
      g.fillStyle = "#8a6a45";
      g.fillRect(dx - 6, BASE - 12, 12, 2);
      g.fillRect(dx - 6, BASE - 6, 12, 2);
      for (let i = 0; i < 10; i++) g.fillRect(dx - 5 + i, BASE - 12 + i, 2, 1);
      const w = textWidth(this.labels.closed) + 4;
      g.fillStyle = "#f4efe4";
      g.fillRect(dx - Math.round(w / 2), BASE - 10, w, 7);
      drawText(g, this.labels.closed, dx - Math.round(w / 2) + 2, BASE - 9, "#c0392b");
    } else {
      g.fillStyle = f.mood === "vacant" || f.mood === "dark" ? "#3c4a5a" : "#5d8fb0";
      g.fillRect(dx - 5, BASE - 13, 4, 13);
      g.fillRect(dx + 1, BASE - 13, 4, 13);
    }
    // awning (gone when the company is close to the end)
    if (tier >= 1 && !ruin && f.mood !== "dark" && f.mood !== "vacant") {
      for (let i = 0; i < 26; i++) {
        g.fillStyle = Math.floor(i / 3) % 2 ? "#ece2cc" : "#c8553d";
        g.fillRect(dx - 13 + i, BASE - 17, 1, 3);
        if (i % 3 === 1) g.fillRect(dx - 13 + i, BASE - 14, 1, 1);
      }
    }
    // the name board above the door (the big buildings carry a neon logo on the roof instead)
    if (tier <= 2) {
      const name = this.boardName();
      const w = textWidth(name) + 6;
      const x = Math.round(dx - w / 2);
      const y = gy + 2;
      g.fillStyle = "#231d2e";
      g.fillRect(x, y, w, 8);
      drawText(g, name, x + 3, y + 2, ruin ? "#5b5361" : "#ece2cc");
    }
    void t;
  }

  private drawRoof(g: CanvasRenderingContext2D, f: Fortune, L: Layout, t: number) {
    const m = L.main;
    const top = m.top - 2;
    const tier = f.tier;
    if (tier === 1) {
      g.fillStyle = "#8d8a94";
      g.fillRect(m.x0 + m.bw - 16, top - 5, 9, 5);
      g.fillStyle = "#6d6a74";
      g.fillRect(m.x0 + m.bw - 15, top - 4, 7, 1);
    }
    if (tier === 2) {
      g.fillStyle = "#6b4a35";
      g.fillRect(m.x0 + 10, top - 4, 1, 4);
      g.fillRect(m.x0 + 17, top - 4, 1, 4);
      g.fillStyle = "#8a6446";
      g.fillRect(m.x0 + 9, top - 13, 10, 9);
      g.fillStyle = "#6b4a35";
      g.fillRect(m.x0 + 9, top - 10, 10, 1);
    }
    if (tier >= 3) {
      // rooftop garden and flags
      if (tier === 3) {
        g.fillStyle = "#3f7a4a";
        for (let x = m.x0 + 2; x < m.x0 + m.bw - 4; x += 7) g.fillRect(x, top - 3, 5, 3);
      }
      for (const x of [m.x0 + 2, m.x0 + m.bw - 3]) {
        g.fillStyle = "#d9d4c8";
        g.fillRect(x, top - 14, 1, 14);
        const wave = Math.floor(t * 2.5 + x) % 2;
        g.fillStyle = x === m.x0 + 2 ? "#f2a541" : "#ece2cc";
        g.fillRect(x + 1, top - 14 + wave, 6, 2);
        g.fillRect(x + 1, top - 12, 5 + wave, 2);
      }
      // the logo frame (its letters glow in drawLights)
      const logoW = textWidth("D&C", 3) + 8;
      const lx = Math.round(m.x0 + m.bw / 2 - logoW / 2);
      g.fillStyle = "#3b3846";
      g.fillRect(lx + 3, top - 6, 1, 6);
      g.fillRect(lx + logoW - 4, top - 6, 1, 6);
      g.fillStyle = "#231d2e";
      g.fillRect(lx, top - 26, logoW, 20);
      drawText(g, "D&C", lx + 4, top - 23, f.mood === "ruin" ? "#4a4452" : "#8a3d5c", 3);
    }
    if (tier === 4) {
      g.fillStyle = "#c9c4b8";
      g.fillRect(m.x0 + m.bw - 12, top - 26, 1, 26);
      g.fillRect(m.x0 + m.bw - 14, top - 20, 5, 1);
      g.fillRect(m.x0 + m.bw - 13, top - 13, 3, 1);
    }
    // the studio's ON AIR sign, on the annex or the side of the building
    if (f.studio && f.mood !== "ruin") {
      const { x, y, w } = this.onAirSpot(L);
      g.fillStyle = "#3b3846";
      g.fillRect(x + 2, y + 7, 1, 3);
      g.fillRect(x + w - 3, y + 7, 1, 3);
      g.fillStyle = "#231d2e";
      g.fillRect(x, y, w, 7);
      drawText(g, this.labels.onAir, x + 2, y + 1, "#7a2a2a");
    }
  }

  private drawTraffic(g: CanvasRenderingContext2D, lane: 0 | 1) {
    for (const c of this.cars) {
      if (c.lane !== lane) continue;
      const y = lane === 0 ? 159 : 167; // wheel line
      const x = Math.round(c.x);
      const len = c.kind === "bus" ? 30 : c.kind === "van" ? 18 : 14;
      const right = c.speed > 0;
      const body = c.kind === "taxi" ? "#f2c230" : c.kind === "bus" ? "#d9822b" : c.color;
      g.fillStyle = body;
      if (c.kind === "bus") {
        g.fillRect(x, y - 9, len, 8);
        g.fillStyle = "#a9d4ee";
        for (let i = 2; i < len - 3; i += 4) g.fillRect(x + i, y - 7, 3, 3);
      } else if (c.kind === "van") {
        g.fillRect(x, y - 7, len, 6);
        g.fillStyle = "#a9d4ee";
        g.fillRect(right ? x + len - 5 : x + 1, y - 6, 4, 2);
      } else {
        g.fillRect(x, y - 4, len, 3);
        g.fillRect(x + 3, y - 6, 8, 2);
        g.fillStyle = "#a9d4ee";
        g.fillRect(x + 4, y - 6, 2, 2);
        g.fillRect(x + 8, y - 6, 2, 2);
        if (c.kind === "taxi") {
          g.fillStyle = "#fff4c0";
          g.fillRect(x + 6, y - 7, 2, 1);
        }
      }
      g.fillStyle = "#17161c";
      g.fillRect(x + 2, y - 1, 3, 2);
      g.fillRect(x + len - 5, y - 1, 3, 2);
    }
  }

  private drawWalkers(g: CanvasRenderingContext2D) {
    for (const w of this.walkers) {
      const x = Math.round(w.x);
      const y = w.y;
      g.globalAlpha = clamp(w.alpha);
      const step = w.still ? 0 : Math.floor(w.phase) % 2;
      g.fillStyle = "#2b2838";
      g.fillRect(x + (step ? 0 : 1), y - 2, 1, 2);
      g.fillRect(x + (step ? 2 : 1), y - 2, 1, 2);
      g.fillStyle = w.shirt;
      g.fillRect(x, y - 5, 3, 3);
      g.fillStyle = w.skin;
      g.fillRect(x + 1, y - 7, 2, 2);
      g.fillStyle = "#3a2a22";
      g.fillRect(x + 1, y - 8, 2, 1);
      g.globalAlpha = 1;
    }
  }

  /** Where the studio's sign hangs: on the annex roof, or on the main roof's corner. */
  private onAirSpot(L: Layout): { x: number; y: number; w: number } {
    const w = textWidth(this.labels.onAir) + 4;
    const host = L.annex ?? L.main;
    const x = L.annex ? Math.round(host.x0 + host.bw / 2 - w / 2) : L.main.x0 + 3;
    return { x, y: host.top - 12, w };
  }

  /** A banner across the second floor (for lease, new management, thank you). Drawn over lit windows. */
  private drawBanner(ctx: CanvasRenderingContext2D, f: Fortune, L: Layout, night: number) {
    const banner = f.ending === "fired" ? this.labels.newBoss : f.ending === "retired" ? this.labels.thanks
      : f.mood === "dark" || f.mood === "vacant" ? this.labels.forLease : null;
    if (!banner) return;
    const m = L.main;
    const floor = Math.min(m.floors, 2);
    const y = BASE - GH - floor * FH + 2;
    const w = textWidth(banner) + 6;
    const x = Math.round(m.x0 + m.bw / 2 - w / 2);
    const dim = 1 - 0.45 * night;
    const cloth = f.ending === "retired" ? hex("#f2c14e") : hex("#f4efe4");
    ctx.fillStyle = css([cloth[0] * dim, cloth[1] * dim, cloth[2] * dim]);
    ctx.fillRect(x, y, w, 9);
    ctx.fillStyle = "rgba(0,0,0,0.25)";
    ctx.fillRect(x, y + 8, w, 1);
    const ink = f.ending === "retired" ? hex("#5a2d0c") : hex("#c0392b");
    drawText(ctx, banner, x + 3, y + 2, css([ink[0] * dim, ink[1] * dim, ink[2] * dim]));
  }

  /** Is (x, y) behind the company's buildings or roof sign? (The glow pass has no depth.) */
  private hidden(x: number, y: number): boolean {
    const L = this.layout;
    if (!L) return false;
    for (const b of [L.main, ...(L.annex ? [L.annex] : [])]) {
      if (x >= b.x0 - 2 && x <= b.x0 + b.bw + 1 && y >= b.top - 3) return true;
    }
    if (this.fortune && this.fortune.tier >= 3) {
      const logoW = textWidth("D&C", 3) + 8;
      const lx = L.main.x0 + L.main.bw / 2 - logoW / 2;
      if (x >= lx - 1 && x <= lx + logoW && y >= L.main.top - 28) return true;
    }
    return false;
  }

  /** Everything that glows: drawn after night has darkened the street. */
  private drawLights(ctx: CanvasRenderingContext2D, night: number, t: number) {
    const f = this.fortune;
    const L = this.layout;
    // distant windows
    if (night > 0.2) {
      for (const b of this.skyline) {
        if (b.far) continue;
        for (let y = BASE - b.h + 4; y < BASE - 4; y += 5) {
          for (let x = b.x + 2; x < b.x + b.w - 2; x += 4) {
            if (this.hidden(x, y) || this.hidden(x + 1, y + 1)) continue;
            if (hash(x, y, Math.floor(t / 31 + hash(x, y, 1) * 9)) < 0.22) {
              ctx.fillStyle = `rgba(255,214,130,${0.55 * night})`;
              ctx.fillRect(x, y, 2, 2);
            }
          }
        }
      }
    }
    // street lamps
    if (night > 0.15) {
      for (const x of this.lampXs()) {
        ctx.fillStyle = `rgba(255,226,140,${0.13 * night})`;
        ctx.beginPath();
        ctx.moveTo(x + 4, BASE - 22);
        ctx.lineTo(x - 12, ROAD_TOP + 7);
        ctx.lineTo(x + 20, ROAD_TOP + 7);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = `rgba(255,244,190,${night})`;
        ctx.fillRect(x + 3, BASE - 22, 3, 1);
      }
    }
    if (f && L) {
      const lit = f.mood === "bright" ? 0.35 + 0.5 * clamp(f.staff / Math.max(1, L.main.wins.length * 0.6)) : f.mood === "dim" ? 0.3 : f.mood === "dark" ? 0.07 : 0;
      if (night > 0.05) {
        for (const b of [L.main, ...(L.annex ? [L.annex] : [])]) {
          for (const w of b.wins) {
            if (f.mood === "ruin" && w.floor === L.fireFloor) continue;
            if (hash(w.floor * 7 + (b === L.main ? 0 : 50), w.col, Math.floor(t / 19 + hash(w.col, w.floor, 5) * 7)) >= lit) continue;
            ctx.fillStyle = `rgba(255,206,110,${night})`;
            ctx.fillRect(w.x, w.y, 7, 7);
            ctx.fillStyle = `rgba(255,190,90,${0.18 * night})`;
            ctx.fillRect(w.x - 1, w.y - 1, 9, 9);
            if (hash(w.col, w.floor, 11) < 0.35) {
              ctx.fillStyle = `rgba(60,40,40,${0.8 * night})`;
              ctx.fillRect(w.x + 2, w.y + 3, 3, 4);
              ctx.fillRect(w.x + 3, w.y + 2, 1, 1);
            }
          }
        }
        // the lobby and shop windows
        if (f.mood === "bright" || f.mood === "dim") {
          ctx.fillStyle = `rgba(255,214,140,${0.45 * night})`;
          ctx.fillRect(L.doorX - 5, BASE - 13, 10, 13);
          const m = L.main;
          const gy = BASE - GH;
          ctx.fillStyle = `rgba(255,206,120,${0.35 * night})`;
          if (f.tier >= 3) ctx.fillRect(m.x0 + 3, gy + 12, m.bw - 6, GH - 12);
          else for (const x of [m.x0 + 4, m.x0 + m.bw - 20]) ctx.fillRect(x, gy + 13, 16, 9);
        }
      }
      // the neon logo on the big buildings
      if (f.tier >= 3 && f.mood !== "ruin" && f.mood !== "dark") {
        const flicker = f.mood === "dim" && hash(Math.floor(t * 6), 3) < 0.3;
        if (!flicker) {
          const logoW = textWidth("D&C", 3) + 8;
          const lx = Math.round(L.main.x0 + L.main.bw / 2 - logoW / 2);
          const y = L.main.top - 2 - 23;
          const a = 0.55 + 0.45 * night;
          ctx.globalAlpha = 0.35 * night;
          drawText(ctx, "D&C", lx + 3, y, "#ff5fa2", 3);
          drawText(ctx, "D&C", lx + 5, y, "#ff5fa2", 3);
          ctx.globalAlpha = a;
          drawText(ctx, "D&C", lx + 4, y, "#ff7cb6", 3);
          ctx.globalAlpha = 1;
        }
      }
      if (f.tier === 4 && Math.floor(t * 1.2) % 2 === 0) {
        ctx.fillStyle = "#ff3b3b";
        ctx.fillRect(L.main.x0 + L.main.bw - 12, L.main.top - 29, 1, 2);
      }
      // ON AIR
      if (f.studio && f.mood !== "ruin") {
        const { x, y } = this.onAirSpot(L);
        const on = 0.75 + 0.25 * Math.sin(t * 3);
        ctx.globalAlpha = on;
        drawText(ctx, this.labels.onAir, x + 2, y + 1, "#ff4a4a");
        ctx.globalAlpha = 1;
      }
      // the name board lights up at night
      if (f.tier <= 2 && (f.mood === "bright" || f.mood === "dim") && night > 0.1) {
        const name = this.boardName();
        const w = textWidth(name) + 6;
        ctx.globalAlpha = night;
        drawText(ctx, name, Math.round(L.doorX - w / 2) + 3, BASE - GH + 4, "#ffe2a6");
        ctx.globalAlpha = 1;
      }
      // fire
      if (f.mood === "ruin") {
        for (const w of L.main.wins.filter((x) => x.floor === L.fireFloor)) {
          ctx.fillStyle = `rgba(255,120,40,${0.2 + 0.25 * night})`;
          ctx.fillRect(w.x - 3, w.y - 6, 13, 15);
          for (let i = 0; i < 7; i++) {
            const h = 3 + Math.floor(hash(i, w.col, Math.floor(t * 10)) * 9);
            for (let k = 0; k < h; k++) {
              ctx.fillStyle = k < h * 0.4 ? "#ffe36e" : k < h * 0.75 ? "#ff8a2a" : "#d83a1f";
              ctx.fillRect(w.x + i, w.y + 6 - k, 1, 1);
            }
          }
        }
        for (const p of this.smoke) {
          ctx.fillStyle = `rgba(${110 + 40 * night},${96 + 10 * night},${100},${0.7 * (1 - p.life / p.max)})`;
          ctx.fillRect(Math.round(p.x), Math.round(p.y), Math.round(p.size), Math.round(p.size));
        }
      }
    }
    if (f && L) this.drawBanner(ctx, f, L, night);
    // headlights and tail lights
    if (night > 0.2) {
      for (const c of this.cars) {
        const y = c.lane === 0 ? 159 : 167;
        const len = c.kind === "bus" ? 30 : c.kind === "van" ? 18 : 14;
        const right = c.speed > 0;
        const fx = right ? c.x + len : c.x - 1;
        const by = c.kind === "bus" ? y - 4 : y - 3;
        ctx.fillStyle = `rgba(255,240,190,${0.16 * night})`;
        ctx.beginPath();
        ctx.moveTo(fx, by);
        ctx.lineTo(fx + (right ? 22 : -22), by - 3);
        ctx.lineTo(fx + (right ? 22 : -22), by + 4);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = `rgba(255,248,210,${night})`;
        ctx.fillRect(fx, by, 1, 1);
        ctx.fillStyle = `rgba(255,60,60,${night})`;
        ctx.fillRect(right ? c.x - 1 : c.x + len, by, 1, 1);
      }
    }
    // fireworks
    for (const p of this.sparks) {
      ctx.globalAlpha = clamp(1 - p.life / p.max);
      ctx.fillStyle = p.color;
      ctx.fillRect(Math.round(p.x), Math.round(p.y), 1, 1);
    }
    ctx.globalAlpha = 1;
  }
}
