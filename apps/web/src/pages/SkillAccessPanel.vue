<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api, ApiError, type AdminGroup } from "../lib/api";
import { toTagPayloads } from "../lib/skillTags";
import AdminGroupFormModal from "./admin/AdminGroupFormModal.vue";
import AdminGroupMemberModal from "./admin/AdminGroupMemberModal.vue";
import SkillGroupsSettingsSection from "./settings/SkillGroupsSettingsSection.vue";
import SkillRolesSettingsSection from "./settings/SkillRolesSettingsSection.vue";
import SkillTagsSettingsSection from "./settings/SkillTagsSettingsSection.vue";
import type { SkillDetail, SkillTagPayload, TagGroup, ToastState } from "../types";

const props = defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ refresh: []; toast: [toast: ToastState] }>();

const tags = ref<SkillTagPayload[]>(toTagPayloads(props.skill.skill.tags ?? []));
const tagGroups = ref<TagGroup[]>([]);
const skillGroups = ref<AdminGroup[]>([]);
const subjectType = ref<"user" | "group">("user");
const subjectId = ref("");
const role = ref("evaluator");
const busy = ref(false);
const groupModalMode = ref<"create" | "edit" | null>(null);
const editingGroup = ref<AdminGroup | null>(null);
const memberGroup = ref<AdminGroup | null>(null);
const activeSection = ref<"tags" | "groups" | "roles">("tags");

const permissions = computed(() => props.skill.capabilities?.permissions ?? {});
const canEditSkill = computed(() => Boolean(permissions.value["skill.edit"]));
const canManageRoles = computed(() => Boolean(permissions.value["role.manage"]));
const effectiveRoles = computed(() => props.skill.capabilities?.effective_roles ?? []);

const sections = computed(() => [
  { id: "tags" as const, label: "Skill Tags", meta: `${tags.value.length} 个 Tag` },
  { id: "groups" as const, label: "用户组", meta: `${skillGroups.value.length} 个用户组` },
  { id: "roles" as const, label: "角色授权", meta: `${props.skill.role_assignments.length} 条授权` },
]);

watch(() => props.skill.skill.id, () => {
  tags.value = toTagPayloads(props.skill.skill.tags ?? []);
  void loadSkillGroups();
});

onMounted(async () => {
  await Promise.all([loadTagGroups(), loadSkillGroups()]);
});

async function loadTagGroups(): Promise<void> {
  try {
    tagGroups.value = await api.listTagGroups();
  } catch (error) {
    showError(error);
  }
}

async function loadSkillGroups(): Promise<void> {
  try {
    skillGroups.value = await api.listSkillGroups(props.skill.skill.id);
    if (subjectType.value === "group" && subjectId.value && !skillGroups.value.some((group) => group.id === subjectId.value)) subjectId.value = "";
  } catch (error) {
    showError(error);
  }
}

async function saveTags(nextTags: SkillTagPayload[] = tags.value): Promise<void> {
  busy.value = true;
  try {
    tags.value = nextTags;
    await api.updateSkill(props.skill.skill.id, { slug: props.skill.skill.slug, owner_ref: props.skill.skill.owner_ref, tags: nextTags });
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

async function saveGroup(payload: { name: string; description?: string }): Promise<void> {
  busy.value = true;
  try {
    if (editingGroup.value) {
      await api.updateSkillGroup(props.skill.skill.id, editingGroup.value.id, payload);
      emit("toast", { tone: "success", message: "用户组已更新。" });
    } else {
      await api.createSkillGroup(props.skill.skill.id, payload);
      emit("toast", { tone: "success", message: "用户组已创建。" });
    }
    await loadSkillGroups();
    emit("refresh");
  } catch (error) {
    showError(error);
  } finally {
    busy.value = false;
    groupModalMode.value = null;
    editingGroup.value = null;
  }
}

async function deleteGroup(group: AdminGroup): Promise<void> {
  if (!confirm(`将删除用户组“${group.name}”，并移除其成员和相关授权。是否继续？`)) return;
  busy.value = true;
  try {
    await api.deleteSkillGroup(props.skill.skill.id, group.id);
    if (subjectId.value === group.id) subjectId.value = "";
    emit("toast", { tone: "success", message: "用户组已删除。" });
    await loadSkillGroups();
    emit("refresh");
  } catch (error) {
    showError(error);
  } finally {
    busy.value = false;
  }
}

async function addMember(subjectId: string): Promise<void> {
  if (!memberGroup.value) return;
  busy.value = true;
  try {
    await api.addSkillGroupMember(props.skill.skill.id, memberGroup.value.id, { subject_id: subjectId });
    emit("toast", { tone: "success", message: "成员已添加。" });
    await loadSkillGroups();
    emit("refresh");
  } catch (error) {
    showError(error);
  } finally {
    busy.value = false;
    memberGroup.value = null;
  }
}

async function removeMember(group: AdminGroup, subjectId: string): Promise<void> {
  busy.value = true;
  try {
    await api.removeSkillGroupMember(props.skill.skill.id, group.id, subjectId);
    emit("toast", { tone: "success", message: "成员已移除。" });
    await loadSkillGroups();
    emit("refresh");
  } catch (error) {
    showError(error);
  } finally {
    busy.value = false;
  }
}

function openCreateGroup(): void {
  editingGroup.value = null;
  groupModalMode.value = "create";
}

function openEditGroup(group: AdminGroup): void {
  editingGroup.value = group;
  groupModalMode.value = "edit";
}

function setSubjectType(next: "user" | "group"): void {
  subjectType.value = next;
  subjectId.value = "";
}

function showError(error: unknown): void {
  const message = error instanceof ApiError || error instanceof Error ? error.message : "操作失败。";
  emit("toast", { tone: "danger", message });
}
</script>

<template>
  <section class="primary-panel access-panel">
    <div class="settings-layout">
      <aside class="settings-nav" aria-label="设置模块">
        <div class="settings-nav-summary">
          <span>当前角色</span>
          <div class="settings-role-chips">
            <span v-for="item in effectiveRoles" :key="item" class="tag-chip">{{ item }}</span>
            <span v-if="!effectiveRoles.length" class="tag-chip muted">无操作角色</span>
          </div>
          <p>Skill 默认公开可见；这里仅管理编辑、测评运行和授权权限。</p>
        </div>

        <div class="settings-nav-list">
          <button
            v-for="section in sections"
            :key="section.id"
            class="settings-nav-item"
            :class="{ active: activeSection === section.id }"
            type="button"
            @click="activeSection = section.id"
          >
            <span>{{ section.label }}</span>
            <small>{{ section.meta }}</small>
          </button>
        </div>
      </aside>

      <div class="settings-content">
        <SkillTagsSettingsSection
          v-if="activeSection === 'tags'"
          :tags="tags"
          :tag-groups="tagGroups"
          :disabled="!canEditSkill || busy"
          @change="tags = $event"
          @done="saveTags"
        />
        <SkillGroupsSettingsSection
          v-else-if="activeSection === 'groups'"
          :groups="skillGroups"
          :busy="busy"
          :can-manage="canManageRoles"
          @create="openCreateGroup"
          @edit="openEditGroup"
          @delete="deleteGroup"
          @add-member="memberGroup = $event"
          @remove-member="removeMember"
        />
        <SkillRolesSettingsSection
          v-else
          :assignments="skill.role_assignments"
          :groups="skillGroups"
          :busy="busy"
          :can-manage="canManageRoles"
          :subject-type="subjectType"
          :subject-id="subjectId"
          :role="role"
          @update:subject-type="setSubjectType"
          @update:subject-id="subjectId = $event"
          @update:role="role = $event"
          @assign="assignRole"
        />
      </div>
    </div>
    <AdminGroupFormModal
      v-if="groupModalMode"
      :group="groupModalMode === 'edit' ? editingGroup : null"
      @close="groupModalMode = null; editingGroup = null"
      @submit="saveGroup"
    />
    <AdminGroupMemberModal
      v-if="memberGroup"
      :group="memberGroup"
      @close="memberGroup = null"
      @submit="addMember"
    />
  </section>
</template>
