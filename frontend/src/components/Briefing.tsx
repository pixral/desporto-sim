import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { CeoAction, ReviewView } from "../api/types";
import { useStore } from "../state/store";
import { AREA_LABEL, describe, editableField, exactDecision, reviewNamer, sameDecision } from "../util/actions";
import { eur, pct, shortDate, signedEur, tone } from "../util/format";
import { DesksSection, HireSection, LabSection, MoneySection, OfficeSection, PeopleSection, type Ops } from "./BriefingSections";

type Source = "advisor" | "queue" | "you";
interface Decision {
  key: number;
  action: CeoAction;
  source: Source;
}
type Section = "people" | "hire" | "desks" | "money" | "lab" | "office";
const SECTIONS: [Section, string][] = [
  ["people", "People"],
  ["hire", "Hire"],
  ["desks", "Desks"],
  ["money", "Money"],
  ["lab", "LAB"],
  ["office", "Office"],
];

/** The CEO's briefing: opens by itself when the clock stops for a review. */
export function Briefing() {
  const reviewId = useStore((s) => (s.state?.player?.review_open ? s.state.player.review_id : null));
  const hiddenFor = useStore((s) => s.briefingHiddenFor);
  const setHidden = useStore((s) => s.setBriefingHidden);
  if (!reviewId || hiddenFor === reviewId) return null;
  return <BriefingModal key={reviewId} onHide={() => setHidden(reviewId)} />;
}

function BriefingModal({ onHide }: { onHide: () => void }) {
  const notify = useStore((s) => s.notify);
  const player = useStore((s) => s.state?.player);
  const setSignoff = useStore((s) => s.setSignoff);
  const [review, setReview] = useState<ReviewView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [memo, setMemo] = useState("");
  const [section, setSection] = useState<Section>("people");
  const [busy, setBusy] = useState(false);
  const nextKey = useRef(1);

  useEffect(() => {
    api
      .review()
      .then((r) => {
        if (!r.open) return;
        setReview(r);
        setMemo(r.advisor.memo);
        setDecisions(r.queue.map((q) => ({ key: nextKey.current++, action: q.action, source: "queue" as Source })));
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const sign = async () => {
    if (!review || busy) return;
    setBusy(true);
    try {
      const res = await api.signReview(
        decisions.map((d) => d.action),
        memo,
      );
      setSignoff({ scope: review.scope, date: review.date, results: res.results });
    } catch (e) {
      notify((e as Error).message);
      setBusy(false);
    }
  };

  // Ctrl/Cmd + Enter signs off
  const signRef = useRef(sign);
  signRef.current = sign;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        signRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (error) {
    return (
      <div className="modal-backdrop">
        <div className="modal">
          <div className="neg">{error}</div>
          <button onClick={onHide}>Close</button>
        </div>
      </div>
    );
  }
  if (!review || !player) {
    return (
      <div className="modal-backdrop">
        <div className="modal briefing">
          <div className="empty">Your advisor is preparing the briefing…</div>
        </div>
      </div>
    );
  }

  const namer = reviewNamer(review);
  const has = (a: CeoAction) => decisions.some((d) => exactDecision(d.action, a));
  const count = (type: CeoAction["type"]) => decisions.filter((d) => d.action.type === type).length;
  const add = (action: CeoAction, source: Source = "you") =>
    setDecisions((ds) => {
      const i = ds.findIndex((d) => sameDecision(d.action, action));
      if (i >= 0) return ds.map((d, j) => (j === i ? { ...d, action } : d)); // e.g. a new stake limit for the same desk
      return [...ds, { key: nextKey.current++, action, source }];
    });
  const remove = (key: number) => setDecisions((ds) => ds.filter((d) => d.key !== key));
  const toggle = (action: CeoAction) => {
    const d = decisions.find((x) => exactDecision(x.action, action));
    if (d) remove(d.key);
    else add(action, "advisor");
  };
  const edit = (key: number, field: "amount" | "pct" | "value", v: number) =>
    setDecisions((ds) => ds.map((d) => (d.key === key ? { ...d, action: { ...d.action, [field]: v } } : d)));
  const ops: Ops = { review, player, has, count, add: (a) => add(a, "you") };

  const c = review.company;
  const lastMonth = c.months[c.months.length - 1];
  const title = review.scope === "monthly" ? "Monthly review" : "Monday briefing";

  return (
    <div className="modal-backdrop">
      <div className="modal briefing" role="dialog" aria-label={title}>
        <div className="panel-title">
          <div>
            <h2>
              {title} · {shortDate(review.date)}
            </h2>
            <div className="muted">
              Season {review.season} of {review.seasons_total} ({review.season_label}) · the clock waits for your sign-off
            </div>
          </div>
          <button onClick={onHide} title="Look around the office first; the briefing waits in the top bar">
            Hide
          </button>
        </div>

        <div className="brief-kpis">
          <Kpi label="Company value" value={eur(c.valuation)} sub={pct(c.valuation / c.starting_capital - 1, 0, true) + " since founding"} />
          <Kpi label="Cash" value={eur(c.cash)} sub={c.debt ? `debt ${eur(c.debt)}` : "no debt"} />
          <Kpi label="Bankroll" value={eur(c.bankroll)} />
          <Kpi label="Runway" value={c.runway_months === null ? "∞" : `${c.runway_months.toFixed(1)} mo`} sub={`burn ${eur(c.monthly_burn)}/mo`} />
          <Kpi
            label={lastMonth ? `Net, ${lastMonth.month}` : "Net this month"}
            value={signedEur(lastMonth ? lastMonth.net : c.month_to_date_net)}
            cls={tone(lastMonth ? lastMonth.net : c.month_to_date_net)}
          />
          <Kpi label="Subscribers" value={c.subscribers.toLocaleString()} sub={c.status} />
        </div>

        <BoardNote review={review} />
        {review.city.headlines.length > 0 && (
          <div className="brief-paper">
            <b>This morning's paper:</b> {review.city.headlines.slice(-3).join(" · ")}
            {review.city.active_effects.length > 0 && <span className="muted"> · In effect: {review.city.active_effects.join(", ")}</span>}
          </div>
        )}

        <div className="brief-body">
          <div className="brief-main">
            <section className="brief-col">
              <div className="panel-title">
                <h3>Your advisor · {review.advisor.label}</h3>
                {review.proposals.length > 1 && (
                  <button className="ghost" onClick={() => review.proposals.forEach((p) => !has(p.action) && add(p.action, "advisor"))}>
                    Accept all
                  </button>
                )}
              </div>
              {review.advisor.thought && <div className="thought">“{review.advisor.thought}”</div>}
              {review.proposals.length === 0 && <div className="empty">Nothing to suggest this time.</div>}
              {review.proposals.map((p, i) => {
                const on = has(p.action);
                return (
                  <div key={i} className={`proposal ${on ? "on" : ""}`}>
                    <button className={on ? "active" : ""} onClick={() => toggle(p.action)} aria-pressed={on}>
                      {on ? "✓ Taken" : "Accept"}
                    </button>
                    <div>
                      <div>
                        {p.label} <span className="chip">{AREA_LABEL[p.area]}</span>
                      </div>
                      {p.reason && <div className="muted">{p.reason}</div>}
                    </div>
                  </div>
                );
              })}
            </section>

            <div className="tabs brief-tabs">
              {SECTIONS.map(([k, label]) => (
                <button key={k} className={section === k ? "active" : ""} onClick={() => setSection(k)}>
                  {label}
                </button>
              ))}
            </div>
            <div className="brief-section">
              {section === "people" && <PeopleSection {...ops} />}
              {section === "hire" && <HireSection {...ops} />}
              {section === "desks" && <DesksSection {...ops} />}
              {section === "money" && <MoneySection {...ops} />}
              {section === "lab" && <LabSection {...ops} />}
              {section === "office" && <OfficeSection {...ops} />}
            </div>
          </div>
          <aside className="brief-col brief-side">
            <div className="panel-title">
              <h3>Your decisions ({decisions.length})</h3>
              {decisions.length > 0 && (
                <button className="ghost" onClick={() => setDecisions([])}>
                  Clear
                </button>
              )}
            </div>
            {decisions.length === 0 && (
              <div className="empty">Nothing decided yet. Accept your advisor's ideas or add your own from the tabs. Doing nothing is allowed.</div>
            )}
            {decisions.map((d) => {
              const f = editableField(d.action);
              const v = f ? (d.action[f.key] as number | undefined) ?? 0 : 0;
              return (
                <div key={d.key} className="decision">
                  <span className={`chip src-${d.source}`}>{d.source === "you" ? "you" : d.source === "queue" ? "queued" : "advice"}</span>
                  <span className="grow">{describe(d.action, namer)}</span>
                  {f && (
                    <input
                      type="number"
                      aria-label="Amount"
                      className="edit-num"
                      min={f.unit === "share" ? f.min * 100 : f.min}
                      max={f.unit === "share" ? f.max * 100 : f.max}
                      step={f.unit === "share" ? f.step * 100 : f.step}
                      value={f.unit === "share" ? +(v * 100).toFixed(1) : v}
                      onChange={(e) => {
                        const n = Number(e.target.value);
                        edit(d.key, f.key, f.unit === "share" ? n / 100 : n);
                      }}
                      title={f.unit === "share" ? "percent" : f.unit}
                    />
                  )}
                  <button className="ghost" onClick={() => remove(d.key)} aria-label="Remove decision">
                    ✕
                  </button>
                </div>
              );
            })}
            <label className="memo-edit">
              <span className="dim">Memo to all staff (optional; your advisor drafted it)</span>
              <textarea rows={3} maxLength={800} value={memo} onChange={(e) => setMemo(e.target.value)} />
            </label>
            <div className="controls" style={{ justifyContent: "flex-end" }}>
              <span className="muted">Ctrl+Enter</span>
              <button className="primary" onClick={sign} disabled={busy}>
                {busy ? "Signing…" : "Sign off and carry on"}
              </button>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, sub, cls }: { label: string; value: string; sub?: string; cls?: string }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className={`value ${cls ?? ""}`}>{value}</div>
      {sub && <div className="muted">{sub}</div>}
    </div>
  );
}

function BoardNote({ review }: { review: ReviewView }) {
  const b = review.board;
  if (b.warned)
    return (
      <div className="board-note warned">
        <b>The board warned you on {shortDate(b.warned)}.</b>{" "}
        {b.easy
          ? "On Easy they grumble but keep you."
          : `If company value is still under ${eur(b.floor_value)} (or the company is deep in a slump) at a monthly review from a month after the warning, you're out.`}
      </div>
    );
  if (!b.watching)
    return (
      <div className="board-note">
        The board starts judging you on day {b.active_from_day} (today is day {review.company.days_since_founding}). After that, a
        company worth under {eur(b.floor_value)} gets you a warning.
      </div>
    );
  return (
    <div className="board-note">
      The board watches company value: under {eur(b.floor_value)} (45% of the starting capital), or a {pct(b.drawdown_limit, 0)}{" "}
      slump while strained, earns a warning; {b.easy ? "on Easy that's all it does." : "still there a month later, you're fired."}
    </div>
  );
}

/** What happened when the player signed off (stays up after the briefing closes). */
export function SignoffResults() {
  const signoff = useStore((s) => s.signoff);
  const setSignoff = useStore((s) => s.setSignoff);
  if (!signoff) return null;
  const done = signoff.results.filter((r) => r.applied).length;
  return (
    <div className="modal-backdrop" onClick={() => setSignoff(null)}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Review results">
        <div className="panel-title">
          <h2>
            {signoff.scope === "monthly" ? "Monthly review" : "Monday briefing"} signed · {shortDate(signoff.date)}
          </h2>
        </div>
        <div className="dim" style={{ marginBottom: 8 }}>
          {signoff.results.length === 0
            ? "No decisions this time. The desks carry on as they were."
            : `${done} of ${signoff.results.length} decision(s) went through.`}
        </div>
        {signoff.results.length > 0 && (
          <table>
            <tbody>
              {signoff.results.map((r, i) => (
                <tr key={i}>
                  <td style={{ width: 110 }}>
                    <span className={`pill ${r.applied ? "won" : "lost"}`}>{r.applied ? "done" : "refused"}</span>
                  </td>
                  <td>{r.result}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="controls" style={{ justifyContent: "flex-end", marginTop: 12 }}>
          <button className="primary" onClick={() => setSignoff(null)}>
            Back to the office
          </button>
        </div>
      </div>
    </div>
  );
}
