import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { CeoAction, ReviewView } from "../api/types";
import { currentLang, t } from "../i18n";
import { useStore } from "../state/store";
import { AREA_LABEL, describe, editableField, exactDecision, reviewNamer, sameDecision } from "../util/actions";
import { eur, fmtNum, pct, shortDate, signedEur, STATUS_LABEL, tone } from "../util/format";
import { DesksSection, HireSection, LabSection, MoneySection, OfficeSection, PeopleSection, type Ops } from "./BriefingSections";

type Source = "advisor" | "queue" | "you";
interface Decision {
  key: number;
  action: CeoAction;
  source: Source;
}
type Section = "people" | "hire" | "desks" | "money" | "lab" | "office";
const DESTRUCTIVE: CeoAction["type"][] = ["FIRE", "CLOSE_DEPARTMENT", "CUT_SALARIES", "RELEASE_SPACE"];
const sections = (): [Section, string][] => [
  ["people", t("People")],
  ["hire", t("Hire")],
  ["desks", t("Desks")],
  ["money", t("Money")],
  ["lab", "LAB"],
  ["office", t("Office")],
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
          <button onClick={onHide}>{t("Close")}</button>
        </div>
      </div>
    );
  }
  if (!review || !player) {
    return (
      <div className="modal-backdrop">
        <div className="modal briefing">
          <div className="empty">{t("Your advisor is preparing the briefing…")}</div>
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
  const title = review.scope === "monthly" ? t("Monthly review") : t("Monday briefing");
  const net = lastMonth ? lastMonth.net : c.month_to_date_net;

  return (
    <div className="modal-backdrop">
      <div className="modal briefing" role="dialog" aria-label={title}>
        <div className="panel-title">
          <div>
            <h2>
              {title} · {shortDate(review.date)}
            </h2>
            <div className="muted">
              {t("Season {season} of {total} ({label}) · the clock waits for your sign-off", {
                season: review.season,
                total: review.seasons_total,
                label: review.season_label,
              })}
            </div>
          </div>
          <button onClick={onHide} title={t("Look around the office first; the briefing waits in the top bar")}>
            {t("Hide")}
          </button>
        </div>

        <div className="brief-kpis">
          <Kpi
            label={t("Company value")}
            value={eur(c.valuation)}
            sub={t("{pct} since founding", { pct: pct(c.valuation / c.starting_capital - 1, 0, true) })}
          />
          <Kpi label={t("Cash")} value={eur(c.cash)} sub={c.debt ? t("debt {amount}", { amount: eur(c.debt) }) : t("no debt")} />
          <Kpi label={t("Bankroll")} value={eur(c.bankroll)} />
          <Kpi
            label={t("Runway")}
            value={c.runway_months === null ? "∞" : t("{n} mo", { n: fmtNum(c.runway_months, 1) })}
            sub={t("burn {amount}/mo", { amount: eur(c.monthly_burn) })}
          />
          <Kpi label={lastMonth ? t("Net, {month}", { month: lastMonth.month }) : t("Net this month")} value={signedEur(net)} cls={tone(net)} />
          <Kpi label={t("Subscribers")} value={fmtNum(c.subscribers)} sub={STATUS_LABEL[c.status]?.toLowerCase() ?? c.status} />
        </div>

        <BoardNote review={review} />
        {review.city.headlines.length > 0 && (
          <div className="brief-paper">
            <b>{t("This morning's paper:")}</b> {review.city.headlines.slice(-3).join(" · ")}
            {review.city.active_effects.length > 0 && (
              <span className="muted"> · {t("In effect: {effects}", { effects: review.city.active_effects.join(", ") })}</span>
            )}
          </div>
        )}

        <div className="brief-body">
          <div className="brief-main">
            <section className="brief-col advisor">
              <div className="panel-title">
                <h3>{t("Your advisor · {style}", { style: t(review.advisor.label) })}</h3>
                {review.proposals.length > 1 && (
                  <button className="ghost" onClick={() => review.proposals.forEach((p) => !has(p.action) && add(p.action, "advisor"))}>
                    {t("Accept all")}
                  </button>
                )}
              </div>
              {review.advisor.thought && <div className="thought">“{review.advisor.thought}”</div>}
              {review.proposals.length === 0 && <div className="empty">{t("Nothing to suggest this time.")}</div>}
              {review.proposals.map((p, i) => {
                const on = has(p.action);
                return (
                  <div key={i} className={`proposal ${on ? "on" : ""}`}>
                    <button className={on ? "taken" : "advice"} onClick={() => toggle(p.action)} aria-pressed={on}>
                      {on ? t("✓ Yours") : t("Accept")}
                    </button>
                    <div>
                      <div>
                        {/* the server writes labels in English; other languages rebuild them with the same wording */}
                        {currentLang() === "en" ? p.label : describe(p.action, namer)} <span className="chip">{AREA_LABEL[p.area]}</span>
                      </div>
                      {p.reason && <div className="muted">{p.reason}</div>}
                    </div>
                  </div>
                );
              })}
            </section>

            <div className="tabs brief-tabs">
              {sections().map(([k, label]) => (
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
              <h3>{t("Your decisions ({n})", { n: decisions.length })}</h3>
              {decisions.length > 0 && (
                <button className="ghost" onClick={() => setDecisions([])}>
                  {t("Clear")}
                </button>
              )}
            </div>
            {decisions.length === 0 && (
              <div className="empty">{t("Nothing decided yet. Accept your advisor's ideas or add your own from the tabs. Doing nothing is allowed.")}</div>
            )}
            {decisions.map((d) => {
              const f = editableField(d.action);
              const v = f ? (d.action[f.key] as number | undefined) ?? 0 : 0;
              return (
                <div key={d.key} className={`decision ${DESTRUCTIVE.includes(d.action.type) ? "danger" : ""}`}>
                  <span className={`chip src-${d.source}`}>{d.source === "you" ? t("you") : d.source === "queue" ? t("queued") : t("advice")}</span>
                  <span className="grow">{describe(d.action, namer)}</span>
                  {f && (
                    <input
                      type="number"
                      aria-label={t("Amount")}
                      className="edit-num"
                      min={f.unit === "share" ? f.min * 100 : f.min}
                      max={f.unit === "share" ? f.max * 100 : f.max}
                      step={f.unit === "share" ? f.step * 100 : f.step}
                      value={f.unit === "share" ? +(v * 100).toFixed(1) : v}
                      onChange={(e) => {
                        const n = Number(e.target.value);
                        edit(d.key, f.key, f.unit === "share" ? n / 100 : n);
                      }}
                      title={f.unit === "share" ? t("percent") : f.unit === "days" ? t("days") : f.unit}
                    />
                  )}
                  <button className="ghost" onClick={() => remove(d.key)} aria-label={t("Remove decision")}>
                    ✕
                  </button>
                </div>
              );
            })}
            <label className="memo-edit">
              <span className="dim">{t("Memo to all staff (optional; your advisor drafted it)")}</span>
              <textarea rows={3} maxLength={800} value={memo} onChange={(e) => setMemo(e.target.value)} />
            </label>
            <div className="controls" style={{ justifyContent: "flex-end" }}>
              <span className="muted">Ctrl+Enter</span>
              <button className="primary" onClick={sign} disabled={busy}>
                {busy ? t("Signing…") : t("Sign off and carry on")}
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
        <b>{t("The board warned you on {date}.", { date: shortDate(b.warned) })}</b>{" "}
        {b.easy
          ? t("On Easy they grumble but keep you.")
          : t(
              "If company value is still under {floor} (or the company is deep in a slump) at a monthly review from a month after the warning, you're out.",
              { floor: eur(b.floor_value) },
            )}
      </div>
    );
  if (!b.watching)
    return (
      <div className="board-note">
        {t("The board starts judging you on day {day} (today is day {today}). After that, a company worth under {floor} gets you a warning.", {
          day: b.active_from_day,
          today: review.company.days_since_founding,
          floor: eur(b.floor_value),
        })}
      </div>
    );
  const params = { floor: eur(b.floor_value), slump: pct(b.drawdown_limit, 0) };
  return (
    <div className="board-note">
      {b.easy
        ? t(
            "The board watches company value: under {floor} (45% of the starting capital), or a {slump} slump while strained, earns a warning; on Easy that's all it does.",
            params,
          )
        : t(
            "The board watches company value: under {floor} (45% of the starting capital), or a {slump} slump while strained, earns a warning; still there a month later, you're fired.",
            params,
          )}
    </div>
  );
}

/** What happened when the player signed off (stays up after the briefing closes). */
export function SignoffResults() {
  const signoff = useStore((s) => s.signoff);
  const setSignoff = useStore((s) => s.setSignoff);
  if (!signoff) return null;
  const done = signoff.results.filter((r) => r.applied).length;
  const date = shortDate(signoff.date);
  return (
    <div className="modal-backdrop" onClick={() => setSignoff(null)}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={t("Review results")}>
        <div className="panel-title">
          <h2>{signoff.scope === "monthly" ? t("Monthly review signed · {date}", { date }) : t("Monday briefing signed · {date}", { date })}</h2>
        </div>
        <div className="dim" style={{ marginBottom: 8 }}>
          {signoff.results.length === 0
            ? t("No decisions this time. The desks carry on as they were.")
            : t("{done} of {total} decision(s) went through.", { done, total: signoff.results.length })}
        </div>
        {signoff.results.length > 0 && (
          <table>
            <tbody>
              {signoff.results.map((r, i) => (
                <tr key={i}>
                  <td style={{ width: 110 }}>
                    <span className={`pill ${r.applied ? "won" : "lost"}`}>{r.applied ? t("done") : t("refused")}</span>
                  </td>
                  <td>{r.result}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="controls" style={{ justifyContent: "flex-end", marginTop: 12 }}>
          <button className="primary" onClick={() => setSignoff(null)}>
            {t("Back to the office")}
          </button>
        </div>
      </div>
    </div>
  );
}
