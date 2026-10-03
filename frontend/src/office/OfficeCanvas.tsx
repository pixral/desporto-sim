import { useEffect, useRef, useState } from "react";
import type { EmployeeCard } from "../api/types";
import { latestState, useStore } from "../state/store";
import { pct } from "../util/format";
import { OfficeRenderer } from "./renderer";

interface Hover {
  emp: EmployeeCard;
  x: number;
  y: number;
}

export function OfficeCanvas() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<OfficeRenderer | null>(null);
  const [hover, setHover] = useState<Hover | null>(null);
  const [names, setNames] = useState(false);
  const [legend, setLegend] = useState(() => {
    try {
      return localStorage.getItem("office-legend") !== "hidden";
    } catch {
      return true;
    }
  });
  const toggleLegend = () => {
    setLegend((v) => {
      try {
        localStorage.setItem("office-legend", v ? "hidden" : "shown");
      } catch {
        /* private mode */
      }
      return !v;
    });
  };
  const [cursor, setCursor] = useState("");
  const selectEmployee = useStore((s) => s.selectEmployee);
  const selectDepartment = useStore((s) => s.selectDepartment);

  useEffect(() => {
    const canvas = canvasRef.current!;
    const wrap = wrapRef.current!;
    const r = new OfficeRenderer(canvas);
    rendererRef.current = r;
    const ro = new ResizeObserver(() => {
      const rect = wrap.getBoundingClientRect();
      r.resize(rect.width, rect.height, window.devicePixelRatio || 1);
    });
    ro.observe(wrap);
    let raf = 0;
    const loop = (t: number) => {
      r.selectedId = useStore.getState().selectedEmployee;
      if (import.meta.env.DEV) (window as unknown as { __office: OfficeRenderer }).__office = r;
      r.frame(latestState(), t);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    document.fonts?.load("12px Silkscreen");
    document.fonts?.load("16px VT323");
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  useEffect(() => {
    if (rendererRef.current) rendererRef.current.showNames = names;
  }, [names]);

  // ------------------------------------------------------------------ input
  const drag = useRef<{ x: number; y: number; moved: number } | null>(null);
  const local = (e: React.MouseEvent | React.WheelEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const onDown = (e: React.MouseEvent) => {
    const p = local(e);
    drag.current = { x: p.x, y: p.y, moved: 0 };
  };
  const onMove = (e: React.MouseEvent) => {
    const r = rendererRef.current;
    if (!r) return;
    const p = local(e);
    if (drag.current && e.buttons & 1) {
      const dx = p.x - drag.current.x;
      const dy = p.y - drag.current.y;
      drag.current.moved += Math.abs(dx) + Math.abs(dy);
      drag.current.x = p.x;
      drag.current.y = p.y;
      r.pan(dx, dy);
      if (drag.current.moved > 4) {
        setCursor("dragging");
        setHover(null);
      }
      return;
    }
    const hit = r.pick(p.x, p.y, latestState());
    r.hoveredId = hit.actorId ?? null;
    const emp = hit.actorId ? latestState()?.employees.find((x) => x.id === hit.actorId) : undefined;
    setHover(emp ? { emp, x: p.x, y: p.y } : null);
    setCursor(hit.actorId || hit.departmentId ? "pointer" : "");
  };
  const onUp = (e: React.MouseEvent) => {
    const r = rendererRef.current;
    const d = drag.current;
    drag.current = null;
    setCursor("");
    if (!r || !d || d.moved > 4) return;
    const p = local(e);
    const hit = r.pick(p.x, p.y, latestState());
    if (hit.actorId) selectEmployee(hit.actorId);
    else if (hit.departmentId) selectDepartment(hit.departmentId);
    else selectEmployee(null);
  };
  const onWheel = (e: React.WheelEvent) => {
    const p = local(e);
    rendererRef.current?.zoomAt(e.deltaY < 0 ? 1.25 : 0.8, p.x, p.y);
  };
  const zoom = (f: number) => {
    const r = rendererRef.current;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (r && rect) r.zoomAt(f, rect.width / 2, rect.height / 2);
  };

  return (
    <div className="office-wrap" ref={wrapRef}>
      <canvas
        ref={canvasRef}
        className={cursor}
        onMouseDown={onDown}
        onMouseMove={onMove}
        onMouseUp={onUp}
        onMouseLeave={() => {
          drag.current = null;
          setHover(null);
          if (rendererRef.current) rendererRef.current.hoveredId = null;
        }}
        onWheel={onWheel}
        aria-label="The office. Click a person or a desk for details."
      />
      {hover && (
        <div className="tooltip" style={{ left: Math.min(hover.x + 16, (wrapRef.current?.clientWidth ?? 800) - 290), top: hover.y + 16 }}>
          <div className="name">{hover.emp.name}</div>
          <div className="dim">
            {hover.emp.title} · {hover.emp.specialty_label}
          </div>
          <div style={{ marginTop: 4 }}>{hover.emp.task || hover.emp.status}</div>
          {hover.emp.thought && <div className="thought">“{hover.emp.thought}”</div>}
          {hover.emp.role !== "ceo" && (
            <div className="muted" style={{ marginTop: 4 }}>
              mood {hover.emp.mood} · stress {pct(hover.emp.stress, 0)} · rep {hover.emp.reputation.toFixed(0)}
              {hover.emp.under_review ? " · UNDER REVIEW" : ""}
            </div>
          )}
        </div>
      )}
      {legend && (
        <div className="office-legend">
          Drag to pan · scroll to zoom · click a person or a desk. Bubbles: <b>?</b> analyzing, <b>€</b> bet placed, ball
          watching, bulb researching, cloud frustrated, red <b>!!</b> stressed, orange <b>!</b> under review. Yellow dotted
          line: someone followed a colleague's call.
        </div>
      )}
      <div className="office-tools">
        <button onClick={toggleLegend} className={legend ? "active" : ""} aria-label="Show legend">
          ?
        </button>
        <button onClick={() => setNames((v) => !v)} className={names ? "active" : ""}>
          Names
        </button>
        <button onClick={() => zoom(0.8)} aria-label="Zoom out">
          −
        </button>
        <button onClick={() => zoom(1.25)} aria-label="Zoom in">
          +
        </button>
        <button onClick={() => rendererRef.current?.fit()}>Fit</button>
      </div>
    </div>
  );
}
