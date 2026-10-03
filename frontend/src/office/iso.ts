// Isometric projection (2:1). Tile (x, y): x grows down-right, y grows down-left on screen.

export const TW = 32; // tile width in native pixels
export const TH = 16; // tile height in native pixels
export const MAP_W = 36;
export const MAP_H = 25;
export const MARGIN = 24;
export const OUTER_WALL_H = 46;
export const INNER_WALL_H = 9;

export const ORIGIN_X = MARGIN + MAP_H * (TW / 2);
export const ORIGIN_Y = MARGIN + OUTER_WALL_H + 6;
export const SCENE_W = Math.ceil(ORIGIN_X + MAP_W * (TW / 2) + MARGIN);
export const SCENE_H = Math.ceil(ORIGIN_Y + (MAP_W + MAP_H) * (TH / 2) + MARGIN);

export interface Pt {
  x: number;
  y: number;
}

/** Tile coordinates (fractional allowed) to native scene pixels. */
export function iso(x: number, y: number): Pt {
  return { x: ORIGIN_X + (x - y) * (TW / 2), y: ORIGIN_Y + (x + y) * (TH / 2) };
}

/** Native scene pixels to (fractional) tile coordinates. */
export function unIso(px: number, py: number): Pt {
  const a = (px - ORIGIN_X) / (TW / 2);
  const b = (py - ORIGIN_Y) / (TH / 2);
  return { x: (a + b) / 2, y: (b - a) / 2 };
}

/** Painter's algorithm key: larger = closer to the camera. */
export function depthOf(x: number, y: number): number {
  return x + y;
}
