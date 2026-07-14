import { onMounted, ref, watch } from "vue";
import { api, ApiError } from "../../lib/api";
import { toTagPayloads } from "../../lib/skillTags";
import type { SkillDetail, SkillTagPayload, TagGroup, ToastState } from "../../types";

type WorkflowSkillTagOptions = {
  skill: () => SkillDetail;
  refresh: () => void;
  toast: (toast: ToastState) => void;
};

export function useWorkflowSkillTags(options: WorkflowSkillTagOptions) {
  const tags = ref<SkillTagPayload[]>(toTagPayloads(options.skill().skill.tags ?? []));
  const groups = ref<TagGroup[]>([]);
  const busy = ref(false);
  const error = ref("");

  watch(
    () => options.skill().skill.tags,
    (value) => {
      if (!busy.value) tags.value = toTagPayloads(value ?? []);
    },
    { deep: true },
  );

  onMounted(() => void loadGroups());

  async function loadGroups(): Promise<void> {
    try {
      groups.value = await api.listTagGroups();
    } catch (caught) {
      error.value = message(caught, "Tag Group 加载失败，Workflow 仍可继续编辑。");
    }
  }

  function update(nextTags: SkillTagPayload[]): void {
    tags.value = nextTags;
    error.value = "";
  }

  async function save(nextTags: SkillTagPayload[]): Promise<void> {
    if (busy.value) return;
    busy.value = true;
    error.value = "";
    tags.value = nextTags;
    const skill = options.skill().skill;
    try {
      const updated = await api.updateSkill(skill.id, { slug: skill.slug, owner_ref: skill.owner_ref, tags: nextTags });
      tags.value = toTagPayloads(updated.tags ?? []);
      options.toast({ tone: "success", message: "Skill Tags 已保存。" });
      options.refresh();
    } catch (caught) {
      error.value = message(caught, "Skill Tags 保存失败，请重试。");
    } finally {
      busy.value = false;
    }
  }

  return { tags, groups, busy, error, update, save };
}

function message(error: unknown, fallback: string): string {
  return error instanceof ApiError || error instanceof Error ? error.message : fallback;
}
