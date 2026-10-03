// Procedural pixel-art: characters, furniture and status icons. No external assets.

import type { Appearance } from "../api/types";
import { iso, TH, TW } from "./iso";
import type { Furniture } from "./layout";
import { fillPoly, isoBox, makeCanvas, outline, shade, tileDiamond, type Ctx } from "./pixel";

export const SPRITE_W = 16;
export const SPRITE_H = 24;

const SKIN = ["#f6d5b8", "#e8b996", "#c98e66", "#a86b46", "#7d4b2e", "#5a3420"];
const HAIR = ["#2b1d14", "#5b3a1e", "#a0622d", "#d9a441", "#e3dccd", "#b33a2b", "#4a58a8"];
const PANTS = ["#2f3640", "#4b3b2f", "#2c3e64", "#5c5c66", "#6e5f47"];
const SHIRT_SHADES = [0, -0.14, 0.14, -0.26, 0.24, -0.06, 0.32, -0.36];
const EYE = "#241a2b";

export interface Look {
  skin: string;
  hair: string;
  hairStyle: number;
  shirt: string;
  pants: string;
  accessory: number;
  role: string;
}

export function lookFor(a: Appearance, deptColor: string, role: string): Look {
  const base = role === "ceo" ? "#2c2436" : deptColor;
  return {
    skin: SKIN[a.skin % SKIN.length],
    hair: HAIR[a.hair_color % HAIR.length],
    hairStyle: a.hair_style % 7,
    shirt: shade(base, SHIRT_SHADES[a.shirt % SHIRT_SHADES.length] * (role === "ceo" ? 0.3 : 1)),
    pants: PANTS[a.pants % PANTS.length],
    accessory: role === "ceo" ? 3 : a.accessory % 5,
    role,
  };
}

export interface CharFrames {
  frontWalk: HTMLCanvasElement[];
  backWalk: HTMLCanvasElement[];
  frontSit: HTMLCanvasElement[];
  backSit: HTMLCanvasElement[];
}

const cache = new Map<string, CharFrames>();

export function characterFrames(look: Look): CharFrames {
  const key = JSON.stringify(look);
  let frames = cache.get(key);
  if (!frames) {
    frames = {
      frontWalk: [0, 1, 2, 3].map((f) => renderChar(look, "front", "walk", f)),
      backWalk: [0, 1, 2, 3].map((f) => renderChar(look, "back", "walk", f)),
      frontSit: [0, 1].map((f) => renderChar(look, "front", "sit", f)),
      backSit: [renderChar(look, "back", "sit", 0)],
    };
    cache.set(key, frames);
  }
  return frames;
}

function renderChar(L: Look, view: "front" | "back", pose: "walk" | "sit", frame: number): HTMLCanvasElement {
  const c = makeCanvas(SPRITE_W, SPRITE_H);
  const ctx = c.getContext("2d")!;
  const px = (x: number, y: number, w: number, h: number, col: string) => {
    ctx.fillStyle = col;
    ctx.fillRect(x, y, w, h);
  };
  const shirtDark = shade(L.shirt, -0.25);
  const coat = L.role === "researcher";
  const torso = coat ? "#e8edf0" : L.shirt;
  const torsoDark = coat ? "#c3cbd1" : shirtDark;
  const pantsDark = shade(L.pants, -0.3);
  const shoe = "#1d1720";

  // ---- legs ----
  if (pose === "walk") {
    const lf = frame === 1 ? 1 : 0;
    const rf = frame === 3 ? 1 : 0;
    px(5, 16, 2, 5 - rf, L.pants);
    px(9, 16, 2, 5 - lf, L.pants);
    px(6, 16, 1, 5 - rf, pantsDark);
    px(10, 16, 1, 5 - lf, pantsDark);
    px(frame === 1 ? 4 : 5, 21 - rf, 2, 1, shoe);
    px(frame === 3 ? 10 : 9, 21 - lf, 2, 1, shoe);
  } else {
    px(4, 16, 8, 2, L.pants);
    px(4, 17, 8, 1, pantsDark);
  }
  // ---- torso & arms ----
  px(4, 10, 8, 6, torso);
  px(11, 10, 1, 6, torsoDark);
  px(4, 15, 8, 1, torsoDark);
  if (coat) {
    px(7, 10, 2, 5, L.shirt);
    if (pose === "walk") px(4, 16, 8, 1, "#e8edf0");
  }
  if (view === "front") {
    px(7, 10, 2, 1, L.skin); // collar
    if (L.accessory === 3) px(7, 11, 2, 4, L.role === "ceo" ? "#c23b3b" : "#b8323a");
    if (L.role === "ceo") {
      px(6, 10, 1, 2, "#e8e4ea");
      px(9, 10, 1, 2, "#e8e4ea");
    }
  }
  if (pose === "sit" && view === "front") {
    const up = frame === 1 ? 1 : 0;
    px(3, 10, 1, 4, torso);
    px(12, 10, 1, 4, torsoDark);
    px(4, 13 - up, 1, 2, L.skin);
    px(11, 13 - (1 - up), 1, 2, L.skin);
  } else {
    const swing = pose === "walk" && (frame === 1 || frame === 3) ? (frame === 1 ? 1 : -1) : 0;
    px(3, 10 + Math.max(0, swing), 1, 5, torso);
    px(12, 10 + Math.max(0, -swing), 1, 5, torsoDark);
    px(3, 15 + Math.max(0, swing), 1, 1, L.skin);
    px(12, 15 + Math.max(0, -swing), 1, 1, L.skin);
  }
  // ---- head ----
  px(7, 9, 2, 1, shade(L.skin, -0.15));
  px(5, 3, 6, 6, L.skin);
  px(10, 3, 1, 6, shade(L.skin, -0.12));
  if (view === "front") {
    px(6, 6, 1, 1, EYE);
    px(9, 6, 1, 1, EYE);
    px(7, 8, 2, 1, shade(L.skin, -0.22));
  }
  drawHair(px, L, view);
  // ---- accessories ----
  if (L.accessory === 1 && view === "front") {
    px(5, 6, 2, 1, "#2a2a33");
    px(9, 6, 2, 1, "#2a2a33");
    px(7, 6, 2, 1, "#55556a");
  } else if (L.accessory === 2) {
    px(5, 1, 6, 1, "#2a2a33");
    px(4, 4, 1, 3, "#2a2a33");
    px(11, 4, 1, 3, "#2a2a33");
  } else if (L.accessory === 4) {
    px(4, 2, 8, 2, "#2f6fb0");
    if (view === "front") px(4, 4, 8, 1, "#24578c");
  }
  outline(c);
  return c;
}

type Px = (x: number, y: number, w: number, h: number, c: string) => void;

function drawHair(px: Px, L: Look, view: "front" | "back"): void {
  const h = L.hair;
  const hd = shade(h, -0.25);
  if (view === "back") {
    switch (L.hairStyle) {
      case 3:
        px(5, 6, 6, 1, h);
        return;
      case 1:
        px(4, 2, 8, 9, h);
        px(4, 10, 8, 1, hd);
        return;
      case 5:
        px(3, 0, 10, 8, h);
        return;
      case 2:
        px(5, 2, 6, 6, h);
        px(7, 0, 2, 2, hd);
        return;
      default:
        px(5, 2, 6, 6, h);
        px(5, 7, 6, 1, hd);
        return;
    }
  }
  switch (L.hairStyle) {
    case 0:
      px(5, 2, 6, 2, h);
      px(5, 4, 1, 1, h);
      px(10, 4, 1, 1, h);
      break;
    case 1:
      px(4, 2, 8, 2, h);
      px(4, 4, 1, 7, h);
      px(11, 4, 1, 7, hd);
      break;
    case 2:
      px(5, 2, 6, 2, h);
      px(7, 0, 2, 2, hd);
      break;
    case 3:
      px(5, 5, 1, 1, hd);
      px(10, 5, 1, 1, hd);
      break;
    case 4:
      px(5, 2, 6, 2, h);
      px(5, 1, 1, 1, h);
      px(7, 0, 1, 2, h);
      px(9, 1, 1, 1, h);
      break;
    case 5:
      px(3, 0, 10, 4, h);
      px(3, 4, 2, 3, h);
      px(11, 4, 2, 3, hd);
      break;
    default:
      px(4, 2, 8, 2, h);
      px(4, 4, 2, 4, h);
      px(10, 4, 2, 2, hd);
  }
}

// ---------------------------------------------------------------------------- status icons
export type IconKind =
  | "question" | "chart" | "ball" | "alert" | "cloud" | "star" | "bulb" | "dots" | "coffee" | "zzz" | "box" | "euro";

const iconCache = new Map<string, HTMLCanvasElement>();

export function icon(kind: IconKind): HTMLCanvasElement {
  let c = iconCache.get(kind);
  if (c) return c;
  c = makeCanvas(13, 13);
  const ctx = c.getContext("2d")!;
  const px = (x: number, y: number, w: number, h: number, col: string) => {
    ctx.fillStyle = col;
    ctx.fillRect(x, y, w, h);
  };
  if (kind !== "box") {
    px(1, 0, 11, 10, "#fdf6e3");
    px(0, 1, 13, 8, "#fdf6e3");
    px(4, 10, 3, 1, "#fdf6e3");
    px(4, 11, 1, 1, "#fdf6e3");
  }
  const ink = "#2b2130";
  switch (kind) {
    case "question":
      px(5, 2, 3, 1, ink); px(8, 3, 1, 2, ink); px(6, 5, 2, 1, ink); px(6, 7, 1, 1, ink);
      break;
    case "chart":
      px(2, 7, 9, 1, ink); px(3, 5, 1, 2, "#3aa35b"); px(5, 4, 1, 3, "#3aa35b"); px(7, 3, 1, 4, "#3aa35b"); px(9, 2, 1, 5, "#3aa35b");
      break;
    case "euro":
      px(5, 2, 4, 1, "#c98a1a"); px(4, 3, 1, 4, "#c98a1a"); px(5, 7, 4, 1, "#c98a1a"); px(3, 4, 5, 1, "#c98a1a"); px(3, 6, 5, 1, "#c98a1a");
      break;
    case "ball":
      px(4, 2, 5, 6, ink); px(5, 3, 3, 4, "#fdf6e3"); px(6, 4, 1, 1, ink); px(4, 2, 1, 1, "#fdf6e3"); px(8, 2, 1, 1, "#fdf6e3"); px(4, 7, 1, 1, "#fdf6e3"); px(8, 7, 1, 1, "#fdf6e3");
      break;
    case "alert":
      px(5, 1, 1, 5, "#d6323a"); px(7, 1, 1, 5, "#d6323a"); px(5, 7, 1, 1, "#d6323a"); px(7, 7, 1, 1, "#d6323a");
      break;
    case "cloud":
      px(3, 3, 7, 3, "#5d5a6b"); px(4, 2, 3, 1, "#5d5a6b"); px(7, 2, 2, 1, "#5d5a6b"); px(5, 6, 1, 2, "#4a7bd1"); px(8, 6, 1, 2, "#4a7bd1");
      break;
    case "star":
      px(6, 1, 1, 7, "#e0a21b"); px(3, 4, 7, 1, "#e0a21b"); px(4, 2, 1, 1, "#e0a21b"); px(8, 2, 1, 1, "#e0a21b"); px(4, 6, 1, 1, "#e0a21b"); px(8, 6, 1, 1, "#e0a21b");
      break;
    case "bulb":
      px(5, 1, 3, 1, "#e8b923"); px(4, 2, 5, 3, "#f5d547"); px(5, 5, 3, 1, "#e8b923"); px(5, 6, 3, 1, "#8a8a99"); px(6, 7, 1, 1, "#8a8a99");
      break;
    case "dots":
      px(3, 4, 1, 1, ink); px(6, 4, 1, 1, ink); px(9, 4, 1, 1, ink);
      break;
    case "coffee":
      px(4, 3, 4, 4, "#8a5a3a"); px(8, 4, 1, 2, "#8a5a3a"); px(4, 7, 5, 1, ink); px(5, 1, 1, 1, "#b8b8c8"); px(6, 2, 1, 1, "#b8b8c8");
      break;
    case "zzz":
      px(3, 2, 3, 1, "#4a58a8"); px(4, 3, 1, 1, "#4a58a8"); px(3, 4, 3, 1, "#4a58a8"); px(7, 5, 3, 1, "#4a58a8"); px(8, 6, 1, 1, "#4a58a8"); px(7, 7, 3, 1, "#4a58a8");
      break;
    case "box":
      px(2, 4, 9, 7, "#b58a5a"); px(2, 4, 9, 2, "#c99d6b"); px(6, 4, 1, 7, "#8d6a42");
      break;
  }
  iconCache.set(kind, c);
  return c;
}

// ---------------------------------------------------------------------------- furniture
export interface Prerendered {
  canvas: HTMLCanvasElement;
  ox: number; // scene position of the canvas' top-left
  oy: number;
}

const FURNITURE_HEIGHT: Record<string, number> = {
  bookshelf: 40, server: 40, arcade: 32, coffee: 26, cooler: 24, trophies: 26, cabinet: 20, plant: 22,
  noticeboard: 26, sofa: 18, desk: 20, lab_desk: 20, ceo_desk: 22, meeting_table: 16, foosball: 14, chair: 14,
  beanbag: 10, box: 10, rug: 2, mat: 2, vacant_sign: 2,
};

export function prerenderFurniture(f: Furniture): Prerendered {
  const h = FURNITURE_HEIGHT[f.kind] ?? 16;
  const left = iso(f.x, f.y + f.d).x - 2;
  const right = iso(f.x + f.w, f.y).x + 2;
  const top = iso(f.x, f.y).y - h - 8;
  const bottom = iso(f.x + f.w, f.y + f.d).y + 2;
  const canvas = makeCanvas(Math.ceil(right - left), Math.ceil(bottom - top));
  const ctx = canvas.getContext("2d")!;
  ctx.translate(-Math.floor(left), -Math.floor(top));
  drawFurniture(ctx, f);
  return { canvas, ox: Math.floor(left), oy: Math.floor(top) };
}

function blob(ctx: Ctx, cx: number, cy: number, r: number, col: string): void {
  ctx.fillStyle = col;
  for (let dy = -r; dy <= r; dy++) {
    const w = Math.round(Math.sqrt(r * r - dy * dy));
    ctx.fillRect(Math.round(cx - w), Math.round(cy + dy), w * 2 + 1, 1);
  }
}

function drawFurniture(ctx: Ctx, f: Furniture): void {
  const { x, y, w, d } = f;
  const wood = { top: "#c99260", left: "#9a6a3f", right: "#7d5233" };
  switch (f.kind) {
    case "desk": {
      isoBox(ctx, x + 0.05, y + 0.1, w - 0.1, d - 0.2, 9, wood);
      isoBox(ctx, x + 0.75, y + 0.15, 0.5, 0.18, 9, { top: "#3a3646", left: "#2b2733", right: "#211e29" }, 9);
      isoBox(ctx, x + 0.95, y + 0.3, 0.1, 0.1, 2, { top: "#3a3646", left: "#2b2733", right: "#211e29" }, 8);
      isoBox(ctx, x + 1.45, y + 0.5, 0.3, 0.25, 2, { top: "#f2efe6", left: "#d8d3c6", right: "#c4bfb2" }, 9);
      break;
    }
    case "lab_desk":
      isoBox(ctx, x + 0.05, y + 0.1, w - 0.1, d - 0.2, 9, { top: "#e2e6ea", left: "#b4bcc6", right: "#98a1ad" });
      isoBox(ctx, x + 0.6, y + 0.15, 0.7, 0.16, 10, { top: "#3a3646", left: "#2b2733", right: "#211e29" }, 9);
      break;
    case "ceo_desk":
      isoBox(ctx, x, y + 0.05, w, d - 0.1, 11, { top: "#8a4a33", left: "#6e3b2a", right: "#552c1f" });
      isoBox(ctx, x + 1.2, y + 0.15, 0.6, 0.15, 10, { top: "#3a3646", left: "#2b2733", right: "#211e29" }, 11);
      isoBox(ctx, x + 0.3, y + 0.6, 0.4, 0.15, 2, { top: "#e2b23a", left: "#b88b22", right: "#9a7419" }, 11);
      break;
    case "meeting_table":
      isoBox(ctx, x + 0.1, y + 0.1, w - 0.2, d - 0.2, 9, { top: "#d8b98a", left: "#b39167", right: "#97774f" });
      for (let i = 0; i < 3; i++)
        isoBox(ctx, x + 0.6 + i * 1.2, y + 0.7, 0.35, 0.25, 1, { top: "#3c3a4a", left: "#2b2733", right: "#211e29" }, 9);
      break;
    case "chair":
      isoBox(ctx, x + 0.22, y + 0.22, 0.56, 0.56, 5, { top: "#4a4258", left: "#3a3346", right: "#2d2738" });
      isoBox(ctx, x + 0.22, y + 0.18, 0.56, 0.12, 9, { top: "#4a4258", left: "#3a3346", right: "#2d2738" }, 5);
      break;
    case "plant": {
      isoBox(ctx, x + 0.3, y + 0.3, 0.4, 0.4, 6, { top: "#5b3a24", left: "#b5603a", right: "#94492b" });
      const c = iso(x + 0.5, y + 0.5);
      blob(ctx, c.x, c.y - 12, 5, "#3a6b2d");
      blob(ctx, c.x - 3, c.y - 14, 3, "#4f8a3c");
      blob(ctx, c.x + 3, c.y - 16, 3, "#6fae4f");
      blob(ctx, c.x, c.y - 19, 2, "#6fae4f");
      break;
    }
    case "bookshelf": {
      isoBox(ctx, x + 0.05, y, 0.6, d, 36, { top: "#7a4f35", left: "#5e3b27", right: "#4a2e1e" });
      const cols = ["#b33a2b", "#3d6fb5", "#e0a21b", "#3aa35b", "#8a4fb5", "#e8e0d0"];
      for (let row = 0; row < 4; row++) {
        for (let i = 0; i < 6; i++) {
          const p = iso(x + 0.65, y + 0.15 + i * 0.3);
          ctx.fillStyle = cols[(row * 3 + i) % cols.length];
          ctx.fillRect(Math.round(p.x) - 1, Math.round(p.y) - 8 - row * 8, 2, 6);
        }
      }
      break;
    }
    case "trophies": {
      isoBox(ctx, x + 0.05, y + 0.1, 0.6, 0.8, 18, { top: "#5e3b27", left: "#4a2e1e", right: "#3b2418" });
      const p = iso(x + 0.35, y + 0.5);
      ctx.fillStyle = "#e2b23a";
      ctx.fillRect(Math.round(p.x) - 2, Math.round(p.y) - 24, 4, 3);
      ctx.fillRect(Math.round(p.x) - 1, Math.round(p.y) - 21, 2, 2);
      ctx.fillStyle = "#c9c9d6";
      ctx.fillRect(Math.round(p.x) + 3, Math.round(p.y) - 22, 3, 2);
      break;
    }
    case "server":
      isoBox(ctx, x + 0.1, y + 0.1, 0.8, 0.8, 36, { top: "#3d4454", left: "#2d3340", right: "#232833" });
      break;
    case "sofa":
      isoBox(ctx, x, y + 0.2, w, d - 0.3, 6, { top: "#4f97a1", left: "#3e7c86", right: "#2f6169" });
      isoBox(ctx, x, y + 0.05, w, 0.25, 14, { top: "#4f97a1", left: "#3e7c86", right: "#2f6169" });
      isoBox(ctx, x, y + 0.05, 0.2, d - 0.2, 10, { top: "#4f97a1", left: "#3e7c86", right: "#2f6169" });
      isoBox(ctx, x + w - 0.2, y + 0.05, 0.2, d - 0.2, 10, { top: "#4f97a1", left: "#3e7c86", right: "#2f6169" });
      break;
    case "beanbag": {
      const c = iso(x + 0.5, y + 0.5);
      blob(ctx, c.x, c.y - 3, 6, f.y % 2 ? "#c25b9a" : "#e08a3a");
      blob(ctx, c.x - 1, c.y - 5, 4, f.y % 2 ? "#d877b0" : "#f0a45a");
      break;
    }
    case "coffee":
      isoBox(ctx, x + 0.1, y + 0.1, 0.8, 0.8, 10, { top: "#9a8e7c", left: "#7a6f60", right: "#61584c" });
      isoBox(ctx, x + 0.25, y + 0.25, 0.5, 0.5, 14, { top: "#3a3646", left: "#2b2733", right: "#211e29" }, 10);
      break;
    case "cooler":
      isoBox(ctx, x + 0.25, y + 0.25, 0.5, 0.5, 12, { top: "#e6e9ee", left: "#c4c9d1", right: "#a9afb9" });
      isoBox(ctx, x + 0.3, y + 0.3, 0.4, 0.4, 10, { top: "#9ccbf0", left: "#6aa9de", right: "#4f8fc6" }, 12);
      break;
    case "foosball":
      isoBox(ctx, x + 0.1, y + 0.15, w - 0.2, d - 0.3, 10, { top: "#3f8f4a", left: "#7a5232", right: "#603f26" });
      for (let i = 0; i < 4; i++) {
        const a = iso(x + 0.4 + i * 0.4, y + 0.1);
        const b = iso(x + 0.4 + i * 0.4, y + 0.9);
        fillPoly(ctx, [{ x: a.x, y: a.y - 11 }, { x: b.x, y: b.y - 11 }, { x: b.x + 1, y: b.y - 10 }, { x: a.x + 1, y: a.y - 10 }], "#c9c9d6");
      }
      break;
    case "arcade":
      isoBox(ctx, x + 0.15, y + 0.15, 0.7, 0.7, 28, { top: "#4a2e6e", left: "#3a2358", right: "#2c1a44" });
      break;
    case "cabinet":
      isoBox(ctx, x + 0.15, y + 0.15, 0.7, 0.6, 18, { top: "#a4aab5", left: "#8d939e", right: "#727884" });
      for (let i = 0; i < 3; i++) {
        const p = iso(x + 0.15, y + 0.75);
        const q = iso(x + 0.85, y + 0.75);
        ctx.fillStyle = "#5c616b";
        ctx.fillRect(Math.round(p.x) + 2, Math.round(p.y) - 5 - i * 5, Math.round(q.x - p.x) - 4, 1);
      }
      break;
    case "box":
      isoBox(ctx, x + 0.2, y + 0.2, 0.6, 0.6, 8, { top: "#c99d6b", left: "#b58a5a", right: "#987247" });
      break;
    case "noticeboard":
      isoBox(ctx, x + 0.1, y + 0.4, 0.8, 0.12, 20, { top: "#a87b4f", left: "#c4935f", right: "#8d643d" }, 2);
      break;
    case "rug":
      for (let yy = y; yy < y + d; yy++) for (let xx = x; xx < x + w; xx++) tileDiamond(ctx, xx, yy, "#8c2f39", 0.04);
      for (let yy = y; yy < y + d; yy++) for (let xx = x; xx < x + w; xx++) tileDiamond(ctx, xx, yy, "#a33a45", 0.2);
      break;
    case "mat":
      tileDiamond(ctx, x, y, "#7a2f2f", 0.08);
      tileDiamond(ctx, x, y, "#a54444", 0.22);
      break;
    case "vacant_sign":
      tileDiamond(ctx, x, y, "#2c2533", 0.15);
      break;
  }
}

/** Approximate pixel footprint centre for dynamic overlays (monitor glow, LEDs). */
export function furnitureAnchor(f: Furniture): { x: number; y: number } {
  return iso(f.x + f.w / 2, f.y + f.d / 2);
}

export const TILE = { w: TW, h: TH };
