import { onBeforeUnmount, onMounted } from "vue";

type WorkflowShortcutOptions = {
  canSave: () => boolean;
  save: () => void;
  undo: () => void;
  redo: () => void;
  escape: () => void;
};

export function useWorkflowShortcuts(options: WorkflowShortcutOptions): void {
  onMounted(() => window.addEventListener("keydown", handle));
  onBeforeUnmount(() => window.removeEventListener("keydown", handle));

  function handle(event: KeyboardEvent): void {
    const command = event.ctrlKey || event.metaKey;
    if (command && event.key.toLowerCase() === "s") {
      event.preventDefault();
      if (options.canSave()) options.save();
      return;
    }
    if (command && event.key.toLowerCase() === "z") {
      event.preventDefault();
      if (event.shiftKey) options.redo();
      else options.undo();
      return;
    }
    if (command && event.key.toLowerCase() === "y") {
      event.preventDefault();
      options.redo();
      return;
    }
    if (event.key === "Escape") options.escape();
  }
}
