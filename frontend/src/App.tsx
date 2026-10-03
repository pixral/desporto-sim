import { useEffect } from "react";
import { api } from "./api/client";
import { DepartmentPanel } from "./components/DepartmentPanel";
import { EmployeePanel } from "./components/EmployeePanel";
import { EndScreen } from "./components/EndScreen";
import { KpiStrip } from "./components/KpiStrip";
import { NavRail } from "./components/NavRail";
import { NewRunDialog } from "./components/NewRunDialog";
import { RecapModal } from "./components/RecapModal";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { OfficeCanvas } from "./office/OfficeCanvas";
import { connectSocket } from "./state/socket";
import { useStore } from "./state/store";
import { AiLog } from "./views/AiLog";
import { Ceo } from "./views/Ceo";
import { Dashboard } from "./views/Dashboard";
import { History } from "./views/History";
import { Lab } from "./views/Lab";
import { Saves } from "./views/Saves";
import { Staff } from "./views/Staff";

export function App() {
  const state = useStore((s) => s.state);
  const connected = useStore((s) => s.connected);
  const tab = useStore((s) => s.tab);
  const selectedEmployee = useStore((s) => s.selectedEmployee);
  const selectedDepartment = useStore((s) => s.selectedDepartment);
  const showNewRun = useStore((s) => s.showNewRun);
  const toast = useStore((s) => s.toast);
  const notify = useStore((s) => s.notify);

  useEffect(() => connectSocket(), []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => notify(null), 2600);
    return () => clearTimeout(t);
  }, [toast, notify]);

  // keyboard: space = run/pause, Esc = close panels
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT") return;
      const s = useStore.getState();
      if (e.key === " " && s.state && !s.state.run.ended) {
        e.preventDefault();
        api.control(s.state.runner.running ? "pause" : "resume").catch(() => undefined);
      } else if (e.key === "Escape") {
        s.selectEmployee(null);
        s.selectDepartment(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!state) {
    return (
      <div className="app" style={{ placeItems: "center", display: "grid" }}>
        <div className="panel" style={{ textAlign: "center", maxWidth: 420 }}>
          <h2 style={{ color: "var(--accent)" }}>DESPORTO &amp; CIA.</h2>
          <p className="dim">
            {connected ? "Waiting for the simulation…" : "Connecting to the simulation server on port 8000…"}
          </p>
          <p className="muted">Start the backend with: uvicorn app.main:app --port 8000</p>
        </div>
      </div>
    );
  }

  const office = tab === "office";
  return (
    <div className="app">
      <TopBar />
      <KpiStrip />
      <div className={`main ${office ? "" : "no-sidebar"}`}>
        <NavRail />
        <main className={`content ${office ? "office" : ""}`}>
          {office && <OfficeCanvas />}
          {tab === "dashboard" && <Dashboard />}
          {tab === "staff" && <Staff />}
          {tab === "lab" && <Lab />}
          {tab === "history" && <History />}
          {tab === "ceo" && <Ceo />}
          {tab === "ai" && <AiLog />}
          {tab === "saves" && <Saves />}
          {selectedEmployee && <EmployeePanel key={selectedEmployee} id={selectedEmployee} />}
          {selectedDepartment && !selectedEmployee && <DepartmentPanel key={selectedDepartment} id={selectedDepartment} />}
        </main>
        {office && <Sidebar />}
      </div>
      {showNewRun && <NewRunDialog />}
      <EndScreen />
      <RecapModal />
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
