import { onBeforeUnmount, onMounted, type Ref } from "vue";

export function useTransientScrollbar(target: Ref<HTMLElement | null>, delay = 700): void {
  let timer: ReturnType<typeof setTimeout> | undefined;

  function show(): void {
    target.value?.classList.add("is-scrolling");
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => target.value?.classList.remove("is-scrolling"), delay);
  }

  onMounted(() => target.value?.addEventListener("scroll", show, { passive: true }));
  onBeforeUnmount(() => {
    if (timer) clearTimeout(timer);
    target.value?.removeEventListener("scroll", show);
  });
}
