import { useEffect, useRef } from "react";
import type { Appearance } from "../api/types";
import { characterFrames, lookFor } from "../office/sprites";

/** The employee's pixel sprite, scaled up for panels. */
export function Portrait({ appearance, color, role, size = 4 }: { appearance: Appearance; color: string; role: string; size?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, c.width, c.height);
    const sprite = characterFrames(lookFor(appearance, color, role)).frontWalk[0];
    ctx.drawImage(sprite, 0, 0, 16 * size, 24 * size);
  }, [appearance, color, role, size]);
  return <canvas ref={ref} className="portrait" width={16 * size} height={24 * size} style={{ width: 16 * size, height: 24 * size }} />;
}
