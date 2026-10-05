import { describe, expect, it } from "vitest";
import { MAP_H, iso, unIso } from "./iso";
import { buildLayout, roomAt, walkable } from "./layout";
import { findPath } from "./pathfind";

const ALL = new Set([0, 1, 2, 3, 4, 5]);

describe("iso projection", () => {
  it("round-trips tile coordinates", () => {
    for (const [x, y] of [
      [0, 0],
      [3.5, 7.25],
      [35, 24],
    ]) {
      const p = iso(x, y);
      const t = unIso(p.x, p.y);
      expect(t.x).toBeCloseTo(x, 6);
      expect(t.y).toBeCloseTo(y, 6);
    }
  });
});

describe("office layout", () => {
  it("covers every tile of the building with exactly one room", () => {
    for (const leased of [new Set<string>(), new Set(["studio"]), new Set(["canteen", "desk_wing", "studio"])]) {
      const L = buildLayout(ALL, leased);
      expect(L.width).toBe(leased.size ? 47 : 36);
      for (let y = 0; y < MAP_H; y++) for (let x = 0; x < L.width; x++) expect(roomAt(L, x, y)).not.toBeNull();
      expect(roomAt(L, L.width, 3)).toBeNull();
    }
  });

  it("the east wing's rooms are reachable once leased, and lots are locked", () => {
    const L = buildLayout(new Set([0, 1, 2, 3, 4, 5, 6]), new Set(["canteen", "desk_wing", "studio"]));
    for (const s of [...L.canteenSeats, ...L.studioSeats, ...L.deskSeats[6]]) {
      expect(findPath(L, L.entrance, s), `no path to ${s.key}`).not.toBeNull();
    }
    expect(L.canteenSeats.length).toBe(12);
    const partial = buildLayout(new Set([0]), new Set(["canteen"]));
    expect(roomAt(partial, 40, 12)?.kind).toBe("lot");
    expect(walkable(partial, 40, 12)).toBe(false);
    expect(partial.furniture.some((f) => f.slot === 6)).toBe(false);
  });

  it("every seat and spot is reachable from the entrance", () => {
    for (const active of [ALL, new Set([0, 1, 2, 3]), new Set<number>()]) {
      const L = buildLayout(active);
      const spots = [
        ...Object.values(L.deskSeats).flat().filter((_, i) => active.has(Math.floor(i / 5))),
        ...L.meetingSeats,
        L.meetingHead,
        L.ceoSeat,
        ...L.labDesks,
        ...L.labBoards,
        ...L.benchSpots,
        ...L.corridorSpots,
      ];
      for (const s of spots) {
        const path = findPath(L, L.entrance, s);
        expect(path, `no path to ${s.key}`).not.toBeNull();
      }
    }
  });

  it("paths never cross walls or furniture", () => {
    const L = buildLayout(ALL);
    const path = findPath(L, L.entrance, L.ceoSeat)!;
    let prev = { x: L.entrance.x, y: L.entrance.y };
    for (const p of path.slice(0, -1)) {
      expect(walkable(L, Math.floor(p.x), Math.floor(p.y))).toBe(true);
      expect(Math.abs(p.x - prev.x) + Math.abs(p.y - prev.y)).toBeCloseTo(1, 6);
      prev = p;
    }
  });

  it("vacant rooms have no desk seats furniture", () => {
    const L = buildLayout(new Set([0]));
    const desks = L.furniture.filter((f) => f.kind === "desk");
    expect(desks.every((f) => f.slot === 0)).toBe(true);
    expect(desks).toHaveLength(5);
  });
});
