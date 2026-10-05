import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Meta } from "../api/types";
import { useStore } from "../state/store";

export function NewRunDialog() {
  const close = () => useStore.getState().setShowNewRun(false);
  const notify = useStore((s) => s.notify);
  const setTab = useStore((s) => s.setTab);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [form, setForm] = useState<Record<string, string | number | boolean>>({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.meta().then((m) => {
      setMeta(m);
      setForm({
        ...m.defaults,
        seed: Math.floor(Math.random() * 10000),
        ai_provider: m.ai_provider_default,
        player_ceo: true,
        player_name: "",
        pause_mode: "monthly",
        ironman: false,
      });
    });
  }, []);
  if (!meta) return null;
  const set = (k: string, v: string | number | boolean) => setForm((f) => ({ ...f, [k]: v }));
  const playing = form.player_ceo === true;
  const submit = async () => {
    setBusy(true);
    try {
      await api.newRun({
        ...form,
        seed: Number(form.seed),
        starting_capital: Number(form.starting_capital),
        initial_tipsters: Number(form.initial_tipsters),
        player_name: playing ? String(form.player_name ?? "").trim() : "",
        ironman: playing && form.ironman === true,
      });
      notify(playing ? `${form.company_name} is yours. The first briefing is on Monday.` : `${form.company_name} is open for business`);
      setTab("office");
      close();
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const nameMissing = playing && !String(form.player_name ?? "").trim();
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
          <input id="cn" value={String(form.company_name ?? "")} maxLength={60} onChange={(e) => set("company_name", e.target.value)} />
        </div>

        <h3 style={{ margin: "12px 0 8px" }}>Who runs it?</h3>
        <div className="style-cards" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
          <div className={`style-card ${playing ? "active" : ""}`} onClick={() => set("player_ceo", true)}>
            <b>You</b>
            You're the CEO: briefings, hiring and firing, money, desks, the LAB. Five seasons to grow it without being fired or
            going bust.
          </div>
          <div className={`style-card ${!playing ? "active" : ""}`} onClick={() => set("player_ceo", false)}>
            <b>An AI CEO</b>
            Watch an AI CEO with a personality run the company on its own. You can still use the sandbox.
          </div>
        </div>

        {playing && (
          <div className="form-row">
            <label htmlFor="pn">Your name</label>
            <input id="pn" value={String(form.player_name ?? "")} maxLength={40} placeholder="As it appears on your door" onChange={(e) => set("player_name", e.target.value)} />
          </div>
        )}

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
              {playing && d.key === "easy" ? " · the board only warns you" : ""}
            </div>
          ))}
        </div>

        <h3 style={{ margin: "12px 0 8px" }}>{playing ? "Your advisor" : "CEO personality"}</h3>
        {playing && (
          <div className="muted" style={{ marginBottom: 6 }}>
            The advisor reads every report, suggests decisions with reasons, and handles the reviews you skip. At the end you'll see
            how you compare.
          </div>
        )}
        <div className="style-cards">
          {meta.ceo_styles.map((s) => (
            <div key={s.key} className={`style-card ${form.ceo_style === s.key ? "active" : ""}`} onClick={() => set("ceo_style", s.key)}>
              <b>{s.label}</b>
              {s.description}
            </div>
          ))}
        </div>

        {playing && (
          <>
            <h3 style={{ margin: "12px 0 8px" }}>When does the clock stop for you?</h3>
            <div className="style-cards" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
              {meta.pause_modes.map((m) => (
                <div key={m.key} className={`style-card ${form.pause_mode === m.key ? "active" : ""}`} onClick={() => set("pause_mode", m.key)}>
                  <b>{m.label}</b>
                  {m.description}
                </div>
              ))}
            </div>
            <label className="check-row">
              <input type="checkbox" checked={form.ironman === true} onChange={(e) => set("ironman", e.target.checked)} />
              <span>
                <b>Ironman</b> · no sandbox, and only the latest save of this company can be loaded.
              </span>
            </label>
          </>
        )}

        <div className="form-row">
          <label htmlFor="cap">Starting capital (€)</label>
          <input id="cap" type="number" min={2000} step={1000} value={Number(form.starting_capital ?? 20000)} onChange={(e) => set("starting_capital", e.target.value)} />
        </div>
        <div className="form-row">
          <label htmlFor="tip">Initial tipsters</label>
          <input id="tip" type="number" min={2} max={16} value={Number(form.initial_tipsters ?? 8)} onChange={(e) => set("initial_tipsters", e.target.value)} />
        </div>
        <div className="form-row">
          <label htmlFor="seed">World seed</label>
          <input id="seed" type="number" value={Number(form.seed ?? 7)} onChange={(e) => set("seed", e.target.value)} />
        </div>
        <div className="muted" style={{ marginTop: -4 }}>
          Same seed = same football and the same founding staff, so you can replay a season against an AI CEO.
        </div>
        <div className="form-row">
          <label htmlFor="ai">AI brains</label>
          <select id="ai" value={String(form.ai_provider ?? "mock")} onChange={(e) => set("ai_provider", e.target.value)}>
            <option value="mock">Mock (free, personality-driven policies)</option>
            <option value="anthropic">Claude via Anthropic API ({meta.default_model}) — costs real API credits</option>
          </select>
        </div>
        <div className="controls" style={{ justifyContent: "flex-end", marginTop: 14 }}>
          <button onClick={close}>Cancel</button>
          <button className="primary" onClick={submit} disabled={busy || !String(form.company_name ?? "").trim() || nameMissing} title={nameMissing ? "Enter your name" : undefined}>
            {busy ? "Founding…" : playing ? "Take the chair" : "Open the doors"}
          </button>
        </div>
      </div>
    </div>
  );
}
