import { t } from "../i18n";
import { useStore } from "../state/store";
import { eur, fmtNum, pct, signedEur, tone } from "../util/format";

function Kpi({ label, value, delta, deltaTone, hero, title }: {
  label: string;
  value: string;
  delta?: string;
  deltaTone?: "pos" | "neg" | "flat";
  hero?: boolean;
  title?: string;
}) {
  return (
    <div className={`kpi ${hero ? "hero" : ""}`} title={title}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {delta !== undefined && <div className={`delta ${deltaTone ?? ""}`}>{delta}</div>}
    </div>
  );
}

export function KpiStrip() {
  const state = useStore((s) => s.state);
  if (!state) return <div className="kpis" />;
  const k = state.kpis;
  const runway = k.runway_months === null ? "∞" : t("{n} mo", { n: fmtNum(k.runway_months, 1) });
  return (
    <div className="kpis">
      <Kpi
        hero
        label={t("Company value")}
        value={eur(k.valuation)}
        delta={`${t("peak {amount}", { amount: eur(k.peak_value) })} · ${
          k.drawdown > 0.005 ? `▼ ${t("{pct} off peak", { pct: pct(k.drawdown, 0) })}` : t("at peak")
        }`}
        deltaTone={k.drawdown > 0.2 ? "neg" : "flat"}
        title={t("Equity + subscriber goodwill + recent profit momentum")}
      />
      <Kpi
        label={t("Cash")}
        value={eur(k.cash)}
        delta={k.debt ? t("debt {amount}", { amount: eur(k.debt) }) : t("payables {amount}", { amount: eur(k.payables) })}
      />
      <Kpi
        label={t("Bankroll")}
        value={eur(k.bankroll)}
        delta={t("{amount} at risk", { amount: eur(k.exposure) })}
        title={t("Desk bankrolls; at risk = open bet stakes")}
      />
      <Kpi label={t("Today P/L")} value={signedEur(k.day_pnl, 2)} delta={t("{n} open bets", { n: k.bets_open })} deltaTone={tone(k.day_pnl)} />
      <Kpi
        label={t("Month betting")}
        value={signedEur(k.month_betting_pnl)}
        delta={t("net {amount}", { amount: signedEur(k.month_net) })}
        deltaTone={tone(k.month_net)}
        title={t("Betting result this month; net includes costs and subscriptions")}
      />
      <Kpi
        label={t("All-time net")}
        value={signedEur(k.total_net)}
        delta={t("betting {amount}", { amount: signedEur(k.total_betting_pnl) })}
        deltaTone={tone(k.total_net)}
      />
      <Kpi
        label={t("Runway")}
        value={runway}
        delta={k.monthly_burn > 0 ? t("burn {amount}/mo", { amount: eur(k.monthly_burn) }) : t("not burning cash")}
        deltaTone={k.runway_months !== null && k.runway_months < 6 ? "neg" : "flat"}
      />
      <Kpi
        label={t("Staff")}
        value={`${k.employees}`}
        delta={t("{busy}/{total} tipsters busy", { busy: k.tipsters_working, total: k.tipsters }) + (k.hiring_frozen ? ` · ${t("freeze")}` : "")}
      />
      <Kpi label={t("Bets placed")} value={fmtNum(k.bets_total)} delta={t("{n} passes", { n: fmtNum(k.no_bets) })} />
      <Kpi
        label={t("AI cost")}
        value={`$${fmtNum(k.ai_cost_usd, 2)}`}
        delta={
          t("{n} calls", { n: fmtNum(k.ai_calls) }) + (k.ai_failures ? ` · ${t("{n} failed", { n: k.ai_failures })}` : "")
        }
        deltaTone={k.ai_failures ? "neg" : "flat"}
        title={t("Provider: {provider}", { provider: state.run.ai_provider })}
      />
      <Kpi
        label={t("Subscribers")}
        value={`${k.subscribers}`}
        delta={t("marketing {amount}/mo", { amount: eur(k.marketing_budget) })}
      />
    </div>
  );
}
