import { useState } from "react";
import { api } from "../api/client";
import type { AiCallFull, EmployeeDetail } from "../api/types";
import { t } from "../i18n";
import { useStore } from "../state/store";
import { eur, fmtNum, MARKET_LABEL, pct, shortDate, signedEur, tone } from "../util/format";
import { useLive } from "../util/hooks";
import { PersonActions } from "./CeoActions";
import { LineChart } from "./charts";
import { Portrait } from "./Portrait";

type T = "overview" | "bets" | "performance" | "relationships" | "history" | "decisions";

function Meter({ label, value, max = 1, color, text }: { label: string; value: number; max?: number; color: string; text?: string }) {
  const w = Math.max(0, Math.min(1, value / max)) * 100;
  return (
    <div className="meter">
      <span className="dim">{label}</span>
      <span className="track">
        <span className="fill" style={{ width: `${w}%`, background: color }} />
      </span>
      <span className="num tab-nums" style={{ textAlign: "right" }}>
        {text ?? `${Math.round(w)}%`}
      </span>
    </div>
  );
}

function stressColor(v: number) {
  return v > 0.75 ? "var(--neg)" : v > 0.5 ? "var(--warn)" : "var(--pos)";
}

function tabLabel(k: T): string {
  switch (k) {
    case "overview":
      return t("overview");
    case "bets":
      return t("bets");
    case "performance":
      return t("performance");
    case "relationships":
      return t("relationships");
    case "history":
      return t("history");
    case "decisions":
      return t("decisions");
  }
}

/** The CEO's specialty reads "CEO — <style>". */
function specialtyLabel(label: string): string {
  return label.startsWith("CEO — ") ? `CEO — ${t(label.slice(6))}` : t(label);
}

function traitLabel(k: string): string {
  switch (k) {
    case "cautious":
      return t("cautious|trait");
    case "analytical":
      return t("analytical|trait");
    case "aggressive":
      return t("aggressive|trait");
    case "ambitious":
      return t("ambitious|trait");
    case "stubborn":
      return t("stubborn|trait");
    case "collaborative":
      return t("collaborative|trait");
    case "independent":
      return t("independent|trait");
    case "risk_seeking":
      return t("risk-seeking|trait");
    case "skeptical":
      return t("skeptical|trait");
    default:
      return k.replace("_", "-");
  }
}

function originLabel(o: string): string {
  if (o === "default") return t("default");
  if (o === "hire") return t("hire");
  if (o === "lab") return t("lab");
  return o;
}

function betStatusLabel(s: string): string {
  if (s === "open") return t("open");
  if (s === "won") return t("won");
  if (s === "lost") return t("lost");
  if (s === "void") return t("void");
  return s;
}

export function EmployeePanel({ id }: { id: string }) {
  const state = useStore((s) => s.state);
  const close = useStore((s) => s.selectEmployee);
  const [tab, setTab] = useState<T>("overview");
  const [call, setCall] = useState<AiCallFull | null>(null);
  const key = `${id}:${state?.clock.day_index}:${state?.clock.phase}`;
  const { data: d, error, reload } = useLive<EmployeeDetail>(() => api.employee(id), key);
  const dept = state?.departments.find((x) => x.id === d?.department_id);
  const color = d?.role === "researcher" ? "#0e9aa7" : dept?.color ?? "#8a7f96";

  return (
    <div className="drawer" role="dialog" aria-label={t("Employee details")}>
      <div className="drawer-head">
        {d && <Portrait appearance={d.appearance} color={color} role={d.role} />}
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2>{d?.name ?? "…"}</h2>
          {d && (
            <>
              <div className="dim">
                {t(d.title)} · {specialtyLabel(d.specialty_label)}
              </div>
              <div className="muted">
                {d.department ? t(d.department) : t("No department")} · {t("{n} days employed", { n: d.tenure_days })}
                {!d.active && d.leave_reason ? ` · ${t("left: {reason}", { reason: d.leave_reason })}` : ""}
              </div>
              <div style={{ marginTop: 4 }}>
                {d.under_review && (
                  <span className="pill lost" style={{ marginRight: 6 }}>
                    {t("under review")}
                  </span>
                )}
                <span className="pill bet">{t(d.mood)}</span>
              </div>
            </>
          )}
          {error && <div className="neg">{error}</div>}
        </div>
        <button onClick={() => close(null)} aria-label={t("Close")}>
          ✕
        </button>
      </div>
      <div className="tabs">
        {(["overview", "bets", "performance", "relationships", "history", "decisions"] as T[]).map((k) => (
          <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {tabLabel(k)}
          </button>
        ))}
      </div>
      <div className="drawer-body">
        {!d ? (
          <div className="empty">{t("Loading…")}</div>
        ) : tab === "overview" ? (
          <>
            <PersonActions d={d} onDone={reload} />
            <Overview d={d} />
          </>
        ) : tab === "bets" ? (
          <Bets d={d} />
        ) : tab === "performance" ? (
          <Performance d={d} />
        ) : tab === "relationships" ? (
          <Relationships d={d} />
        ) : tab === "history" ? (
          <div className="timeline">
            {[...d.career].reverse().map((c, i) => (
              <div key={i} className="tl-item">
                <span className="muted">{shortDate(c.day)}</span>
                <span className="bar" style={{ background: c.kind === "fired" || c.kind === "warning" ? "var(--neg)" : c.kind === "promoted" ? "var(--pos)" : "var(--line-strong)" }} />
                <span>{c.text}</span>
              </div>
            ))}
          </div>
        ) : (
          <Decisions d={d} onCall={async (cid) => setCall(await api.aiCall(cid))} />
        )}
      </div>
      {call && <PromptModal call={call} onClose={() => setCall(null)} />}
    </div>
  );
}

function Overview({ d }: { d: EmployeeDetail }) {
  const s = d.stats;
  return (
    <>
      <div className="panel">
        <h3>{t("Current task")}</h3>
        <div style={{ margin: "4px 0" }}>{d.task || d.status}</div>
        {d.thought && <div className="thought">“{d.thought}”</div>}
      </div>
      {d.role === "tipster" && (
        <div className="panel">
          <div className="stats">
            <div className="stat">
              <div className="label">{t("Career P/L")}</div>
              <div className={`value ${tone(s.profit)}`}>{signedEur(s.profit, 2)}</div>
            </div>
            <div className="stat">
              <div className="label">{t("Recent P/L (30 bets)")}</div>
              <div className={`value ${tone(s.recent30.profit)}`}>{signedEur(s.recent30.profit, 2)}</div>
            </div>
            <div className="stat">
              <div className="label">ROI</div>
              <div className="value">{pct(s.roi, 1, true)}</div>
            </div>
            <div className="stat">
              <div className="label">{t("Bets (W/L)")}</div>
              <div className="value">
                {s.bets} <span className="muted">({s.wins}/{s.losses})</span>
              </div>
            </div>
            <div className="stat">
              <div className="label">{t("Passes")}</div>
              <div className="value">{pct(s.no_bet_rate, 0)}</div>
            </div>
            <div className="stat">
              <div className="label">{t("Max stake")}</div>
              <div className="value">{eur(d.max_stake, 2)}</div>
            </div>
            <div className="stat">
              <div className="label">{t("Salary / bonuses")}</div>
              <div className="value">
                {eur(d.salary)} <span className="muted">/ {eur(d.bonuses)}</span>
              </div>
            </div>
            <div className="stat">
              <div className="label">{t("Streak")}</div>
              <div className="value">{d.streak > 0 ? t("{n}W", { n: d.streak }) : d.streak < 0 ? t("{n}L", { n: -d.streak }) : "—"}</div>
            </div>
          </div>
        </div>
      )}
      <div className="panel">
        <h3>{t("State of mind")}</h3>
        <Meter label={t("Stress")} value={d.stress} color={stressColor(d.stress)} />
        <Meter label={t("Confidence")} value={d.confidence} color="var(--series-1)" />
        <Meter label={t("Risk tolerance")} value={d.risk_tolerance} color="var(--series-2)" />
        <Meter label={t("Reputation")} value={d.reputation} max={100} color="var(--accent)" text={d.reputation.toFixed(0)} />
      </div>
      <div className="panel">
        <h3>{t("Personality")}</h3>
        <div className="dim" style={{ margin: "4px 0 6px" }}>
          {d.traits_text}
        </div>
        {Object.entries(d.traits).map(([k, v]) => (
          <Meter key={k} label={traitLabel(k)} value={v} color="var(--line-strong)" />
        ))}
      </div>
      {d.strategy && (
        <div className="panel">
          <h3>{t("Strategy: {name}", { name: d.strategy.name })}</h3>
          <div style={{ margin: "4px 0" }}>{d.strategy.summary}</div>
          <div className="muted">
            {t("Origin: {origin} · live {n} bets, ROI {roi}", {
              origin: originLabel(d.strategy.origin),
              n: d.strategy.live_bets,
              roi: pct(d.strategy.live_roi, 1, true),
            })}
            {d.strategy.backtest
              ? ` · ${t("backtest {n} bets, ROI {roi}", { n: d.strategy.backtest.sample_size, roi: pct(d.strategy.backtest.roi, 1, true) })}`
              : ""}
          </div>
        </div>
      )}
    </>
  );
}

function Bets({ d }: { d: EmployeeDetail }) {
  if (!d.bets_list.length) return <div className="empty">{t("No bets yet.")}</div>;
  return (
    <table className="tab-nums">
      <thead>
        <tr>
          <th>{t("Date")}</th>
          <th>{t("Match / pick")}</th>
          <th className="r">{t("Stake")}</th>
          <th className="r">{t("Odds")}</th>
          <th className="r">{t("Result")}</th>
        </tr>
      </thead>
      <tbody>
        {d.bets_list.map((b) => (
          <tr key={b.id} title={b.reason}>
            <td className="muted">{shortDate(b.placed)}</td>
            <td>
              <div>{b.match}</div>
              <div className="muted">
                {t(b.selection)} ({MARKET_LABEL[b.market]}) @ {b.book}
                {b.score ? ` · ${b.score}` : ""}
                {b.influenced_by.length ? ` · ${t("swayed by {names}", { names: b.influenced_by.join(", ") })}` : ""}
              </div>
            </td>
            <td className="r">{eur(b.stake, 2)}</td>
            <td className="r">
              {fmtNum(b.odds, 2)}
              {b.clv !== null && <div className="muted">CLV {pct(b.clv, 1, true)}</div>}
            </td>
            <td className="r">
              <span className={`pill ${b.status}`}>{betStatusLabel(b.status)}</span>
              {b.status !== "open" && <div className={tone(b.profit)}>{signedEur(b.profit, 2)}</div>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Performance({ d }: { d: EmployeeDetail }) {
  if (d.series.length < 2) return <div className="empty">{t("Not enough history yet.")}</div>;
  const x = d.series.map((r) => t("Day {n}", { n: r[0] }));
  return (
    <>
      <div className="panel">
        <h3>{t("Cumulative P/L")}</h3>
        <LineChart
          x={x}
          series={[{ key: "pl", label: t("Cumulative P/L"), color: "var(--series-1)", values: d.series.map((r) => r[1]) }]}
          format={(v) => eur(v)}
          zeroLine
        />
      </div>
      <div className="panel">
        <h3>{t("Reputation, stress and confidence (0–100)")}</h3>
        <LineChart
          x={x}
          series={[
            { key: "rep", label: t("Reputation"), color: "var(--series-1)", values: d.series.map((r) => r[2]) },
            { key: "stress", label: t("Stress"), color: "var(--series-2)", values: d.series.map((r) => r[3] * 100) },
            { key: "conf", label: t("Confidence"), color: "var(--series-3)", values: d.series.map((r) => r[4] * 100) },
          ]}
          format={(v) => v.toFixed(0)}
        />
      </div>
      {Object.keys(d.stats.by_market).length > 0 && (
        <div className="panel">
          <h3>{t("By market")}</h3>
          <table className="tab-nums">
            <thead>
              <tr>
                <th>{t("Market")}</th>
                <th className="r">{t("Bets")}</th>
                <th className="r">ROI</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(d.stats.by_market).map(([k, v]) => (
                <tr key={k}>
                  <td>{MARKET_LABEL[k] ?? k}</td>
                  <td className="r">{v.bets}</td>
                  <td className={`r ${tone(v.roi)}`}>{pct(v.roi, 1, true)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Relationships({ d }: { d: EmployeeDetail }) {
  const select = useStore((s) => s.selectEmployee);
  if (!d.relationships.length) return <div className="empty">{t("No colleagues yet.")}</div>;
  return (
    <>
      {d.relationships.map((r) => (
        <div key={r.id} className="panel" style={{ cursor: "pointer" }} onClick={() => select(r.id)}>
          <div className="panel-title" style={{ marginBottom: 4 }}>
            <b>{r.name}</b>
            <span className="muted">{t(r.title)}</span>
          </div>
          <Meter label={t("Trust")} value={r.trust} max={100} color="var(--series-1)" text={r.trust.toFixed(0)} />
          <Meter label={t("Respect")} value={r.respect} max={100} color="var(--series-3)" text={r.respect.toFixed(0)} />
          <Meter label={t("Rivalry")} value={r.rivalry} max={100} color="var(--series-2)" text={r.rivalry.toFixed(0)} />
        </div>
      ))}
    </>
  );
}

function Decisions({ d, onCall }: { d: EmployeeDetail; onCall: (id: number) => void }) {
  return (
    <>
      {d.ai_calls.length > 0 && (
        <div className="panel">
          <h3>{t("Recent AI calls")}</h3>
          <table className="tab-nums">
            <tbody>
              {d.ai_calls.map((c) => (
                <tr key={c.id} className="clickable" onClick={() => onCall(c.id)}>
                  <td className="muted">{shortDate(c.sim_time)}</td>
                  <td>{c.purpose}</td>
                  <td>{c.ok ? "ok" : <span className="neg">{t("failed")}</span>}</td>
                  <td className="r">{c.input_tokens + c.output_tokens} tok</td>
                  <td className="r">${c.cost_usd.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!d.decisions.length && <div className="empty">{t("No decisions logged yet.")}</div>}
      {d.decisions.map((x, i) => (
        <div key={i} className="panel">
          <div className="panel-title" style={{ marginBottom: 4 }}>
            <span>
              <span className={`pill ${x.decision === "BET" ? "bet" : "nobet"}`}>{x.decision === "BET" ? t("BET") : t("NO BET")}</span>{" "}
              {x.match_label}
            </span>
            <span className="muted">{shortDate(x.time)}</span>
          </div>
          {x.decision === "BET" && (
            <div>
              {x.selection ? t(x.selection) : x.selection} @ {x.odds == null ? x.odds : fmtNum(x.odds, 2)} ·{" "}
              {t("stake {amount} · confidence {pct}", { amount: eur(x.stake ?? 0, 2), pct: pct(x.confidence, 0) })}
              {x.model_edge !== null && <span className="muted"> · {t("model edge {pct}", { pct: pct(x.model_edge, 1, true) })}</span>}
            </div>
          )}
          <div className="thought">“{x.reason}”</div>
          {x.influenced_by.length > 0 && <div className="muted">{t("Influenced by {names}", { names: x.influenced_by.join(", ") })}</div>}
          {x.notes.map((n) => (
            <div key={n} className="muted">
              ⚑ {n}
            </div>
          ))}
        </div>
      ))}
    </>
  );
}

export function PromptModal({ call, onClose }: { call: AiCallFull; onClose: () => void }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={t("AI call")}>
        <div className="panel-title">
          <h2>
            {call.agent_name} · {call.purpose}
          </h2>
          <button onClick={onClose}>✕</button>
        </div>
        <div className="muted" style={{ marginBottom: 10 }}>
          {call.provider} / {call.model} · {t("{input} in + {output} out tokens", { input: call.input_tokens, output: call.output_tokens })}
          {call.estimated ? ` ${t("(estimated)")}` : ""} · ${call.cost_usd.toFixed(4)} · {call.latency_ms.toFixed(0)} ms ·{" "}
          {t("retries {n}", { n: call.retries })}
          {call.error ? ` · ${t("error: {error}", { error: call.error })}` : ""}
        </div>
        <h3>{t("System prompt")}</h3>
        <pre className="prompt">{call.system}</pre>
        <h3 style={{ marginTop: 10 }}>{t("Prompt")}</h3>
        <pre className="prompt">{call.prompt}</pre>
        <h3 style={{ marginTop: 10 }}>{t("Response")}</h3>
        <pre className="prompt">{call.response}</pre>
      </div>
    </div>
  );
}
