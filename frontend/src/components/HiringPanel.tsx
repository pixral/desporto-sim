import { useState } from "react";
import { api } from "../api/client";
import type { CandidatesView, ReviewCandidate } from "../api/types";
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
        <h3>Applicants</h3>
        <span className="muted">
          LAB slots {lab.free_slots} free of {lab.slots} · hiring happens at the monthly review{data.hiring_frozen ? " · hiring is frozen" : ""}
        </span>
      </div>
      <div className="dim" style={{ marginBottom: 8 }}>
        A CV says little about skill. Ask the LAB to backtest an applicant's method (it takes a LAB slot until Monday), then queue the
        hire for the 1st.
      </div>
      {data.candidates.length === 0 && <div className="empty">No applicants right now.</div>}
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
        <span className="muted">{eur(c.salary_ask)}/mo</span>
      </div>
      <div className="dim">
        {researcher ? "Researcher" : "Tipster"} · {c.specialty_label} · {c.experience}y · in the pool until {shortDate(c.expires)}
      </div>
      <div className="evidence">
        <span title="How good the CV looks. Not proof of skill.">CV {c.cv_rating}/100</span>
        {tested ? (
          <span>
            LAB test <b className={tone(c.lab_backtest_roi)}>{pct(c.lab_backtest_roi, 1, true)}</b> over {c.lab_backtest_n} bets
          </span>
        ) : c.test_due ? (
          <span className="muted">LAB test running · results {shortDate(c.test_due)}</span>
        ) : (
          <span className="muted">{researcher ? "Researchers aren't backtested" : "Not tested"}</span>
        )}
      </div>
      <div className="muted">{c.traits_text}</div>
      <div className="pitch">“{c.pitch}”</div>
      <div className="row-actions">
        {canTest && (
          <button
            disabled={busy || data.lab.free_slots <= 0}
            title={data.lab.free_slots <= 0 ? "Every LAB slot is busy" : "Results next Monday"}
            onClick={() =>
              run(async () => {
                const r = await api.act({ type: "TEST_CANDIDATE", candidate_id: c.id });
                return r.applied ? r.result : `Refused: ${r.result}`;
              })
            }
          >
            Test
          </button>
        )}
        {targets.length > 0 && !queued && (
          <>
            <select value={to} onChange={(e) => setTo(e.target.value)} aria-label="Hire into">
              {targets.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                  {t.fit ? " (fits)" : ""}
                </option>
              ))}
            </select>
            <button
              className="ghost"
              disabled={busy || !to}
              onClick={() =>
                run(async () => {
                  const p = await api.queue({ type: "HIRE", candidate_id: c.id, department_id: to });
                  return `Queued for the monthly review: ${p.label}`;
                })
              }
            >
              Queue hire
            </button>
          </>
        )}
        {queued && <span className="chip src-queue">hire queued</span>}
        {targets.length === 0 && <span className="muted">No free seat for them.</span>}
      </div>
    </div>
  );
}
