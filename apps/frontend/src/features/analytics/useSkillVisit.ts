import { watch, type Ref } from "vue";
import type { RouteState } from "../../lib/navigation";
import { recordSkillVisit } from "./api";

/** 每次进入详情分配事件 ID，只有对应数据成功显示后才上报。 */
export function useSkillVisit(route: Ref<RouteState>, client = recordSkillVisit) {
  let entry: { skillId: string; eventId: string; sent: boolean } | null = null;
  watch(() => JSON.stringify([route.value.section, route.value.skillId]), () => {
    const { section, skillId } = route.value;
    entry = section === "skills" && skillId ? { skillId, eventId: crypto.randomUUID(), sent: false } : null;
  }, { immediate: true, flush: "sync" });

  /** 取得本次路由进入标识，用于拒绝往返同一 Skill 的旧响应。 */
  function token(): string | null { return entry?.eventId ?? null; }

  /** 上报失败重试一次，保持浏览流程成功且不生成新访问 ID。 */
  async function displayed(skillId: string, entryToken: string | null): Promise<void> {
    if (!entry || entry.eventId !== entryToken || entry.skillId !== skillId || entry.sent) return;
    const current = entry;
    current.sent = true;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try { await client(current.skillId, current.eventId); return; }
      catch { if (attempt === 1) console.warn("Skill 访问统计暂时不可用。"); }
    }
  }
  return { token, displayed };
}
