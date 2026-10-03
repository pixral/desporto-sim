import { useStore } from "../state/store";
import { eur, pct, shortDate, signedEur } from "../util/format";

export function EndScreen() {
  const state = useStore((s) => s.state);
  const dismissed = useStore((s) => s.summaryDismissedFor);
  const dismiss = useStore((s) => s.dismissSummary);
  const setShowNewRun = useStore((s) => s.setShowNewRun);
  const setTab = useStore((s) => s.setTab);
  if (!state?.run.ended || !state.summary || dismissed === state.run.id) return null;
  const s = state.summary;
  const rows: [string, string][] = [
    ["Peak company value", `${eur(s.peak_value)}${s.peak_value_day ? ` (${shortDate(s.peak_value_day)})` : ""}`],
    ["Final company value", eur(s.final_value)],
    ["Worst drawdown", `-${pct(s.worst_drawdown, 0)}`],
    ["Betting result", signedEur(s.betting_profit)],
    ["Total expenses", eur(s.total_expenses)],
    ["Employees hired", String(s.employees_hired)],
    ["Employees fired", String(s.employees_fired)],
    ["Resignations", String(s.employees_resigned)],
    ["Bets placed", s.bets_placed.toLocaleString()],
    ["Times they said NO BET", s.no_bet_decisions.toLocaleString()],
    ["Best employee", s.best_employee ? `${s.best_employee} (${signedEur(s.best_employee_profit)})` : "—"],
    ["Worst employee", s.worst_employee ? `${s.worst_employee} (${signedEur(s.worst_employee_profit)})` : "—"],
    ["Departments created / closed", `${s.departments_created} / ${s.departments_closed}`],
    ["Strategies invented by the LAB", String(s.strategies_invented)],
    ["CEOs fired by the board", String(s.ceo_changes ?? 0)],
    ["Seasons completed", String(s.seasons ?? 0)],
    ["AI calls / cost", `${s.ai_calls.toLocaleString()} / $${s.ai_cost_usd.toFixed(2)}`],
  ];
  return (
    <div className="modal-backdrop">
      <div className="end-card" role="dialog" aria-label="Run summary">
        <div className="muted" style={{ fontFamily: "var(--font-head)", fontSize: 12 }}>
          BANKRUPT
        </div>
        <h1>{s.company_name.toUpperCase()}</h1>
        <div className="days">{s.days_survived} days survived</div>
        <div className="dim">
          {shortDate(s.founded)} – {shortDate(s.last_day)} · CEO {s.ceo_name} ({s.ceo_style.replace("_", " ")})
        </div>
        <div className="thought" style={{ marginTop: 8 }}>
          {s.end_reason}
        </div>
        <div className="end-grid">
          {rows.map(([k, v]) => (
            <div key={k} style={{ display: "contents" }}>
              <span className="dim">{k}</span>
              <span className="v">{v}</span>
            </div>
          ))}
        </div>
        <div className="controls" style={{ justifyContent: "center" }}>
          <button
            onClick={() => {
              dismiss(state.run.id);
              setTab("history");
            }}
          >
            Read the history
          </button>
          <button
            className="primary"
            onClick={() => {
              dismiss(state.run.id);
              setShowNewRun(true);
            }}
          >
            Found a new company
          </button>
        </div>
      </div>
    </div>
  );
}
