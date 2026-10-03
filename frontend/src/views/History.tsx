import { useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { monthLabel, shortDate } from "../util/format";
import { useLive } from "../util/hooks";

export function History() {
  const state = useStore((s) => s.state);
  const select = useStore((s) => s.selectEmployee);
  const openRecap = useStore((s) => s.setRecapOpen);
  const [minImp, setMinImp] = useState(2);
  const { data } = useLive(() => api.history(minImp), `${minImp}:${state?.clock.day_index}`);
  const groups: [string, NonNullable<typeof data>][] = [];
  for (const e of data ?? []) {
    const m = e.time.slice(0, 7);
    const g = groups[groups.length - 1];
    if (!g || g[0] !== m) groups.push([m, [e]]);
    else g[1].push(e);
  }
  return (
    <div className="page">
      <div className="panel">
        <div className="panel-title">
          <h2>Company history</h2>
          <div className="speed-group">
            {[
              [3, "Landmarks"],
              [2, "Notable"],
              [1, "Everything"],
            ].map(([v, label]) => (
              <button key={v} className={minImp === v ? "active" : ""} onClick={() => setMinImp(v as number)}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="timeline">
          {groups.map(([m, items]) => (
            <div key={m}>
              <div className="month">{monthLabel(m)}</div>
              {items.map((e) => (
                <div
                  key={e.id}
                  className={`tl-item tone-${e.tone} imp-${e.importance}`}
                  onClick={() =>
                    e.kind === "season_awards" && e.data.recap_id
                      ? openRecap(String(e.data.recap_id))
                      : e.employee_ids[0] && select(e.employee_ids[0])
                  }
                  style={{ cursor: e.employee_ids[0] || e.kind === "season_awards" ? "pointer" : "default", marginBottom: 4 }}
                >
                  <span className="muted">{shortDate(e.time)}</span>
                  <span className="bar" />
                  <span>
                    <b>{e.title}</b>
                    {e.text && <div className="dim">{e.text}</div>}
                  </span>
                </div>
              ))}
            </div>
          ))}
          {!groups.length && <div className="empty">History is still being written.</div>}
        </div>
      </div>
    </div>
  );
}
