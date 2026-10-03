// Crisp pixel-art primitives. Canvas paths anti-alias; scanline spans of fillRect do not.

import { iso, type Pt } from "./iso";

export type Ctx = CanvasRenderingContext2D;

/** Fill a convex polygon with hard pixel edges. */
export function fillPoly(ctx: Ctx, pts: Pt[], color: string): void {
  let minY = Infinity;
  let maxY = -Infinity;
  for (const p of pts) {
    minY = Math.min(minY, p.y);
    maxY = Math.max(maxY, p.y);
  }
  ctx.fillStyle = color;
  const y0 = Math.round(minY);
  const y1 = Math.round(maxY);
  for (let y = y0; y < y1; y++) {
    const sy = y + 0.5;
    let lo = Infinity;
    let hi = -Infinity;
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i];
      const b = pts[(i + 1) % pts.length];
      if ((a.y <= sy && b.y > sy) || (b.y <= sy && a.y > sy)) {
        const x = a.x + ((sy - a.y) / (b.y - a.y)) * (b.x - a.x);
        lo = Math.min(lo, x);
        hi = Math.max(hi, x);
      }
    }
    if (hi > lo) ctx.fillRect(Math.round(lo), y, Math.max(1, Math.round(hi) - Math.round(lo)), 1);
  }
}

export interface BoxColors {
  top: string;
  left: string;
  right: string;
  edge?: string;
}

/** An isometric box standing on tile (x, y) with footprint wx × wy tiles and height h pixels. */
export function isoBox(ctx: Ctx, x: number, y: number, wx: number, wy: number, h: number, c: BoxColors, lift = 0): void {
  const p0 = iso(x, y);
  const p1 = iso(x + wx, y);
  const p2 = iso(x + wx, y + wy);
  const p3 = iso(x, y + wy);
  const up = (p: Pt, d: number) => ({ x: p.x, y: p.y - d });
  const base = lift;
  const top = lift + h;
  fillPoly(ctx, [up(p3, base), up(p2, base), up(p2, top), up(p3, top)], c.left);
  fillPoly(ctx, [up(p2, base), up(p1, base), up(p1, top), up(p2, top)], c.right);
  fillPoly(ctx, [up(p0, top), up(p1, top), up(p2, top), up(p3, top)], c.top);
  if (c.edge) {
    ctx.fillStyle = c.edge;
    const a = up(p2, top);
    ctx.fillRect(Math.round(a.x), Math.round(a.y), 1, Math.max(1, Math.round(h)));
  }
}

export function tileDiamond(ctx: Ctx, x: number, y: number, color: string, inset = 0): void {
  const p0 = iso(x + inset, y + inset);
  const p1 = iso(x + 1 - inset, y + inset);
  const p2 = iso(x + 1 - inset, y + 1 - inset);
  const p3 = iso(x + inset, y + 1 - inset);
  fillPoly(ctx, [p0, p1, p2, p3], color);
}

// ------------------------------------------------------------------ colour helpers
export function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function rgbToHex(r: number, g: number, b: number): string {
  const c = (v: number) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0");
  return `#${c(r)}${c(g)}${c(b)}`;
}

/** amount > 0 lightens towards white, < 0 darkens towards black. */
export function shade(hex: string, amount: number): string {
  const [r, g, b] = hexToRgb(hex);
  if (amount >= 0) return rgbToHex(r + (255 - r) * amount, g + (255 - g) * amount, b + (255 - b) * amount);
  return rgbToHex(r * (1 + amount), g * (1 + amount), b * (1 + amount));
}

export function mix(a: string, b: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(a);
  const [r2, g2, b2] = hexToRgb(b);
  return rgbToHex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t);
}

export function makeCanvas(w: number, h: number): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  return c;
}

/** Add a 1px dark outline around every opaque pixel cluster (readability on busy floors). */
export function outline(canvas: HTMLCanvasElement, color = [27, 20, 38, 220]): void {
  const ctx = canvas.getContext("2d")!;
  const { width: w, height: h } = canvas;
  const img = ctx.getImageData(0, 0, w, h);
  const src = new Uint8ClampedArray(img.data);
  const a = (x: number, y: number) => (x < 0 || y < 0 || x >= w || y >= h ? 0 : src[(y * w + x) * 4 + 3]);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (a(x, y) > 0) continue;
      if (a(x - 1, y) > 128 || a(x + 1, y) > 128 || a(x, y - 1) > 128 || a(x, y + 1) > 128) {
        const i = (y * w + x) * 4;
        img.data[i] = color[0];
        img.data[i + 1] = color[1];
        img.data[i + 2] = color[2];
        img.data[i + 3] = color[3];
      }
    }
  }
  ctx.putImageData(img, 0, 0);
}
