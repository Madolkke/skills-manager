import { computed, ref } from "vue";

const LEFT_MIN = 216;
const LEFT_MAX = 360;
const RIGHT_MIN = 320;
const RIGHT_MAX = 620;

export function useWorkflowLayout() {
  const leftWidth = ref(252);
  const rightWidth = ref(390);
  const leftCollapsed = ref(false);
  const rightCollapsed = ref(false);
  const gridStyle = computed(() => ({
    gridTemplateColumns: `${leftCollapsed.value ? 0 : leftWidth.value}px ${leftCollapsed.value ? 20 : 6}px minmax(560px, 1fr) ${rightCollapsed.value ? 20 : 6}px ${rightCollapsed.value ? 0 : rightWidth.value}px`,
  }));

  function startResize(side: "left" | "right", event: PointerEvent): void {
    const startX = event.clientX;
    const startWidth = side === "left" ? leftWidth.value : rightWidth.value;
    document.body.classList.add("workflow-resizing");
    const move = (next: PointerEvent) => {
      const delta = next.clientX - startX;
      if (side === "left") leftWidth.value = clamp(startWidth + delta, LEFT_MIN, LEFT_MAX);
      else rightWidth.value = clamp(startWidth - delta, RIGHT_MIN, RIGHT_MAX);
    };
    const stop = () => {
      document.body.classList.remove("workflow-resizing");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop, { once: true });
  }

  return { leftCollapsed, rightCollapsed, gridStyle, startResize };
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}
