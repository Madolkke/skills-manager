import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import type { Page } from "../lib/api/paginationApi";

/** 保存列表路由状态，并在翻页、筛选和重试时丢弃过期响应。 */
export function usePagedQuery<R extends Page<unknown>>(
  key: string,
  filters: () => Record<string, unknown>,
  fetchPage: (params: Record<string, unknown>, signal: AbortSignal) => Promise<R>,
  options: { route?: boolean; immediate?: boolean } = {},
) {
  const readPage = () => { const n = Number(new URLSearchParams(location.search).get(`${key}_page`)); return Number.isSafeInteger(n) && n > 0 ? n : 1; };
  const readSize = () => { const n = Number(new URLSearchParams(location.search).get(`${key}_size`)); return [20, 50, 100].includes(n) ? n : 20; };
  const page = ref(options.route === false ? 1 : readPage());
  const pageSize = ref(options.route === false ? 20 : readSize());
  const result = shallowRef<R | null>(null);
  const items = computed<R["items"]>(() => result.value?.items ?? []);
  const total = computed(() => result.value?.total ?? 0);
  const loading = ref(false);
  const error = ref("");
  let sequence = 0;
  let controller: AbortController | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let disposed = false;
  let restoring = false;
  let resettingFilters = false;

  /** 当前数据保留到新请求完成，失败展示错误而非空状态。 */
  async function reload() {
    clearTimeout(timer);
    controller?.abort();
    controller = new AbortController();
    const current = ++sequence;
    loading.value = true;
    error.value = "";
    try {
      const response = await fetchPage({ ...filters(), page: page.value, page_size: pageSize.value }, controller.signal);
      if (disposed || current !== sequence) return;
      const last = Math.max(1, Math.ceil(response.total / pageSize.value));
      if (page.value > last) { page.value = last; return; }
      result.value = response;
    } catch (caught) {
      if (!disposed && current === sequence && !controller.signal.aborted) error.value = caught instanceof Error ? caught.message : "加载失败，请重试。";
    } finally {
      if (current === sequence) loading.value = false;
    }
  }

  function schedule(delay = 0) {
    controller?.abort();
    sequence++;
    loading.value = true;
    clearTimeout(timer);
    timer = setTimeout(() => void reload(), delay);
  }
  watch(() => JSON.stringify(filters()), () => {
    if (!restoring) { resettingFilters = true; page.value = 1; }
    schedule(restoring ? 0 : 300);
    queueMicrotask(() => { resettingFilters = false; });
  });
  watch(pageSize, () => { if (!restoring) page.value = 1; });
  watch([page, pageSize], () => {
    if (resettingFilters) return;
    if (options.route !== false && !restoring) {
      const url = new URL(location.href);
      url.searchParams.set(`${key}_page`, String(page.value));
      url.searchParams.set(`${key}_size`, String(pageSize.value));
      history.pushState(history.state, "", url);
    }
    schedule();
  });
  function restore() { restoring = true; page.value = readPage(); pageSize.value = readSize(); schedule(); queueMicrotask(() => { restoring = false; }); }
  if (options.route !== false) window.addEventListener("popstate", restore);
  if (options.immediate !== false) void reload();
  onBeforeUnmount(() => { disposed = true; sequence++; controller?.abort(); clearTimeout(timer); window.removeEventListener("popstate", restore); });
  return { page, pageSize, result, items, total, loading, error, reload };
}
