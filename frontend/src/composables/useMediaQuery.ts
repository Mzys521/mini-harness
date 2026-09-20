import { onScopeDispose, ref } from "vue";

/** Reactive `matchMedia`, cleaned up with the owning effect scope. */
export function useMediaQuery(query: string) {
  const list = window.matchMedia(query);
  const matches = ref(list.matches);

  const update = (event: MediaQueryListEvent): void => {
    matches.value = event.matches;
  };
  list.addEventListener("change", update);
  onScopeDispose(() => list.removeEventListener("change", update));

  return matches;
}

/** Mirrors the 900px breakpoint in `styles/responsive.css`. */
export function useIsMobile() {
  return useMediaQuery("(max-width: 900px)");
}
