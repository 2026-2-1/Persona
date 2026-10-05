import type { Health, SessionDetail, SessionSummary } from "./types";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...options.headers },
  });

  if (!response.ok) {
    let detail = `서버 요청에 실패했습니다 (${response.status}).`;
    try {
      const body: { detail?: unknown } = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Preserve the HTTP status when the response is not JSON.
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: (signal?: AbortSignal) => request<Health>("/health", { signal }),
  sessions: (signal?: AbortSignal) =>
    request<SessionSummary[]>("/sessions", { signal }),
  session: (id: string, signal?: AbortSignal) =>
    request<SessionDetail>(`/sessions/${encodeURIComponent(id)}`, { signal }),
  createSession: (idempotencyKey: string) =>
    request<SessionDetail>("/sessions", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ persona_name: "초보 러너", task_id: "T02" }),
    }),
  cancelSession: (id: string) =>
    request<SessionDetail>(`/sessions/${encodeURIComponent(id)}/cancel`, {
      method: "POST",
    }),
};

export function screenshotUrl(path: string): string {
  return new URL(path, `${API_BASE_URL}/`).toString();
}

export function errorMessage(error: unknown): string {
  if (error instanceof TypeError) {
    return "서버에 연결할 수 없습니다. API가 실행 중인지 확인하고 다시 연결해 주세요.";
  }
  return error instanceof Error ? error.message : "요청을 처리하지 못했습니다.";
}
