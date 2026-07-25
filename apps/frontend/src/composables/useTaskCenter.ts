import { computed, ref, watch, type ComputedRef } from "vue";
import { api } from "../lib/api";
import { buildTaskCenterGroups, taskCenterBadgeCount, type TaskCenterGroup, type TaskCenterItem } from "../lib/taskCenter";
import type { SkillDetail } from "../types";

type TaskCenterInput = {
  actor: ComputedRef<string>;
  currentSkill: ComputedRef<SkillDetail | null>;
  evaluationsVisible: boolean;
  errorMessage: (error: unknown) => string;
  openReviews: () => void;
  openSkillTab: (skillId: string, tab: "evaluate" | "publish") => void;
};

export function useTaskCenter(input: TaskCenterInput) {
  const open = ref(false);
  const groups = ref<TaskCenterGroup[]>([]);
  const loading = ref(false);
  const error = ref("");
  const badgeCount = computed(() => taskCenterBadgeCount(groups.value));

  watch(
    () => [input.actor.value, input.currentSkill.value?.skill.id ?? ""] as const,
    () => void load(),
    { immediate: true },
  );

  /**
   * Opens the panel after refreshing its cross-page task summary.
   */
  async function show(): Promise<void> {
    open.value = true;
    await load();
  }

  /**
   * Aggregates task-center data without exposing evaluation tasks when disabled.
   */
  async function load(): Promise<void> {
    loading.value = true;
    error.value = "";
    try {
      const skill = input.currentSkill.value;
      const publishOverviewPromise = skill ? api.getSkillPublishOverview(skill.skill.id) : Promise.resolve(null);
      const [reviews, notifications, publishOverview] = await Promise.all([
        api.listMyReviews(),
        api.listMyNotifications(),
        publishOverviewPromise,
      ]);
      groups.value = buildTaskCenterGroups(
        { reviews, notifications, skill, publishOverview },
        { evaluationsVisible: input.evaluationsVisible },
      );
    } catch (loadError) {
      error.value = input.errorMessage(loadError);
    } finally {
      loading.value = false;
    }
  }

  /**
   * Closes the panel and dispatches the selected task to its owning page.
   */
  function openItem(item: TaskCenterItem): void {
    open.value = false;
    if (item.target === "reviews" || item.target === "notifications") {
      input.openReviews();
      return;
    }
    const skillId = input.currentSkill.value?.skill.id;
    if (skillId) input.openSkillTab(skillId, item.target);
  }

  return { open, groups, loading, error, badgeCount, show, load, openItem };
}
