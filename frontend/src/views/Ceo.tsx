import { api } from "../api/client";
import type { ManagementEntry } from "../api/types";
import { FacilityQueueButton } from "../components/CeoActions";
import { HiringPanel } from "../components/HiringPanel";
import { useStore } from "../state/store";
import { eur, shortDate } from "../util/format";
import { useLive } from "../util/hooks";

const PAUSE_LABEL: Record<string, string> = {
  monthly: "monthly reviews (your advisor takes the Mondays)",
  every_review: "every review",
  events_only: "hands off (your advisor runs every review)",
};
const BY_LABEL: Record<ManagementEntry["by"], string> = { ai: "AI CEO", player: "You", advisor: "Advisor acted" };

export function Ceo() {
  const state = useStore((s) => s.state);
  const notify = useStore((s) => s.notify);
  const { data, reload } = useLive(() => api.management(), `${state?.clock.day_index}:${state?.clock.phase}:${state?.player?.queue.length}`);
  const ceo = state?.employees.find((e) => e.role === "ceo");
  const player = state?.player;
  const unqueue = async (i: number) => {
    try {
      await api.unqueue(i);
      reload();
    } catch (e) {
      notify((e as Error).message);
    }
  };
  return (
    <div className="page">
      <div className="panel">
        {player ? (
          <>
            <h2>{player.name} — you run the company</h2>
            <div className="dim" style={{ marginTop: 4 }}>
              Advisor: {player.advisor_label}. The clock stops for {PAUSE_LABEL[player.pause_mode]}. Between reviews you can talk to
              people, warn, give time off, move them, set desk limits and bankrolls, and fire (one a week): click someone in the
              office. Everything else is decided at the monthly review; queue it below.
            </div>
            <div className="stats" style={{ marginTop: 10 }}>
              <div className="stat">
                <div className="label">Season</div>
                <div className="value">
                  {player.season}/{player.seasons_total}
                </div>
                <div className="muted">{player.days_to_season_end} days to 1 June</div>
              </div>
              <div className="stat">
                <div className="label">Briefings you signed</div>
                <div className="value">{player.reviews_signed}</div>
              </div>
              <div className="stat">
                <div className="label">Handled by the advisor</div>
                <div className="value">{player.reviews_auto}</div>
              </div>
              <div className="stat">
                <div className="label">Advice taken / skipped</div>
                <div className="value">
                  {player.advice_taken} / {player.advice_skipped}
                </div>
              </div>
              <div className="stat">
                <div className="label">Next briefing</div>
                <div className="value" style={{ fontSize: 18 }}>
                  {player.next_review.date ? shortDate(player.next_review.date) : "—"}
                </div>
                <div className="muted">{player.next_review.scope ?? "your advisor handles them"}</div>
              </div>
            </div>
          </>
        ) : (
          <>
            <h2>{ceo ? `${ceo.name} — ${state?.run.ceo_style_label}` : "CEO"}</h2>
            <div className="dim" style={{ marginTop: 4 }}>
              The CEO reviews the company every Monday (light) and on the 1st of each month (full review: people, money, desks,
              LAB). Every proposed action is validated; rejected actions are shown with the reason.
            </div>
          </>
        )}
      </div>
      {player && (
        <div className="panel">
          <div className="panel-title">
            <h3>Queued for the monthly review</h3>
            <span className="muted">{player.queue.length} of 12</span>
          </div>
          {player.queue.length === 0 ? (
            <div className="muted">
              Nothing queued. Hires, promotions, leases and closing desks can be queued between reviews; they come pre-ticked in
              the next monthly briefing.
            </div>
          ) : (
            <table>
              <tbody>
                {player.queue.map((q, i) => (
                  <tr key={i}>
                    <td>{q.label}</td>
                    <td className="r">
                      <button className="ghost" onClick={() => unqueue(i)}>
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      {player && <HiringPanel />}
      {state && (
        <div className="panel">
          <div className="panel-title">
            <h3>Office space</h3>
            <span className="muted">{state.office.desk_rooms} desk rooms</span>
          </div>
          <div className="dim" style={{ marginBottom: 10 }}>
            The east wing next door is for lease. Leases are signed at monthly reviews: each space costs a one-off fit-out plus a
            monthly bill, and changes how the company works.
          </div>
          <div className="facilities">
            {state.office.facilities.map((f) => (
              <div key={f.key} className={`facility ${f.leased ? "leased" : ""}`}>
                <div className="facility-name">{f.name}</div>
                <div>{f.effect}</div>
                <div className="muted">
                  {f.leased
                    ? `Leased since ${shortDate(f.since!)} · ${eur(f.monthly_cost)}/month`
                    : `Fit-out ${eur(f.fit_out)} · ${eur(f.monthly_cost)}/month`}
                </div>
                <FacilityQueueButton facility={f.key} leased={f.leased} />
              </div>
            ))}
          </div>
        </div>
      )}
      {(data ?? []).map((m, i) => (
        <div className="panel" key={i}>
          <div className="panel-title">
            <h3>
              {m.scope === "office" ? "Office hours" : `${m.scope} review`} · {shortDate(m.time)}
            </h3>
            <span>
              {player && <span className={`chip by-${m.by}`}>{BY_LABEL[m.by]}</span>}{" "}
              <span className="muted">{m.actions.length} action(s)</span>
            </span>
          </div>
          {m.thought && (
            <div className="thought">
              {m.by === "ai" ? "" : "Advisor: "}“{m.thought}”
            </div>
          )}
          {m.memo && <div className="memo" style={{ margin: "8px 0" }}>{m.memo}</div>}
          {m.actions.length > 0 && (
            <table>
              <tbody>
                {m.actions.map((a, j) => (
                  <tr key={j}>
                    <td style={{ width: 160 }}>
                      <span className={`pill ${a.applied ? "won" : "lost"}`}>{a.applied ? "done" : "rejected"}</span> {a.type}
                    </td>
                    <td>
                      {a.result}
                      {a.reason && <div className="muted">{a.reason}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {m.skipped.length > 0 && (
            <div className="muted" style={{ marginTop: 6 }}>
              {m.by === "advisor" ? "Left for you: " : "You turned down: "}
              {m.skipped.join(" · ")}
            </div>
          )}
        </div>
      ))}
      {data && !data.length && <div className="panel empty">No reviews yet. The first one happens on the next Monday.</div>}
    </div>
  );
}
