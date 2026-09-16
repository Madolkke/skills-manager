import { computed, onBeforeUnmount, ref } from "vue";

const LEFT_MIN = 216;
const LEFT_MAX = 360;
const RIGHT_MIN = 340;
const RIGHT_MAX = 780;
const COMPACT_WORKBENCH_MAX = 1439;

export function useWorkflowLayout() {
  const viewportWidth = ref(typeof window === "undefined" ? 1600 : window.innerWidth);
  const compact = computed(() => viewportWidth.value < 1180);
  const activePanel = ref<"structure" | "editor" | "preview">("editor");
  const leftWidth = ref(workflowInitialLeftWidth(viewportWidth.value));
  const rightWidth = ref(workflowInitialRightWidth(viewportWidth.value));
  const leftCollapsed = ref(false);
  const rightCollapsed = ref(false);
  const graphExpanded = ref(false);
  const resizing = ref(false);
  let stopResize: (() => void) | null = null;
  const gridStyle = computed(() => ({
    gridTemplateColumns: compact.value ? "minmax(0, 1fr)" : `${leftCollapsed.value ? 0 : leftWidth.value}px ${leftCollapsed.value ? 20 : 6}px minmax(560px, 1fr) ${rightCollapsed.value ? 20 : 6}px ${rightCollapsed.value ? 0 : rightWidth.value}px`,
  }));

  function startResize(side: "left" | "right", event: PointerEvent): void {
    if (compact.value) return;
    if ((side === "left" && leftCollapsed.value) || (side === "right" && rightCollapsed.value)) return;
    stopResize?.();
    const startX = event.clientX;
    const startWidth = side === "left" ? leftWidth.value : rightWidth.value;
    document.body.classList.add("workflow-resizing");
    resizing.value = true;
    const move = (next: PointerEvent) => {
      const delta = next.clientX - startX;
      if (side === "left") leftWidth.value = clamp(startWidth + delta, LEFT_MIN, LEFT_MAX);
      else rightWidth.value = clamp(startWidth - delta, RIGHT_MIN, RIGHT_MAX);
    };
    const stop = () => {
      document.body.classList.remove("workflow-resizing");
      resizing.value = false;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      stopResize = null;
    };
    stopResize = stop;
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop, { once: true });
  }

  function toggle(side: "left" | "right"): void {
    if (side === "left") leftCollapsed.value = !leftCollapsed.value;
    else rightCollapsed.value = !rightCollapsed.value;
  }

  function setGraphExpanded(expanded: boolean): void {
    graphExpanded.value = expanded;
  }

  /** 在隐藏编辑器前提交待处理输入，保持桌面布局状态独立。 */
  function showPanel(panel: "structure" | "editor" | "preview"): void {
    if (compact.value && activePanel.value !== panel) flushFocusedInput();
    activePanel.value = panel;
  }

  /** 断点变化只改变可见面板，不覆盖桌面栏宽和折叠状态。 */
  function resizeViewport(): void {
    flushFocusedInput();
    viewportWidth.value = window.innerWidth;
    if (compact.value) stopResize?.();
  }
  window.addEventListener("resize", resizeViewport);
  onBeforeUnmount(() => { stopResize?.(); window.removeEventListener("resize", resizeViewport); });

  return { compact, activePanel, showPanel, leftCollapsed, rightCollapsed, graphExpanded, resizing, gridStyle, startResize, toggle, setGraphExpanded };
}

export function workflowInitialRightWidth(viewportWidth: number): number {
  return viewportWidth <= COMPACT_WORKBENCH_MAX ? 360 : 440;
}

export function workflowInitialLeftWidth(viewportWidth: number): number {
  return viewportWidth <= COMPACT_WORKBENCH_MAX ? 232 : 252;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

/** blur 由各编辑器负责同步草稿并关闭补全。 */
function flushFocusedInput(): void {
  if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
}
