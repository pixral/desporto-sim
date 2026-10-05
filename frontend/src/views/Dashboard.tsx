import { useState } from "react";
import { api } from "../api/client";
import type { CostLines } from "../api/types";
import { ColumnChart, LineChart } from "../components/charts";
import { useStore } from "../state/store";
import { dayMonth, eur, monthLabel, pct, signedEur, tone } from "../util/format";
import { useLive } from "../util/hooks";

const COST_ROWS: [keyof CostLines, string][] = [
  ["salaries", "Salaries"],
  ["bonuses", "Bonuses"],
  ["severance", "Severance"],
  ["rent", "Rent"],
  ["data", "Sports data"],
  ["marketing", "Marketing"],
  ["lab", "LAB budget"],
  ["ai", "AI / API"],
  ["interest", "Interest"],
  ["other_costs", "One-offs (fit-outs, disasters)"],
];

export function Dashboard() {
  const state = useStore((s) => s.state);
  const { data } = useLive(() => api.finance(), state?.clock.day_index);
  const [table, setTable] = useState(false);
  if (!data || !state) return <div className="page empty">Loading the books…</div>;
  const daily = data.daily;
  const x = daily.map((p) => dayMonth(p.day));
  const reports = data.reports;
  const mtd = data.month_to_date;
  return (
    <div className="page">
      <div className="grid-2">
        <div className="panel">
          <div className="panel-title">
            <h2>Company value, cash and bankroll</h2>
            <button className="ghost" onClick={() => setTable((t) => !t)}>
              {table ? "Charts" : "Table"}
            </button>
          </div>
          {daily.length < 2 ? (
            <div className="empty">Charts appear after the first simulated day.</div>
          ) : table ? (
            <div style={{ maxHeight: 260, overflow: "auto" }}>
              <table className="tab-nums">
                <thead>
                  <tr>
                    <th>Day</th>
                    <th className="r">Value</th>
                    <th className="r">Cash</th>
                    <th className="r">Bankroll</th>
                    <th className="r">Day P/L</th>
                  </tr>
                </thead>
                <tbody>
                  {[...daily].reverse().map((p) => (
                    <tr key={p.day}>
                      <td>{dayMonth(p.day)}</td>
                      <td className="r">{eur(p.valuation)}</td>
                      <td className="r">{eur(p.cash)}</td>
                      <td className="r">{eur(p.bankroll)}</td>
                      <td className={`r ${tone(p.day_pnl)}`}>{signedEur(p.day_pnl, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <LineChart
              x={x}
              format={(v) => eur(v)}
              series={[
                { key: "val", label: "Company value", color: "var(--series-1)", values: daily.map((p) => p.valuation) },
                { key: "cash", label: "Cash", color: "var(--series-2)", values: daily.map((p) => p.cash) },
                { key: "bank", label: "Desk bankrolls", color: "var(--series-3)", values: daily.map((p) => p.bankroll) },
              ]}
            />
          )}
        </div>
        <div className="panel">
          <h2 style={{ marginBottom: 10 }}>Net result by month</h2>
          {reports.length === 0 ? (
            <div className="empty">The first month hasn't closed yet. Month to date: {signedEur(mtd.net)}.</div>
          ) : (
            <ColumnChart
              format={(v) => eur(v)}
              data={reports.map((r) => ({
                label: monthLabel(r.month),
                value: r.net,
                detail: (
                  <div className="muted">
                    betting {signedEur(r.lines.betting_pnl)} · subs {eur(r.lines.subscriptions)} · costs {eur(r.expenses)}
                  </div>
                ),
              }))}
            />
          )}
          <div className="muted" style={{ marginTop: 6 }}>
            Blue months made money, red months lost it. Hover a column for the breakdown; every value is in the table below.
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: 16 }}>
        <div className="panel">
          <h2 style={{ marginBottom: 10 }}>This month so far</h2>
          <table className="tab-nums">
            <tbody>
              <tr>
                <td>Betting result</td>
                <td className={`r ${tone(mtd.betting_pnl)}`}>{signedEur(mtd.betting_pnl, 2)}</td>
              </tr>
              <tr>
                <td>Subscriptions</td>
                <td className="r dim">collected at month end ({data.subscribers} × {eur(data.subscription_price)})</td>
              </tr>
              {mtd.other_income ? (
                <tr>
                  <td>Other income</td>
                  <td className="r pos">+{eur(mtd.other_income, 2)}</td>
                </tr>
              ) : null}
              {COST_ROWS.map(([k, label]) =>
                mtd[k] ? (
                  <tr key={k}>
                    <td>{label}</td>
                    <td className="r">−{eur(mtd[k] as number, 2)}</td>
                  </tr>
                ) : null,
              )}
              <tr>
                <td>
                  <b>Net so far</b>
                </td>
                <td className={`r ${tone(mtd.net)}`}>
                  <b>{signedEur(mtd.net, 2)}</b>
                </td>
              </tr>
            </tbody>
          </table>
          <div className="muted" style={{ marginTop: 8 }}>
            Credit available: {eur(data.credit_available)} · debt {eur(state.kpis.debt)}
          </div>
        </div>
        <div className="panel">
          <h2 style={{ marginBottom: 10 }}>Desks</h2>
          <table className="tab-nums">
            <thead>
              <tr>
                <th>Desk</th>
                <th className="r">Bets</th>
                <th className="r">ROI</th>
                <th className="r">All-time P/L</th>
              </tr>
            </thead>
            <tbody>
              {data.departments.map((d) => (
                <tr key={d.id} className={d.active ? "" : "inactive"}>
                  <td>
                    {d.name}
                    {!d.active && " (closed)"}
                  </td>
                  <td className="r">{d.bets}</td>
                  <td className="r">{pct(d.roi, 1, true)}</td>
                  <td className={`r ${tone(d.total_profit)}`}>{signedEur(d.total_profit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 16 }}>
        <h2 style={{ marginBottom: 10 }}>Monthly reports</h2>
        {reports.length === 0 ? (
          <div className="empty">No closed months yet.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="tab-nums">
              <thead>
                <tr>
                  <th>Month</th>
                  <th className="r">Betting</th>
                  <th className="r">Subs</th>
                  <th className="r">Salaries+bonus</th>
                  <th className="r">Other costs</th>
                  <th className="r">Net</th>
                  <th className="r">Cash</th>
                  <th className="r">Bankroll</th>
                  <th className="r">Value</th>
                  <th className="r">Staff</th>
                  <th className="r">Subscribers</th>
                </tr>
              </thead>
              <tbody>
                {[...reports].reverse().map((r) => {
                  const people = r.lines.salaries + r.lines.bonuses + r.lines.severance;
                  return (
                    <tr key={r.month}>
                      <td>{monthLabel(r.month)}</td>
                      <td className={`r ${tone(r.lines.betting_pnl)}`}>{signedEur(r.lines.betting_pnl)}</td>
                      <td className="r">{eur(r.lines.subscriptions)}</td>
                      <td className="r">{eur(people)}</td>
                      <td className="r">{eur(r.expenses - people)}</td>
                      <td className={`r ${tone(r.net)}`}>{signedEur(r.net)}</td>
                      <td className="r">{eur(r.end_cash)}</td>
                      <td className="r">{eur(r.end_bankroll)}</td>
                      <td className="r">{eur(r.valuation)}</td>
                      <td className="r">{r.headcount}</td>
                      <td className="r">{r.subscribers}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
