import Sortable from "sortablejs";
import { onBeforeUnmount, watch, type Ref } from "vue";

type SortableListOptions = {
  disabled: () => boolean;
  handle?: string;
  itemSelector?: string;
  onReorder: (ids: string[]) => void;
};

export function useSortableList(container: Ref<HTMLElement | null>, options: SortableListOptions): void {
  let sortable: Sortable | null = null;

  watch(container, (element) => {
    sortable?.destroy();
    sortable = element ? createSortable(element, options) : null;
  }, { flush: "post", immediate: true });

  watch(options.disabled, (disabled) => sortable?.option("disabled", disabled));
  onBeforeUnmount(() => sortable?.destroy());
}

function createSortable(element: HTMLElement, options: SortableListOptions): Sortable {
  return new Sortable(element, {
    animation: 160,
    disabled: options.disabled(),
    draggable: options.itemSelector ?? "[data-sort-id]",
    ghostClass: "workflow-sort-ghost",
    chosenClass: "workflow-sort-chosen",
    handle: options.handle ?? ".workflow-drag-handle",
    onEnd: () => {
      const ids = [...element.querySelectorAll<HTMLElement>("[data-sort-id]")]
        .map((item) => item.dataset.sortId)
        .filter((id): id is string => Boolean(id));
      options.onReorder(ids);
    },
  });
}
