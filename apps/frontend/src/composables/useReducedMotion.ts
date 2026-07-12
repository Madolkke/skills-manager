import { onBeforeUnmount, onMounted, readonly, ref } from "vue";

export function useReducedMotion() {
  const reduced = ref(typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  let query: MediaQueryList | null = null;

  function update(event?: MediaQueryListEvent): void {
    reduced.value = event?.matches ?? query?.matches ?? false;
  }

  onMounted(() => {
    query = window.matchMedia("(prefers-reduced-motion: reduce)");
    update();
    query.addEventListener("change", update);
  });

  onBeforeUnmount(() => query?.removeEventListener("change", update));
  return readonly(reduced);
}
