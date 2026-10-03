import { useStore } from "../state/store";
import { eur, pct, signedEur, tone } from "../util/format";

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
  const runway = k.runway_months === null ? "∞" : `${k.runway_months.toFixed(1)} mo`;
  return (
    <div className="kpis">
      <Kpi
        hero
        label="Company value"
        value={eur(k.valuation)}
        delta={`peak ${eur(k.peak_value)} · ${k.drawdown > 0.005 ? `▼ ${pct(k.drawdown, 0)} off peak` : "at peak"}`}
        deltaTone={k.drawdown > 0.2 ? "neg" : "flat"}
        title="Equity + subscriber goodwill + recent profit momentum"
      />
      <Kpi label="Cash" value={eur(k.cash)} delta={k.debt ? `debt ${eur(k.debt)}` : `payables ${eur(k.payables)}`} />
      <Kpi label="Bankroll" value={eur(k.bankroll)} delta={`${eur(k.exposure)} at risk`} title="Desk bankrolls; at risk = open bet stakes" />
      <Kpi label="Today P/L" value={signedEur(k.day_pnl, 2)} delta={`${k.bets_open} open bets`} deltaTone={tone(k.day_pnl)} />
      <Kpi
        label="Month betting"
        value={signedEur(k.month_betting_pnl)}
        delta={`net ${signedEur(k.month_net)}`}
        deltaTone={tone(k.month_net)}
        title="Betting result this month; net includes costs and subscriptions"
      />
      <Kpi label="All-time net" value={signedEur(k.total_net)} delta={`betting ${signedEur(k.total_betting_pnl)}`} deltaTone={tone(k.total_net)} />
      <Kpi
        label="Runway"
        value={runway}
        delta={k.monthly_burn > 0 ? `burn ${eur(k.monthly_burn)}/mo` : "not burning cash"}
        deltaTone={k.runway_months !== null && k.runway_months < 6 ? "neg" : "flat"}
      />
      <Kpi label="Staff" value={`${k.employees}`} delta={`${k.tipsters_working}/${k.tipsters} tipsters busy${k.hiring_frozen ? " · freeze" : ""}`} />
      <Kpi label="Bets placed" value={k.bets_total.toLocaleString()} delta={`${k.no_bets.toLocaleString()} passes`} />
      <Kpi
        label="AI cost"
        value={`$${k.ai_cost_usd.toFixed(2)}`}
        delta={`${k.ai_calls.toLocaleString()} calls${k.ai_failures ? ` · ${k.ai_failures} failed` : ""}`}
        deltaTone={k.ai_failures ? "neg" : "flat"}
        title={`Provider: ${state.run.ai_provider}`}
      />
      <Kpi label="Subscribers" value={`${k.subscribers}`} delta={`marketing ${eur(k.marketing_budget)}/mo`} />
    </div>
  );
}
