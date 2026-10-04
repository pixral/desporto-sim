import { api } from "../api/client";
import { useStore } from "../state/store";
import { PHASE_LABEL, shortDate, STATUS_LABEL } from "../util/format";

const SPEED_LABEL: Record<string, string> = { "1x": "1×", "2x": "2×", "4x": "4×", "16x": "16×", "64x": "64×", max: "MAX" };

export function TopBar() {
  const state = useStore((s) => s.state);
  const connected = useStore((s) => s.connected);
  const notify = useStore((s) => s.notify);
  const setShowNewRun = useStore((s) => s.setShowNewRun);
  const setGodOpen = useStore((s) => s.setGodOpen);
  if (!state) return <div className="topbar" />;
  const { run, clock, runner, kpis } = state;

  const control = async (action: string, speed?: string) => {
    try {
      await api.control(action, speed);
    } catch (e) {
      notify((e as Error).message);
    }
  };
  const save = async () => {
    try {
      await api.save(`Manual save — ${clock.date}`);
      notify("Game saved");
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
            CEO style: {run.ceo_style_label} · paper betting only
          </div>
        </div>
      </div>
      <div className="clock" title={`Founded ${shortDate(run.founded)}`}>
        <span className="date">
          {clock.weekday.slice(0, 3)} {shortDate(clock.date)} · {clock.time}
        </span>
        <span className="phase">
          Day {clock.day_index} · {clock.time === "07:00" ? "Overnight" : PHASE_LABEL[clock.phase] ?? clock.phase}
          {state.today.matches ? ` · ${state.today.matches} matches today` : " · no matches today"}
        </span>
      </div>
      <div className="controls">
        {runner.running ? (
          <button className="primary" onClick={() => control("pause")} title="Pause (space)">
            ❚❚ Pause
          </button>
        ) : (
          <button className="primary" onClick={() => control("resume")} disabled={run.ended} title="Run (space)">
            ▶ Run
          </button>
        )}
        <button onClick={() => control("step")} disabled={run.ended} title="Advance one phase">
          Step
        </button>
        <button onClick={() => control("day")} disabled={run.ended} title="Advance one day">
          +1 Day
        </button>
        <div className="speed-group" role="group" aria-label="Simulation speed">
          {runner.speeds.map((s) => (
            <button key={s} className={runner.speed === s ? "active" : ""} onClick={() => control("speed", s)}>
              {SPEED_LABEL[s] ?? s}
            </button>
          ))}
        </div>
      </div>
      <div className="spacer" />
      <span className={`status-badge st-${kpis.status}`}>{STATUS_LABEL[kpis.status]}</span>
      <button className="sandbox" onClick={() => setGodOpen(true)} title="Sandbox tools: disasters, investors, market shocks…">
        Sandbox{state.sandbox.god_actions ? ` · ${state.sandbox.god_actions}` : ""}
      </button>
      <button onClick={save} disabled={run.ended}>
        Save
      </button>
      <button onClick={() => setShowNewRun(true)}>New company</button>
      <span className={`conn ${connected ? "on" : ""}`} title={connected ? "Live" : "Disconnected — retrying"} />
    </header>
  );
}
