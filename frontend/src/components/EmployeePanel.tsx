import { useState } from "react";
import { api } from "../api/client";
import type { AiCallFull, EmployeeDetail } from "../api/types";
import { useStore } from "../state/store";
import { eur, MARKET_LABEL, pct, shortDate, signedEur, tone } from "../util/format";
import { useLive } from "../util/hooks";
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

export function EmployeePanel({ id }: { id: string }) {
  const state = useStore((s) => s.state);
  const close = useStore((s) => s.selectEmployee);
  const [tab, setTab] = useState<T>("overview");
  const [call, setCall] = useState<AiCallFull | null>(null);
  const key = `${id}:${state?.clock.day_index}:${state?.clock.phase}`;
  const { data: d, error } = useLive<EmployeeDetail>(() => api.employee(id), key);
  const dept = state?.departments.find((x) => x.id === d?.department_id);
  const color = d?.role === "researcher" ? "#0e9aa7" : dept?.color ?? "#8a7f96";

  return (
    <div className="drawer" role="dialog" aria-label="Employee details">
      <div className="drawer-head">
        {d && <Portrait appearance={d.appearance} color={color} role={d.role} />}
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2>{d?.name ?? "…"}</h2>
          {d && (
            <>
              <div className="dim">
                {d.title} · {d.specialty_label}
              </div>
              <div className="muted">
                {d.department ?? "No department"} · {d.tenure_days} days employed
                {!d.active && d.leave_reason ? ` · left: ${d.leave_reason}` : ""}
              </div>
              <div style={{ marginTop: 4 }}>
                {d.under_review && <span className="pill lost" style={{ marginRight: 6 }}>under review</span>}
                <span className="pill bet">{d.mood}</span>
              </div>
            </>
          )}
          {error && <div className="neg">{error}</div>}
        </div>
        <button onClick={() => close(null)} aria-label="Close">
          ✕
        </button>
      </div>
      <div className="tabs">
        {(["overview", "bets", "performance", "relationships", "history", "decisions"] as T[]).map((t) => (
          <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      <div className="drawer-body">
        {!d ? (
          <div className="empty">Loading…</div>
        ) : tab === "overview" ? (
          <Overview d={d} />
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
        <h3>Current task</h3>
        <div style={{ margin: "4px 0" }}>{d.task || d.status}</div>
        {d.thought && <div className="thought">“{d.thought}”</div>}
      </div>
      {d.role === "tipster" && (
        <div className="panel">
          <div className="stats">
            <div className="stat">
              <div className="label">Career P/L</div>
              <div className={`value ${tone(s.profit)}`}>{signedEur(s.profit, 2)}</div>
            </div>
            <div className="stat">
              <div className="label">Recent P/L (30 bets)</div>
              <div className={`value ${tone(s.recent30.profit)}`}>{signedEur(s.recent30.profit, 2)}</div>
            </div>
            <div className="stat">
              <div className="label">ROI</div>
              <div className="value">{pct(s.roi, 1, true)}</div>
            </div>
            <div className="stat">
              <div className="label">Bets (W/L)</div>
              <div className="value">
                {s.bets} <span className="muted">({s.wins}/{s.losses})</span>
              </div>
            </div>
            <div className="stat">
              <div className="label">Passes</div>
              <div className="value">{pct(s.no_bet_rate, 0)}</div>
            </div>
            <div className="stat">
              <div className="label">Max stake</div>
              <div className="value">{eur(d.max_stake, 2)}</div>
            </div>
            <div className="stat">
              <div className="label">Salary / bonuses</div>
              <div className="value">
                {eur(d.salary)} <span className="muted">/ {eur(d.bonuses)}</span>
              </div>
            </div>
            <div className="stat">
              <div className="label">Streak</div>
              <div className="value">{d.streak > 0 ? `${d.streak}W` : d.streak < 0 ? `${-d.streak}L` : "—"}</div>
            </div>
          </div>
        </div>
      )}
      <div className="panel">
        <h3>State of mind</h3>
        <Meter label="Stress" value={d.stress} color={stressColor(d.stress)} />
        <Meter label="Confidence" value={d.confidence} color="var(--series-1)" />
        <Meter label="Risk tolerance" value={d.risk_tolerance} color="var(--series-2)" />
        <Meter label="Reputation" value={d.reputation} max={100} color="var(--accent)" text={d.reputation.toFixed(0)} />
      </div>
      <div className="panel">
        <h3>Personality</h3>
        <div className="dim" style={{ margin: "4px 0 6px" }}>
          {d.traits_text}
        </div>
        {Object.entries(d.traits).map(([k, v]) => (
          <Meter key={k} label={k.replace("_", "-")} value={v} color="var(--line-strong)" />
        ))}
      </div>
      {d.strategy && (
        <div className="panel">
          <h3>Strategy: {d.strategy.name}</h3>
          <div style={{ margin: "4px 0" }}>{d.strategy.summary}</div>
          <div className="muted">
            Origin: {d.strategy.origin} · live {d.strategy.live_bets} bets, ROI {pct(d.strategy.live_roi, 1, true)}
            {d.strategy.backtest
              ? ` · backtest ${d.strategy.backtest.sample_size} bets, ROI ${pct(d.strategy.backtest.roi, 1, true)}`
              : ""}
          </div>
        </div>
      )}
    </>
  );
}

function Bets({ d }: { d: EmployeeDetail }) {
  if (!d.bets_list.length) return <div className="empty">No bets yet.</div>;
  return (
    <table className="tab-nums">
      <thead>
        <tr>
          <th>Date</th>
          <th>Match / pick</th>
          <th className="r">Stake</th>
          <th className="r">Odds</th>
          <th className="r">Result</th>
        </tr>
      </thead>
      <tbody>
        {d.bets_list.map((b) => (
          <tr key={b.id} title={b.reason}>
            <td className="muted">{shortDate(b.placed)}</td>
            <td>
              <div>{b.match}</div>
              <div className="muted">
                {b.selection} ({MARKET_LABEL[b.market]}) @ {b.book}
                {b.score ? ` · ${b.score}` : ""}
                {b.influenced_by.length ? ` · swayed by ${b.influenced_by.join(", ")}` : ""}
              </div>
            </td>
            <td className="r">{eur(b.stake, 2)}</td>
            <td className="r">
              {b.odds.toFixed(2)}
              {b.clv !== null && <div className="muted">CLV {pct(b.clv, 1, true)}</div>}
            </td>
            <td className="r">
              <span className={`pill ${b.status}`}>{b.status}</span>
              {b.status !== "open" && <div className={tone(b.profit)}>{signedEur(b.profit, 2)}</div>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Performance({ d }: { d: EmployeeDetail }) {
  if (d.series.length < 2) return <div className="empty">Not enough history yet.</div>;
  const x = d.series.map((r) => `Day ${r[0]}`);
  return (
    <>
      <div className="panel">
        <h3>Cumulative P/L</h3>
        <LineChart x={x} series={[{ key: "pl", label: "Cumulative P/L", color: "var(--series-1)", values: d.series.map((r) => r[1]) }]} format={(v) => eur(v)} zeroLine />
      </div>
      <div className="panel">
        <h3>Reputation, stress and confidence (0–100)</h3>
        <LineChart
          x={x}
          series={[
            { key: "rep", label: "Reputation", color: "var(--series-1)", values: d.series.map((r) => r[2]) },
            { key: "stress", label: "Stress", color: "var(--series-2)", values: d.series.map((r) => r[3] * 100) },
            { key: "conf", label: "Confidence", color: "var(--series-3)", values: d.series.map((r) => r[4] * 100) },
          ]}
          format={(v) => v.toFixed(0)}
        />
      </div>
      {Object.keys(d.stats.by_market).length > 0 && (
        <div className="panel">
          <h3>By market</h3>
          <table className="tab-nums">
            <thead>
              <tr>
                <th>Market</th>
                <th className="r">Bets</th>
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
  if (!d.relationships.length) return <div className="empty">No colleagues yet.</div>;
  return (
    <>
      {d.relationships.map((r) => (
        <div key={r.id} className="panel" style={{ cursor: "pointer" }} onClick={() => select(r.id)}>
          <div className="panel-title" style={{ marginBottom: 4 }}>
            <b>{r.name}</b>
            <span className="muted">{r.title}</span>
          </div>
          <Meter label="Trust" value={r.trust} max={100} color="var(--series-1)" text={r.trust.toFixed(0)} />
          <Meter label="Respect" value={r.respect} max={100} color="var(--series-3)" text={r.respect.toFixed(0)} />
          <Meter label="Rivalry" value={r.rivalry} max={100} color="var(--series-2)" text={r.rivalry.toFixed(0)} />
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
          <h3>Recent AI calls</h3>
          <table className="tab-nums">
            <tbody>
              {d.ai_calls.map((c) => (
                <tr key={c.id} className="clickable" onClick={() => onCall(c.id)}>
                  <td className="muted">{shortDate(c.sim_time)}</td>
                  <td>{c.purpose}</td>
                  <td>{c.ok ? "ok" : <span className="neg">failed</span>}</td>
                  <td className="r">{c.input_tokens + c.output_tokens} tok</td>
                  <td className="r">${c.cost_usd.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!d.decisions.length && <div className="empty">No decisions logged yet.</div>}
      {d.decisions.map((x, i) => (
        <div key={i} className="panel">
          <div className="panel-title" style={{ marginBottom: 4 }}>
            <span>
              <span className={`pill ${x.decision === "BET" ? "bet" : "nobet"}`}>{x.decision === "BET" ? "BET" : "NO BET"}</span>{" "}
              {x.match_label}
            </span>
            <span className="muted">{shortDate(x.time)}</span>
          </div>
          {x.decision === "BET" && (
            <div>
              {x.selection} @ {x.odds?.toFixed(2)} · stake {eur(x.stake ?? 0, 2)} · confidence {pct(x.confidence, 0)}
              {x.model_edge !== null && <span className="muted"> · model edge {pct(x.model_edge, 1, true)}</span>}
            </div>
          )}
          <div className="thought">“{x.reason}”</div>
          {x.influenced_by.length > 0 && <div className="muted">Influenced by {x.influenced_by.join(", ")}</div>}
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
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="AI call">
        <div className="panel-title">
          <h2>
            {call.agent_name} · {call.purpose}
          </h2>
          <button onClick={onClose}>✕</button>
        </div>
        <div className="muted" style={{ marginBottom: 10 }}>
          {call.provider} / {call.model} · {call.input_tokens} in + {call.output_tokens} out tokens
          {call.estimated ? " (estimated)" : ""} · ${call.cost_usd.toFixed(4)} · {call.latency_ms.toFixed(0)} ms · retries {call.retries}
          {call.error ? ` · error: ${call.error}` : ""}
        </div>
        <h3>System prompt</h3>
        <pre className="prompt">{call.system}</pre>
        <h3 style={{ marginTop: 10 }}>Prompt</h3>
        <pre className="prompt">{call.prompt}</pre>
        <h3 style={{ marginTop: 10 }}>Response</h3>
        <pre className="prompt">{call.response}</pre>
      </div>
    </div>
  );
}
