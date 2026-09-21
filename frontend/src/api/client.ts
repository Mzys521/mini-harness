/**
 * Single HTTP entry point for the workspace UI.
 *
 * Same-origin by design: FastAPI serves the app at `/` and its assets at `/ui`,
 * so there is no configurable base URL — a mismatched origin is reported as a
 * problem instead of being retried silently.
 */

export class ApiError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function messageFor(response: Response, data: Record<string, unknown> | null): string {
  const detail = data?.detail;
  if (typeof detail === "string") return `${response.status} · ${detail}`;
  return `${response.status} · 请确认已通过 python main.py api 启动本地服务。`;
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
      headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
  } catch (error) {
    if ((error as { name?: string }).name === "TimeoutError") {
      throw new ApiError("服务响应超时。任务可能仍在服务端继续，请稍后刷新。");
    }
    throw new ApiError("无法连接本地 Harness 服务，请检查服务是否正在运行。");
  }

  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("json")
    ? ((await response.json()) as Record<string, unknown>)
    : null;

  if (!response.ok) throw new ApiError(messageFor(response, data), response.status);
  if (!data) throw new ApiError("当前地址不是 Harness API 服务，请从服务首页打开工作台。");
  return data as T;
}

/** One decoded SSE frame (`data: {json}`) from a run stream. */
export type RunEvent = Record<string, unknown> & { type: string };

export interface RunStreamHandlers {
  onEvent: (event: RunEvent) => void;
  /** Called once when the browser gives up reconnecting. */
  onError?: (message: string) => void;
}

/**
 * Subscribes to `/v1/runs/{id}/stream`.
 *
 * The server replays every buffered event first, so opening the stream after the
 * run already started loses nothing. Returns the unsubscribe function.
 */
export function streamRun(runId: string, handlers: RunStreamHandlers): () => void {
  const source = new EventSource(`/v1/runs/${encodeURIComponent(runId)}/stream`);

  source.onmessage = (message: MessageEvent<string>) => {
    try {
      handlers.onEvent(JSON.parse(message.data) as RunEvent);
    } catch {
      // A malformed frame must never break the transcript.
    }
  };

  source.onerror = () => {
    // 0 = CONNECTING (the browser retries), 2 = CLOSED (no further retry).
    if (source.readyState === EventSource.CLOSED) {
      handlers.onError?.("与服务的实时连接已断开，请刷新页面查看结果。");
    }
  };

  return () => source.close();
}
