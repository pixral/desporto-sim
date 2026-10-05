import { useEffect } from "react";
import { api } from "../api/client";
import { t } from "../i18n";
import { useStore } from "../state/store";
import { eur, fmtNum, signedEur } from "../util/format";
import { useLive } from "../util/hooks";

const ICON: Record<string, string> = {
  MVP: "★",
  "Flop of the season": "▼",
  Sharpest: "◎",
  "Biggest win": "€",
  "Desk of the season": "⌂",
  "LAB idea of the season": "⚗",
};

/** Season awards: shown once when a season closes, and again from the History view. */
export function RecapModal() {
  const state = useStore((s) => s.state);
  const open = useStore((s) => s.recapOpen);
  const setOpen = useStore((s) => s.setRecapOpen);
  const setTab = useStore((s) => s.setTab);
  const latest = state?.latest_recap;

  useEffect(() => {
    if (!latest || !state) return;
    const key = `recap-seen:${state.run.id}`;
    let seen: string[] = [];
    try {
      seen = JSON.parse(localStorage.getItem(key) ?? "[]");
    } catch {
      /* storage unavailable: show it anyway */
    }
    if (!seen.includes(latest.id)) {
      setOpen(latest.id);
      try {
        localStorage.setItem(key, JSON.stringify([...seen, latest.id].slice(-20)));
      } catch {
        /* ignore */
      }
    }
  }, [latest?.id, state?.run.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const { data } = useLive(() => (open ? api.recaps() : Promise.resolve([])), open);
  if (!open) return null;
  const r = data?.find((x) => x.id === open);
  if (!r) return null;
  const change = r.value_end - r.value_start;
  return (
    <div className="modal-backdrop" onClick={() => setOpen(null)}>
      <div className="end-card recap" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={t("Season {n} awards", { n: r.season })}>
        <div className="muted" style={{ fontFamily: "var(--font-head)", fontSize: 12 }}>
          {t("SEASON {n}", { n: r.season })}
        </div>
        <h1>{t("AWARDS NIGHT")}</h1>
        <div className="dim" style={{ marginBottom: 14 }}>
          {state?.run.company_name}: {t("company value {start} → {end}", { start: eur(r.value_start), end: eur(r.value_end) })} (
          <span className={change >= 0 ? "pos" : "neg"}>{signedEur(change)}</span>)
        </div>
        <div className="awards">
          {r.awards.map((a) => (
            <div key={a.title} className={`award ${a.title === "Flop of the season" ? "flop" : ""}`}>
              <div className="award-icon" aria-hidden>
                {ICON[a.title] ?? "★"}
              </div>
              <div>
                <div className="award-title">{t(a.title)}</div>
                <div className="award-name">{a.name}</div>
                <div className="muted">{a.text}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="end-grid">
          <span className="dim">{t("Betting result")}</span>
          <span className="v">{signedEur(r.betting)}</span>
          <span className="dim">{t("Net result (after costs)")}</span>
          <span className="v">{signedEur(r.net)}</span>
          <span className="dim">{t("Bets settled")}</span>
          <span className="v">{fmtNum(r.bets)}</span>
          <span className="dim">{t("Hired / fired / left")}</span>
          <span className="v">
            {r.hires} / {r.fires} / {r.quits}
          </span>
        </div>
        <div className="controls" style={{ justifyContent: "center" }}>
          <button
            onClick={() => {
              setOpen(null);
              setTab("history");
            }}
          >
            {t("Read the history")}
          </button>
          <button className="primary" onClick={() => setOpen(null)}>
            {t("Back to work")}
          </button>
        </div>
      </div>
    </div>
  );
}
