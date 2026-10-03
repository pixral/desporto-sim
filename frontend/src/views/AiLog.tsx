import { useState } from "react";
import { api } from "../api/client";
import type { AiCallFull } from "../api/types";
import { PromptModal } from "../components/EmployeePanel";
import { useStore } from "../state/store";
import { shortDate } from "../util/format";
import { useLive } from "../util/hooks";

export function AiLog() {
  const state = useStore((s) => s.state);
  const [purpose, setPurpose] = useState("");
  const [failures, setFailures] = useState(false);
  const [open, setOpen] = useState<AiCallFull | null>(null);
  const { data } = useLive(
    () => api.aiCalls({ purpose: purpose || undefined, failures_only: failures || undefined, limit: 200 }),
    `${purpose}:${failures}:${state?.clock.day_index}:${state?.clock.phase}`,
  );
  const k = state?.kpis;
  return (
    <div className="page">
      <div className="panel">
        <div className="panel-title">
          <h2>AI calls</h2>
          <span className="muted">provider: {state?.run.ai_provider}</span>
        </div>
        {k && (
          <div className="stats" style={{ marginBottom: 12 }}>
            <div className="stat">
              <div className="label">Calls</div>
              <div className="value">{k.ai_calls.toLocaleString()}</div>
            </div>
            <div className="stat">
              <div className="label">Failures</div>
              <div className="value">{k.ai_failures}</div>
            </div>
            <div className="stat">
              <div className="label">Total cost</div>
              <div className="value">${k.ai_cost_usd.toFixed(3)}</div>
            </div>
            <div className="stat">
              <div className="label">This month (charged)</div>
              <div className="value">€{k.ai_cost_month_eur.toFixed(2)}</div>
            </div>
          </div>
        )}
        <div className="controls" style={{ marginBottom: 10 }}>
          <select value={purpose} onChange={(e) => setPurpose(e.target.value)} aria-label="Purpose">
            <option value="">All purposes</option>
            <option value="tipster_day">Tipster decisions</option>
            <option value="ceo_review">CEO reviews</option>
            <option value="lab_hypothesis">LAB hypotheses</option>
          </select>
          <label className="dim">
            <input type="checkbox" checked={failures} onChange={(e) => setFailures(e.target.checked)} /> failures only
          </label>
          <span className="muted">Mock-provider token counts are estimates priced at the reference model.</span>
        </div>
        <table className="tab-nums">
          <thead>
            <tr>
              <th>When</th>
              <th>Agent</th>
              <th>Purpose</th>
              <th>Model</th>
              <th className="r">Tokens</th>
              <th className="r">Cost</th>
              <th className="r">Retries</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((c) => (
              <tr key={c.id} className="clickable" onClick={async () => setOpen(await api.aiCall(c.id))}>
                <td className="muted">
                  {shortDate(c.sim_time)} {c.sim_time.slice(11, 16)}
                </td>
                <td>{c.agent_name}</td>
                <td>{c.purpose}</td>
                <td className="muted">{c.model}</td>
                <td className="r">
                  {c.input_tokens.toLocaleString()} / {c.output_tokens.toLocaleString()}
                  {c.estimated ? "*" : ""}
                </td>
                <td className="r">${c.cost_usd.toFixed(4)}</td>
                <td className="r">{c.retries}</td>
                <td>{c.ok ? "ok" : <span className="neg">{c.used_fallback ? "fallback" : "failed"}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && !data.length && <div className="empty">No calls yet.</div>}
      </div>
      {open && <PromptModal call={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
