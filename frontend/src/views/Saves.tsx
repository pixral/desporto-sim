import { api } from "../api/client";
import { currentLang, t } from "../i18n";
import { useStore } from "../state/store";
import { eur, shortDate } from "../util/format";
import { useLive } from "../util/hooks";

export function Saves() {
  const state = useStore((s) => s.state);
  const notify = useStore((s) => s.notify);
  const setShowNewRun = useStore((s) => s.setShowNewRun);
  const { data, reload } = useLive(() => api.saves(), state?.run.id);
  const save = async () => {
    await api.save(t("Manual save — {date}", { date: String(state?.clock.date) }));
    notify(t("Game saved"));
    reload();
  };
  const load = async (id: number) => {
    try {
      await api.load(id);
      notify(t("Save loaded"));
      reload();
    } catch (e) {
      notify((e as Error).message);
    }
  };
  const del = async (id: number) => {
    if (!confirm(t("Delete this save permanently?"))) return;
    await api.deleteSave(id);
    reload();
  };
  return (
    <div className="page">
      <div className="panel">
        <div className="panel-title">
          <h2>{t("Saves")}</h2>
          <div className="controls">
            <button className="primary" onClick={save} disabled={!state || state.run.ended}>
              {t("Save now")}
            </button>
            <button onClick={() => setShowNewRun(true)}>{t("New company")}</button>
          </div>
        </div>
        <div className="muted" style={{ marginBottom: 10 }}>
          {t(
            "The game autosaves at every month close, on shutdown and when a company goes bankrupt. Loading a save restores the exact simulation state, including the random number generators, so the future plays out identically.",
          )}
        </div>
        <table className="tab-nums">
          <thead>
            <tr>
              <th>{t("Company")}</th>
              <th>{t("Label")}</th>
              <th>{t("Sim date")}</th>
              <th className="r">{t("Day")}</th>
              <th className="r">{t("Value")}</th>
              <th>{t("Saved")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((s) => (
              <tr key={s.id} className={s.run_id === state?.run.id ? "" : "inactive"}>
                <td>
                  {s.company_name}
                  <div className="muted">
                    {t(s.ceo_style.replace("_", " "))}
                    {s.ended ? ` · ${t("ended")}` : ""}
                  </div>
                </td>
                <td>
                  {s.label} <span className="muted">({t(s.kind)})</span>
                </td>
                <td>{shortDate(s.sim_date)}</td>
                <td className="r">{s.day_index}</td>
                <td className="r">{eur(s.valuation)}</td>
                <td className="muted">{new Date(s.created_at + "Z").toLocaleString(currentLang() === "es" ? "es-ES" : undefined)}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <button onClick={() => load(s.id)}>{t("Load")}</button>{" "}
                  <button className="danger" onClick={() => del(s.id)} aria-label={t("Delete save")}>
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && !data.length && <div className="empty">{t("No saves yet.")}</div>}
      </div>
    </div>
  );
}
