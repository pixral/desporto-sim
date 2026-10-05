import { useState } from "react";
import { api } from "../api/client";
import type { AiCallFull } from "../api/types";
import { PromptModal } from "../components/EmployeePanel";
import { t } from "../i18n";
import { useStore } from "../state/store";
import { eur, fmtNum, shortDate } from "../util/format";
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
          <h2>{t("AI calls")}</h2>
          <span className="muted">{t("provider: {name}", { name: state?.run.ai_provider ?? "" })}</span>
        </div>
        {k && (
          <div className="stats" style={{ marginBottom: 12 }}>
            <div className="stat">
              <div className="label">{t("Calls")}</div>
              <div className="value">{fmtNum(k.ai_calls)}</div>
            </div>
            <div className="stat">
              <div className="label">{t("Failures")}</div>
              <div className="value">{k.ai_failures}</div>
            </div>
            <div className="stat">
              <div className="label">{t("Total cost")}</div>
              <div className="value">${fmtNum(k.ai_cost_usd, 3)}</div>
            </div>
            <div className="stat">
              <div className="label">{t("This month (charged)")}</div>
              <div className="value">{eur(k.ai_cost_month_eur, 2)}</div>
            </div>
          </div>
        )}
        <div className="controls" style={{ marginBottom: 10 }}>
          <select value={purpose} onChange={(e) => setPurpose(e.target.value)} aria-label={t("Purpose")}>
            <option value="">{t("All purposes")}</option>
            <option value="tipster_day">{t("Tipster decisions")}</option>
            <option value="ceo_review">{t("CEO reviews")}</option>
            <option value="lab_hypothesis">{t("LAB hypotheses")}</option>
          </select>
          <label className="dim">
            <input type="checkbox" checked={failures} onChange={(e) => setFailures(e.target.checked)} /> {t("failures only")}
          </label>
          <span className="muted">{t("Mock-provider token counts are estimates priced at the reference model.")}</span>
        </div>
        <table className="tab-nums">
          <thead>
            <tr>
              <th>{t("When")}</th>
              <th>{t("Agent")}</th>
              <th>{t("Purpose")}</th>
              <th>{t("Model")}</th>
              <th className="r">{t("Tokens")}</th>
              <th className="r">{t("Cost")}</th>
              <th className="r">{t("Retries")}</th>
              <th>{t("Status")}</th>
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
                  {fmtNum(c.input_tokens)} / {fmtNum(c.output_tokens)}
                  {c.estimated ? "*" : ""}
                </td>
                <td className="r">${fmtNum(c.cost_usd, 4)}</td>
                <td className="r">{c.retries}</td>
                <td>{c.ok ? t("ok") : <span className="neg">{c.used_fallback ? t("fallback") : t("failed")}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && !data.length && <div className="empty">{t("No calls yet.")}</div>}
      </div>
      {open && <PromptModal call={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
