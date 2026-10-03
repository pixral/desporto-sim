// Mirrors backend/app/simulation/views.py. Every number on screen comes from these payloads.

export interface Appearance {
  skin: number;
  hair_style: number;
  hair_color: number;
  shirt: number;
  pants: number;
  accessory: number;
}

export interface EmployeeCard {
  id: string;
  name: string;
  role: "tipster" | "researcher" | "ceo";
  title: string;
  level: number;
  specialty: string;
  specialty_label: string;
  department_id: string | null;
  desk_index: number;
  active: boolean;
  status: string;
  task: string;
  thought: string;
  mood: string;
  stress: number;
  confidence: number;
  reputation: number;
  risk_tolerance: number;
  day_profit: number;
  month_profit: number;
  profit: number;
  roi: number;
  bets: number;
  streak: number;
  under_review: boolean;
  appearance: Appearance;
  pnl_flash_seq: number;
  tenure_days: number;
  left: string | null;
}

export interface DepartmentCard {
  id: string;
  name: string;
  kind: string;
  color: string;
  room_slot: number;
  bankroll: number;
  stake_limit_pct: number;
  month_profit: number;
  day_profit: number;
  total_profit: number;
  bets: number;
  competitions: string[];
  head_id: string | null;
  active: boolean;
  headcount: number;
}

export interface HistoryEvent {
  id: string;
  time: string;
  kind: string;
  title: string;
  text: string;
  importance: number;
  tone: "good" | "bad" | "neutral" | "drama";
  employee_ids: string[];
  department_id: string | null;
  data: Record<string, unknown>;
}

export interface BetView {
  id: string;
  placed: string;
  employee_id: string;
  employee: string;
  department_id: string;
  match_id: string;
  match: string;
  competition: string;
  market: string;
  selection: string;
  book: string;
  odds: number;
  stake: number;
  status: "open" | "won" | "lost" | "void";
  profit: number;
  confidence: number;
  model_prob: number | null;
  model_edge: number | null;
  closing_odds: number | null;
  clv: number | null;
  score: string | null;
  reason: string;
  influenced_by: string[];
}

export interface Kpis {
  cash: number;
  bankroll: number;
  exposure: number;
  debt: number;
  payables: number;
  equity: number;
  valuation: number;
  peak_value: number;
  drawdown: number;
  max_drawdown: number;
  runway_months: number | null;
  monthly_burn: number;
  monthly_costs: number;
  status: "thriving" | "stable" | "strained" | "distress" | "bankrupt";
  day_pnl: number;
  month_betting_pnl: number;
  month_net: number;
  month_expenses: number;
  total_betting_pnl: number;
  total_net: number;
  tipsters: number;
  tipsters_working: number;
  employees: number;
  bets_total: number;
  bets_open: number;
  no_bets: number;
  ai_cost_usd: number;
  ai_calls: number;
  ai_failures: number;
  ai_cost_month_eur: number;
  subscribers: number;
  marketing_budget: number;
  lab_budget: number;
  hiring_frozen: boolean;
}

export interface RunSummary {
  company_name: string;
  ceo_name: string;
  ceo_style: string;
  ended: boolean;
  end_reason: string | null;
  founded: string;
  last_day: string;
  days_survived: number;
  starting_capital: number;
  peak_value: number;
  peak_value_day: string | null;
  final_value: number;
  worst_drawdown: number;
  employees_hired: number;
  employees_fired: number;
  employees_resigned: number;
  bets_placed: number;
  no_bet_decisions: number;
  betting_profit: number;
  total_expenses: number;
  best_employee: string | null;
  best_employee_profit: number | null;
  worst_employee: string | null;
  worst_employee_profit: number | null;
  departments_created: number;
  departments_closed: number;
  strategies_invented: number;
  ai_cost_usd: number;
  ai_calls: number;
}

export interface StateView {
  run: {
    id: string;
    company_name: string;
    ceo_style: string;
    ceo_style_label: string;
    seed: number;
    starting_capital: number;
    ended: boolean;
    end_reason: string | null;
    ai_provider: string;
    sports_provider: string;
    founded: string;
  };
  clock: {
    now: string;
    date: string;
    weekday: string;
    time: string;
    phase: string;
    next_phase: string;
    day_index: number;
  };
  runner: { running: boolean; speed: string; speeds: string[]; phase_seconds: number };
  kpis: Kpis;
  departments: DepartmentCard[];
  employees: EmployeeCard[];
  events: HistoryEvent[];
  ticker: BetView[];
  memo: { time: string; author_id: string; scope: string; text: string } | null;
  ceo_thought: string;
  lab: { budget: number; running: { id: string; name: string; researcher_id: string; due: string }[]; ready: number };
  today: { matches: number; live: number; finished: number };
  summary: RunSummary | null;
}

export interface PerfStats {
  bets: number;
  wins: number;
  staked: number;
  profit: number;
  roi: number;
  z: number;
}

export interface DecisionLog {
  time: string;
  match_id: string;
  match_label: string;
  decision: "BET" | "NO_BET";
  market: string | null;
  selection: string | null;
  odds: number | null;
  stake: number | null;
  confidence: number;
  reason: string;
  bet_id: string | null;
  model_edge: number | null;
  influenced_by: string[];
  notes: string[];
}

export interface AiCallSummary {
  id: number;
  sim_time: string;
  agent_id: string;
  agent_name: string;
  purpose: string;
  provider: string;
  model: string;
  ok: boolean;
  error: string | null;
  retries: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
  estimated: boolean;
  used_fallback: boolean;
}

export interface AiCallFull extends AiCallSummary {
  system: string;
  prompt: string;
  response: string;
}

export interface EmployeeDetail extends EmployeeCard {
  department: string | null;
  hired: string;
  leave_reason: string | null;
  salary: number;
  traits: Record<string, number>;
  traits_text: string;
  warnings: number;
  promotions: number;
  bonuses: number;
  allocation: number;
  max_stake: number;
  stats: {
    bets: number;
    wins: number;
    losses: number;
    staked: number;
    profit: number;
    roi: number;
    best_streak: number;
    worst_streak: number;
    no_bet_rate: number;
    recent30: PerfStats;
    last90: PerfStats;
    by_market: Record<string, { bets: number; roi: number }>;
  };
  strategy: {
    id: string;
    name: string;
    origin: string;
    summary: string;
    live_bets: number;
    live_roi: number;
    backtest: { sample_size: number; roi: number; win_rate: number; max_drawdown_units: number } | null;
    params: Record<string, unknown>;
  } | null;
  series: number[][];
  relationships: { id: string; name: string; title: string; trust: number; respect: number; rivalry: number }[];
  career: { day: string; kind: string; text: string }[];
  decisions: DecisionLog[];
  bets_list: BetView[];
  ai_calls: AiCallSummary[];
}

export interface CostLines {
  betting_pnl: number;
  salaries: number;
  bonuses: number;
  severance: number;
  rent: number;
  data: number;
  marketing: number;
  lab: number;
  ai: number;
  interest: number;
  subscriptions: number;
  expenses: number;
  net: number;
}

export interface MonthlyReport {
  month: string;
  lines: CostLines;
  by_department: Record<string, number>;
  end_cash: number;
  end_bankroll: number;
  end_debt: number;
  valuation: number;
  subscribers: number;
  headcount: number;
  bets: number;
  net: number;
  expenses: number;
}

export interface DailyPoint {
  day: string;
  cash: number;
  bankroll: number;
  exposure: number;
  debt: number;
  payables: number;
  valuation: number;
  day_pnl: number;
  subscribers: number;
}

export interface FinanceView {
  month_to_date: CostLines;
  totals: CostLines;
  reports: MonthlyReport[];
  daily: DailyPoint[];
  departments: { id: string; name: string; active: boolean; total_profit: number; bets: number; roi: number; profit_by_month: Record<string, number> }[];
  subscribers: number;
  subscription_price: number;
  credit_available: number;
}

export interface Experiment {
  id: string;
  researcher_id: string;
  researcher: string;
  name: string;
  hypothesis: string;
  rationale: string;
  strategy_id: string;
  started: string;
  due: string;
  completed: string | null;
  status: "running" | "completed" | "deployed" | "rejected";
  result: { sample_size: number; roi: number; win_rate: number; max_drawdown_units: number; avg_odds: number } | null;
  holdout: { sample_size: number; roi: number } | null;
  recommendation: "" | "DEPLOY" | "PROMISING" | "REJECT";
  recommendation_text: string;
  deployed_names: string[];
  strategy_summary: string;
}

export interface LabView {
  budget: number;
  researchers: EmployeeCard[];
  experiments: Experiment[];
  audit: { id: string; day: string; employee: string; segment: string; bets: number; roi: number; text: string; resolved: boolean }[];
  strategies: { id: string; name: string; origin: string; summary: string; live_bets: number; live_roi: number; users: string[]; retired: boolean; backtest_roi: number | null; backtest_n: number | null }[];
}

export interface ManagementEntry {
  time: string;
  scope: "weekly" | "monthly";
  thought: string;
  memo: string;
  actions: { type: string; params: Record<string, unknown>; reason: string; applied: boolean; result: string }[];
}

export interface SaveInfo {
  id: number;
  run_id: string;
  label: string;
  kind: string;
  created_at: string;
  sim_date: string;
  day_index: number;
  valuation: number;
  size_bytes: number;
  company_name: string;
  ceo_style: string;
  ended: boolean;
}

export interface Meta {
  ceo_styles: { key: string; label: string; description: string }[];
  speeds: string[];
  defaults: {
    company_name: string;
    ceo_style: string;
    seed: number;
    start_date: string;
    starting_capital: number;
    initial_tipsters: number;
    ai_provider: string;
  };
  ai_provider_default: string;
  default_model: string;
  paper_trading_only: boolean;
}

export interface DepartmentDetail {
  id: string;
  name: string;
  kind: string;
  active: boolean;
  founded: string;
  closed: string | null;
  competitions: string[];
  bankroll: number;
  stake_limit_pct: number;
  total_profit: number;
  total_staked: number;
  bets: number;
  month_profit: number;
  profit_by_month: Record<string, number>;
  last30: PerfStats;
  last90: PerfStats;
  members: EmployeeCard[];
  head: string | null;
}
