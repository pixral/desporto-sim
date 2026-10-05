import { useState } from "react";
import type { CeoAction, PlayerView, ReviewPerson, ReviewView } from "../api/types";
import { t } from "../i18n";
import { BRIEF_MARKETS, briefLabel, COMP_NAMES, theDesk } from "../util/actions";
import { eur, fmtNum, pct, shortDate, signedEur, tone } from "../util/format";

export interface Ops {
  review: ReviewView;
  player: PlayerView;
  has: (a: CeoAction) => boolean;
  count: (type: CeoAction["type"]) => number;
  add: (a: CeoAction) => void;
}

function Add({ ops, action, label, disabled, why, danger }: { ops: Ops; action: CeoAction; label: string; disabled?: boolean; why?: string; danger?: boolean }) {
  const taken = ops.has(action);
  return (
    <button
      className={taken ? "taken" : danger ? "danger" : ""}
      disabled={disabled || taken}
      title={taken ? t("Already in your decisions") : why}
      onClick={() => ops.add(action)}
    >
      {taken ? `✓ ${label}` : label}
    </button>
  );
}

// ---------------------------------------------------------------------------------- people
export function PeopleSection(ops: Ops) {
  const { review, player } = ops;
  const [all, setAll] = useState(false);
  const fires = ops.count("FIRE");
  const talks = ops.count("TALK");
  const talksLeft = (player.limits_left.TALK ?? 0) - talks;
  const rows = [...review.people]
    .filter((p) => all || p.flagged)
    .sort((a, b) => Number(b.flagged) - Number(a.flagged) || b.flags.length - a.flags.length || a.name.localeCompare(b.name));
  const sinceParty = review.company.days_since_team_event;
  const staff = review.people.length;
  return (
    <>
      <div className="row-between">
        <div className="muted">
          {t("Firing: {fires} of {max} this review · one-to-ones left this week: {talks}", {
            fires,
            max: review.limits.max_fires,
            talks: Math.max(0, talksLeft),
          })}
        </div>
        <button className="ghost" onClick={() => setAll((v) => !v)}>
          {all ? t("Flagged only") : t("Show everyone ({n})", { n: staff })}
        </button>
      </div>
      {rows.length === 0 && <div className="empty">{t("Nobody is flagged. Show everyone to act on someone anyway.")}</div>}
      <div className="people-list">
        {rows.map((p) => (
          <PersonRow key={p.id} ops={ops} p={p} canFire={fires < review.limits.max_fires} canTalk={talksLeft > 0} />
        ))}
      </div>
      <div className="brief-box">
        <b>{t("Team night out")}</b> · {t("about {cost} on the company · lowers everyone's stress.", { cost: eur(12 * staff) })}{" "}
        {!review.review_only.team_event ? (
          <span className="muted">{t("Planned at the monthly review.")}</span>
        ) : sinceParty < 45 ? (
          <span className="muted">{t("The last one was {n} days ago (45-day gap).", { n: sinceParty })}</span>
        ) : (
          <Add ops={ops} action={{ type: "TEAM_EVENT" }} label={t("Plan it")} />
        )}
      </div>
    </>
  );
}

function flagTone(flag: string): string {
  if (flag === "in form") return "good";
  if (flag === "losing" || flag === "not betting") return "bad";
  if (flag.startsWith("away")) return "calm";
  return ""; // a warning: stressed, under review, lost nerve
}

function PersonRow({ ops, p, canFire, canTalk }: { ops: Ops; p: ReviewPerson; canFire: boolean; canTalk: boolean }) {
  const [days, setDays] = useState(3);
  const [to, setTo] = useState("");
  const desks = p.role === "researcher" ? [] : ops.review.desks.filter((d) => d.id !== p.department_id && d.free_seats > 0);
  const talked = ops.player.talked_this_week.includes(p.id);
  return (
    <div className="person-row">
      <div className="row-between">
        <div>
          <b>{p.name}</b>{" "}
          <span className="dim">
            {t(p.title)} · {p.department ? t(p.department) : "—"}
          </span>
          {p.flags.map((f) => (
            <span key={f} className={`chip flag ${flagTone(f)}`}>
              {t(f)}
            </span>
          ))}
        </div>
        <span className="muted tab-nums">
          {p.role === "tipster" ? (
            <>
              {t("90d")} <span className={tone(p.roi_90d)}>{pct(p.roi_90d, 1, true)}</span> {t("over {n} bets", { n: p.bets_90d })} ·{" "}
            </>
          ) : null}
          {t("stress {pct} · {salary}/mo", { pct: pct(p.stress, 0), salary: eur(p.salary) })}
        </span>
      </div>
      {p.note && <div className="advisor-note">{t("Advisor: {note}", { note: p.note })}</div>}
      <div className="row-actions">
        <Add
          ops={ops}
          action={{ type: "TALK", employee_id: p.id }}
          label={t("Talk")}
          disabled={!canTalk || talked || !!p.away}
          why={talked ? t("Already talked this week") : p.away ? t("Away|person") : t("No one-to-ones left this week")}
        />
        {p.under_review ? (
          <Add ops={ops} action={{ type: "CLEAR_REVIEW", employee_id: p.id }} label={t("Lift review")} />
        ) : (
          <Add ops={ops} action={{ type: "WARN", employee_id: p.id, reason: "Formal warning" }} label={t("Warn")} />
        )}
        {p.role === "tipster" && p.level < 3 && <Add ops={ops} action={{ type: "PROMOTE", employee_id: p.id }} label={t("Promote")} />}
        <span className="inline">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label={t("Days off")} disabled={!!p.away}>
            {[1, 2, 3, 5, 7].map((d) => (
              <option key={d} value={d}>
                {t("{n}d", { n: d })}
              </option>
            ))}
          </select>
          <Add ops={ops} action={{ type: "GIVE_TIME_OFF", employee_id: p.id, value: days }} label={t("Time off")} disabled={!!p.away} why={t("Already away")} />
        </span>
        {desks.length > 0 && (
          <span className="inline">
            <select value={to} onChange={(e) => setTo(e.target.value)} aria-label={t("Move to desk")}>
              <option value="">{t("Move to…")}</option>
              {desks.map((d) => (
                <option key={d.id} value={d.id}>
                  {t(d.name)}
                </option>
              ))}
            </select>
            {to && <Add ops={ops} action={{ type: "TRANSFER_EMPLOYEE", employee_id: p.id, department_id: to }} label={t("Move")} />}
          </span>
        )}
        <Add
          ops={ops}
          action={{ type: "FIRE", employee_id: p.id, reason: "Let go at the review" }}
          label={t("Fire")}
          danger
          disabled={!canFire}
          why={t("Firing limit for this review reached")}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------- hiring
export function HireSection(ops: Ops) {
  const { review } = ops;
  const hires = ops.count("HIRE");
  const frozen = review.company.hiring_frozen;
  return (
    <>
      <div className="row-between">
        <div className="muted">
          {review.review_only.hire
            ? t("Hiring: {hires} of {max} this review. The LAB tests applicants' methods when it has budget.", { hires, max: review.limits.max_hires })
            : t("Hiring happens at the monthly review (on the 1st). You can look at the applicants now.")}
        </div>
        {frozen ? (
          <Add ops={ops} action={{ type: "UNFREEZE_HIRING" }} label={t("Lift the freeze")} />
        ) : (
          <Add ops={ops} action={{ type: "FREEZE_HIRING" }} label={t("Freeze hiring")} />
        )}
      </div>
      {review.candidates.length === 0 && <div className="empty">{t("No applicants right now.")}</div>}
      <div className="cand-grid">
        {review.candidates.map((c) => (
          <CandidateCard key={c.id} ops={ops} c={c} disabled={!review.review_only.hire || frozen || hires >= review.limits.max_hires} />
        ))}
      </div>
    </>
  );
}

function CandidateCard({ ops, c, disabled }: { ops: Ops; c: ReviewView["candidates"][number]; disabled: boolean }) {
  const { review } = ops;
  const researcher = c.role === "researcher";
  const targets = researcher
    ? review.lab.department_id && review.lab.free_seats > 0
      ? [{ id: review.lab.department_id, name: "LAB", fit: true }]
      : []
    : review.desks
        .filter((d) => d.free_seats > 0)
        .map((d) => ({ id: d.id, name: d.name, fit: d.preferred_specialties.includes(c.specialty) }))
        .sort((a, b) => Number(b.fit) - Number(a.fit));
  const [to, setTo] = useState(targets[0]?.id ?? "");
  const tested = c.lab_backtest_n !== null && c.lab_backtest_roi !== null;
  const lab = review.lab;
  const canTest = c.testable && !tested && !c.test_due && lab.researchers.length > 0 && lab.budget >= lab.min_test_budget;
  const freeAfter = lab.free_slots - ops.count("TEST_CANDIDATE");
  return (
    <div className="cand">
      <div className="row-between">
        <b>{c.name}</b>
        <span className="muted">{t("{amount}/mo", { amount: eur(c.salary_ask) })}</span>
      </div>
      <div className="dim">
        {researcher ? t("Researcher") : t("Tipster")} · {t(c.specialty_label)} · {t("{n}y experience", { n: c.experience })}
      </div>
      <div className="evidence">
        <span title={t("How good the CV looks. Not proof of skill.")}>CV {c.cv_rating}/100</span>
        {tested ? (
          <span title={t("The LAB backtested this applicant's method on the last 8 months")}>
            {t("LAB test")} <b className={tone(c.lab_backtest_roi)}>{pct(c.lab_backtest_roi, 1, true)}</b>{" "}
            {t("over {n} bets", { n: c.lab_backtest_n ?? 0 })}
          </span>
        ) : c.test_due ? (
          <span className="muted">{t("LAB test running · results {date}", { date: shortDate(c.test_due) })}</span>
        ) : (
          <span className="muted">{researcher ? t("Researchers aren't backtested") : t("Not tested by the LAB")}</span>
        )}
        {canTest && (
          <Add
            ops={ops}
            action={{ type: "TEST_CANDIDATE", candidate_id: c.id }}
            label={t("Test")}
            disabled={freeAfter <= 0}
            why={t("Every LAB slot is busy")}
          />
        )}
      </div>
      <div className="muted">{c.traits_text}</div>
      <div className="pitch">“{c.pitch}”</div>
      {targets.length === 0 ? (
        <div className="muted">{t("No free seat for them.")}</div>
      ) : (
        <div className="row-actions">
          <select value={to} onChange={(e) => setTo(e.target.value)} aria-label={t("Hire into")}>
            {targets.map((x) => (
              <option key={x.id} value={x.id}>
                {x.fit ? t("{desk} (fits)", { desk: t(x.name) }) : t(x.name)}
              </option>
            ))}
          </select>
          <Add ops={ops} action={{ type: "HIRE", candidate_id: c.id, department_id: to }} label={t("Hire")} disabled={disabled || !to} why={t("Not at this review")} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------- desks
export function DesksSection(ops: Ops) {
  const { review } = ops;
  const [kind, setKind] = useState(review.available_department_kinds[0]?.kind ?? "");
  const [seed, setSeed] = useState(1500);
  const canOpen = review.limits.desks < review.limits.max_desks && review.available_department_kinds.length > 0;
  return (
    <>
      <div className="desk-grid">
        {review.desks.map((d) => (
          <DeskCard key={d.id} ops={ops} d={d} />
        ))}
      </div>
      <div className="brief-box">
        <b>{t("Open a desk")}</b> · {t("{n} of {max} desk rooms in use.", { n: review.limits.desks, max: review.limits.max_desks })}{" "}
        {canOpen ? (
          <span className="inline">
            <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label={t("Desk kind")}>
              {review.available_department_kinds.map((k) => (
                <option key={k.kind} value={k.kind}>
                  {t(k.name)}
                </option>
              ))}
            </select>
            <input
              type="number"
              className="edit-num"
              min={300}
              step={100}
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
              aria-label={t("Seed bankroll")}
            />
            <Add ops={ops} action={{ type: "CREATE_DEPARTMENT", department_kind: kind, amount: seed }} label={t("Open")} disabled={!kind} />
          </span>
        ) : (
          <span className="muted">{t("No free room (lease the east desk wing for a seventh) or every kind of desk already exists.")}</span>
        )}
      </div>
    </>
  );
}

function DeskCard({ ops, d }: { ops: Ops; d: ReviewView["desks"][number] }) {
  const [limit, setLimit] = useState(+(d.stake_limit_pct * 100).toFixed(1));
  const [amount, setAmount] = useState(500);
  const books = Object.entries(d.bookmaker_limits);
  return (
    <div className="desk-card">
      <div className="row-between">
        <b>{t(d.name)}</b>
        <span className="muted">{t("{n} tipster(s) · {free} free seat(s)", { n: d.headcount, free: d.free_seats })}</span>
      </div>
      <div className="tab-nums">
        {t("Bankroll {amount}", { amount: eur(d.bankroll) })} · {t("30d")} <span className={tone(d.profit_30d)}>{signedEur(d.profit_30d)}</span> ·{" "}
        {t("90d")} <span className={tone(d.profit_90d)}>{signedEur(d.profit_90d)}</span> (
        {t("{roi} over {n} bets", { roi: pct(d.roi_90d, 1, true), n: d.bets_90d })})
      </div>
      {books.length > 0 && (
        <div className="muted">{t("Max bet per bookmaker: {list}", { list: books.map(([b, v]) => `${b} ${eur(v)}`).join(" · ") })}</div>
      )}
      <div className="row-actions">
        <span className="inline">
          <input
            type="number"
            className="edit-num"
            min={0.5}
            max={10}
            step={0.5}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            aria-label={t("Max stake percent")}
          />
          %
          <Add
            ops={ops}
            action={{ type: "SET_STAKE_LIMIT", department_id: d.id, pct: limit / 100 }}
            label={t("Set max stake")}
            disabled={Math.abs(limit / 100 - d.stake_limit_pct) < 1e-4}
            why={t("That's the current limit")}
          />
        </span>
        <span className="inline">
          <input type="number" className="edit-num" min={0} step={100} value={amount} onChange={(e) => setAmount(Number(e.target.value))} aria-label={t("Amount")} />
          <Add ops={ops} action={{ type: "FUND_DEPARTMENT", department_id: d.id, amount }} label={t("Fund")} disabled={amount <= 0} />
          <Add ops={ops} action={{ type: "WITHDRAW_BANKROLL", department_id: d.id, amount }} label={t("Withdraw")} disabled={amount <= 0} />
        </span>
        <Add ops={ops} action={{ type: "CLOSE_DEPARTMENT", department_id: d.id, reason: "Closed at the review" }} label={t("Close desk")} danger />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------- money
export function MoneySection(ops: Ops) {
  const c = ops.review.company;
  const [marketing, setMarketing] = useState(c.marketing_budget);
  const [borrow, setBorrow] = useState(Math.min(2000, Math.floor(c.credit_available / 100) * 100));
  const [repay, setRepay] = useState(Math.min(c.debt, c.cash));
  const [cut, setCut] = useState(0.1);
  return (
    <>
      <div className="stats">
        <Stat label={t("Cash")} value={eur(c.cash)} />
        <Stat label={t("Debt")} value={eur(c.debt)} />
        <Stat label={t("Credit available")} value={eur(c.credit_available)} />
        <Stat label={t("Payroll")} value={t("{amount}/mo", { amount: eur(c.monthly_payroll) })} />
        <Stat label={t("Running costs")} value={t("{amount}/mo", { amount: eur(c.monthly_costs) })} />
        <Stat label={t("Subscribers")} value={fmtNum(c.subscribers)} />
      </div>
      <div className="money-rows">
        <div className="inline">
          <span className="lbl">{t("Marketing (brings subscribers)")}</span>
          <input
            type="number"
            className="edit-num"
            min={0}
            max={600}
            step={10}
            value={marketing}
            onChange={(e) => setMarketing(Number(e.target.value))}
            aria-label={t("Marketing budget")}
          />
          {t("€/month")}
          <Add
            ops={ops}
            action={{ type: "SET_MARKETING_BUDGET", amount: marketing }}
            label={t("Set")}
            disabled={marketing === c.marketing_budget}
            why={t("That's the current budget")}
          />
        </div>
        <div className="inline">
          <span className="lbl">{t("Borrow from the credit line")}</span>
          <input type="number" className="edit-num" min={0} step={500} value={borrow} onChange={(e) => setBorrow(Number(e.target.value))} aria-label={t("Loan amount")} />
          <Add
            ops={ops}
            action={{ type: "TAKE_LOAN", amount: borrow }}
            label={t("Borrow")}
            disabled={borrow <= 0 || c.credit_available <= 0}
            why={t("No credit available")}
          />
        </div>
        {c.debt > 0 && (
          <div className="inline">
            <span className="lbl">{t("Repay debt")}</span>
            <input type="number" className="edit-num" min={0} step={100} value={repay} onChange={(e) => setRepay(Number(e.target.value))} aria-label={t("Repay amount")} />
            <Add ops={ops} action={{ type: "REPAY_LOAN", amount: repay }} label={t("Repay")} disabled={repay <= 0} />
          </div>
        )}
        <div className="inline">
          <span className="lbl">{t("Company-wide pay cut (everyone's stress rises)")}</span>
          <select value={cut} onChange={(e) => setCut(Number(e.target.value))} aria-label={t("Pay cut")}>
            {[0.05, 0.1, 0.15, 0.2, 0.3].map((v) => (
              <option key={v} value={v}>
                {pct(v, 0)}
              </option>
            ))}
          </select>
          <Add ops={ops} action={{ type: "CUT_SALARIES", pct: cut, reason: "Cost cutting" }} label={t("Cut pay")} danger />
        </div>
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------------- LAB
export function LabSection(ops: Ops) {
  const { review } = ops;
  const lab = review.lab;
  const [budget, setBudget] = useState(lab.budget);
  const tipsters = review.people.filter((p) => p.role === "tipster");
  return (
    <>
      <div className="inline">
        <span className="lbl">
          {t("LAB budget · {n} researcher(s): {names}", { n: lab.researchers.length, names: lab.researchers.join(", ") || t("none") })}
        </span>
        <input
          type="number"
          className="edit-num"
          min={0}
          max={400}
          step={10}
          value={budget}
          onChange={(e) => setBudget(Number(e.target.value))}
          aria-label={t("LAB budget")}
        />
        {t("€/month")}
        <Add ops={ops} action={{ type: "SET_LAB_BUDGET", amount: budget }} label={t("Set")} disabled={budget === lab.budget} why={t("That's the current budget")} />
      </div>
      <div className="muted" style={{ margin: "4px 0 10px" }}>
        {t(
          "{slots} LAB slot(s), {free} free · {tests} applicant test(s) running. More budget = faster experiments and more slots (€90 and €160 unlock extra ones). Applicant tests take a slot until Monday; under {min} the LAB can't run them.",
          { slots: lab.slots, free: lab.free_slots, tests: lab.pending_tests, min: eur(lab.min_test_budget) },
        )}
      </div>
      <BriefPicker ops={ops} />
      <h3>{t("Finished experiments")}</h3>
      {lab.ready.length === 0 && <div className="empty">{t("Nothing ready to roll out.")}</div>}
      {lab.ready.map((x) => (
        <ExperimentCard key={x.id} ops={ops} x={x} tipsters={tipsters} />
      ))}
      <h3 style={{ marginTop: 12 }}>{t("Audit findings")}</h3>
      {lab.audit.length === 0 && <div className="empty">{t("No open findings.")}</div>}
      {lab.audit.map((a) => (
        <div key={a.id} className="person-row">
          <div>{a.text}</div>
          {a.field && a.value !== null ? (
            <div className="row-actions">
              <Add
                ops={ops}
                action={{ type: "ADJUST_STRATEGY", employee_id: a.employee_id, field: a.field, value: a.value }}
                label={t("Set {field} to {value}", { field: a.field, value: a.value })}
              />
            </div>
          ) : (
            <div className="muted">{t("No simple fix suggested.")}</div>
          )}
        </div>
      ))}
    </>
  );
}

/** The LAB's verdict on an experiment (shown lowercase, as the server's DEPLOY / PROMISING / REJECT). */
function recommendationLabel(r: string): string {
  if (r === "DEPLOY") return t("deploy");
  if (r === "PROMISING") return t("promising");
  if (r === "REJECT") return t("reject");
  return r.toLowerCase();
}

function ExperimentCard({ ops, x, tipsters }: { ops: Ops; x: ReviewView["lab"]["ready"][number]; tipsters: ReviewPerson[] }) {
  const [to, setTo] = useState("");
  return (
    <div className="person-row">
      <div className="row-between">
        <b>{x.name}</b>
        <span className={`pill ${x.recommendation === "DEPLOY" ? "won" : "open"}`}>{recommendationLabel(x.recommendation)}</span>
      </div>
      <div className="dim">{x.hypothesis}</div>
      <div className="tab-nums muted">
        {t("Backtest {n} bets, ROI", { n: x.sample })} <span className={tone(x.roi)}>{pct(x.roi, 1, true)}</span>,{" "}
        {t("drawdown {drawdown} · fresh data {n} bets, ROI {roi}", {
          drawdown: pct(x.drawdown, 0),
          n: x.holdout_sample,
          roi: x.holdout_roi === null ? "—" : pct(x.holdout_roi, 1, true),
        })}
      </div>
      <div className="row-actions">
        <Add ops={ops} action={{ type: "SHELVE_STRATEGY", experiment_id: x.id }} label={t("Shelve")} />
        <select value={to} onChange={(e) => setTo(e.target.value)} aria-label={t("Roll out to")}>
          <option value="">{t("Roll out to…")}</option>
          {tipsters.map((tp) => (
            <option key={tp.id} value={tp.id} disabled={tp.strategy_age_days < 60}>
              {tp.name} ({tp.department ? t(tp.department) : tp.department})
              {tp.strategy_age_days < 60 ? ` · ${t("switched {n}d ago", { n: tp.strategy_age_days })}` : ""}
            </option>
          ))}
        </select>
        {to && <Add ops={ops} action={{ type: "DEPLOY_STRATEGY", experiment_id: x.id, employee_id: to }} label={t("Roll out")} />}
      </div>
    </div>
  );
}

function BriefPicker({ ops }: { ops: Ops }) {
  const { review } = ops;
  const brief = review.lab.brief;
  const [choice, setChoice] = useState("none");
  const options: [string, string][] = [
    ["none", t("Researchers' own ideas (no brief)")],
    ...review.competitions.map((c) => [`competition:${c.code}`, t("League: {name}", { name: COMP_NAMES[c.code] ?? t(c.name) })] as [string, string]),
    ...Object.entries(BRIEF_MARKETS).map(([k, v]) => [`market:${k}`, t("Market: {name}", { name: v })] as [string, string]),
    ["underdogs", t("Underdogs at longer odds")],
    ...review.desks.map((d) => [`desk:${d.id}`, t("Help {desk}", { desk: theDesk(d.name) })] as [string, string]),
  ];
  const action = choice.startsWith("desk:")
    ? { type: "SET_LAB_BRIEF" as const, field: "desk", department_id: choice.slice(5) }
    : { type: "SET_LAB_BRIEF" as const, field: choice };
  // the server's label is English: rebuild it (a desk that no longer exists keeps the server's wording)
  const briefDesk = brief?.kind === "desk" ? review.desks.find((d) => d.id === brief.value)?.name : undefined;
  const now = !brief ? "" : brief.kind === "desk" && !briefDesk ? brief.label : briefLabel(brief.kind, brief.value, briefDesk ?? "");
  return (
    <div className="brief-box">
      <b>{t("Research brief")}</b>
      <span className="muted">
        {brief ? t("Now: {brief} (since {date}).", { brief: now, date: shortDate(brief.since) }) : t("Now: researchers' own ideas.")}
      </span>
      {review.scope === "monthly" ? (
        <span className="inline">
          <select value={choice} onChange={(e) => setChoice(e.target.value)} aria-label={t("Research brief")}>
            {options.map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
          <Add ops={ops} action={action} label={t("Set brief")} />
        </span>
      ) : (
        <span className="muted">{t("Set at the monthly review. Stubborn researchers may still chase their own ideas.")}</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------- office
export function OfficeSection(ops: Ops) {
  const { review } = ops;
  const o = review.office;
  return (
    <>
      <div className="muted" style={{ marginBottom: 8 }}>
        {t("Average staff stress {pct} · {n} voluntary departure(s) in 90 days.", { pct: pct(o.avg_staff_stress, 0), n: o.voluntary_departures_90d })}
      </div>
      <div className="facilities">
        {o.facilities.map((f) => (
          <div key={f.key} className={`facility ${f.leased ? "leased" : ""}`}>
            <div className="facility-name">{t(f.name)}</div>
            <div>{t(f.effect)}</div>
            <div className="muted">
              {f.leased
                ? t("Leased since {date} · {monthly}/month", { date: f.since ?? "", monthly: eur(f.monthly_cost) })
                : t("Fit-out {cost} · {monthly}/month", { cost: eur(f.fit_out), monthly: eur(f.monthly_cost) })}
            </div>
            <div className="row-actions">
              {f.leased ? (
                <Add ops={ops} action={{ type: "RELEASE_SPACE", facility: f.key }} label={t("Give up (break fee)")} danger />
              ) : review.review_only.lease ? (
                <Add ops={ops} action={{ type: "LEASE_SPACE", facility: f.key }} label={t("Lease")} />
              ) : (
                <span className="muted">{t("Leases are signed at the monthly review.")}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
