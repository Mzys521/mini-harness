/**
 * jsdom lacks a few browser APIs the workspace relies on. Each stub keeps the
 * real semantics that matter (change listeners, storability) so component
 * behaviour under test matches the browser.
 */

type Listener = (event: { matches: boolean; media: string }) => void;

const mediaListeners = new Map<string, Set<Listener>>();
let viewportWidth = 1440;

function matchesFor(query: string): boolean {
  const max = /max-width:\s*(\d+)px/.exec(query);
  if (max) return viewportWidth <= Number(max[1]);
  const min = /min-width:\s*(\d+)px/.exec(query);
  if (min) return viewportWidth >= Number(min[1]);
  return false;
}

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    media: query,
    get matches() {
      return matchesFor(query);
    },
    onchange: null,
    addEventListener: (_type: string, listener: Listener) => {
      if (!mediaListeners.has(query)) mediaListeners.set(query, new Set());
      mediaListeners.get(query)!.add(listener);
    },
    removeEventListener: (_type: string, listener: Listener) => {
      mediaListeners.get(query)?.delete(listener);
    },
    dispatchEvent: () => true,
  }),
});

/** Resize the simulated viewport and notify media-query subscribers. */
export function setViewportWidth(width: number): void {
  viewportWidth = width;
  for (const [query, listeners] of mediaListeners) {
    for (const listener of listeners) listener({ matches: matchesFor(query), media: query });
  }
}

// The workspace only ever talks to same-origin JSON endpoints; tests stub them.
globalThis.fetch = (async () =>
  new Response(JSON.stringify({ status: "unavailable" }), {
    status: 503,
    headers: { "content-type": "application/json" },
  })) as typeof fetch;
