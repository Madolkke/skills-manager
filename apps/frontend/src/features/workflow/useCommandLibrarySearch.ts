import { computed, onBeforeUnmount, ref, watch, type Ref } from "vue";
import { api } from "../../lib/api";
import type { CommandLibrarySearchResult } from "../../types";
import { commandLibraryIncludeUser } from "./commandLibrarySession";

/** 提供共享的系统/用户 CLI 命令搜索状态，两个入口使用同一排序和来源语义。 */
export function useCommandLibrarySearch(query: Ref<string>, enabled?: Ref<boolean>) {
  const includeUser = commandLibraryIncludeUser;
  const searchEnabled = computed(() => enabled?.value ?? true);
  const results = ref<CommandLibrarySearchResult[]>([]);
  const loading = ref(false);
  const error = ref("");
  let controller: AbortController | null = null;
  let timer: number | null = null;

  async function search(): Promise<void> {
    if (!searchEnabled.value) {
      results.value = [];
      loading.value = false;
      return;
    }
    const value = query.value.trim();
    controller?.abort();
    controller = new AbortController();
    loading.value = true;
    error.value = "";
    try {
      const response = await api.searchCommandLibrary(value, includeUser.value, undefined, controller.signal);
      results.value = response.results;
    } catch (caught) {
      if ((caught as Error).name !== "AbortError") {
        results.value = [];
        error.value = caught instanceof Error ? caught.message : "命令搜索失败。";
      }
    } finally {
      loading.value = false;
    }
  }

  function schedule(): void {
    if (timer !== null) window.clearTimeout(timer);
    controller?.abort();
    if (!searchEnabled.value) {
      results.value = [];
      loading.value = false;
      return;
    }
    timer = window.setTimeout(() => void search(), 180);
  }

  watch([query, includeUser, searchEnabled], (_next, previous) => {
    if (previous?.[1] === true && includeUser.value === false) {
      results.value = results.value.filter((item) => item.source === "system");
    }
    schedule();
  }, { immediate: true });
  onBeforeUnmount(() => {
    controller?.abort();
    if (timer !== null) window.clearTimeout(timer);
  });

  return { includeUser, results, loading, error, hasQuery: computed(() => Boolean(query.value.trim())), search };
}
