import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Meta } from "../api/types";
import { useStore } from "../state/store";

export function NewRunDialog() {
  const close = () => useStore.getState().setShowNewRun(false);
  const notify = useStore((s) => s.notify);
  const setTab = useStore((s) => s.setTab);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [form, setForm] = useState<Record<string, string | number>>({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.meta().then((m) => {
      setMeta(m);
      setForm({ ...m.defaults, seed: Math.floor(Math.random() * 10000), ai_provider: m.ai_provider_default });
    });
  }, []);
  if (!meta) return null;
  const set = (k: string, v: string | number) => setForm((f) => ({ ...f, [k]: v }));
  const submit = async () => {
    setBusy(true);
    try {
      await api.newRun({
        ...form,
        seed: Number(form.seed),
        starting_capital: Number(form.starting_capital),
        initial_tipsters: Number(form.initial_tipsters),
      });
      notify(`${form.company_name} is open for business`);
      setTab("office");
      close();
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="New company">
        <div className="panel-title">
          <h2>Found a new company</h2>
          <button onClick={close} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="muted">Paper betting only: every euro here is simulated. The current company keeps its saves.</div>
        <div className="form-row">
          <label htmlFor="cn">Company name</label>
          <input id="cn" value={form.company_name ?? ""} maxLength={60} onChange={(e) => set("company_name", e.target.value)} />
        </div>
        <h3 style={{ margin: "12px 0 8px" }}>Difficulty</h3>
        <div className="style-cards" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
          {meta.difficulties.map((d) => (
            <div
              key={d.key}
              className={`style-card ${form.difficulty === d.key ? "active" : ""}`}
              onClick={() => setForm((f) => ({ ...f, difficulty: d.key, starting_capital: d.capital }))}
            >
              <b>{d.key}</b>
              €{d.capital.toLocaleString()} capital · costs {d.cost_mult === 1 ? "normal" : d.cost_mult < 1 ? "lower" : "higher"} ·{" "}
              {d.market_xg < 0 ? "softer" : d.market_xg > 0 ? "sharper" : "normal"} bookmakers · {d.start_subs} subscribers
            </div>
          ))}
        </div>
        <h3 style={{ margin: "12px 0 8px" }}>CEO personality</h3>
        <div className="style-cards">
          {meta.ceo_styles.map((s) => (
            <div key={s.key} className={`style-card ${form.ceo_style === s.key ? "active" : ""}`} onClick={() => set("ceo_style", s.key)}>
              <b>{s.label}</b>
              {s.description}
            </div>
          ))}
        </div>
        <div className="form-row">
          <label htmlFor="cap">Starting capital (€)</label>
          <input id="cap" type="number" min={2000} step={1000} value={form.starting_capital ?? 20000} onChange={(e) => set("starting_capital", e.target.value)} />
        </div>
        <div className="form-row">
          <label htmlFor="tip">Initial tipsters</label>
          <input id="tip" type="number" min={2} max={16} value={form.initial_tipsters ?? 8} onChange={(e) => set("initial_tipsters", e.target.value)} />
        </div>
        <div className="form-row">
          <label htmlFor="seed">World seed</label>
          <input id="seed" type="number" value={form.seed ?? 7} onChange={(e) => set("seed", e.target.value)} />
        </div>
        <div className="muted" style={{ marginTop: -4 }}>
          Same seed = same football season, so you can replay it under a different CEO.
        </div>
        <div className="form-row">
          <label htmlFor="ai">AI brains</label>
          <select id="ai" value={form.ai_provider ?? "mock"} onChange={(e) => set("ai_provider", e.target.value)}>
            <option value="mock">Mock (free, personality-driven policies)</option>
            <option value="anthropic">Claude via Anthropic API ({meta.default_model}) — costs real API credits</option>
          </select>
        </div>
        <div className="controls" style={{ justifyContent: "flex-end", marginTop: 14 }}>
          <button onClick={close}>Cancel</button>
          <button className="primary" onClick={submit} disabled={busy || !String(form.company_name ?? "").trim()}>
            {busy ? "Founding…" : "Open the doors"}
          </button>
        </div>
      </div>
    </div>
  );
}
