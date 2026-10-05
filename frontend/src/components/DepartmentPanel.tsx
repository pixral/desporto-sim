import { api } from "../api/client";
import { useStore } from "../state/store";
import { eur, monthLabel, pct, shortDate, signedEur, tone } from "../util/format";
import { useLive } from "../util/hooks";
import { DeskActions } from "./CeoActions";
import { ColumnChart } from "./charts";
import { Portrait } from "./Portrait";

export function DepartmentPanel({ id }: { id: string }) {
  const state = useStore((s) => s.state);
  const close = useStore((s) => s.selectDepartment);
  const selectEmployee = useStore((s) => s.selectEmployee);
  const { data: d, reload } = useLive(() => api.department(id), `${id}:${state?.clock.day_index}`);
  const color = state?.departments.find((x) => x.id === id)?.color ?? "#888";
  return (
    <div className="drawer" role="dialog" aria-label="Department details">
      <div className="drawer-head" style={{ boxShadow: `inset 6px 0 0 ${color}` }}>
        <div style={{ flex: 1 }}>
          <h2>{d?.name ?? "…"}</h2>
          {d && (
            <div className="muted">
              Founded {shortDate(d.founded)} · {d.competitions.join(", ") || "research"}
              {d.head ? ` · head: ${d.head}` : ""}
            </div>
          )}
        </div>
        <button onClick={() => close(null)} aria-label="Close">
          ✕
        </button>
      </div>
      <div className="drawer-body">
        {!d ? (
          <div className="empty">Loading…</div>
        ) : (
          <>
            <DeskActions d={d} onDone={reload} />
            {d.kind !== "lab" && (
              <div className="panel">
                <div className="stats">
                  <div className="stat">
                    <div className="label">Bankroll</div>
                    <div className="value">{eur(d.bankroll)}</div>
                  </div>
                  <div className="stat">
                    <div className="label">Max stake</div>
                    <div className="value">{pct(d.stake_limit_pct, 1)}</div>
                  </div>
                  <div className="stat">
                    <div className="label">This month</div>
                    <div className={`value ${tone(d.month_profit)}`}>{signedEur(d.month_profit)}</div>
                  </div>
                  <div className="stat">
                    <div className="label">All time</div>
                    <div className={`value ${tone(d.total_profit)}`}>{signedEur(d.total_profit)}</div>
                  </div>
                  <div className="stat">
                    <div className="label">ROI (90 days)</div>
                    <div className="value">{pct(d.last90.roi, 1, true)}</div>
                  </div>
                  <div className="stat">
                    <div className="label">Bets (90 days)</div>
                    <div className="value">{d.last90.bets}</div>
                  </div>
                </div>
              </div>
            )}
            {d.kind !== "lab" && d.book_limits?.length > 0 && (
              <div className="panel">
                <h3>Bookmaker limits</h3>
                <div className="muted" style={{ margin: "4px 0 8px" }}>
                  Most a bookmaker accepts from this desk on one bet. Soft books cut it for desks that keep winning
                  their money; bets then go to worse prices elsewhere.
                </div>
                <table>
                  <tbody>
                    {d.book_limits.map((b) => (
                      <tr key={b.book}>
                        <td>{b.book}</td>
                        <td className="r">{eur(b.limit)}</td>
                        <td className="r">
                          {b.limit < b.default ? (
                            <span className="pill lost">limited</span>
                          ) : (
                            <span className="muted">normal</span>
                          )}
                        </td>
                        <td className="r muted">{b.bets} bets</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {Object.keys(d.profit_by_month).length > 0 && (
              <div className="panel">
                <h3>Profit by month</h3>
                <ColumnChart
                  height={180}
                  data={Object.entries(d.profit_by_month).map(([k, v]) => ({ label: monthLabel(k), value: v }))}
                  format={(v) => eur(v)}
                />
              </div>
            )}
            <div className="panel">
              <h3>People</h3>
              {d.members.map((m) => (
                <div key={m.id} className="panel-title" style={{ cursor: "pointer", marginTop: 8 }} onClick={() => selectEmployee(m.id)}>
                  <span style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <Portrait appearance={m.appearance} color={color} role={m.role} size={2} />
                    <span>
                      <b>{m.name}</b>
                      <div className="muted">
                        {m.title} · {m.mood}
                      </div>
                    </span>
                  </span>
                  <span className={tone(m.profit)}>{m.role === "tipster" ? signedEur(m.profit, 2) : ""}</span>
                </div>
              ))}
              {!d.members.length && <div className="empty">Nobody works here.</div>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
