import { useState } from "react";
import { api } from "../api/client";
import type { CeoAction, DepartmentDetail, EmployeeDetail } from "../api/types";
import { t } from "../i18n";
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
      notify(r.applied ? r.result : t("Refused: {reason}", { reason: r.result }));
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
      notify(t("Queued for the monthly review: {label}", { label: p.label }));
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
        <h3>{t("You, the CEO")}</h3>
        <span className="muted">
          {t("one-to-ones left {talks}/{maxTalks} · firings left {fires}/{maxFires} this week", {
            talks: talksLeft,
            maxTalks: player.weekly_limits.TALK,
            fires: firesLeft,
            maxFires: player.weekly_limits.FIRE,
          })}
        </span>
      </div>
      {d.advisor_note && <div className="advisor-note">{t("Advisor: {note}", { note: d.advisor_note })}</div>}
      {d.trust_in_ceo !== null && (
        <div className="muted" style={{ margin: "4px 0" }}>
          {t("Trust in you: {n}/100", { n: d.trust_in_ceo })}
        </div>
      )}
      <div className="row-actions">
        <button
          onClick={() => act({ type: "TALK", employee_id: d.id })}
          disabled={busy || away || talked || talksLeft <= 0}
          title={talked ? t("Already talked this week") : away ? t("Away|person") : t("Stress −5 points, trust in you +3")}
        >
          {t("Talk")}
        </button>
        {d.under_review ? (
          <button onClick={() => act({ type: "CLEAR_REVIEW", employee_id: d.id })} disabled={busy} title={t("Stress eases a little")}>
            {t("Lift review")}
          </button>
        ) : (
          <button onClick={() => act({ type: "WARN", employee_id: d.id, reason: "Formal warning" })} disabled={busy} title={t("Under review: stress rises")}>
            {t("Warn")}
          </button>
        )}
        <span className="inline">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label={t("Days off")} disabled={away}>
            {[1, 2, 3, 5, 7].map((n) => (
              <option key={n} value={n}>
                {t("{n}d", { n })}
              </option>
            ))}
          </select>
          <button onClick={() => act({ type: "GIVE_TIME_OFF", employee_id: d.id, value: days })} disabled={busy || away} title={t("Paid rest; no bets meanwhile")}>
            {t("Time off")}
          </button>
        </span>
        {desks.length > 0 && (
          <span className="inline">
            <select value={to} onChange={(e) => setTo(e.target.value)} aria-label={t("Move to desk")}>
              <option value="">{t("Move to…")}</option>
              {desks.map((x) => (
                <option key={x.id} value={x.id}>
                  {t(x.name)}
                </option>
              ))}
            </select>
            {to && (
              <button onClick={() => act({ type: "TRANSFER_EMPLOYEE", employee_id: d.id, department_id: to })} disabled={busy}>
                {t("Move")}
              </button>
            )}
          </span>
        )}
        {confirmFire ? (
          <>
            <button className="danger" onClick={() => act({ type: "FIRE", employee_id: d.id, reason: "Let go by the CEO" })} disabled={busy}>
              {t("Confirm: fire ({amount} severance)", { amount: eur(severance) })}
            </button>
            <button className="ghost" onClick={() => setConfirmFire(false)}>
              {t("Cancel")}
            </button>
          </>
        ) : (
          <button
            className="danger"
            onClick={() => setConfirmFire(true)}
            disabled={busy || firesLeft <= 0}
            title={firesLeft <= 0 ? t("One firing a week between reviews") : t("Asks to confirm")}
          >
            {t("Fire")}
          </button>
        )}
      </div>
      {d.role === "tipster" && d.level < 3 && (
        <div className="review-only">
          <span className="muted">{t("Promotions are decided at the monthly review.")}</span>
          <button className="ghost" onClick={() => queue({ type: "PROMOTE", employee_id: d.id })} disabled={busy}>
            {t("Queue a promotion")}
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
        <h3>{t("You, the CEO")}</h3>
      </div>
      <div className="row-actions">
        <span className="inline">
          {t("Max stake")}
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
          {t("% of bankroll")}
          <button onClick={() => act({ type: "SET_STAKE_LIMIT", department_id: d.id, pct: limit / 100 })} disabled={busy}>
            {t("Set")}
          </button>
        </span>
      </div>
      <div className="row-actions">
        <span className="inline">
          <input type="number" className="edit-num" min={0} step={100} value={amount} onChange={(e) => setAmount(Number(e.target.value))} aria-label={t("Amount")} />
          <button onClick={() => act({ type: "FUND_DEPARTMENT", department_id: d.id, amount })} disabled={busy || amount <= 0} title={t("From company cash")}>
            {t("Fund")}
          </button>
          <button onClick={() => act({ type: "WITHDRAW_BANKROLL", department_id: d.id, amount })} disabled={busy || amount <= 0} title={t("Back to company cash")}>
            {t("Withdraw")}
          </button>
        </span>
      </div>
      <div className="review-only">
        <span className="muted">{t("Closing a desk is decided at the monthly review.")}</span>
        <button className="ghost" onClick={() => queue({ type: "CLOSE_DEPARTMENT", department_id: d.id, reason: "Queued by the CEO" })} disabled={busy}>
          {t("Queue closing it")}
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
      title={t("Decided at the monthly review")}
    >
      {queued ? t("Queued") : leased ? t("Queue giving it up") : t("Queue the lease")}
    </button>
  );
}
