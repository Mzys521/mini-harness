/**
 * jsdom lacks a few browser APIs the workspace touches. Each stub keeps the
 * semantics that matter, so component behaviour under test matches the browser.
 */

HTMLElement.prototype.scrollIntoView = function () {};
HTMLDialogElement.prototype.showModal = function () { this.open = true; };
HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new Event('close')); };

// The workspace only ever talks to same-origin JSON endpoints; tests stub them.
globalThis.fetch = (async () =>
  new Response(JSON.stringify({ detail: "unavailable" }), {
    status: 503,
    headers: { "content-type": "application/json" },
  })) as typeof fetch;
