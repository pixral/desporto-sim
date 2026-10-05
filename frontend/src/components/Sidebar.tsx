import { useState } from "react";
import { t } from "../i18n";
import { useStore } from "../state/store";
import { dayMonth, eur, fmtNum, MARKET_LABEL, signedEur } from "../util/format";

export function Sidebar() {
  const state = useStore((s) => s.state);
  const selectEmployee = useStore((s) => s.selectEmployee);
  const setTab = useStore((s) => s.setTab);
  const [notableOnly, setNotableOnly] = useState(false);
  if (!state) return <aside className="sidebar" />;
  const ceo = state.employees.find((e) => e.role === "ceo");
  const player = state.player;
  const events = [...state.events].reverse().filter((e) => !notableOnly || e.importance >= 2);
  const bets = [...state.ticker].reverse().slice(0, 14);
  return (
    <aside className="sidebar">
      {state.memo && (
        <div className="memo">
          <h3>{t("Memo from {name}", { name: ceo?.name ?? t("the CEO") })}</h3>
          <div>{state.memo.text}</div>
          <div className="meta">
            {t("{scope} review", { scope: t(state.memo.scope) })} · {dayMonth(state.memo.time)}
          </div>
        </div>
      )}
      {state.city.headline && (
        <button className="paper-teaser" onClick={() => setTab("paper")} title={t("Read the morning paper")}>
          <span className="paper-name">{state.city.paper}</span>
          <span>{state.city.headline}</span>
        </button>
      )}
      {player && (
        <button className="player-box" onClick={() => setTab("ceo")} title={t("Your CEO page: queue, log, season")}>
          <span>
            {t("Season {season}/{total} · {days} days to 1 June", {
              season: player.season,
              total: player.seasons_total,
              days: player.days_to_season_end,
            })}
          </span>
          <span className="muted">
            {player.review_open
              ? t("A briefing is waiting for you")
              : player.next_review.date
                ? t("Next briefing {date} ({scope})", { date: dayMonth(player.next_review.date), scope: t(player.next_review.scope ?? "") })
                : t("Your advisor runs the reviews")}{" "}
            · {t("talks {talks} · firings {firings}", { talks: player.limits_left.TALK ?? 0, firings: player.limits_left.FIRE ?? 0 })}
            {player.queue.length ? ` · ${t("{n} queued", { n: player.queue.length })}` : ""}
          </span>
          {player.board.warned && <span className="neg">{t("The board has warned you")}</span>}
        </button>
      )}
      {player
        ? player.advisor_thought && (
            <div className="thought" title={t("Your advisor's read of the situation")}>
              {t("Your advisor: “{thought}”", { thought: player.advisor_thought })}
            </div>
          )
        : state.ceo_thought && (
            <div className="thought" title={t("The CEO's private read of the situation")}>
              {t("{name} thinks: “{thought}”", { name: ceo?.name ?? "", thought: state.ceo_thought })}
            </div>
          )}
      <section>
        <div className="panel-title">
          <h3>{t("Live feed")}</h3>
          <button className="ghost" onClick={() => setNotableOnly((v) => !v)}>
            {notableOnly ? t("Show all") : t("Notable only")}
          </button>
        </div>
        <div className="feed">
          {events.length === 0 && <div className="empty">{t("Nothing yet.")}</div>}
          {events.slice(0, 30).map((e) => (
            <div
              key={e.id}
              className={`feed-item tone-${e.tone} imp-${e.importance}`}
              onClick={() => e.employee_ids[0] && selectEmployee(e.employee_ids[0])}
              style={{ cursor: e.employee_ids[0] ? "pointer" : "default" }}
              title={e.text}
            >
              <span className="bar" />
              <div>
                <div>{e.title}</div>
                <div className="t">
                  {dayMonth(e.time)} {e.time.slice(11, 16)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
      <section>
        <h3 style={{ marginBottom: 8 }}>{t("Bet slip")}</h3>
        <div className="feed">
          {bets.length === 0 && <div className="empty">{t("No bets yet.")}</div>}
          {bets.map((b) => (
            <div key={b.id} className="ticker-row" onClick={() => selectEmployee(b.employee_id)} style={{ cursor: "pointer" }} title={b.reason}>
              <div>
                <div className="sel">
                  {b.employee}: {b.selection} <span className="muted">({MARKET_LABEL[b.market]})</span>
                </div>
                <div className="muted">
                  {b.match} · {eur(b.stake, 2)} @ {fmtNum(b.odds, 2)}
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <span className={`pill ${b.status}`}>{t(b.status)}</span>
                {b.status !== "open" && <div className={b.profit >= 0 ? "pos" : "neg"}>{signedEur(b.profit, 2)}</div>}
              </div>
            </div>
          ))}
        </div>
      </section>
    </aside>
  );
}
