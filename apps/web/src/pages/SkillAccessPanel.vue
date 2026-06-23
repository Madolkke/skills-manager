<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import SkillTagPicker from "../components/SkillTagPicker.vue";
import { api, ApiError } from "../lib/api";
import { tagLabel, toTagPayloads } from "../lib/skillTags";
import type { SkillDetail, SkillTagPayload, TagGroup, ToastState } from "../types";

const props = defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ refresh: []; toast: [toast: ToastState] }>();

const tags = ref<SkillTagPayload[]>(toTagPayloads(props.skill.skill.tags ?? []));
const tagGroups = ref<TagGroup[]>([]);
const subjectType = ref<"user" | "group">("user");
const subjectId = ref("");
const role = ref("evaluator");
const busy = ref(false);

const permissions = computed(() => props.skill.capabilities?.permissions ?? {});
const canEditSkill = computed(() => Boolean(permissions.value["skill.edit"]));
const canManageRoles = computed(() => Boolean(permissions.value["role.manage"]));

watch(() => props.skill.skill.id, () => {
  tags.value = toTagPayloads(props.skill.skill.tags ?? []);
});

onMounted(loadTagGroups);

async function loadTagGroups(): Promise<void> {
  try {
    tagGroups.value = await api.listTagGroups();
  } catch (error) {
    showError(error);
  }
}

async function saveTags(): Promise<void> {
  busy.value = true;
  try {
    await api.updateSkill(props.skill.skill.id, { slug: props.skill.skill.slug, owner_ref: props.skill.skill.owner_ref, tags: tags.value });
    emit("toast", { tone: "success", message: "Skill Tag 已保存。" });
    emit("refresh");
  } catch (error) {
    showError(error);
  } finally {
    busy.value = false;
  }
}

async function assignRole(): Promise<void> {
  busy.value = true;
  try {
    await api.assignSkillRole(props.skill.skill.id, { subject_type: subjectType.value, subject_id: subjectId.value, role: role.value });
    subjectId.value = "";
    emit("toast", { tone: "success", message: "角色已授权。" });
    emit("refresh");
  } catch (error) {
    showError(error);
  } finally {
    busy.value = false;
  }
}

function showError(error: unknown): void {
  const message = error instanceof ApiError || error instanceof Error ? error.message : "操作失败。";
  emit("toast", { tone: "danger", message });
}
</script>

<template>
  <section class="primary-panel access-panel">
    <div class="panel-title-row">
      <div>
        <h2>权限与 Tag</h2>
        <p>Skill 默认公开可见，权限只控制编辑、测评运行和授权等操作。</p>
      </div>
      <div class="tag-row">
        <span v-for="item in skill.capabilities?.effective_roles ?? []" :key="item" class="tag-chip">{{ item }}</span>
        <span v-if="!(skill.capabilities?.effective_roles ?? []).length" class="tag-chip muted">无操作角色</span>
      </div>
    </div>

    <div class="access-grid">
      <div class="access-card">
        <h3>Skill Tags</h3>
        <SkillTagPicker :value="tags" :groups="tagGroups" :disabled="!canEditSkill || busy" @change="tags = $event" />
        <p class="field-help">Tag 值由后台 Tag Group 维护。若 Tag 被授权策略引用，修改需要 admin 角色。</p>
        <div v-if="skill.skill.tags?.length" class="tag-row">
          <span v-for="tag in skill.skill.tags" :key="`${tag.group_id}:${tag.value}`" class="tag-chip">{{ tagLabel(tag, tagGroups) }}</span>
        </div>
        <button class="secondary-button" type="button" :disabled="!canEditSkill || busy" @click="saveTags">保存 Tag</button>
      </div>

      <div class="access-card">
        <h3>Skill 角色</h3>
        <div v-if="canManageRoles" class="access-role-form">
          <select v-model="subjectType">
            <option value="user">用户</option>
            <option value="group">用户组</option>
          </select>
          <input v-model="subjectId" placeholder="身份 ID 或用户组 ID" />
          <select v-model="role">
            <option value="viewer">viewer</option>
            <option value="evaluator">evaluator</option>
            <option value="maintainer">maintainer</option>
            <option value="owner">owner</option>
            <option value="admin">admin</option>
          </select>
          <button class="primary-button" type="button" :disabled="busy || !subjectId.trim()" @click="assignRole">授权</button>
        </div>
        <p v-else class="field-help">只有 owner 或 admin 可以管理 Skill 角色。</p>
        <div class="access-role-list">
          <div v-for="assignment in skill.role_assignments" :key="assignment.id" class="access-role-row">
            <span>{{ assignment.subject_type }}:{{ assignment.subject_id }}</span>
            <strong>{{ assignment.role }}</strong>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
