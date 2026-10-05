export type SessionStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "technical_error"
  | "cancelled";

export interface Health {
  status: "ok";
  service: string;
  model_provider: string;
}

export interface SessionSummary {
  id: string;
  persona_name: string;
  task_id: string;
  status: SessionStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  steps_count?: number;
}

export interface SessionStep {
  id: string;
  step_no: number;
  action: string;
  url: string;
  description: string;
  status: string;
  created_at: string;
  screenshot_before: string | null;
  screenshot_after: string | null;
}

export interface SessionDetail extends SessionSummary {
  steps: SessionStep[];
}

export function isActive(status: SessionStatus): boolean {
  return status === "queued" || status === "running";
}
