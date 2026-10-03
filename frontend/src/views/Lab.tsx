import { api } from "../api/client";
import { useStore } from "../state/store";
import { eur, pct, shortDate, tone } from "../util/format";
import { useLive } from "../util/hooks";

const REC_PILL: Record<string, string> = { DEPLOY: "won", PROMISING: "open", REJECT: "lost" };

export function Lab() {
  const state = useStore((s) => s.state);
  const select = useStore((s) => s.selectEmployee);
  const { data } = useLive(() => api.lab(), state?.clock.day_index);
  if (!data) return <div className="page empty">Loading the LAB…</div>;
  const running = data.experiments.filter((x) => x.status === "running");
  const done = data.experiments.filter((x) => x.status !== "running");
  return (
    <div className="page">
      <div className="grid-2">
        <div className="panel">
          <div className="panel-title">
            <h2>Research team</h2>
            <span className="muted">budget {eur(data.budget)}/month</span>
          </div>
          {data.researchers.map((r) => (
            <div key={r.id} className="panel-title" style={{ cursor: "pointer" }} onClick={() => select(r.id)}>
              <span>
                <b>{r.name}</b> <span className="muted">· {r.specialty_label}</span>
              </span>
              <span className="dim">{r.task}</span>
            </div>
          ))}
          {!data.researchers.length && <div className="empty">The LAB is empty. The CEO can hire researchers.</div>}
          <h3 style={{ marginTop: 14 }}>Running experiments</h3>
          {running.map((x) => (
            <div key={x.id} style={{ margin: "8px 0" }}>
              <b>{x.name}</b> <span className="muted">· {x.researcher} · due {shortDate(x.due)}</span>
              <div className="dim">{x.hypothesis}</div>
            </div>
          ))}
          {!running.length && <div className="muted">Nothing running.</div>}
        </div>
        <div className="panel">
          <h2 style={{ marginBottom: 10 }}>Audit findings</h2>
          {data.audit.map((a) => (
            <div key={a.id} style={{ margin: "6px 0" }} className={a.resolved ? "muted" : ""}>
              <span className="muted">{shortDate(a.day)}</span> {a.text} {a.resolved && "(fixed)"}
            </div>
          ))}
          {!data.audit.length && <div className="muted">No weak spots flagged yet. Audits run at each month close.</div>}
        </div>
      </div>
      <div className="panel" style={{ marginTop: 16 }}>
        <h2 style={{ marginBottom: 10 }}>Experiments</h2>
        {!done.length ? (
          <div className="empty">No completed experiments yet.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="tab-nums">
              <thead>
                <tr>
                  <th>Finished</th>
                  <th>Strategy</th>
                  <th className="r">Bets</th>
                  <th className="r">ROI</th>
                  <th className="r">Win rate</th>
                  <th>Verdict</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {done.map((x) => (
                  <tr key={x.id} title={x.rationale}>
                    <td className="muted">{x.completed ? shortDate(x.completed) : "—"}</td>
                    <td>
                      <b>{x.name}</b> <span className="muted">by {x.researcher}</span>
                      <div className="dim">{x.hypothesis}</div>
                    </td>
                    <td className="r">{x.result?.sample_size ?? "—"}</td>
                    <td className={`r ${tone(x.result?.roi)}`}>{x.result ? pct(x.result.roi, 1, true) : "—"}</td>
                    <td className="r">{x.result ? pct(x.result.win_rate, 0) : "—"}</td>
                    <td>
                      <span className={`pill ${REC_PILL[x.recommendation] ?? "void"}`}>{x.recommendation || "—"}</span>
                    </td>
                    <td>{x.status === "deployed" ? `live: ${x.deployed_names.join(", ")}` : x.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <div className="panel" style={{ marginTop: 16 }}>
        <h2 style={{ marginBottom: 10 }}>Strategies in use</h2>
        <table className="tab-nums">
          <thead>
            <tr>
              <th>Strategy</th>
              <th>Used by</th>
              <th className="r">Live bets</th>
              <th className="r">Live ROI</th>
              <th className="r">Backtest ROI</th>
            </tr>
          </thead>
          <tbody>
            {data.strategies.map((s) => (
              <tr key={s.id} className={s.users.length ? "" : "inactive"}>
                <td>
                  <b>{s.name}</b> <span className="muted">({s.origin})</span>
                  <div className="dim">{s.summary}</div>
                </td>
                <td>{s.users.join(", ") || "retired"}</td>
                <td className="r">{s.live_bets}</td>
                <td className={`r ${tone(s.live_roi)}`}>{pct(s.live_roi, 1, true)}</td>
                <td className="r">{s.backtest_roi !== null ? `${pct(s.backtest_roi, 1, true)} (${s.backtest_n})` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
