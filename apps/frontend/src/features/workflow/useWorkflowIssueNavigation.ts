import { nextTick, onBeforeUnmount, type Ref } from "vue";
import type { WorkflowSelection } from "../../types";

export function useWorkflowIssueNavigation(editorPane: Ref<HTMLElement | null>) {
  let highlighted: HTMLElement | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  onBeforeUnmount(() => {
    if (timer) clearTimeout(timer);
    highlighted?.classList.remove("is-issue-target");
  });

  async function navigate(selection: WorkflowSelection): Promise<void> {
    await nextTick();
    await animationFrame();
    const root = editorPane.value;
    if (!root) return;
    const field = "field" in selection ? selection.field : undefined;
    const itemId = "itemId" in selection ? selection.itemId : undefined;
    const fieldItemId = field?.match(/(?:\.|\[)([^.[\]]+)\]?$/)?.[1];
    const itemIndex = field?.match(/\[(\d+)\]$/)?.[1];
    const section = "section" in selection ? query(root, "data-workflow-section", selection.section) : null;
    const scope = section ?? root;
    const target = query(scope, "data-workflow-field", field)
      ?? query(scope, "data-workflow-item", fieldItemId)
      ?? query(scope, "data-workflow-item", itemId)
      ?? query(scope, "data-workflow-index", itemIndex)
      ?? section
      ?? root.querySelector<HTMLElement>(".workflow-document");
    if (!target) return;
    highlighted?.classList.remove("is-issue-target");
    if (timer) clearTimeout(timer);
    highlighted = target;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    const control = target.matches("input, textarea, select, button")
      ? target
      : target.querySelector<HTMLElement>("input:not(:disabled), textarea:not(:disabled), select:not(:disabled), button:not(:disabled)");
    control?.focus({ preventScroll: true });
    target.classList.remove("is-issue-target");
    void target.offsetWidth;
    target.classList.add("is-issue-target");
    timer = setTimeout(() => {
      target.classList.remove("is-issue-target");
      if (highlighted === target) highlighted = null;
    }, 900);
  }

  return { navigate };

  function animationFrame(): Promise<void> {
    return new Promise((resolve) => requestAnimationFrame(() => resolve()));
  }
}

function query(root: HTMLElement, attribute: string, value?: string): HTMLElement | null {
  return value ? root.querySelector<HTMLElement>(`[${attribute}="${CSS.escape(value)}"]`) : null;
}
