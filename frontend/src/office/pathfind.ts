// A* over the office grid (4-neighbour, walls block edges).

import { MAP_H, MAP_W, type Pt } from "./iso";
import { canStep, type Layout } from "./layout";

export function findPath(layout: Layout, from: Pt, to: Pt): Pt[] | null {
  const sx = Math.floor(from.x);
  const sy = Math.floor(from.y);
  const tx = Math.floor(to.x);
  const ty = Math.floor(to.y);
  if (sx === tx && sy === ty) return [];
  const N = MAP_W * MAP_H;
  const g = new Float64Array(N).fill(Infinity);
  const came = new Int32Array(N).fill(-1);
  const closed = new Uint8Array(N);
  const open: number[] = [];
  const f = new Float64Array(N).fill(Infinity);
  const start = sy * MAP_W + sx;
  const goal = ty * MAP_W + tx;
  g[start] = 0;
  f[start] = Math.abs(tx - sx) + Math.abs(ty - sy);
  open.push(start);
  const dirs = [
    [1, 0],
    [-1, 0],
    [0, 1],
    [0, -1],
  ];
  while (open.length) {
    let bi = 0;
    for (let i = 1; i < open.length; i++) if (f[open[i]] < f[open[bi]]) bi = i;
    const cur = open[bi];
    open.splice(bi, 1);
    if (cur === goal) break;
    if (closed[cur]) continue;
    closed[cur] = 1;
    const cx = cur % MAP_W;
    const cy = (cur - cx) / MAP_W;
    for (const [dx, dy] of dirs) {
      const nx = cx + dx;
      const ny = cy + dy;
      const isGoal = nx === tx && ny === ty;
      if (nx < 0 || ny < 0 || nx >= MAP_W || ny >= MAP_H) continue;
      // the goal may be a seat on a "blocking" tile; allow stepping onto it
      if (!canStep(layout, cx, cy, nx, ny) && !(isGoal && edgeOpen(layout, cx, cy, nx, ny))) continue;
      const ni = ny * MAP_W + nx;
      const ng = g[cur] + 1;
      if (ng < g[ni]) {
        g[ni] = ng;
        came[ni] = cur;
        f[ni] = ng + Math.abs(tx - nx) + Math.abs(ty - ny);
        open.push(ni);
      }
    }
  }
  if (came[goal] === -1) return null;
  const path: Pt[] = [];
  let c = goal;
  while (c !== start) {
    const x = c % MAP_W;
    path.push({ x: x + 0.5, y: (c - x) / MAP_W + 0.5 });
    c = came[c];
  }
  return path.reverse();
}

function edgeOpen(layout: Layout, x: number, y: number, nx: number, ny: number): boolean {
  const i = (px: number, py: number) => py * MAP_W + px;
  if (nx === x + 1) return !layout.wallW[i(nx, ny)];
  if (nx === x - 1) return !layout.wallW[i(x, y)];
  if (ny === y + 1) return !layout.wallN[i(nx, ny)];
  if (ny === y - 1) return !layout.wallN[i(x, y)];
  return false;
}
