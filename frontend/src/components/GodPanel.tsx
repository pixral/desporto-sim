import { useState } from "react";
import { api } from "../api/client";
import { t } from "../i18n";
import { useStore } from "../state/store";
import { eur } from "../util/format";
import { useLive } from "../util/hooks";

const DISASTER_LABEL: Record<string, string> = {
  get fire() {
    return t("Server-room fire");
  },
  get flood() {
    return t("Office flood");
  },
  get lawsuit() {
    return t("Lawsuit");
  },
  get hack() {
    return t("Data breach");
  },
  get tax() {
    return t("Tax audit");
  },
};
const STYLE_LABEL: Record<string, string> = {
  conservative_operator: "Conservative operator",
  aggressive_expansionist: "Aggressive expansionist",
  data_driven: "Data-driven manager",
  chaotic_founder: "Chaotic founder",
};

/** The player's sandbox: every tool changes the real simulation and is logged in the history. */
export function GodPanel() {
  const open = useStore((s) => s.godOpen);
  const setOpen = useStore((s) => s.setGodOpen);
  const state = useStore((s) => s.state);
  const notify = useStore((s) => s.notify);
  const { data: cat } = useLive(() => api.godCatalog(), open);
  const [busy, setBusy] = useState(false);
  const value = state?.kpis.valuation ?? 20000;
  const [invest, setInvest] = useState("");
  const [windfall, setWindfall] = useState("2000");
  const [windKind, setWindKind] = useState("sponsor");
  const [disaster, setDisaster] = useState("fire");
  const [severity, setSeverity] = useState("major");
  const [sector, setSector] = useState("betting");
  const [move, setMove] = useState(-25);
  const [headline, setHeadline] = useState("");
  const [ticker, setTicker] = useState("");
  const [tickerMove, setTickerMove] = useState(-10);
  const [style, setStyle] = useState("chaotic_founder");
  const [level, setLevel] = useState(state ? "normal" : "normal");
  if (!open || !state) return null;
  const ended = state.run.ended;

  const run = async (action: string, params: Record<string, unknown> = {}) => {
    setBusy(true);
    try {
      const r = await api.god(action, params);
      notify(r.message);
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const disabled = busy || ended;
  const suggested = Math.max(2000, Math.round((0.25 * value) / 100) * 100);
  const cost = eur(
    (cat?.disasters.find((d) => d.key === disaster)?.share ?? 0.1) *
      ({ minor: 0.5, major: 1, catastrophic: 2 }[severity] ?? 1) *
      Math.max(value, 0.4 * state.run.starting_capital),
  );
  const disasterCost =
    disaster === "hack"
      ? t("Costs about {amount} and a share of subscribers, plus stress for everyone.", { amount: cost })
      : disaster === "fire"
        ? t("Costs about {amount} and any running LAB experiments, plus stress for everyone.", { amount: cost })
        : t("Costs about {amount}, plus stress for everyone.", { amount: cost });

  return (
    <div className="modal-backdrop" onClick={() => setOpen(false)}>
      <div className="modal god" role="dialog" aria-label={t("Sandbox tools")} onClick={(e) => e.stopPropagation()}>
        <div className="panel-title">
          <h2>{t("Sandbox tools")}</h2>
          <button onClick={() => setOpen(false)} aria-label={t("Close")}>
            ✕
          </button>
        </div>
        <p className="dim">
          {t("Play god. Everything here really happens in the simulation, is written into the company history and shows up on the end screen ({count} so far).", {
            count:
              state.sandbox.god_actions === 1
                ? t("{n} intervention", { n: state.sandbox.god_actions })
                : t("{n} interventions", { n: state.sandbox.god_actions }),
          })}
        </p>
        {ended && <p className="neg">{t("This company is gone. Found a new one to keep playing.")}</p>}

        <div className="god-grid">
          <section>
            <h3>{t("Money")}</h3>
            <label>
              {t("An investor puts in")}
              <div className="row">
                <input type="number" min={100} step={100} placeholder={String(suggested)} value={invest}
                  onChange={(e) => setInvest(e.target.value)} />
                <button disabled={disabled} onClick={() => run("invest", { amount: Number(invest || suggested) })}>
                  {t("Invest")}
                </button>
              </div>
            </label>
            <label>
              {t("Windfall")}
              <div className="row">
                <select value={windKind} onChange={(e) => setWindKind(e.target.value)}>
                  {(cat?.windfalls ?? []).map((w) => (
                    <option key={w.key} value={w.key}>
                      {t(w.label)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="row">
                <input type="number" min={100} step={100} value={windfall} onChange={(e) => setWindfall(e.target.value)} />
                <button disabled={disabled} onClick={() => run("windfall", { amount: Number(windfall), kind: windKind })}>
                  {t("Grant")}
                </button>
              </div>
            </label>
            <div className="muted">{t("Investor money is not profit; windfalls count as other income.")}</div>
          </section>

          <section>
            <h3>{t("Disasters")}</h3>
            <div className="row wrap">
              {(cat?.disasters ?? []).map((d) => (
                <button key={d.key} className={disaster === d.key ? "active" : ""} onClick={() => setDisaster(d.key)}>
                  {DISASTER_LABEL[d.key] ?? d.title}
                </button>
              ))}
            </div>
            <div className="row wrap">
              {(cat?.severities ?? []).map((s) => (
                <button key={s} className={severity === s ? "active" : ""} onClick={() => setSeverity(s)}>
                  {t(s)}
                </button>
              ))}
            </div>
            <div className="muted">{disasterCost}</div>
            <button className="danger" disabled={disabled} onClick={() => run("disaster", { kind: disaster, severity })}>
              {t("Unleash")}
            </button>
          </section>

          <section>
            <h3>{t("The city")}</h3>
            <label>
              {t("Move the stock market")}
              <div className="row">
                <select value={sector} onChange={(e) => setSector(e.target.value)}>
                  <option value="all">{t("Whole market")}</option>
                  {(cat?.sectors ?? []).map((s) => (
                    <option key={s} value={s}>
                      {t(s)}
                    </option>
                  ))}
                </select>
                <input type="range" min={-50} max={50} step={5} value={move} onChange={(e) => setMove(Number(e.target.value))} />
                <span className="num">{move > 0 ? "+" : ""}{move}%</span>
              </div>
            </label>
            <button disabled={disabled || move === 0} onClick={() => run("market", { sector, pct: move / 100 })}>
              {move < 0 ? t("Crash") : t("Rally")}
            </button>
            <div className="muted">{t("Betting shares set the value of our subscriber business.")}</div>
            <label>
              {t("Plant a headline in the morning paper")}
              <input type="text" maxLength={120} placeholder={t("Crane collapses at the new stadium")} value={headline}
                onChange={(e) => setHeadline(e.target.value)} />
            </label>
            <div className="row">
              <select value={ticker} onChange={(e) => setTicker(e.target.value)} aria-label={t("Company affected")}>
                <option value="">{t("No stock affected")}</option>
                {["ATLS", "NORD", "KICK", "PVTV", "BRKH", "STRD", "NEUR", "STAT", "PBNK", "VOLT", "SKYP", "MESA"].map((tk) => (
                  <option key={tk} value={tk}>
                    {tk}
                  </option>
                ))}
              </select>
              {ticker && (
                <>
                  <input type="range" min={-40} max={40} step={5} value={tickerMove}
                    onChange={(e) => setTickerMove(Number(e.target.value))} />
                  <span className="num">{tickerMove > 0 ? "+" : ""}{tickerMove}%</span>
                </>
              )}
            </div>
            <button disabled={disabled || !headline.trim()}
              onClick={() => run("headline", { headline, ticker, pct: ticker ? tickerMove / 100 : 0,
                section: ticker ? "business" : "city" })}>
              {t("Print it")}
            </button>
          </section>

          <section>
            <h3>{t("People")}</h3>
            <div className="row wrap">
              <button disabled={disabled} onClick={() => run("morale", { delta: 0.2 })}>{t("Team retreat")}</button>
              <button disabled={disabled} onClick={() => run("morale", { delta: -0.2 })}>{t("Panic wave")}</button>
              <button disabled={disabled} onClick={() => run("star", {})}>{t("Star applicant")}</button>
            </div>
            <div className="row wrap">
              <button disabled={disabled} onClick={() => run("subscribers", { delta: 50 })}>{t("Viral tip +50 subs")}</button>
              <button disabled={disabled} onClick={() => run("subscribers", { delta: -30 })}>{t("Bad press −30 subs")}</button>
            </div>
            <label>
              {t("Replace the CEO with")}
              <div className="row">
                <select value={style} onChange={(e) => setStyle(e.target.value)}>
                  {(cat?.ceo_styles ?? []).map((s) => (
                    <option key={s} value={s}>
                      {t(STYLE_LABEL[s] ?? s)}
                    </option>
                  ))}
                </select>
                <button disabled={disabled} onClick={() => run("replace_ceo", { style })}>
                  {t("Replace")}
                </button>
              </div>
            </label>
          </section>

          <section>
            <h3>{t("Office")}</h3>
            {state.office.facilities.map((f) => (
              <div className="row between" key={f.key}>
                <span>
                  {t(f.name)}{" "}
                  <span className="muted">{f.leased ? `· ${t("leased")}` : `· ${t("{amount}/mo", { amount: eur(f.monthly_cost) })}`}</span>
                </span>
                <button disabled={disabled}
                  onClick={() => run("facility", { facility: f.key, op: f.leased ? "release" : "lease" })}>
                  {f.leased ? t("Close") : t("Open free")}
                </button>
              </div>
            ))}
            <div className="muted">{t("Free opening skips the fit-out; the monthly cost still applies.")}</div>
          </section>

          <section>
            <h3>{t("Rules")}</h3>
            <label>
              {t("Difficulty from now on")}
              <div className="row">
                <select value={level} onChange={(e) => setLevel(e.target.value)}>
                  {(cat?.difficulties ?? []).map((d) => (
                    <option key={d} value={d}>
                      {t(d)}
                    </option>
                  ))}
                </select>
                <button disabled={disabled} onClick={() => run("difficulty", { level })}>
                  {t("Apply")}
                </button>
              </div>
            </label>
          </section>
        </div>
      </div>
    </div>
  );
}
