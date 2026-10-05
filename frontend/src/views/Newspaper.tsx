import { useState } from "react";
import { api } from "../api/client";
import type { PressItem, StockRow } from "../api/types";
import { Sparkline } from "../components/charts";
import { currentLang, t } from "../i18n";
import { useStore } from "../state/store";
import { fmtNum, pct } from "../util/format";
import { useLive } from "../util/hooks";

const SECTION_TITLE: Record<string, string> = {
  get business() {
    return t("Business");
  },
  get city() {
    return t("The city");
  },
  get sports() {
    return t("Sport");
  },
  get company() {
    return t("Desporto watch");
  },
};

const SECTOR_LABEL: Record<string, string> = {
  get betting() {
    return t("betting");
  },
  get media() {
    return t("media");
  },
  get construction() {
    return t("construction");
  },
  get sportswear() {
    return t("sportswear");
  },
  get tech() {
    return t("tech");
  },
  get banking() {
    return t("banking");
  },
  get energy() {
    return t("energy");
  },
  get airlines() {
    return t("airlines");
  },
  get food() {
    return t("food");
  },
};

/** Like toLocaleString with at most `digits` decimals, in the current language's style. */
function upTo(v: number, digits: number): string {
  const f = 10 ** digits;
  return fmtNum(v, Number.isInteger(Math.round(v * f) / f) ? 0 : digits);
}

function longDate(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(currentLang() === "es" ? "es-ES" : "en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function Change({ v }: { v: number | null | undefined }) {
  if (v === null || v === undefined) return null;
  const cls = v > 0.0005 ? "up" : v < -0.0005 ? "down" : "";
  return (
    <span className={`chg ${cls}`}>
      {v > 0 ? "▲" : v < 0 ? "▼" : "•"} {pct(Math.abs(v), 1)}
    </span>
  );
}

function Story({ item, big = false }: { item: PressItem; big?: boolean }) {
  return (
    <article className={`story ${big ? "lead" : ""} imp-${item.importance}`}>
      <h3>{item.headline}</h3>
      {item.body && <p>{item.body}</p>}
      {(item.tickers.length > 0 || item.move !== null) && item.kind !== "wrap" && (
        <div className="story-meta">
          {item.tickers.join(" · ")} {item.move !== null && <Change v={item.move} />}
        </div>
      )}
      {item.effect && (
        <div className="effect">
          <b>{t("For us:")}</b> {item.effect}
        </div>
      )}
    </article>
  );
}

function StockTable({ rows }: { rows: StockRow[] }) {
  return (
    <table className="stocks">
      <thead>
        <tr>
          <th>{t("Ticker")}</th>
          <th>{t("Company")}</th>
          <th className="r">{t("Close|price")}</th>
          <th className="r">{t("Day")}</th>
          <th className="r">{t("30 days")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((s) => (
          <tr key={s.ticker} className={s.sector === "betting" ? "betting" : ""}>
            <td>
              <b>{s.ticker}</b>
            </td>
            <td>
              {s.name}
              <div className="sector">{SECTOR_LABEL[s.sector] ?? s.sector}</div>
            </td>
            <td className="r num">{fmtNum(s.price, 2)}</td>
            <td className="r">
              <Change v={s.change} />
            </td>
            <td className="r">
              <Sparkline values={s.spark} width={70} height={18} color="#5b4a3a" dot="#2b2130" />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Newspaper() {
  const state = useStore((s) => s.state);
  const [day, setDay] = useState<string | undefined>(undefined);
  const { data, error } = useLive(() => api.newspaper(day), `${day ?? "latest"}:${state?.city.edition}:${state?.sandbox.god_actions}`);
  if (error) return <div className="page"><div className="panel empty">{error}</div></div>;
  if (!data) return <div className="page"><div className="panel empty">{t("Fetching the paper…")}</div></div>;
  if (!data.available) {
    return (
      <div className="page">
        <div className="panel empty">{t("{paper} prints its first edition tomorrow morning at 08:00.", { paper: data.paper })}</div>
      </div>
    );
  }
  const items = data.items ?? [];
  const lead = items.find((i) => i.lead);
  const rest = items.filter((i) => !i.lead);
  const by = (section: string) => rest.filter((i) => i.section === section && i.kind !== "wrap");
  const wrap = items.find((i) => i.kind === "wrap");
  const columns = ["company", "business", "city", "sports"].filter((s) => by(s).length > 0);
  const latest = data.day === data.latest;
  return (
    <div className="page">
      <div className="paper">
        <div className="paper-nav">
          <button onClick={() => setDay(data.prev ?? undefined)} disabled={!data.prev}>
            {t("‹ Previous")}
          </button>
          <span className="muted-ink">
            {latest ? t("Today's edition") : t("Back issue")} · {t("No. {n}", { n: data.edition_no ?? "" })}
          </span>
          <button onClick={() => setDay(data.next ?? undefined)} disabled={!data.next}>
            {t("Next ›")}
          </button>
          {!latest && <button onClick={() => setDay(undefined)}>{t("Today")}</button>}
        </div>
        <header className="masthead">
          <h1>{data.paper.toUpperCase()}</h1>
          <div className="dateline">
            {longDate(data.day!)} · {data.city} · {t("Morning edition")}
          </div>
        </header>

        <div className="paper-grid">
          <div className="paper-main">
            {lead && <Story item={lead} big />}
            <div className="paper-cols">
              {columns.map((s) => (
                <section key={s}>
                  <h4>{SECTION_TITLE[s]}</h4>
                  {by(s).map((i) => (
                    <Story key={i.id} item={i} />
                  ))}
                </section>
              ))}
            </div>
            {(data.results?.length ?? 0) > 0 && (
              <section className="results">
                <h4>{t("Results")}</h4>
                <div className="results-grid">
                  {data.results!.map((r, i) => (
                    <div key={i} className="result">
                      <span className="comp">{r.competition}</span>
                      <span>{r.home}</span>
                      <b className="num">{r.score}</b>
                      <span>{r.away}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>

          <aside className="paper-side">
            <section>
              <h4>{t("Markets")}</h4>
              {data.index && (
                <div className="index-box">
                  <div>
                    <div className="sector">{t("PVX 12 index")}</div>
                    <div className="num big">{upTo(data.index.value, 1)}</div>
                    <Change v={data.index.change} />
                  </div>
                  <Sparkline values={data.index.spark} width={120} height={40} color="#5b4a3a" dot="#2b2130" />
                </div>
              )}
              {wrap?.body && <p className="wrap">{wrap.body}</p>}
              <StockTable rows={data.stocks ?? []} />
              <p className="footnote">{t("Highlighted: listed bookmakers. Investors price our subscriber business like theirs.")}</p>
            </section>
            <section>
              <h4>{t("The economy & us")}</h4>
              <dl className="econ">
                <dt>{t("Central bank rate")}</dt>
                <dd>{typeof data.base_rate === "number" ? fmtNum(data.base_rate, 2) : ""}%</dd>
                <dt>{t("Our credit line")}</dt>
                <dd>{t("{rate} / month", { rate: pct(data.loan_rate_monthly ?? 0, 2) })}</dd>
                <dt>{t("Consumer confidence")}</dt>
                <dd>
                  {(data.economy ?? 0) > 0.15 ? t("Upbeat") : (data.economy ?? 0) < -0.15 ? t("Gloomy") : t("Steady")} (
                  {(data.economy ?? 0) >= 0 ? "+" : ""}
                  {fmtNum(data.economy ?? 0, 2)})
                </dd>
                <dt>{t("Betting stocks vs. 120-day average")}</dt>
                <dd>{t("×{x} on our subscriber value", { x: fmtNum(data.betting_sentiment ?? 1, 2) })}</dd>
              </dl>
              {(data.modifiers?.length ?? 0) > 0 ? (
                <ul className="effects">
                  {data.modifiers!.map((m, i) => (
                    <li key={i}>
                      <b>{m.label}</b> — {t("{n} days left", { n: m.days_left })}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="footnote">{t("No news is currently changing how the company works.")}</p>
              )}
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
