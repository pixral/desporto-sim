import { useState } from "react";
import { api } from "../api/client";
import type { CandidatesView, ReviewCandidate } from "../api/types";
import { t } from "../i18n";
import { useStore } from "../state/store";
import { eur, pct, shortDate, tone } from "../util/format";
import { useLive } from "../util/hooks";

/** Player mode: the applicant pool between reviews. Tests start now; hires wait for the monthly review. */
export function HiringPanel() {
  const state = useStore((s) => s.state);
  const { data, reload } = useLive(() => api.candidates(), `${state?.clock.day_index}:${state?.player?.queue.length}`);
  if (!data) return null;
  const lab = data.lab;
  return (
    <div className="panel">
      <div className="panel-title">
        <h3>{t("Applicants")}</h3>
        <span className="muted">
          {t("LAB slots {free} free of {slots} · hiring happens at the monthly review", { free: lab.free_slots, slots: lab.slots })}
          {data.hiring_frozen ? ` · ${t("hiring is frozen")}` : ""}
        </span>
      </div>
      <div className="dim" style={{ marginBottom: 8 }}>
        {t(
          "A CV says little about skill. Ask the LAB to backtest an applicant's method (it takes a LAB slot until Monday), then queue the hire for the 1st.",
        )}
      </div>
      {data.candidates.length === 0 && <div className="empty">{t("No applicants right now.")}</div>}
      <div className="cand-grid">
        {data.candidates.map((c) => (
          <Applicant key={c.id} c={c} data={data} onDone={reload} />
        ))}
      </div>
    </div>
  );
}

function Applicant({ c, data, onDone }: { c: ReviewCandidate; data: CandidatesView; onDone: () => void }) {
  const notify = useStore((s) => s.notify);
  const queued = useStore((s) => s.state?.player?.queue.some((q) => q.action.candidate_id === c.id) ?? false);
  const researcher = c.role === "researcher";
  const targets = researcher
    ? data.lab.department_id && data.lab.free_seats > 0
      ? [{ id: data.lab.department_id, name: "LAB", fit: true }]
      : []
    : data.desks
        .filter((d) => d.free_seats > 0)
        .map((d) => ({ id: d.id, name: d.name, fit: d.preferred_specialties.includes(c.specialty) }))
        .sort((a, b) => Number(b.fit) - Number(a.fit));
  const [to, setTo] = useState(targets[0]?.id ?? "");
  const [busy, setBusy] = useState(false);
  const tested = c.lab_backtest_n !== null && c.lab_backtest_roi !== null;
  const canTest = c.testable && !tested && !c.test_due && data.lab.budget >= data.lab.min_test_budget;
  const run = async (fn: () => Promise<string>) => {
    setBusy(true);
    try {
      notify(await fn());
      onDone();
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="cand">
      <div className="row-between">
        <b>{c.name}</b>
        <span className="muted">{t("{amount}/mo", { amount: eur(c.salary_ask) })}</span>
      </div>
      <div className="dim">
        {researcher ? t("Researcher") : t("Tipster")} · {t(c.specialty_label)} · {t("{n}y", { n: c.experience })} ·{" "}
        {t("in the pool until {date}", { date: shortDate(c.expires) })}
      </div>
      <div className="evidence">
        <span title={t("How good the CV looks. Not proof of skill.")}>CV {c.cv_rating}/100</span>
        {tested ? (
          <span>
            {t("LAB test")} <b className={tone(c.lab_backtest_roi)}>{pct(c.lab_backtest_roi, 1, true)}</b> {t("over {n} bets", { n: c.lab_backtest_n ?? 0 })}
          </span>
        ) : c.test_due ? (
          <span className="muted">{t("LAB test running · results {date}", { date: shortDate(c.test_due) })}</span>
        ) : (
          <span className="muted">{researcher ? t("Researchers aren't backtested") : t("Not tested")}</span>
        )}
      </div>
      <div className="muted">{c.traits_text}</div>
      <div className="pitch">“{c.pitch}”</div>
      <div className="row-actions">
        {canTest && (
          <button
            disabled={busy || data.lab.free_slots <= 0}
            title={data.lab.free_slots <= 0 ? t("Every LAB slot is busy") : t("Results next Monday")}
            onClick={() =>
              run(async () => {
                const r = await api.act({ type: "TEST_CANDIDATE", candidate_id: c.id });
                return r.applied ? r.result : t("Refused: {reason}", { reason: r.result });
              })
            }
          >
            {t("Test")}
          </button>
        )}
        {targets.length > 0 && !queued && (
          <>
            <select value={to} onChange={(e) => setTo(e.target.value)} aria-label={t("Hire into")}>
              {targets.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.fit ? t("{desk} (fits)", { desk: t(x.name) }) : t(x.name)}
                </option>
              ))}
            </select>
            <button
              className="ghost"
              disabled={busy || !to}
              onClick={() =>
                run(async () => {
                  const p = await api.queue({ type: "HIRE", candidate_id: c.id, department_id: to });
                  return t("Queued for the monthly review: {label}", { label: p.label });
                })
              }
            >
              {t("Queue hire")}
            </button>
          </>
        )}
        {queued && <span className="chip src-queue">{t("hire queued")}</span>}
        {targets.length === 0 && <span className="muted">{t("No free seat for them.")}</span>}
      </div>
    </div>
  );
}
