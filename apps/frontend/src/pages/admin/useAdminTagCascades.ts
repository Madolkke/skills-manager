import { ref, type Ref } from "vue";
import type { AdminTab } from "../../lib/admin";
import { api, ApiError } from "../../lib/api";
import type { TagDiagnosticFocus } from "../../lib/tagCascades";
import type { TagCascadeOverview } from "../../types";

type Toast = { tone: "success" | "danger" | "info"; message: string };

export function useAdminTagCascades(options: {
  activeTab: Ref<AdminTab>;
  emitToast: (toast: Toast) => void;
}) {
  const overview = ref<TagCascadeOverview | null>(null);
  const focus = ref<TagDiagnosticFocus | null>(null);

  async function attach(payload: { parent_group_id: string; parent_value: string; child_group_id: string }): Promise<void> {
    try {
      overview.value = await api.adminCreateTagCascade(payload);
      options.emitToast({ tone: "success", message: "Tag 级联已建立。" });
    } catch (error) {
      showError(error);
    }
  }

  async function detach(childGroupId: string): Promise<void> {
    if (!confirm("将解除该子 Tag Group 的父级关系。历史 Skill 可能因此出现新的必填缺失，是否继续？")) return;
    try {
      overview.value = await api.adminDeleteTagCascade(childGroupId);
      options.emitToast({ tone: "success", message: "Tag 级联已解除。" });
    } catch (error) {
      showError(error);
    }
  }

  function inspect(nextFocus: TagDiagnosticFocus): void {
    focus.value = nextFocus;
    options.activeTab.value = "skill-tags";
  }

  function showError(error: unknown): void {
    const message = error instanceof ApiError || error instanceof Error ? error.message : "操作失败。";
    options.emitToast({ tone: "danger", message });
  }

  return { overview, focus, attach, detach, inspect };
}
