import { useState } from "react";
import { api } from "../api/client";
import type { CostLines } from "../api/types";
import { ColumnChart, LineChart } from "../components/charts";
import { t } from "../i18n";
import { useStore } from "../state/store";
import { dayMonth, eur, monthLabel, pct, signedEur, tone } from "../util/format";
import { useLive } from "../util/hooks";

function costRows(): [keyof CostLines, string][] {
  return [
    ["salaries", t("Salaries")],
    ["bonuses", t("Bonuses")],
    ["severance", t("Severance")],
    ["rent", t("Rent")],
    ["data", t("Sports data")],
    ["marketing", t("Marketing")],
    ["lab", t("LAB budget")],
    ["ai", t("AI / API")],
    ["interest", t("Interest")],
    ["other_costs", t("One-offs (fit-outs, disasters)")],
  ];
}

export function Dashboard() {
  const state = useStore((s) => s.state);
  const { data } = useLive(() => api.finance(), state?.clock.day_index);
  const [table, setTable] = useState(false);
  if (!data || !state) return <div className="page empty">{t("Loading the books…")}</div>;
  const daily = data.daily;
  const x = daily.map((p) => dayMonth(p.day));
  const reports = data.reports;
  const mtd = data.month_to_date;
  return (
    <div className="page">
      <div className="grid-2">
        <div className="panel">
          <div className="panel-title">
            <h2>{t("Company value, cash and bankroll")}</h2>
            <button className="ghost" onClick={() => setTable((on) => !on)}>
              {table ? t("Charts") : t("Table")}
            </button>
          </div>
          {daily.length < 2 ? (
            <div className="empty">{t("Charts appear after the first simulated day.")}</div>
          ) : table ? (
            <div style={{ maxHeight: 260, overflow: "auto" }}>
              <table className="tab-nums">
                <thead>
                  <tr>
                    <th>{t("Day")}</th>
                    <th className="r">{t("Value")}</th>
                    <th className="r">{t("Cash")}</th>
                    <th className="r">{t("Bankroll")}</th>
                    <th className="r">{t("Day P/L")}</th>
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
                { key: "val", label: t("Company value"), color: "var(--series-1)", values: daily.map((p) => p.valuation) },
                { key: "cash", label: t("Cash"), color: "var(--series-2)", values: daily.map((p) => p.cash) },
                { key: "bank", label: t("Desk bankrolls"), color: "var(--series-3)", values: daily.map((p) => p.bankroll) },
              ]}
            />
          )}
        </div>
        <div className="panel">
          <h2 style={{ marginBottom: 10 }}>{t("Net result by month")}</h2>
          {reports.length === 0 ? (
            <div className="empty">{t("The first month hasn't closed yet. Month to date: {net}.", { net: signedEur(mtd.net) })}</div>
          ) : (
            <ColumnChart
              format={(v) => eur(v)}
              data={reports.map((r) => ({
                label: monthLabel(r.month),
                value: r.net,
                detail: (
                  <div className="muted">
                    {t("betting {pnl} · subs {subs} · costs {costs}", {
                      pnl: signedEur(r.lines.betting_pnl),
                      subs: eur(r.lines.subscriptions),
                      costs: eur(r.expenses),
                    })}
                  </div>
                ),
              }))}
            />
          )}
          <div className="muted" style={{ marginTop: 6 }}>
            {t("Blue months made money, red months lost it. Hover a column for the breakdown; every value is in the table below.")}
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: 16 }}>
        <div className="panel">
          <h2 style={{ marginBottom: 10 }}>{t("This month so far")}</h2>
          <table className="tab-nums">
            <tbody>
              <tr>
                <td>{t("Betting result")}</td>
                <td className={`r ${tone(mtd.betting_pnl)}`}>{signedEur(mtd.betting_pnl, 2)}</td>
              </tr>
              <tr>
                <td>{t("Subscriptions")}</td>
                <td className="r dim">
                  {t("collected at month end ({n} × {price})", { n: data.subscribers, price: eur(data.subscription_price) })}
                </td>
              </tr>
              {mtd.other_income ? (
                <tr>
                  <td>{t("Other income")}</td>
                  <td className="r pos">+{eur(mtd.other_income, 2)}</td>
                </tr>
              ) : null}
              {costRows().map(([k, label]) =>
                mtd[k] ? (
                  <tr key={k}>
                    <td>{label}</td>
                    <td className="r">−{eur(mtd[k] as number, 2)}</td>
                  </tr>
                ) : null,
              )}
              <tr>
                <td>
                  <b>{t("Net so far")}</b>
                </td>
                <td className={`r ${tone(mtd.net)}`}>
                  <b>{signedEur(mtd.net, 2)}</b>
                </td>
              </tr>
            </tbody>
          </table>
          <div className="muted" style={{ marginTop: 8 }}>
            {t("Credit available: {credit} · debt {debt}", { credit: eur(data.credit_available), debt: eur(state.kpis.debt) })}
          </div>
        </div>
        <div className="panel">
          <h2 style={{ marginBottom: 10 }}>{t("Desks")}</h2>
          <table className="tab-nums">
            <thead>
              <tr>
                <th>{t("Desk")}</th>
                <th className="r">{t("Bets")}</th>
                <th className="r">ROI</th>
                <th className="r">{t("All-time P/L")}</th>
              </tr>
            </thead>
            <tbody>
              {data.departments.map((d) => (
                <tr key={d.id} className={d.active ? "" : "inactive"}>
                  <td>
                    {t(d.name)}
                    {!d.active && ` ${t("(closed)")}`}
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
        <h2 style={{ marginBottom: 10 }}>{t("Monthly reports")}</h2>
        {reports.length === 0 ? (
          <div className="empty">{t("No closed months yet.")}</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="tab-nums">
              <thead>
                <tr>
                  <th>{t("Month")}</th>
                  <th className="r">{t("Betting")}</th>
                  <th className="r">{t("Subs")}</th>
                  <th className="r">{t("Salaries+bonus")}</th>
                  <th className="r">{t("Other costs")}</th>
                  <th className="r">{t("Net")}</th>
                  <th className="r">{t("Cash")}</th>
                  <th className="r">{t("Bankroll")}</th>
                  <th className="r">{t("Value")}</th>
                  <th className="r">{t("Staff")}</th>
                  <th className="r">{t("Subscribers")}</th>
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
