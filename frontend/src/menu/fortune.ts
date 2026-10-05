import type { StateView } from "../api/types";

/** How the company's building looks on the title screen. Derived only from real company numbers. */
export interface Fortune {
  /** 0 a small first office … 4 a tower */
  tier: 0 | 1 | 2 | 3 | 4;
  /** bright: busy and lit · dim: half the lights off · dark: nearly empty · ruin: closed, a floor on fire · vacant: no company */
  mood: "bright" | "dim" | "dark" | "ruin" | "vacant";
  ending: "fired" | "retired" | "bankrupt" | null;
  /** people working there (lit windows, people at the door) */
  staff: number;
  canteen: boolean;
  studio: boolean;
  deskWing: boolean;
  /** value ÷ starting capital (for the caption) */
  ratio: number;
}

export const VACANT: Fortune = {
  tier: 0,
  mood: "vacant",
  ending: null,
  staff: 0,
  canteen: false,
  studio: false,
  deskWing: false,
  ratio: 0,
};

function tierFor(ratio: number): Fortune["tier"] {
  if (ratio >= 3) return 4;
  if (ratio >= 1.8) return 3;
  if (ratio >= 1.25) return 2;
  return 1;
}

export function fortuneFrom(state: StateView | null): Fortune {
  if (!state) return VACANT;
  const capital = state.run.starting_capital || 1;
  const value = state.kpis.valuation ?? 0;
  const ratio = value / capital;
  const leased = state.office?.leased ?? {};
  const base = {
    staff: state.employees.filter((e) => e.active).length,
    canteen: "canteen" in leased,
    studio: "studio" in leased,
    deskWing: "desk_wing" in leased,
    ratio,
  };
  const kind = state.run.end_kind ?? (state.run.ended ? "bankrupt" : null);
  if (kind === "bankrupt") {
    // the building it had grown into, closed and burning
    return { ...base, tier: tierFor((state.kpis.peak_value ?? value) / capital), mood: "ruin", ending: "bankrupt", staff: 0 };
  }
  const tier = state.clock.day_index < 30 && !state.run.ended ? 0 : tierFor(ratio);
  if (kind === "retired") return { ...base, tier, mood: "bright", ending: "retired" };
  if (kind === "fired") return { ...base, tier, mood: "dim", ending: "fired" };
  const status = state.kpis.status;
  const mood: Fortune["mood"] =
    status === "distress" || ratio < 0.55 ? "dark" : status === "strained" || ratio < 0.8 ? "dim" : "bright";
  return { ...base, tier, mood, ending: null };
}
