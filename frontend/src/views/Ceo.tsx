import { api } from "../api/client";
import { useStore } from "../state/store";
import { shortDate } from "../util/format";
import { useLive } from "../util/hooks";

export function Ceo() {
  const state = useStore((s) => s.state);
  const { data } = useLive(() => api.management(), state?.clock.day_index);
  const ceo = state?.employees.find((e) => e.role === "ceo");
  return (
    <div className="page">
      <div className="panel">
        <h2>{ceo ? `${ceo.name} — ${state?.run.ceo_style_label}` : "CEO"}</h2>
        <div className="dim" style={{ marginTop: 4 }}>
          The CEO reviews the company every Monday (light) and on the 1st of each month (full review: people, money,
          desks, LAB). Every proposed action is validated; rejected actions are shown with the reason.
        </div>
      </div>
      {(data ?? []).map((m, i) => (
        <div className="panel" key={i}>
          <div className="panel-title">
            <h3>
              {m.scope} review · {shortDate(m.time)}
            </h3>
            <span className="muted">{m.actions.length} action(s)</span>
          </div>
          {m.thought && <div className="thought">“{m.thought}”</div>}
          {m.memo && <div className="memo" style={{ margin: "8px 0" }}>{m.memo}</div>}
          {m.actions.length > 0 && (
            <table>
              <tbody>
                {m.actions.map((a, j) => (
                  <tr key={j}>
                    <td style={{ width: 160 }}>
                      <span className={`pill ${a.applied ? "won" : "lost"}`}>{a.applied ? "done" : "rejected"}</span> {a.type}
                    </td>
                    <td>
                      {a.result}
                      {a.reason && <div className="muted">{a.reason}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}
      {data && !data.length && <div className="panel empty">No reviews yet. The first one happens on the next Monday.</div>}
    </div>
  );
}
