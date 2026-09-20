import { onBeforeUnmount, reactive, watch } from "vue";

/** 按列表命名空间保存筛选；恢复历史时不额外制造历史记录。 */
export function useListFilters<T extends Record<string, unknown>>(key: string, defaults: T, validators: Partial<Record<keyof T, (value: unknown) => boolean>> = {}) {
  const read = (): T => {
    const raw = new URLSearchParams(location.search).get(`${key}_filters`);
    try {
      const saved = JSON.parse(raw || "{}");
      return Object.fromEntries(Object.entries(defaults).map(([name, value]) => [name,
        saved[name] !== undefined && typeof saved[name] === typeof value && Array.isArray(saved[name]) === Array.isArray(value) && (!validators[name] || validators[name]!(saved[name]))
          ? saved[name] : value])) as T;
    } catch { return { ...defaults }; }
  };
  const state = reactive(read()) as T;
  let restoring = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  watch(() => JSON.stringify(state), () => {
    if (restoring) return;
    clearTimeout(timer);
    timer = setTimeout(() => {
      const url = new URL(location.href);
      url.searchParams.set(`${key}_filters`, JSON.stringify(state));
      url.searchParams.set(`${key}_page`, "1");
      history.pushState(history.state, "", url);
    }, 300);
  });
  function restore() {
    clearTimeout(timer); restoring = true; Object.assign(state, read());
    queueMicrotask(() => { restoring = false; });
  }
  window.addEventListener("popstate", restore);
  onBeforeUnmount(() => { clearTimeout(timer); window.removeEventListener("popstate", restore); });
  return state;
}
