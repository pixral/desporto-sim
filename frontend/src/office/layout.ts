// The office floor plan. Everything (walls, walkability, seats) is derived from room rectangles.
//
//   y 0-6   CEO office | Meeting room | LAB | The Bench (lounge)
//   y 7-8   corridor ─────────────────────────────────────┐
//   y 9-15  desk slot 0 | desk slot 1 | desk slot 2       │ east corridor
//   y16-17  corridor ─────────────────────────────────────┤
//   y18-24  desk slot 3 | desk slot 4 | desk slot 5       │ entrance (bottom)
//
// The east wing (x 36-46) next door appears once the company leases any of it:
//   y 0-6   the canteen (door from The Bench)
//   y 7-15  corridor + desk slot 6        (the "desk wing")
//   y16-24  corridor + media studio
// Plots that are not leased are drawn as empty, locked lots.

import { MAP_H, MAP_W, type Pt } from "./iso";

export type RoomKind = "ceo" | "meeting" | "lab" | "bench" | "corridor" | "desk" | "canteen" | "studio" | "lot";
export type Face = "front" | "back";
/** Map direction a seated person faces: N = -y (up-right on screen), S = +y, E = +x, W = -x. */
export type Dir = "N" | "S" | "E" | "W";

export interface Room {
  id: string;
  kind: RoomKind;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  slot?: number;
  label: string;
}

export interface Furniture {
  kind: string;
  x: number;
  y: number;
  w: number;
  d: number;
  blocks: boolean;
  depthBias?: number;
  slot?: number;
  index?: number;
  face?: Dir; // chairs: the way the sitter faces (the backrest is on the opposite side)
  part?: "seat" | "back"; // chairs whose backrest is nearer the camera than the sitter are drawn in two pieces
}

export interface Spot {
  x: number; // tile coords of the standing/sitting point (tile centre = +0.5)
  y: number;
  pose: "sit" | "stand";
  face: Face;
  flip: boolean; // true = facing left on screen
  key: string;
}

export interface Wall {
  x: number;
  y: number;
  side: "N" | "W";
  outer: boolean;
}

export interface Layout {
  rooms: Room[];
  roomGrid: (Room | null)[];
  furniture: Furniture[];
  walls: Wall[];
  blocked: Uint8Array;
  wallN: Uint8Array;
  wallW: Uint8Array;
  deskSeats: Record<number, Spot[]>;
  meetingSeats: Spot[];
  meetingHead: Spot;
  ceoSeat: Spot;
  ceoVisitors: Spot[];
  labDesks: Spot[];
  labBoards: Spot[];
  benchSpots: Spot[];
  corridorSpots: Spot[];
  canteenSeats: Spot[];
  studioSeats: Spot[];
  entrance: Spot;
  activeSlots: Set<number>;
  leased: Set<string>;
  width: number; // tiles across: 36, or 47 with the east wing
}

export const BASE_W = 36;
export const ANNEX_X = 36;
/** Facility key -> the lot it occupies in the east wing. */
export const LOTS: Record<string, { y0: number; y1: number; label: string }> = {
  canteen: { y0: 0, y1: 7, label: "CANTEEN" },
  desk_wing: { y0: 7, y1: 16, label: "DESK WING" },
  studio: { y0: 16, y1: 25, label: "STUDIO" },
};

export const SLOT_ORIGINS: Pt[] = [
  { x: 0, y: 9 },
  { x: 11, y: 9 },
  { x: 22, y: 9 },
  { x: 0, y: 18 },
  { x: 11, y: 18 },
  { x: 22, y: 18 },
  { x: 36, y: 9 }, // east desk wing
];
export const SLOT_W = 11;
export const SLOT_D = 7;

const idx = (x: number, y: number) => y * MAP_W + x;

function spot(x: number, y: number, pose: "sit" | "stand", face: Face, flip: boolean, key: string): Spot {
  return { x: x + 0.5, y: y + 0.5, pose, face, flip, key };
}

export function buildLayout(activeSlots: Set<number>, leased: Set<string> = new Set()): Layout {
  const annex = leased.size > 0;
  const width = annex ? MAP_W : BASE_W;
  const rooms: Room[] = [
    { id: "ceo", kind: "ceo", x0: 0, y0: 0, x1: 8, y1: 7, label: "CEO OFFICE" },
    { id: "meeting", kind: "meeting", x0: 8, y0: 0, x1: 16, y1: 7, label: "MEETING ROOM" },
    { id: "lab", kind: "lab", x0: 16, y0: 0, x1: 26, y1: 7, label: "LAB" },
    { id: "bench", kind: "bench", x0: 26, y0: 0, x1: 36, y1: 7, label: "THE BENCH" },
    { id: "c1", kind: "corridor", x0: 0, y0: 7, x1: 33, y1: 9, label: "" },
    { id: "c2", kind: "corridor", x0: 0, y0: 16, x1: 33, y1: 18, label: "" },
    { id: "c3", kind: "corridor", x0: 33, y0: 7, x1: 36, y1: 25, label: "" },
  ];
  SLOT_ORIGINS.slice(0, 6).forEach((o, slot) =>
    rooms.push({ id: `slot${slot}`, kind: "desk", x0: o.x, y0: o.y, x1: o.x + SLOT_W, y1: o.y + SLOT_D, slot, label: "" }),
  );
  if (annex) {
    const x0 = ANNEX_X;
    const x1 = MAP_W;
    for (const [key, lot] of Object.entries(LOTS)) {
      if (!leased.has(key)) {
        rooms.push({ id: `lot-${key}`, kind: "lot", x0, y0: lot.y0, x1, y1: lot.y1, label: lot.label });
      } else if (key === "canteen") {
        rooms.push({ id: "canteen", kind: "canteen", x0, y0: 0, x1, y1: 7, label: "THE CANTEEN" });
      } else if (key === "desk_wing") {
        rooms.push({ id: "c1e", kind: "corridor", x0, y0: 7, x1, y1: 9, label: "" });
        const o = SLOT_ORIGINS[6];
        rooms.push({ id: "slot6", kind: "desk", x0: o.x, y0: o.y, x1: o.x + SLOT_W, y1: o.y + SLOT_D, slot: 6, label: "" });
      } else {
        rooms.push({ id: "c2e", kind: "corridor", x0, y0: 16, x1, y1: 18, label: "" });
        rooms.push({ id: "studio", kind: "studio", x0, y0: 18, x1, y1: 25, label: "MEDIA STUDIO" });
      }
    }
  }
  const roomGrid: (Room | null)[] = new Array(MAP_W * MAP_H).fill(null);
  for (const r of rooms) for (let y = r.y0; y < r.y1; y++) for (let x = r.x0; x < r.x1; x++) roomGrid[idx(x, y)] = r;

  // ---- doors (edges that stay open) ----------------------------------------------------
  const open = new Set<string>();
  const door = (x: number, y: number, side: "N" | "W") => open.add(`${x},${y},${side}`);
  [5, 6].forEach((x) => door(x, 7, "N")); // CEO office
  [14, 15].forEach((x) => door(x, 7, "N")); // meeting room
  [19, 20].forEach((x) => door(x, 7, "N")); // LAB
  [29, 30].forEach((x) => door(x, 7, "N")); // bench
  [7, 8, 16, 17].forEach((y) => door(33, y, "W")); // corridor junctions
  SLOT_ORIGINS.forEach((o) => [o.x + 9, o.x + 10].forEach((x) => door(x, o.y, "N")));
  if (leased.has("canteen")) door(ANNEX_X, 4, "W"); // from The Bench
  if (leased.has("desk_wing")) [7, 8].forEach((y) => door(ANNEX_X, y, "W"));
  if (leased.has("studio")) {
    [16, 17].forEach((y) => door(ANNEX_X, y, "W"));
    [37, 38].forEach((x) => door(x, 18, "N"));
  }

  const walls: Wall[] = [];
  const wallN = new Uint8Array(MAP_W * MAP_H);
  const wallW = new Uint8Array(MAP_W * MAP_H);
  for (const r of rooms) {
    for (let x = r.x0; x < r.x1; x++) {
      const outer = r.y0 === 0;
      if (outer || roomGrid[idx(x, r.y0 - 1)] !== r) {
        if (!open.has(`${x},${r.y0},N`)) {
          walls.push({ x, y: r.y0, side: "N", outer });
          wallN[idx(x, r.y0)] = 1;
        }
      }
    }
    for (let y = r.y0; y < r.y1; y++) {
      const outer = r.x0 === 0;
      if (outer || roomGrid[idx(r.x0 - 1, y)] !== r) {
        if (!open.has(`${r.x0},${y},W`)) {
          walls.push({ x: r.x0, y, side: "W", outer });
          wallW[idx(r.x0, y)] = 1;
        }
      }
    }
  }

  // ---- furniture ------------------------------------------------------------------------
  const F: Furniture[] = [];
  const add = (kind: string, x: number, y: number, w = 1, d = 1, blocks = true, extra: Partial<Furniture> = {}) =>
    F.push({ kind, x, y, w, d, blocks, ...extra });
  const chair = (x: number, y: number, face: Dir, extra: Partial<Furniture> = {}) => {
    if (face === "S" || face === "E") {
      add("chair", x, y, 1, 1, false, { depthBias: -0.6, face, ...extra });
    } else {
      // backrest between the sitter and the camera: seat behind the person, backrest in front
      add("chair", x, y, 1, 1, false, { depthBias: -0.6, face, part: "seat", ...extra });
      add("chair", x, y, 1, 1, false, { depthBias: 0.3, face, part: "back", ...extra });
    }
  };

  // CEO office
  add("rug", 1, 2, 5, 3, false, { depthBias: -100 });
  // big pieces get an explicit depth so people behind them are hidden and visitors in front are not
  add("ceo_desk", 2, 3, 3, 1, true, { depthBias: 0.2 });
  chair(3, 2, "S");
  add("bookshelf", 0, 1, 1, 2);
  add("trophies", 0, 4, 1, 1);
  add("plant", 7, 0);
  chair(2, 4, "N"); // visitors face the CEO across the desk
  chair(4, 4, "N");
  // Meeting room
  add("meeting_table", 10, 2, 3, 2, true, { depthBias: 0.9 });
  for (let x = 10; x < 13; x++) {
    chair(x, 1, "S");
    chair(x, 4, "N");
  }
  chair(9, 2, "E");
  chair(9, 3, "E");
  add("plant", 8, 6);
  add("plant", 15, 0);
  // LAB
  [17, 20, 23].forEach((x, i) => {
    chair(x, 3, "S");
    add("lab_desk", x, 4, 2, 1, true, { index: i });
  });
  add("server", 25, 0);
  add("server", 25, 1);
  add("server", 25, 2);
  add("plant", 16, 6);
  // The Bench (lounge)
  add("sofa", 28, 0, 3, 1, false, { depthBias: -0.7 });
  add("coffee", 35, 1);
  add("cooler", 35, 3);
  add("foosball", 31, 4, 2, 1);
  add("beanbag", 27, 4, 1, 1, false, { depthBias: -0.7 });
  add("beanbag", 27, 5, 1, 1, false, { depthBias: -0.7 });
  add("arcade", 35, 5);
  add("plant", 26, 6);
  add("plant", 35, 0);
  // corridors
  add("plant", 0, 8);
  add("plant", 32, 7);
  add("plant", 0, 17);
  add("noticeboard", 12, 7, 1, 1, false, { depthBias: -100 });
  // east wing
  if (leased.has("canteen")) {
    add("counter", 37, 0, 5, 1, true, { depthBias: 0.4 });
    add("fridge", 43, 0);
    add("fridge", 44, 0);
    add("plant", 46, 0);
    add("plant", 46, 6);
    for (const [tx, ty] of [[38, 3], [42, 3], [40, 5]]) {
      add("cafe_table", tx, ty, 2, 1, true, { depthBias: 0.5 });
      chair(tx, ty - 1, "S");
      chair(tx + 1, ty - 1, "S");
      if (ty + 1 < 7) {
        chair(tx, ty + 1, "N");
        chair(tx + 1, ty + 1, "N");
      }
    }
  }
  if (leased.has("studio")) {
    add("backdrop", 39, 18, 5, 1, true, { depthBias: -0.4 });
    add("studio_desk", 40, 21, 3, 1, true, { depthBias: 0.5 });
    chair(40, 20, "S");
    chair(42, 20, "S");
    add("camera", 41, 23);
    add("camera", 44, 22);
    add("lamp_stand", 38, 22);
    add("lamp_stand", 45, 20);
    add("plant", 46, 24);
  }
  if (leased.has("desk_wing")) add("plant", 46, 7);
  for (const [key, lot] of Object.entries(LOTS)) {
    if (annex && !leased.has(key)) {
      add("box", ANNEX_X + 3, lot.y0 + 2, 1, 1, true);
      add("box", ANNEX_X + 7, lot.y0 + 4, 1, 1, true);
      add("sawhorse", ANNEX_X + 5, lot.y0 + 3, 2, 1, true);
    }
  }
  // desk rooms
  SLOT_ORIGINS.forEach((o, slot) => {
    if (slot === 6 && !leased.has("desk_wing")) return;
    if (activeSlots.has(slot)) {
      const desks = [
        [o.x + 1, o.y + 1],
        [o.x + 4, o.y + 1],
        [o.x + 7, o.y + 1],
        [o.x + 2, o.y + 4],
        [o.x + 5, o.y + 4],
      ];
      desks.forEach(([cx, cy], i) => {
        chair(cx, cy, "S", { slot, index: i });
        add("desk", cx, cy + 1, 2, 1, true, { slot, index: i });
      });
      add("plant", o.x + 10, o.y + 6, 1, 1, true, { slot });
      add("cabinet", o.x, o.y, 1, 1, true, { slot });
    } else {
      add("box", o.x + 2, o.y + 2, 1, 1, true, { slot });
      add("box", o.x + 7, o.y + 4, 1, 1, true, { slot });
      chair(o.x + 5, o.y + 5, "E", { slot });
    }
  });

  const blocked = new Uint8Array(MAP_W * MAP_H);
  for (const f of F) {
    if (!f.blocks) continue;
    for (let y = f.y; y < f.y + f.d; y++) for (let x = f.x; x < f.x + f.w; x++) blocked[idx(x, y)] = 1;
  }

  // ---- seats & spots -------------------------------------------------------------------
  const deskSeats: Record<number, Spot[]> = {};
  SLOT_ORIGINS.forEach((o, slot) => {
    deskSeats[slot] = [
      spot(o.x + 1, o.y + 1, "sit", "front", true, `desk${slot}-0`),
      spot(o.x + 4, o.y + 1, "sit", "front", true, `desk${slot}-1`),
      spot(o.x + 7, o.y + 1, "sit", "front", true, `desk${slot}-2`),
      spot(o.x + 2, o.y + 4, "sit", "front", true, `desk${slot}-3`),
      spot(o.x + 5, o.y + 4, "sit", "front", true, `desk${slot}-4`),
    ];
  });
  const meetingSeats: Spot[] = [];
  for (let x = 10; x < 13; x++) meetingSeats.push(spot(x, 1, "sit", "front", true, `meet-n${x}`));
  for (let x = 10; x < 13; x++) meetingSeats.push(spot(x, 4, "sit", "back", false, `meet-s${x}`));
  meetingSeats.push(spot(9, 2, "sit", "front", false, "meet-w2"), spot(9, 3, "sit", "front", false, "meet-w3"));
  const canteenSeats: Spot[] = [];
  if (leased.has("canteen")) {
    for (const [tx, ty] of [[38, 3], [42, 3], [40, 5]]) {
      for (const dx of [0, 1]) {
        canteenSeats.push(spot(tx + dx, ty - 1, "sit", "front", true, `canteen-${tx + dx}-${ty - 1}`));
        if (ty + 1 < 7) canteenSeats.push(spot(tx + dx, ty + 1, "sit", "back", false, `canteen-${tx + dx}-${ty + 1}`));
      }
    }
  }
  const studioSeats: Spot[] = leased.has("studio")
    ? [spot(40, 20, "sit", "front", true, "studio-0"), spot(42, 20, "sit", "front", true, "studio-1")]
    : [];
  const benchSpots: Spot[] = [
    spot(28, 0, "sit", "front", false, "sofa0"),
    spot(29, 0, "sit", "front", true, "sofa1"),
    spot(30, 0, "sit", "front", true, "sofa2"),
    spot(27, 4, "sit", "front", false, "bean0"),
    spot(27, 5, "sit", "front", false, "bean1"),
    spot(30, 4, "stand", "front", false, "foos0"),
    spot(33, 4, "stand", "back", true, "foos1"),
    spot(34, 1, "stand", "front", false, "coffee"),
    spot(34, 3, "stand", "front", false, "cooler"),
    spot(34, 5, "stand", "front", false, "arcade"),
    spot(31, 2, "stand", "front", false, "chat0"),
    spot(32, 2, "stand", "front", true, "chat1"),
    spot(29, 3, "stand", "front", false, "chat2"),
    spot(30, 6, "stand", "back", true, "chat3"),
  ];
  const corridorSpots: Spot[] = [
    spot(2, 8, "stand", "front", false, "cor0"),
    spot(3, 8, "stand", "front", true, "cor1"),
    spot(9, 7, "stand", "front", false, "cor2"),
    spot(17, 8, "stand", "front", true, "cor3"),
    spot(25, 7, "stand", "front", false, "cor4"),
    spot(5, 16, "stand", "front", false, "cor5"),
    spot(6, 16, "stand", "front", true, "cor6"),
    spot(14, 17, "stand", "front", false, "cor7"),
    spot(27, 16, "stand", "front", true, "cor8"),
    spot(34, 12, "stand", "front", false, "cor9"),
  ];
  return {
    rooms,
    roomGrid,
    furniture: F,
    walls,
    blocked,
    wallN,
    wallW,
    deskSeats,
    meetingSeats,
    meetingHead: spot(13, 2, "stand", "front", true, "meet-head"),
    ceoSeat: spot(3, 2, "sit", "front", true, "ceo"),
    ceoVisitors: [spot(2, 4, "sit", "back", false, "ceo-v0"), spot(4, 4, "sit", "back", false, "ceo-v1")],
    labDesks: [17, 20, 23].map((x, i) => spot(x, 3, "sit", "front", true, `lab${i}`)),
    labBoards: [spot(18, 1, "stand", "back", false, "board0"), spot(22, 1, "stand", "back", true, "board1")],
    benchSpots,
    corridorSpots,
    canteenSeats,
    studioSeats,
    entrance: spot(34, 24, "stand", "front", false, "entrance"),
    activeSlots,
    leased,
    width,
  };
}

export function roomAt(layout: Layout, x: number, y: number): Room | null {
  const tx = Math.floor(x);
  const ty = Math.floor(y);
  if (tx < 0 || ty < 0 || tx >= MAP_W || ty >= MAP_H) return null;
  return layout.roomGrid[idx(tx, ty)];
}

export function walkable(layout: Layout, x: number, y: number): boolean {
  if (x < 0 || y < 0 || x >= MAP_W || y >= MAP_H) return false;
  const room = layout.roomGrid[idx(x, y)];
  return room !== null && room.kind !== "lot" && !layout.blocked[idx(x, y)];
}

/** Can you step from (x, y) to the 4-neighbour (nx, ny) without crossing a wall? */
export function canStep(layout: Layout, x: number, y: number, nx: number, ny: number): boolean {
  if (!walkable(layout, nx, ny)) return false;
  if (nx === x + 1) return !layout.wallW[idx(nx, ny)];
  if (nx === x - 1) return !layout.wallW[idx(x, y)];
  if (ny === y + 1) return !layout.wallN[idx(nx, ny)];
  if (ny === y - 1) return !layout.wallN[idx(x, y)];
  return false;
}
