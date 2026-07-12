import { computed, shallowRef } from "vue";

const HISTORY_LIMIT = 50;
const INPUT_GROUP_WINDOW_MS = 750;

export function useWorkflowHistory<T>(current: () => T | null, restore: (value: T) => void) {
  const past = shallowRef<T[]>([]);
  const future = shallowRef<T[]>([]);
  const saved = shallowRef<T | null>(null);
  let lastGroup = "";
  let lastRecordedAt = 0;
  const dirty = computed(() => {
    const value = current();
    return value !== null && saved.value !== null && serialized(value) !== serialized(saved.value);
  });

  function resetBaseline(): void {
    saved.value = current();
    past.value = [];
    future.value = [];
    resetGroup();
  }

  function record(before: T, group = ""): void {
    const now = Date.now();
    const grouped = Boolean(group && group === lastGroup && now - lastRecordedAt <= INPUT_GROUP_WINDOW_MS);
    if (!grouped) past.value = [...past.value, before].slice(-HISTORY_LIMIT);
    future.value = [];
    lastGroup = group;
    lastRecordedAt = now;
  }

  function undo(): void {
    const previous = past.value.at(-1);
    const value = current();
    if (!previous || value === null) return;
    future.value = [value, ...future.value].slice(0, HISTORY_LIMIT);
    past.value = past.value.slice(0, -1);
    restore(previous);
    resetGroup();
  }

  function redo(): void {
    const next = future.value[0];
    const value = current();
    if (!next || value === null) return;
    past.value = [...past.value, value].slice(-HISTORY_LIMIT);
    future.value = future.value.slice(1);
    restore(next);
    resetGroup();
  }

  function discard(): void {
    if (saved.value) restore(saved.value);
    past.value = [];
    future.value = [];
    resetGroup();
  }

  function resetGroup(): void {
    lastGroup = "";
    lastRecordedAt = 0;
  }

  return {
    dirty,
    canUndo: computed(() => past.value.length > 0),
    canRedo: computed(() => future.value.length > 0),
    resetBaseline,
    record,
    undo,
    redo,
    discard,
  };
}

function serialized(value: unknown): string {
  return JSON.stringify(value);
}
