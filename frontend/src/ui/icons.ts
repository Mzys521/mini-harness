/**
 * Inline SVG icon paths. Kept local (no icon font, no remote sprite) so the
 * workspace still works when served from a machine without internet access.
 */
export const icons: Record<string, string> = {
  harness: '<path d="m4 7 5 5-5 5m11-10 5 5-5 5M13 4l-3 16"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  moon: '<path d="M20.5 13.4A8.5 8.5 0 0 1 10.6 3.5a8.5 8.5 0 1 0 9.9 9.9Z"/>',
  sun:
    '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5"/>',
  settings:
    '<path d="m9 3-.7 2.2-2.2 1L4 5.9l-2 3.5 1.7 1.7v2L2 14.7l2 3.5 2.1-.4 2.2 1L9 21h4l.8-2.2 2.1-1 2.1.4 2-3.5-1.7-1.6v-2L20 9.4l-2-3.5-2.1.3-2.1-1L13 3Z"/><circle cx="11" cy="12" r="3"/>',
  compose: '<path d="M12 4H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-7M15.5 3.5a2.1 2.1 0 0 1 3 3L10 15l-4 1 1-4Z"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  box: '<path d="m12 3 9 5v9l-9 5-9-5V8Zm0 10 9-5M3 8l9 5v9M7.5 5.5l9 5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  plug: '<path d="m8 3 4 4m3-11 4 4" transform="translate(0 4)"/><path d="m5 10 9-9m-9 9 3 3a5 5 0 0 0 7 0l3-3-9-9M7 17l-4 4m4-4 2-2"/>',
  "arrow-up-right": '<path d="M6 18 18 6M6 6h12v12"/>',
  "arrow-right": '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  "arrow-up": '<path d="M12 20V4m-6 6 6-6 6 6"/>',
  folder: '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
  "folder-open": '<path d="M3 9V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2M3 9h19l-3 11H3Z"/>',
  layers: '<path d="m12 3 10 5-10 5L2 8Zm-9 10 9 5 9-5M3 18l9 5 9-5"/>',
  book: '<path d="M12 5C8 2 4 3 2 4v15c4-2 7-1 10 1 3-2 6-3 10-1V4c-3-1-7-2-10 1Zm0 0v15"/>',
  terminal: '<rect x="2" y="3" width="20" height="18" rx="3"/><path d="m6 8 4 4-4 4m7 0h5"/>',
  sparkles: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5ZM20 2v4m-2-2h4"/>',
  "chevron-down": '<path d="m6 9 6 6 6-6"/>',
  "chevron-right": '<path d="m9 6 6 6-6 6"/>',
  code: '<path d="m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/>',
  "list-clear": '<path d="M3 5h18M3 10h12M3 15h7m6 0 5 5m-5 0 5-5"/>',
  shield: '<path d="M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6ZM8 12l3 3 5-6"/>',
  branch: '<circle cx="6" cy="5" r="2"/><circle cx="18" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><path d="M6 7v10M18 7c0 5-12 3-12 8"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v2"/>',
  sidebar: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 3v18"/>',
  chat: '<path d="M21 11.5a9 9 0 0 1-9 9 10 10 0 0 1-4-.9L3 21l1.4-4.7A9 9 0 1 1 21 11.5Z"/>',
  x: '<path d="m6 6 12 12M6 18 18 6"/>',
  key: '<circle cx="8" cy="9" r="5"/><path d="m12 13 8 8m-3-3 3-3m-6 0 3-3"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Zm0 0v6h6M8 13h8m-8 4h6"/>',
  copy: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h4"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>',
  "panel-collapse": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M15 3v18m3-12-3 3 3 3"/>',
  "panel-expand": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M15 3v18m0-12-3 3 3 3"/>',
  "panel-bottom-collapse": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 15h18m-12 3 3 3 3-3"/>',
  "panel-bottom-expand": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 15h18m-12 3 3-3 3 3"/>',
};

export function iconPaths(name: string): string {
  return icons[name] ?? icons.file;
}
