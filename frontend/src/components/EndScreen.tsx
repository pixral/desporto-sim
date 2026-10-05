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
    ...(s.player_ceo ? [] : [["CEOs fired by the board", String(s.ceo_changes ?? 0)] as [string, string]]),
    ["Seasons completed", String(s.seasons ?? 0)],
    ["AI calls / cost", `${s.ai_calls.toLocaleString()} / $${s.ai_cost_usd.toFixed(2)}`],
  ];
  if (s.god_actions) rows.push(["Sandbox interventions", String(s.god_actions)]);
  if (s.player_ceo) {
    rows.splice(0, 0, ["Briefings you signed", String(s.reviews_signed ?? 0)], ["Advice taken / skipped", `${s.advice_taken ?? 0} / ${s.advice_skipped ?? 0}`]);
  }
  const kind = s.end_kind ?? "bankrupt";
  const heading = { bankrupt: "BANKRUPT", fired: "FIRED BY THE BOARD", retired: "RETIRED" }[kind];
  const lasted = s.player_ceo
    ? kind === "retired"
      ? `${s.seasons} seasons in charge`
      : `You lasted ${s.days_survived} days`
    : `${s.days_survived} days survived`;
  return (
    <div className="modal-backdrop">
      <div className="end-card" role="dialog" aria-label="Run summary">
        <div className="muted" style={{ fontFamily: "var(--font-head)", fontSize: 12 }}>
          {heading}
          {s.god_actions ? " · SANDBOX RUN" : ""}
        </div>
        <h1>{s.company_name.toUpperCase()}</h1>
        <div className="days">{lasted}</div>
        <div className="dim">
          {shortDate(s.founded)} – {shortDate(s.last_day)} · CEO {s.ceo_name}{" "}
          {s.player_ceo ? `(you) · advisor: ${s.ceo_style.replaceAll("_", " ")}` : `(${s.ceo_style.replaceAll("_", " ")})`}
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
