import { useState } from "react";
import { api } from "../api/client";
import type { CeoAction, DepartmentDetail, EmployeeDetail } from "../api/types";
import { useStore } from "../state/store";
import { eur } from "../util/format";

/** Office hours (act now) or the queue (for the monthly review). Both report back with a toast. */
function useCeo(onDone?: () => void) {
  const notify = useStore((s) => s.notify);
  const [busy, setBusy] = useState(false);
  const act = async (action: CeoAction) => {
    setBusy(true);
    try {
      const r = await api.act(action);
      notify(r.applied ? r.result : `Refused: ${r.result}`);
      if (r.applied) onDone?.();
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const queue = async (action: CeoAction) => {
    setBusy(true);
    try {
      const p = await api.queue(action);
      notify(`Queued for the monthly review: ${p.label}`);
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return { act, queue, busy };
}

/** The CEO's menu for one person (player mode only). */
export function PersonActions({ d, onDone }: { d: EmployeeDetail; onDone: () => void }) {
  const player = useStore((s) => s.state?.player);
  const departments = useStore((s) => s.state?.departments ?? []);
  const { act, queue, busy } = useCeo(onDone);
  const [days, setDays] = useState(3);
  const [to, setTo] = useState("");
  const [confirmFire, setConfirmFire] = useState(false);
  if (!player || !d.active || d.role === "ceo") return null;
  const away = d.status === "away";
  const talked = player.talked_this_week.includes(d.id);
  const talksLeft = player.limits_left.TALK ?? 0;
  const firesLeft = player.limits_left.FIRE ?? 0;
  const severance = d.salary * player.severance_months;
  const desks = departments.filter((x) => x.id !== d.department_id && (d.role === "researcher" ? x.kind === "lab" : x.kind !== "lab"));
  return (
    <div className="panel ceo-menu">
      <div className="panel-title">
        <h3>You, the CEO</h3>
        <span className="muted">
          one-to-ones left {talksLeft}/{player.weekly_limits.TALK} · firings left {firesLeft}/{player.weekly_limits.FIRE} this week
        </span>
      </div>
      {d.advisor_note && <div className="advisor-note">Advisor: {d.advisor_note}</div>}
      {d.trust_in_ceo !== null && (
        <div className="muted" style={{ margin: "4px 0" }}>
          Trust in you: {d.trust_in_ceo}/100
        </div>
      )}
      <div className="row-actions">
        <button
          onClick={() => act({ type: "TALK", employee_id: d.id })}
          disabled={busy || away || talked || talksLeft <= 0}
          title={talked ? "Already talked this week" : away ? "Away" : "Stress −5 points, trust in you +3"}
        >
          Talk
        </button>
        {d.under_review ? (
          <button onClick={() => act({ type: "CLEAR_REVIEW", employee_id: d.id })} disabled={busy} title="Stress eases a little">
            Lift review
          </button>
        ) : (
          <button onClick={() => act({ type: "WARN", employee_id: d.id, reason: "Formal warning" })} disabled={busy} title="Under review: stress rises">
            Warn
          </button>
        )}
        <span className="inline">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Days off" disabled={away}>
            {[1, 2, 3, 5, 7].map((n) => (
              <option key={n} value={n}>
                {n}d
              </option>
            ))}
          </select>
          <button onClick={() => act({ type: "GIVE_TIME_OFF", employee_id: d.id, value: days })} disabled={busy || away} title="Paid rest; no bets meanwhile">
            Time off
          </button>
        </span>
        {desks.length > 0 && (
          <span className="inline">
            <select value={to} onChange={(e) => setTo(e.target.value)} aria-label="Move to desk">
              <option value="">Move to…</option>
              {desks.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name}
                </option>
              ))}
            </select>
            {to && (
              <button onClick={() => act({ type: "TRANSFER_EMPLOYEE", employee_id: d.id, department_id: to })} disabled={busy}>
                Move
              </button>
            )}
          </span>
        )}
        {confirmFire ? (
          <>
            <button className="danger" onClick={() => act({ type: "FIRE", employee_id: d.id, reason: "Let go by the CEO" })} disabled={busy}>
              Confirm: fire ({eur(severance)} severance)
            </button>
            <button className="ghost" onClick={() => setConfirmFire(false)}>
              Cancel
            </button>
          </>
        ) : (
          <button className="danger" onClick={() => setConfirmFire(true)} disabled={busy || firesLeft <= 0} title={firesLeft <= 0 ? "One firing a week between reviews" : "Asks to confirm"}>
            Fire
          </button>
        )}
      </div>
      {d.role === "tipster" && d.level < 3 && (
        <div className="review-only">
          <span className="muted">Promotions are decided at the monthly review.</span>
          <button className="ghost" onClick={() => queue({ type: "PROMOTE", employee_id: d.id })} disabled={busy}>
            Queue a promotion
          </button>
        </div>
      )}
    </div>
  );
}

/** The CEO's menu for a desk (player mode only). */
export function DeskActions({ d, onDone }: { d: DepartmentDetail; onDone: () => void }) {
  const player = useStore((s) => s.state?.player);
  const { act, queue, busy } = useCeo(onDone);
  const [limit, setLimit] = useState(+(d.stake_limit_pct * 100).toFixed(1));
  const [amount, setAmount] = useState(500);
  if (!player || !d.active || d.kind === "lab") return null;
  return (
    <div className="panel ceo-menu">
      <div className="panel-title">
        <h3>You, the CEO</h3>
      </div>
      <div className="row-actions">
        <span className="inline">
          Max stake
          <input type="number" className="edit-num" min={0.5} max={10} step={0.5} value={limit} onChange={(e) => setLimit(Number(e.target.value))} aria-label="Max stake percent" />
          % of bankroll
          <button onClick={() => act({ type: "SET_STAKE_LIMIT", department_id: d.id, pct: limit / 100 })} disabled={busy}>
            Set
          </button>
        </span>
      </div>
      <div className="row-actions">
        <span className="inline">
          <input type="number" className="edit-num" min={0} step={100} value={amount} onChange={(e) => setAmount(Number(e.target.value))} aria-label="Amount" />
          <button onClick={() => act({ type: "FUND_DEPARTMENT", department_id: d.id, amount })} disabled={busy || amount <= 0} title="From company cash">
            Fund
          </button>
          <button onClick={() => act({ type: "WITHDRAW_BANKROLL", department_id: d.id, amount })} disabled={busy || amount <= 0} title="Back to company cash">
            Withdraw
          </button>
        </span>
      </div>
      <div className="review-only">
        <span className="muted">Closing a desk is decided at the monthly review.</span>
        <button className="ghost" onClick={() => queue({ type: "CLOSE_DEPARTMENT", department_id: d.id, reason: "Queued by the CEO" })} disabled={busy}>
          Queue closing it
        </button>
      </div>
    </div>
  );
}

/** Queue a lease (or giving one up) for the monthly review, from the office space panel. */
export function FacilityQueueButton({ facility, leased }: { facility: "canteen" | "desk_wing" | "studio"; leased: boolean }) {
  const player = useStore((s) => s.state?.player);
  const { queue, busy } = useCeo();
  if (!player) return null;
  const queued = player.queue.some((q) => q.action.facility === facility);
  return (
    <button
      className="ghost"
      disabled={busy || queued}
      onClick={() => queue({ type: leased ? "RELEASE_SPACE" : "LEASE_SPACE", facility })}
      title="Decided at the monthly review"
    >
      {queued ? "Queued" : leased ? "Queue giving it up" : "Queue the lease"}
    </button>
  );
}
