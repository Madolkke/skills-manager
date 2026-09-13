import { onScopeDispose, ref } from "vue";
import { getAnalytics } from "./api";
import { presetRange } from "./dates";
import type { AnalyticsOverview, AnalyticsRange } from "./types";

/** 维护独立看板加载状态，并屏蔽过期查询结果。 */
export function useAnalytics(client = getAnalytics) {
  const range = ref<AnalyticsRange>(presetRange("year"));
  const data = ref<AnalyticsOverview | null>(null);
  const loading = ref(false);
  const error = ref("");
  let controller: AbortController | undefined;
  let sequence = 0;
  onScopeDispose(() => { sequence += 1; controller?.abort(); });

  /** 每次加载取消旧请求；日期错误不会覆盖已显示的数据。 */
  async function load(next: AnalyticsRange = range.value): Promise<void> {
    const current = ++sequence;
    controller?.abort();
    if (!next.start_date || !next.end_date || next.end_date < next.start_date) {
      loading.value = false;
      error.value = "请选择有效日期范围。";
      return;
    }
    controller = new AbortController();
    range.value = { ...next };
    error.value = "";
    loading.value = true;
    try {
      const result = await client(next, controller.signal);
      if (current === sequence) data.value = result;
    } catch (cause) {
      if (current === sequence) error.value = cause instanceof Error ? cause.message : "统计加载失败，请重试。";
    } finally {
      if (current === sequence) loading.value = false;
    }
  }
  return { range, data, loading, error, load };
}
