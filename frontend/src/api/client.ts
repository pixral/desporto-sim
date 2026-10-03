import type {
  AiCallFull,
  DepartmentDetail,
  AiCallSummary,
  EmployeeDetail,
  FinanceView,
  HistoryEvent,
  LabView,
  ManagementEntry,
  Meta,
  RunSummary,
  SaveInfo,
  SeasonRecap,
} from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* keep status text */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  meta: () => req<Meta>("/api/meta"),
  control: (action: string, speed?: string) =>
    req<{ running: boolean; speed: string }>("/api/control", { method: "POST", body: JSON.stringify({ action, speed }) }),
  employee: (id: string) => req<EmployeeDetail>(`/api/employees/${id}`),
  employees: () => req<(EmployeeDetail & { department: string | null })[]>("/api/employees"),
  department: (id: string) => req<DepartmentDetail>(`/api/departments/${id}`),
  finance: () => req<FinanceView>("/api/finance"),
  lab: () => req<LabView>("/api/lab"),
  history: (minImportance = 1) => req<HistoryEvent[]>(`/api/history?min_importance=${minImportance}&limit=800`),
  management: () => req<ManagementEntry[]>("/api/management"),
  summary: () => req<RunSummary>("/api/summary"),
  recaps: () => req<SeasonRecap[]>("/api/recaps"),
  aiCalls: (params: { agent_id?: string; purpose?: string; failures_only?: boolean; limit?: number } = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && v !== "" && q.set(k, String(v)));
    return req<AiCallSummary[]>(`/api/ai/calls?${q.toString()}`);
  },
  aiCall: (id: number) => req<AiCallFull>(`/api/ai/calls/${id}`),
  saves: () => req<SaveInfo[]>("/api/saves"),
  save: (label: string) => req<{ save_id: number }>("/api/saves", { method: "POST", body: JSON.stringify({ label }) }),
  load: (id: number) => req<{ run_id: string }>(`/api/saves/${id}/load`, { method: "POST" }),
  deleteSave: (id: number) => req<{ deleted: number }>(`/api/saves/${id}`, { method: "DELETE" }),
  newRun: (body: Record<string, unknown>) =>
    req<{ run_id: string }>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
};
