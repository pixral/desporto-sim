import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { SaveInfo, StateView } from "../api/types";
import { LANGS, t, useLang } from "../i18n";
import { useStore } from "../state/store";
import { eur, fmtNum, shortDate, STATUS_LABEL } from "../util/format";
import { type Fortune, fortuneFrom } from "./fortune";
import { CityScene } from "./scene";

type View = "main" | "new" | "load";

/** The title screen: the company's building, live, and the way into the game. */
export function StartMenu() {
  const state = useStore((s) => s.state);
  const connected = useStore((s) => s.connected);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sceneRef = useRef<CityScene | null>(null);
  const [view, setView] = useState<View>("main");
  const fortune = useMemo(() => fortuneFrom(state), [state?.run.id, state?.clock.day_index, state?.run.ended, state?.kpis.status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const canvas = canvasRef.current!;
    const scene = new CityScene(canvas);
    sceneRef.current = scene;
    if (import.meta.env.DEV) Object.assign(window, { __scene: scene }); // debugging: render frames by hand
    const ro = new ResizeObserver(() => scene.resize(canvas.clientWidth, canvas.clientHeight));
    ro.observe(canvas);
    let raf = 0;
    const loop = (now: number) => {
      scene.frame(now);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  useEffect(() => {
    sceneRef.current?.setFortune(fortune, {
      name: (state?.run.company_name ?? "Desporto & Cia.").toUpperCase(),
      forLease: t("FOR LEASE"),
      closed: t("CLOSED"),
      onAir: t("ON AIR"),
      newBoss: t("UNDER NEW MANAGEMENT"),
      thanks: t("THANK YOU, BOSS!"),
    });
  }, [fortune, state?.run.company_name]);

  // the game waits while the menu is open
  useEffect(() => {
    if (useStore.getState().state?.runner.running) api.control("pause").catch(() => undefined);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setView("main");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="start">
      <canvas ref={canvasRef} className="start-scene" aria-hidden />
      <div className="start-overlay">
        <header className="start-title">
          <h1>DESPORTO &amp; CIA.</h1>
          <p>{t("A paper-betting management game")}</p>
        </header>
        <div className="start-panel" role="dialog" aria-label={t("Main menu")}>
          {view === "main" && <MainView state={state} connected={connected} onNew={() => setView("new")} onLoad={() => setView("load")} />}
          {view === "new" && <NewView onBack={() => setView("main")} />}
          {view === "load" && <LoadView onBack={() => setView("main")} />}
        </div>
        <div className="start-caption">{caption(fortune, state)}</div>
        <footer className="start-foot">{t("Paper betting only: every euro here is simulated.")}</footer>
      </div>
    </div>
  );
}

function caption(f: Fortune, state: StateView | null): string {
  if (!state) return t("An empty building is waiting for a company.");
  const ratio = fmtNum(f.ratio, 1);
  if (f.ending === "bankrupt") return t("Bankrupt. The building stands closed, and a floor is on fire.");
  if (f.ending === "fired") return t("Fired by the board. The building has new management.");
  if (f.ending === "retired") return t("Retired after five seasons. Fireworks over the office.");
  if (f.tier === 0) return t("Day {n}: a small first office.", { n: state.clock.day_index });
  return t("{status} · worth {ratio}× its starting capital", { status: STATUS_LABEL[state.kpis.status] ?? state.kpis.status, ratio });
}

function MainView({ state, connected, onNew, onLoad }: { state: StateView | null; connected: boolean; onNew: () => void; onLoad: () => void }) {
  const setMenuOpen = useStore((s) => s.setMenuOpen);
  const lang = useLang((s) => s.lang);
  const setLang = useLang((s) => s.setLang);
  const canContinue = !!state && !state.run.ended;
  return (
    <>
      {state ? (
        <div className="start-company">
          <b>{state.run.company_name}</b>
          <span className="muted">
            {state.player ? t("You run it · advisor: {style}", { style: t(state.player.advisor_label) }) : t("AI CEO: {style}", { style: t(state.run.ceo_style_label) })}
          </span>
          <span>
            {shortDate(state.clock.date)} · {t("day {n}", { n: state.clock.day_index })} · {eur(state.kpis.valuation)}
          </span>
          {state.run.ended && <span className="neg">{state.run.end_reason}</span>}
        </div>
      ) : (
        <div className="start-company muted">{connected ? t("No company yet.") : t("Connecting to the simulation server…")}</div>
      )}
      <div className="start-buttons">
        {canContinue && (
          <button className="primary" onClick={() => setMenuOpen(false)} autoFocus>
            {t("Continue")}
          </button>
        )}
        <button className={canContinue ? "" : "primary"} onClick={onNew} disabled={!connected}>
          {t("New game")}
        </button>
        <button onClick={onLoad} disabled={!connected}>
          {t("Load game")}
        </button>
      </div>
      <div className="start-lang" role="group" aria-label={t("Language")}>
        <span className="muted">{t("Language")}</span>
        {LANGS.map((l) => (
          <button key={l.key} className={lang === l.key ? "active" : ""} onClick={() => setLang(l.key)}>
            {l.label}
          </button>
        ))}
      </div>
    </>
  );
}

function NewView({ onBack }: { onBack: () => void }) {
  const open = (mode: "player" | "ai") => {
    const s = useStore.getState();
    s.setNewRunMode(mode);
    s.setShowNewRun(true);
  };
  return (
    <>
      <h2>{t("Who runs the company?")}</h2>
      <button className="start-choice" onClick={() => open("player")} autoFocus>
        <b>{t("You, as CEO")}</b>
        <span>{t("Briefings, hiring and firing, money, desks and the LAB, with an AI advisor. Five seasons, don't get fired.")}</span>
      </button>
      <button className="start-choice" onClick={() => open("ai")}>
        <b>{t("An AI CEO")}</b>
        <span>{t("Watch an AI CEO with a personality run the company on its own.")}</span>
      </button>
      <button className="ghost" onClick={onBack}>
        ← {t("Back")}
      </button>
    </>
  );
}

function LoadView({ onBack }: { onBack: () => void }) {
  const notify = useStore((s) => s.notify);
  const setMenuOpen = useStore((s) => s.setMenuOpen);
  const [saves, setSaves] = useState<SaveInfo[] | null>(null);
  useEffect(() => {
    api.saves().then(setSaves).catch((e: Error) => notify(e.message));
  }, [notify]);
  const load = async (id: number) => {
    try {
      await api.load(id);
      setMenuOpen(false);
    } catch (e) {
      notify((e as Error).message);
    }
  };
  return (
    <>
      <h2>{t("Load game")}</h2>
      <div className="start-saves">
        {saves === null && <div className="muted">{t("Loading…")}</div>}
        {saves?.length === 0 && <div className="muted">{t("No saves yet.")}</div>}
        {saves?.slice(0, 30).map((s) => (
          <button key={s.id} className="start-save" onClick={() => load(s.id)}>
            <b>{s.company_name}</b>
            <span>
              {shortDate(s.sim_date)} · {t("day {n}", { n: s.day_index })} · {eur(s.valuation)}
              {s.ended ? ` · ${t("ended")}` : ""}
            </span>
            <span className="muted">{s.label}</span>
          </button>
        ))}
      </div>
      <button className="ghost" onClick={onBack}>
        ← {t("Back")}
      </button>
    </>
  );
}
