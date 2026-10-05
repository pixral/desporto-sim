import { useState } from "react";
import type { CeoAction, PlayerView, ReviewPerson, ReviewView } from "../api/types";
import { BRIEF_MARKETS, COMP_NAMES } from "../util/actions";
import { eur, pct, shortDate, signedEur, tone } from "../util/format";

export interface Ops {
  review: ReviewView;
  player: PlayerView;
  has: (a: CeoAction) => boolean;
  count: (t: CeoAction["type"]) => number;
  add: (a: CeoAction) => void;
}

function Add({ ops, action, label, disabled, why, danger }: { ops: Ops; action: CeoAction; label: string; disabled?: boolean; why?: string; danger?: boolean }) {
  const taken = ops.has(action);
  return (
    <button
      className={taken ? "active" : danger ? "danger" : ""}
      disabled={disabled || taken}
      title={taken ? "Already in your decisions" : why}
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
          Firing: {fires} of {review.limits.max_fires} this review · one-to-ones left this week: {Math.max(0, talksLeft)}
        </div>
        <button className="ghost" onClick={() => setAll((v) => !v)}>
          {all ? "Flagged only" : `Show everyone (${staff})`}
        </button>
      </div>
      {rows.length === 0 && <div className="empty">Nobody is flagged. Show everyone to act on someone anyway.</div>}
      <div className="people-list">
        {rows.map((p) => (
          <PersonRow key={p.id} ops={ops} p={p} canFire={fires < review.limits.max_fires} canTalk={talksLeft > 0} />
        ))}
      </div>
      <div className="brief-box">
        <b>Team night out</b> · about {eur(12 * staff)} on the company · lowers everyone's stress.{" "}
        {!review.review_only.team_event ? (
          <span className="muted">Planned at the monthly review.</span>
        ) : sinceParty < 45 ? (
          <span className="muted">The last one was {sinceParty} days ago (45-day gap).</span>
        ) : (
          <Add ops={ops} action={{ type: "TEAM_EVENT" }} label="Plan it" />
        )}
      </div>
    </>
  );
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
          <b>{p.name}</b> <span className="dim">{p.title} · {p.department ?? "—"}</span>
          {p.flags.map((f) => (
            <span key={f} className={`chip flag ${f === "in form" ? "good" : ""}`}>
              {f}
            </span>
          ))}
        </div>
        <span className="muted tab-nums">
          {p.role === "tipster" ? (
            <>
              90d <span className={tone(p.roi_90d)}>{pct(p.roi_90d, 1, true)}</span> over {p.bets_90d} bets ·{" "}
            </>
          ) : null}
          stress {pct(p.stress, 0)} · {eur(p.salary)}/mo
        </span>
      </div>
      {p.note && <div className="advisor-note">Advisor: {p.note}</div>}
      <div className="row-actions">
        <Add ops={ops} action={{ type: "TALK", employee_id: p.id }} label="Talk" disabled={!canTalk || talked || !!p.away} why={talked ? "Already talked this week" : p.away ? "Away" : "No one-to-ones left this week"} />
        {p.under_review ? (
          <Add ops={ops} action={{ type: "CLEAR_REVIEW", employee_id: p.id }} label="Lift review" />
        ) : (
          <Add ops={ops} action={{ type: "WARN", employee_id: p.id, reason: "Formal warning" }} label="Warn" />
        )}
        {p.role === "tipster" && p.level < 3 && <Add ops={ops} action={{ type: "PROMOTE", employee_id: p.id }} label="Promote" />}
        <span className="inline">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Days off" disabled={!!p.away}>
            {[1, 2, 3, 5, 7].map((d) => (
              <option key={d} value={d}>
                {d}d
              </option>
            ))}
          </select>
          <Add ops={ops} action={{ type: "GIVE_TIME_OFF", employee_id: p.id, value: days }} label="Time off" disabled={!!p.away} why="Already away" />
        </span>
        {desks.length > 0 && (
          <span className="inline">
            <select value={to} onChange={(e) => setTo(e.target.value)} aria-label="Move to desk">
              <option value="">Move to…</option>
              {desks.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
            {to && <Add ops={ops} action={{ type: "TRANSFER_EMPLOYEE", employee_id: p.id, department_id: to }} label="Move" />}
          </span>
        )}
        <Add ops={ops} action={{ type: "FIRE", employee_id: p.id, reason: "Let go at the review" }} label="Fire" danger disabled={!canFire} why="Firing limit for this review reached" />
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
            ? `Hiring: ${hires} of ${review.limits.max_hires} this review. The LAB tests applicants' methods when it has budget.`
            : "Hiring happens at the monthly review (on the 1st). You can look at the applicants now."}
        </div>
        {frozen ? <Add ops={ops} action={{ type: "UNFREEZE_HIRING" }} label="Lift the freeze" /> : <Add ops={ops} action={{ type: "FREEZE_HIRING" }} label="Freeze hiring" />}
      </div>
      {review.candidates.length === 0 && <div className="empty">No applicants right now.</div>}
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
        <span className="muted">{eur(c.salary_ask)}/mo</span>
      </div>
      <div className="dim">
        {researcher ? "Researcher" : "Tipster"} · {c.specialty_label} · {c.experience}y experience
      </div>
      <div className="evidence">
        <span title="How good the CV looks. Not proof of skill.">CV {c.cv_rating}/100</span>
        {tested ? (
          <span title="The LAB backtested this applicant's method on the last 8 months">
            LAB test <b className={tone(c.lab_backtest_roi)}>{pct(c.lab_backtest_roi, 1, true)}</b> over {c.lab_backtest_n} bets
          </span>
        ) : c.test_due ? (
          <span className="muted">LAB test running · results {shortDate(c.test_due)}</span>
        ) : (
          <span className="muted">{researcher ? "Researchers aren't backtested" : "Not tested by the LAB"}</span>
        )}
        {canTest && (
          <Add
            ops={ops}
            action={{ type: "TEST_CANDIDATE", candidate_id: c.id }}
            label="Test"
            disabled={freeAfter <= 0}
            why="Every LAB slot is busy"
          />
        )}
      </div>
      <div className="muted">{c.traits_text}</div>
      <div className="pitch">“{c.pitch}”</div>
      {targets.length === 0 ? (
        <div className="muted">No free seat for them.</div>
      ) : (
        <div className="row-actions">
          <select value={to} onChange={(e) => setTo(e.target.value)} aria-label="Hire into">
            {targets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
                {t.fit ? " (fits)" : ""}
              </option>
            ))}
          </select>
          <Add ops={ops} action={{ type: "HIRE", candidate_id: c.id, department_id: to }} label="Hire" disabled={disabled || !to} why="Not at this review" />
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
        <b>Open a desk</b> · {review.limits.desks} of {review.limits.max_desks} desk rooms in use.{" "}
        {canOpen ? (
          <span className="inline">
            <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Desk kind">
              {review.available_department_kinds.map((k) => (
                <option key={k.kind} value={k.kind}>
                  {k.name}
                </option>
              ))}
            </select>
            <input type="number" className="edit-num" min={300} step={100} value={seed} onChange={(e) => setSeed(Number(e.target.value))} aria-label="Seed bankroll" />
            <Add ops={ops} action={{ type: "CREATE_DEPARTMENT", department_kind: kind, amount: seed }} label="Open" disabled={!kind} />
          </span>
        ) : (
          <span className="muted">No free room (lease the east desk wing for a seventh) or every kind of desk already exists.</span>
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
        <b>{d.name}</b>
        <span className="muted">
          {d.headcount} tipster(s) · {d.free_seats} free seat(s)
        </span>
      </div>
      <div className="tab-nums">
        Bankroll {eur(d.bankroll)} · 30d <span className={tone(d.profit_30d)}>{signedEur(d.profit_30d)}</span> · 90d{" "}
        <span className={tone(d.profit_90d)}>{signedEur(d.profit_90d)}</span> ({pct(d.roi_90d, 1, true)} over {d.bets_90d} bets)
      </div>
      {books.length > 0 && <div className="muted">Max bet per bookmaker: {books.map(([b, v]) => `${b} ${eur(v)}`).join(" · ")}</div>}
      <div className="row-actions">
        <span className="inline">
          <input type="number" className="edit-num" min={0.5} max={10} step={0.5} value={limit} onChange={(e) => setLimit(Number(e.target.value))} aria-label="Max stake percent" />
          %
          <Add ops={ops} action={{ type: "SET_STAKE_LIMIT", department_id: d.id, pct: limit / 100 }} label="Set max stake" disabled={Math.abs(limit / 100 - d.stake_limit_pct) < 1e-4} why="That's the current limit" />
        </span>
        <span className="inline">
          <input type="number" className="edit-num" min={0} step={100} value={amount} onChange={(e) => setAmount(Number(e.target.value))} aria-label="Amount" />
          <Add ops={ops} action={{ type: "FUND_DEPARTMENT", department_id: d.id, amount }} label="Fund" disabled={amount <= 0} />
          <Add ops={ops} action={{ type: "WITHDRAW_BANKROLL", department_id: d.id, amount }} label="Withdraw" disabled={amount <= 0} />
        </span>
        <Add ops={ops} action={{ type: "CLOSE_DEPARTMENT", department_id: d.id, reason: "Closed at the review" }} label="Close desk" danger />
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
        <Stat label="Cash" value={eur(c.cash)} />
        <Stat label="Debt" value={eur(c.debt)} />
        <Stat label="Credit available" value={eur(c.credit_available)} />
        <Stat label="Payroll" value={`${eur(c.monthly_payroll)}/mo`} />
        <Stat label="Running costs" value={`${eur(c.monthly_costs)}/mo`} />
        <Stat label="Subscribers" value={c.subscribers.toLocaleString()} />
      </div>
      <div className="money-rows">
        <div className="inline">
          <span className="lbl">Marketing (brings subscribers)</span>
          <input type="number" className="edit-num" min={0} max={600} step={10} value={marketing} onChange={(e) => setMarketing(Number(e.target.value))} aria-label="Marketing budget" />
          €/month
          <Add ops={ops} action={{ type: "SET_MARKETING_BUDGET", amount: marketing }} label="Set" disabled={marketing === c.marketing_budget} why="That's the current budget" />
        </div>
        <div className="inline">
          <span className="lbl">Borrow from the credit line</span>
          <input type="number" className="edit-num" min={0} step={500} value={borrow} onChange={(e) => setBorrow(Number(e.target.value))} aria-label="Loan amount" />
          <Add ops={ops} action={{ type: "TAKE_LOAN", amount: borrow }} label="Borrow" disabled={borrow <= 0 || c.credit_available <= 0} why="No credit available" />
        </div>
        {c.debt > 0 && (
          <div className="inline">
            <span className="lbl">Repay debt</span>
            <input type="number" className="edit-num" min={0} step={100} value={repay} onChange={(e) => setRepay(Number(e.target.value))} aria-label="Repay amount" />
            <Add ops={ops} action={{ type: "REPAY_LOAN", amount: repay }} label="Repay" disabled={repay <= 0} />
          </div>
        )}
        <div className="inline">
          <span className="lbl">Company-wide pay cut (everyone's stress rises)</span>
          <select value={cut} onChange={(e) => setCut(Number(e.target.value))} aria-label="Pay cut">
            {[0.05, 0.1, 0.15, 0.2, 0.3].map((v) => (
              <option key={v} value={v}>
                {pct(v, 0)}
              </option>
            ))}
          </select>
          <Add ops={ops} action={{ type: "CUT_SALARIES", pct: cut, reason: "Cost cutting" }} label="Cut pay" danger />
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
          LAB budget · {lab.researchers.length} researcher(s): {lab.researchers.join(", ") || "none"}
        </span>
        <input type="number" className="edit-num" min={0} max={400} step={10} value={budget} onChange={(e) => setBudget(Number(e.target.value))} aria-label="LAB budget" />
        €/month
        <Add ops={ops} action={{ type: "SET_LAB_BUDGET", amount: budget }} label="Set" disabled={budget === lab.budget} why="That's the current budget" />
      </div>
      <div className="muted" style={{ margin: "4px 0 10px" }}>
        {lab.slots} LAB slot(s), {lab.free_slots} free · {lab.pending_tests} applicant test(s) running. More budget = faster
        experiments and more slots (€90 and €160 unlock extra ones). Applicant tests take a slot until Monday; under{" "}
        {eur(lab.min_test_budget)} the LAB can't run them.
      </div>
      <BriefPicker ops={ops} />
      <h3>Finished experiments</h3>
      {lab.ready.length === 0 && <div className="empty">Nothing ready to roll out.</div>}
      {lab.ready.map((x) => (
        <ExperimentCard key={x.id} ops={ops} x={x} tipsters={tipsters} />
      ))}
      <h3 style={{ marginTop: 12 }}>Audit findings</h3>
      {lab.audit.length === 0 && <div className="empty">No open findings.</div>}
      {lab.audit.map((a) => (
        <div key={a.id} className="person-row">
          <div>{a.text}</div>
          {a.field && a.value !== null ? (
            <div className="row-actions">
              <Add ops={ops} action={{ type: "ADJUST_STRATEGY", employee_id: a.employee_id, field: a.field, value: a.value }} label={`Set ${a.field} to ${a.value}`} />
            </div>
          ) : (
            <div className="muted">No simple fix suggested.</div>
          )}
        </div>
      ))}
    </>
  );
}

function ExperimentCard({ ops, x, tipsters }: { ops: Ops; x: ReviewView["lab"]["ready"][number]; tipsters: ReviewPerson[] }) {
  const [to, setTo] = useState("");
  return (
    <div className="person-row">
      <div className="row-between">
        <b>{x.name}</b>
        <span className={`pill ${x.recommendation === "DEPLOY" ? "won" : "open"}`}>{x.recommendation.toLowerCase()}</span>
      </div>
      <div className="dim">{x.hypothesis}</div>
      <div className="tab-nums muted">
        Backtest {x.sample} bets, ROI <span className={tone(x.roi)}>{pct(x.roi, 1, true)}</span>, drawdown {pct(x.drawdown, 0)} · fresh data{" "}
        {x.holdout_sample} bets, ROI {x.holdout_roi === null ? "—" : pct(x.holdout_roi, 1, true)}
      </div>
      <div className="row-actions">
        <Add ops={ops} action={{ type: "SHELVE_STRATEGY", experiment_id: x.id }} label="Shelve" />
        <select value={to} onChange={(e) => setTo(e.target.value)} aria-label="Roll out to">
          <option value="">Roll out to…</option>
          {tipsters.map((t) => (
            <option key={t.id} value={t.id} disabled={t.strategy_age_days < 60}>
              {t.name} ({t.department}){t.strategy_age_days < 60 ? ` · switched ${t.strategy_age_days}d ago` : ""}
            </option>
          ))}
        </select>
        {to && <Add ops={ops} action={{ type: "DEPLOY_STRATEGY", experiment_id: x.id, employee_id: to }} label="Roll out" />}
      </div>
    </div>
  );
}

function BriefPicker({ ops }: { ops: Ops }) {
  const { review } = ops;
  const brief = review.lab.brief;
  const [choice, setChoice] = useState("none");
  const options: [string, string][] = [
    ["none", "Researchers' own ideas (no brief)"],
    ...review.competitions.map((c) => [`competition:${c.code}`, `League: ${COMP_NAMES[c.code] ?? c.name}`] as [string, string]),
    ...Object.entries(BRIEF_MARKETS).map(([k, v]) => [`market:${k}`, `Market: ${v}`] as [string, string]),
    ["underdogs", "Underdogs at longer odds"],
    ...review.desks.map((d) => [`desk:${d.id}`, `Help the ${d.name}`] as [string, string]),
  ];
  const action = choice.startsWith("desk:")
    ? { type: "SET_LAB_BRIEF" as const, field: "desk", department_id: choice.slice(5) }
    : { type: "SET_LAB_BRIEF" as const, field: choice };
  return (
    <div className="brief-box">
      <b>Research brief</b>
      <span className="muted">Now: {brief ? `${brief.label} (since ${shortDate(brief.since)})` : "researchers' own ideas"}.</span>
      {review.scope === "monthly" ? (
        <span className="inline">
          <select value={choice} onChange={(e) => setChoice(e.target.value)} aria-label="Research brief">
            {options.map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
          <Add ops={ops} action={action} label="Set brief" />
        </span>
      ) : (
        <span className="muted">Set at the monthly review. Stubborn researchers may still chase their own ideas.</span>
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
        Average staff stress {pct(o.avg_staff_stress, 0)} · {o.voluntary_departures_90d} voluntary departure(s) in 90 days.
      </div>
      <div className="facilities">
        {o.facilities.map((f) => (
          <div key={f.key} className={`facility ${f.leased ? "leased" : ""}`}>
            <div className="facility-name">{f.name}</div>
            <div>{f.effect}</div>
            <div className="muted">
              {f.leased ? `Leased since ${f.since} · ${eur(f.monthly_cost)}/month` : `Fit-out ${eur(f.fit_out)} · ${eur(f.monthly_cost)}/month`}
            </div>
            <div className="row-actions">
              {f.leased ? (
                <Add ops={ops} action={{ type: "RELEASE_SPACE", facility: f.key }} label="Give up (break fee)" danger />
              ) : review.review_only.lease ? (
                <Add ops={ops} action={{ type: "LEASE_SPACE", facility: f.key }} label="Lease" />
              ) : (
                <span className="muted">Leases are signed at the monthly review.</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
