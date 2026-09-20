/**
 * Thin, failure-tolerant localStorage port.
 *
 * Browser storage can be unavailable (private mode, disabled cookies). The
 * workspace degrades to in-memory state and surfaces a single warning instead
 * of throwing.
 */

let warned = false;
let onUnavailable: (() => void) | null = null;

export function onStorageUnavailable(handler: () => void): void {
  onUnavailable = handler;
}

export function readJSON<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? null : (JSON.parse(raw) as T);
  } catch {
    return null;
  }
}

export function writeJSON(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    if (warned) return;
    warned = true;
    onUnavailable?.();
  }
}

export const STORAGE_KEYS = {
  workspace: "mini-harness.workspace.v1",
  layout: "mini-harness.layout.v1",
  theme: "mini-harness.theme.v1",
} as const;
