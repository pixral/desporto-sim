import { useMemo, useState } from "react";
import { api } from "../api/client";
import { useStore } from "../state/store";
import { eur, pct, signedEur, tone } from "../util/format";
import { useLive } from "../util/hooks";

type Key = "name" | "department" | "title" | "profit" | "roi" | "bets" | "stress" | "reputation" | "tenure_days" | "salary";

export function Staff() {
  const state = useStore((s) => s.state);
  const select = useStore((s) => s.selectEmployee);
  const { data } = useLive(() => api.employees(), `${state?.clock.day_index}:${state?.clock.phase}`);
  const [sort, setSort] = useState<{ key: Key; dir: 1 | -1 }>({ key: "profit", dir: -1 });
  const [former, setFormer] = useState(false);
  const rows = useMemo(() => {
    const list = (data ?? []).filter((e) => e.active || former);
    return [...list].sort((a, b) => {
      const av = a[sort.key] ?? "";
      const bv = b[sort.key] ?? "";
      return (av > bv ? 1 : av < bv ? -1 : 0) * sort.dir;
    });
  }, [data, sort, former]);
  const head = (key: Key, label: string, right = false) => (
    <th
      className={`sortable ${right ? "r" : ""}`}
      onClick={() => setSort((s) => ({ key, dir: s.key === key ? ((-s.dir) as 1 | -1) : -1 }))}
      aria-sort={sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
    >
      {label}
      {sort.key === key ? (sort.dir === 1 ? " ▲" : " ▼") : ""}
    </th>
  );
  return (
    <div className="page">
      <div className="panel">
        <div className="panel-title">
          <h2>Staff</h2>
          <label className="dim">
            <input type="checkbox" checked={former} onChange={(e) => setFormer(e.target.checked)} /> show former employees
          </label>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="tab-nums">
            <thead>
              <tr>
                {head("name", "Name")}
                {head("title", "Role")}
                {head("department", "Desk")}
                {head("profit", "Career P/L", true)}
                {head("roi", "ROI", true)}
                {head("bets", "Bets", true)}
                {head("stress", "Stress", true)}
                {head("reputation", "Rep", true)}
                {head("tenure_days", "Days", true)}
                {head("salary", "Salary", true)}
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr key={e.id} className={`clickable ${e.active ? "" : "inactive"}`} onClick={() => select(e.id)}>
                  <td>
                    {e.name}
                    {e.under_review && <span className="pill lost" style={{ marginLeft: 6 }}>review</span>}
                  </td>
                  <td>
                    {e.title}
                    <div className="muted">{e.specialty_label}</div>
                  </td>
                  <td>{e.department ?? "—"}</td>
                  <td className={`r ${tone(e.profit)}`}>{e.role === "tipster" ? signedEur(e.profit, 2) : "—"}</td>
                  <td className="r">{e.role === "tipster" ? pct(e.roi, 1, true) : "—"}</td>
                  <td className="r">{e.bets || "—"}</td>
                  <td className="r">{pct(e.stress, 0)}</td>
                  <td className="r">{e.reputation.toFixed(0)}</td>
                  <td className="r">{e.tenure_days}</td>
                  <td className="r">{eur(e.salary)}</td>
                  <td>{e.active ? `${e.mood}` : <span className="muted">{e.leave_reason}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
