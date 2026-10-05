import { api } from "../api/client";
import { t } from "../i18n";
import { useStore } from "../state/store";
import { PHASE_LABEL, shortDate, STATUS_LABEL, weekday } from "../util/format";

const SPEED_LABEL: Record<string, string> = {
  "1x": "1×",
  "2x": "2×",
  "4x": "4×",
  "16x": "16×",
  "64x": "64×",
  get max() {
    return t("MAX");
  },
};

export function TopBar() {
  const state = useStore((s) => s.state);
  const connected = useStore((s) => s.connected);
  const notify = useStore((s) => s.notify);
  const setShowNewRun = useStore((s) => s.setShowNewRun);
  const setGodOpen = useStore((s) => s.setGodOpen);
  const setBriefingHidden = useStore((s) => s.setBriefingHidden);
  const setMenuOpen = useStore((s) => s.setMenuOpen);
  if (!state) return <div className="topbar" />;
  const { run, clock, runner, kpis, player } = state;
  const waiting = !!player?.review_open;

  const control = async (action: string, speed?: string) => {
    try {
      await api.control(action, speed);
    } catch (e) {
      notify((e as Error).message);
    }
  };
  const save = async () => {
    try {
      await api.save(t("Manual save — {date}", { date: clock.date }));
      notify(t("Game saved"));
    } catch (e) {
      notify((e as Error).message);
    }
  };

  return (
    <header className="topbar">
      <div className="logo">
        <div className="logo-mark" aria-hidden />
        <div>
          <h1>{run.company_name.toUpperCase()}</h1>
          <div className="sub">
            {player
              ? t("CEO: {name} (you) · advisor: {advisor} · season {season}/{total}", {
                  name: player.name,
                  advisor: t(player.advisor_label),
                  season: player.season,
                  total: player.seasons_total,
                }) + (player.ironman ? " · ironman" : "")
              : t("CEO style: {style}", { style: t(run.ceo_style_label) })}{" "}
            · {t("paper betting only")}
          </div>
        </div>
      </div>
      <div className="clock" title={t("Founded {date}", { date: shortDate(run.founded) })}>
        <span className="date">
          {weekday(clock.weekday).slice(0, 3)} {shortDate(clock.date)} · {clock.time}
        </span>
        <span className="phase">
          {t("Day {n}", { n: clock.day_index })} · {clock.time === "07:00" ? t("Overnight") : PHASE_LABEL[clock.phase] ?? clock.phase}
          {state.today.matches ? ` · ${t("{n} matches today", { n: state.today.matches })}` : ` · ${t("no matches today")}`}
        </span>
      </div>
      <div className="controls">
        {waiting ? (
          <button className="primary pulse" onClick={() => setBriefingHidden(null)} title={t("The clock waits for your sign-off (space)")}>
            {player?.review_scope === "monthly" ? t("Monthly review") : t("Briefing")} ▸
          </button>
        ) : runner.running ? (
          <button className="primary" onClick={() => control("pause")} title={t("Pause (space)")}>
            ❚❚ {t("Pause")}
          </button>
        ) : (
          <button className="primary" onClick={() => control("resume")} disabled={run.ended} title={t("Run (space)")}>
            ▶ {t("Run")}
          </button>
        )}
        <button onClick={() => control("step")} disabled={run.ended || waiting} title={t("Advance one phase")}>
          {t("Step")}
        </button>
        <button onClick={() => control("day")} disabled={run.ended || waiting} title={t("Advance one day")}>
          {t("+1 Day")}
        </button>
        <div className="speed-group" role="group" aria-label={t("Simulation speed")}>
          {runner.speeds.map((s) => (
            <button key={s} className={runner.speed === s ? "active" : ""} onClick={() => control("speed", s)}>
              {SPEED_LABEL[s] ?? s}
            </button>
          ))}
        </div>
      </div>
      <div className="spacer" />
      <span className={`status-badge st-${kpis.status}`}>{STATUS_LABEL[kpis.status]}</span>
      <button
        className="sandbox"
        onClick={() => setGodOpen(true)}
        disabled={state.sandbox.locked}
        title={state.sandbox.locked ? t("Ironman company: the sandbox is locked") : t("Sandbox tools: disasters, investors, market shocks…")}
      >
        {t("Sandbox")}
        {state.sandbox.god_actions ? ` · ${state.sandbox.god_actions}` : ""}
      </button>
      <button onClick={save} disabled={run.ended}>
        {t("Save")}
      </button>
      <button onClick={() => setShowNewRun(true)}>{t("New company")}</button>
      <button onClick={() => setMenuOpen(true)} title={t("Title screen (the game pauses)")}>
        {t("Menu")}
      </button>
      <span className={`conn ${connected ? "on" : ""}`} title={connected ? t("Live") : t("Disconnected — retrying")} />
    </header>
  );
}
