import { create } from "zustand";
import type { ActionResult, StateView } from "../api/types";

export type Tab = "office" | "dashboard" | "staff" | "lab" | "history" | "ceo" | "paper" | "ai" | "saves";

interface Store {
  state: StateView | null;
  connected: boolean;
  tab: Tab;
  selectedEmployee: string | null;
  selectedDepartment: string | null;
  showNewRun: boolean;
  summaryDismissedFor: string | null;
  toast: string | null;
  recapOpen: string | null;
  setRecapOpen: (id: string | null) => void;
  godOpen: boolean;
  setGodOpen: (v: boolean) => void;
  menuOpen: boolean;
  setMenuOpen: (v: boolean) => void;
  newRunMode: "player" | "ai";
  setNewRunMode: (m: "player" | "ai") => void;
  briefingHiddenFor: string | null;
  setBriefingHidden: (id: string | null) => void;
  signoff: { scope: string; date: string; results: ActionResult[] } | null;
  setSignoff: (v: { scope: string; date: string; results: ActionResult[] } | null) => void;
  setState: (s: StateView) => void;
  setConnected: (c: boolean) => void;
  setTab: (t: Tab) => void;
  selectEmployee: (id: string | null) => void;
  selectDepartment: (id: string | null) => void;
  setShowNewRun: (v: boolean) => void;
  dismissSummary: (runId: string) => void;
  notify: (msg: string | null) => void;
}

export const useStore = create<Store>((set) => ({
  state: null,
  connected: false,
  tab: "office",
  selectedEmployee: null,
  selectedDepartment: null,
  showNewRun: false,
  summaryDismissedFor: null,
  toast: null,
  recapOpen: null,
  setRecapOpen: (id) => set({ recapOpen: id }),
  godOpen: false,
  setGodOpen: (v) => set({ godOpen: v }),
  menuOpen: true, // the game opens on the title screen
  setMenuOpen: (v) => set({ menuOpen: v }),
  newRunMode: "player",
  setNewRunMode: (m) => set({ newRunMode: m }),
  briefingHiddenFor: null,
  setBriefingHidden: (id) => set({ briefingHiddenFor: id }),
  signoff: null,
  setSignoff: (v) => set({ signoff: v }),
  setState: (s) => set({ state: s }),
  setConnected: (c) => set({ connected: c }),
  setTab: (t) => set({ tab: t }),
  selectEmployee: (id) => set({ selectedEmployee: id, selectedDepartment: null }),
  selectDepartment: (id) => set({ selectedDepartment: id, selectedEmployee: null }),
  setShowNewRun: (v) => set({ showNewRun: v }),
  dismissSummary: (runId) => set({ summaryDismissedFor: runId }),
  notify: (msg) => set({ toast: msg }),
}));

/** Latest snapshot for the canvas loop, which must not re-render React on every frame. */
export function latestState(): StateView | null {
  return useStore.getState().state;
}
