import { t } from "../i18n";
import { useStore } from "../state/store";
import { eur, fmtNum, pct, shortDate, signedEur } from "../util/format";

export function EndScreen() {
  const state = useStore((s) => s.state);
  const dismissed = useStore((s) => s.summaryDismissedFor);
  const dismiss = useStore((s) => s.dismissSummary);
  const setTab = useStore((s) => s.setTab);
  if (!state?.run.ended || !state.summary || dismissed === state.run.id) return null;
  const s = state.summary;
  const rows: [string, string][] = [
    [t("Peak company value"), `${eur(s.peak_value)}${s.peak_value_day ? ` (${shortDate(s.peak_value_day)})` : ""}`],
    [t("Final company value"), eur(s.final_value)],
    [t("Worst drawdown"), `-${pct(s.worst_drawdown, 0)}`],
    [t("Betting result"), signedEur(s.betting_profit)],
    [t("Total expenses"), eur(s.total_expenses)],
    [t("Employees hired"), String(s.employees_hired)],
    [t("Employees fired"), String(s.employees_fired)],
    [t("Resignations"), String(s.employees_resigned)],
    [t("Bets placed"), fmtNum(s.bets_placed)],
    [t("Times they said NO BET"), fmtNum(s.no_bet_decisions)],
    [t("Best employee"), s.best_employee ? `${s.best_employee} (${signedEur(s.best_employee_profit)})` : "—"],
    [t("Worst employee"), s.worst_employee ? `${s.worst_employee} (${signedEur(s.worst_employee_profit)})` : "—"],
    [t("Departments created / closed"), `${s.departments_created} / ${s.departments_closed}`],
    [t("Strategies invented by the LAB"), String(s.strategies_invented)],
    ...(s.player_ceo ? [] : [[t("CEOs fired by the board"), String(s.ceo_changes ?? 0)] as [string, string]]),
    [t("Seasons completed"), String(s.seasons ?? 0)],
    [t("AI calls / cost"), `${fmtNum(s.ai_calls)} / $${fmtNum(s.ai_cost_usd, 2)}`],
  ];
  if (s.god_actions) rows.push([t("Sandbox interventions"), String(s.god_actions)]);
  if (s.player_ceo) {
    rows.splice(
      0,
      0,
      [t("Briefings you signed"), String(s.reviews_signed ?? 0)],
      [t("Advice taken / skipped"), `${s.advice_taken ?? 0} / ${s.advice_skipped ?? 0}`],
    );
  }
  const kind = s.end_kind ?? "bankrupt";
  const heading = { bankrupt: t("BANKRUPT"), fired: t("FIRED BY THE BOARD"), retired: t("RETIRED") }[kind];
  const lasted = s.player_ceo
    ? kind === "retired"
      ? t("{n} seasons in charge", { n: s.seasons ?? 0 })
      : t("You lasted {n} days", { n: s.days_survived })
    : t("{n} days survived", { n: s.days_survived });
  // the style key, readable ("conservative operator")
  const style = t(s.ceo_style.replaceAll("_", " "));
  return (
    <div className="modal-backdrop">
      <div className="end-card" role="dialog" aria-label={t("Run summary")}>
        <div className="muted" style={{ fontFamily: "var(--font-head)", fontSize: 12 }}>
          {heading}
          {s.god_actions ? ` · ${t("SANDBOX RUN")}` : ""}
        </div>
        <h1>{s.company_name.toUpperCase()}</h1>
        <div className="days">{lasted}</div>
        <div className="dim">
          {shortDate(s.founded)} – {shortDate(s.last_day)} · CEO {s.ceo_name}{" "}
          {s.player_ceo ? t("(you) · advisor: {style}", { style }) : `(${style})`}
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
            {t("Read the history")}
          </button>
          <button
            className="primary"
            onClick={() => {
              dismiss(state.run.id);
              useStore.getState().setMenuOpen(true);
            }}
          >
            {t("Found a new company")}
          </button>
        </div>
      </div>
    </div>
  );
}
