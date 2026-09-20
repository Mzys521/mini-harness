import type { Principal, RunState, RunSubmission } from "@/types/domain";

/**
 * Single fetch entry point. Same-origin by design: FastAPI serves the built
 * workspace at `/` and the assets at `/ui`, so no base URL is configurable —
 * a mismatched origin is reported as a problem, not silently retried.
 */

export class ApiError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

let apiKey = "";

export function setApiKey(value: string): void {
  apiKey = value;
}

export function getApiKey(): string {
  return apiKey;
}

function messageFor(response: Response, data: Record<string, unknown> | null): string {
  // RFC 9457 `application/problem+json` plus FastAPI's own `detail`.
  const detail = data?.detail;
  const title = data?.title;
  if (typeof detail === "string") return `${response.status} · ${detail}`;
  if (typeof title === "string") return `${response.status} · ${title}`;
  return `${response.status} · 请确认通过 python main.py api 启动服务，并从服务首页连接。`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
        ...(init.headers ?? {}),
      },
    });
  } catch (error) {
    const name = (error as { name?: string }).name;
    if (name === "TimeoutError") {
      throw new ApiError("服务响应超时。运行可能仍在服务端继续，请恢复状态查询。");
    }
    throw new ApiError("无法连接 Harness，请检查服务是否正在运行。");
  }

  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("json")
    ? ((await response.json()) as Record<string, unknown>)
    : null;

  if (!response.ok) throw new ApiError(messageFor(response, data), response.status);
  if (!data) throw new ApiError("当前地址不是 Harness API 服务，请从服务首页打开工作台。");
  return data as T;
}

export const api = {
  healthz(): Promise<{ status: string; version: string }> {
    return request("/healthz");
  },
  me(candidateKey: string): Promise<Principal> {
    return request("/v1/me", { headers: { "X-API-Key": candidateKey } });
  },
  submitRun(body: { input: string; conversation_id?: string }): Promise<RunSubmission> {
    return request("/v1/runs", { method: "POST", body: JSON.stringify(body) });
  },
  runState(runId: string): Promise<RunState> {
    return request(`/v1/runs/${encodeURIComponent(runId)}`);
  },
  approveRun(runId: string): Promise<unknown> {
    return request(`/v1/runs/${encodeURIComponent(runId)}/approve`, { method: "POST" });
  },
  cancelRun(runId: string): Promise<unknown> {
    return request(`/v1/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" });
  },
};
