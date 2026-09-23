import { onUnmounted, ref } from 'vue';

export const NAV_PAGES = [
  { id: 'pull-requests', label: 'Pull Request', icon: 'branch' },
  { id: 'automations', label: '定时任务', icon: 'clock' },
  { id: 'skills', label: '技能', icon: 'skill' },
  { id: 'plugins', label: '插件', icon: 'plugin' },
  { id: 'explore', label: '探索', icon: 'explore' },
] as const;
export type Page = 'chat' | 'temporary' | 'preferences' | typeof NAV_PAGES[number]['id'] | 'not-found';
export interface WorkbenchRoute { page: Page; workspace: string; session: string }

export function chatHref(workspace = '', session = ''): string {
  const params = new URLSearchParams();
  if (workspace) params.set('workspace', workspace);
  if (session) params.set('session', session);
  return `#/chat${params.size ? `?${params}` : ''}`;
}

function readRoute(): WorkbenchRoute {
  const [path, query] = (window.location.hash.slice(1) || '/chat').split('?');
  const name = path?.replace(/^\//, '');
  const page: Page = name === 'chat' || name === 'temporary' || name === 'preferences' ? name : NAV_PAGES.find(item => item.id === name)?.id ?? 'not-found';
  const params = new URLSearchParams(query);
  return { page, workspace: params.get('workspace') ?? '', session: params.get('session') ?? '' };
}

/** Hash URLs work with the existing FastAPI static mount, including refreshes. */
export function useWorkbenchRoute() {
  const route = ref(readRoute());
  const sync = () => { route.value = readRoute(); };
  window.addEventListener('hashchange', sync);
  window.addEventListener('popstate', sync);
  onUnmounted(() => {
    window.removeEventListener('hashchange', sync);
    window.removeEventListener('popstate', sync);
  });
  function navigate(href: string, replace = false): void {
    if (window.location.hash === href) return;
    window.history[replace ? 'replaceState' : 'pushState'](null, '', href);
    sync();
  }
  return { route, navigate };
}
