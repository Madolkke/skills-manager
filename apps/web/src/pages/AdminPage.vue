<script setup lang="ts">
import { ref } from "vue";
import { ADMIN_TABS, type AdminTab } from "../lib/admin";
import { api, ApiError, type AdminGroup } from "../lib/api";
import { toTagPayloads } from "../lib/skillTags";
import type { RoleAssignment, SkillSummary, SkillTagPayload, TagGroup, TagValueOption } from "../types";
import AdminGroupsTab from "./admin/AdminGroupsTab.vue";
import AdminOverviewTab from "./admin/AdminOverviewTab.vue";
import AdminRoleAssignmentsTab from "./admin/AdminRoleAssignmentsTab.vue";
import AdminSkillTagsTab from "./admin/AdminSkillTagsTab.vue";
import AdminTagGroupsTab from "./admin/AdminTagGroupsTab.vue";

const emit = defineEmits<{ toast: [toast: { tone: "success" | "danger" | "info"; message: string } | null] }>();

const key = ref(sessionStorage.getItem("skillhub.admin.key") || "");
const unlocked = ref(Boolean(key.value));
const loading = ref(false);
const activeTab = ref<AdminTab>("overview");
const skills = ref<SkillSummary[]>([]);
const groups = ref<AdminGroup[]>([]);
const tagGroups = ref<TagGroup[]>([]);
const roles = ref<RoleAssignment[]>([]);
const selectedGroupId = ref("");
const selectedTagGroupId = ref("");
const tagDrafts = ref<Record<string, SkillTagPayload[]>>({});

async function unlock(): Promise<void> {
  sessionStorage.setItem("skillhub.admin.key", key.value.trim());
  unlocked.value = true;
  await load();
}

async function load(): Promise<void> {
  loading.value = true;
  try {
    const [nextSkills, nextGroups, nextTagGroups, nextRoles] = await Promise.all([api.adminListSkills(), api.adminListGroups(), api.adminListTagGroups(), api.adminListRoleAssignments()]);
    skills.value = nextSkills;
    groups.value = nextGroups;
    tagGroups.value = nextTagGroups;
    roles.value = nextRoles;
    tagDrafts.value = Object.fromEntries(nextSkills.map((item) => [item.skill.id, toTagPayloads(item.skill.tags ?? [])]));
    if (!selectedGroupId.value && nextGroups.length) selectedGroupId.value = nextGroups[0].id;
    if (!selectedTagGroupId.value && nextTagGroups.length) selectedTagGroupId.value = nextTagGroups[0].id;
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function createGroup(payload: { name: string; description?: string }): Promise<void> {
  await runAdminAction(async () => {
    const group = await api.adminCreateGroup(payload);
    selectedGroupId.value = group.id;
  }, "用户组已创建。");
}

async function updateGroup(groupId: string, payload: { name: string; description?: string }): Promise<void> {
  await runAdminAction(() => api.adminUpdateGroup(groupId, payload), "用户组已更新。");
}

async function deleteGroup(group: AdminGroup): Promise<void> {
  if (!confirm(`将强制删除用户组“${group.name}”，并移除其成员和相关授权。是否继续？`)) return;
  await runAdminAction(async () => {
    await api.adminDeleteGroup(group.id);
    selectedGroupId.value = "";
  }, "用户组已删除。");
}

async function addGroupMember(groupId: string, subjectId: string): Promise<void> {
  await runAdminAction(() => api.adminAddGroupMember(groupId, { subject_id: subjectId }), "成员已添加。");
}

async function removeGroupMember(groupId: string, subjectId: string): Promise<void> {
  await runAdminAction(() => api.adminRemoveGroupMember(groupId, subjectId), "成员已移除。");
}

async function createTagGroup(payload: { id: string; display_name: string; description?: string; sort_order?: number }): Promise<void> {
  await runAdminAction(async () => {
    const group = await api.adminCreateTagGroup(payload);
    selectedTagGroupId.value = group.id;
  }, "Tag Group 已创建。");
}

async function updateTagGroup(groupId: string, payload: { display_name: string; description?: string; sort_order?: number }): Promise<void> {
  await runAdminAction(() => api.adminUpdateTagGroup(groupId, payload), "Tag Group 已更新。");
}

async function deleteTagGroup(group: TagGroup): Promise<void> {
  if (!confirm(`将强制删除 Tag Group“${group.display_name}”，并移除其 Tag 值、Skill Tag 绑定和相关授权。是否继续？`)) return;
  await runAdminAction(async () => {
    await api.adminDeleteTagGroup(group.id);
    selectedTagGroupId.value = "";
  }, "Tag Group 已删除。");
}

async function createTagValue(groupId: string, payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }): Promise<void> {
  await runAdminAction(() => api.adminCreateTagValue(groupId, payload), "Tag 值已创建。");
}

async function updateTagValue(groupId: string, value: string, payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }): Promise<void> {
  await runAdminAction(() => api.adminUpdateTagValue(groupId, value, payload), "Tag 值已更新。");
}

async function deleteTagValue(group: TagGroup, value: TagValueOption): Promise<void> {
  if (!confirm(`将强制删除 Tag 值“${value.display_name || value.value}”，并移除相关 Skill Tag 绑定和授权。是否继续？`)) return;
  await runAdminAction(() => api.adminDeleteTagValue(group.id, value.value), "Tag 值已删除。");
}

async function assignRole(payload: { subject_type: "user" | "group"; subject_id: string; resource_type: "skill" | "skill_tag"; resource_id: string; role: string }): Promise<void> {
  await runAdminAction(() => api.adminAssignRole(payload), "角色已授权。");
}

async function revokeRole(role: RoleAssignment): Promise<void> {
  if (!confirm(`将撤销 ${role.subject_type}:${role.subject_id} 的 ${role.role} 授权。是否继续？`)) return;
  await runAdminAction(() => api.adminDeleteRoleAssignment(role.id), "授权已撤销。");
}

async function saveSkillTags(skill: SkillSummary): Promise<void> {
  await runAdminAction(() => api.adminUpdateSkill(skill.skill.id, { tags: tagDrafts.value[skill.skill.id] ?? [] }), "Skill Tag 已更新。");
}

async function runAdminAction(action: () => Promise<unknown>, successMessage: string): Promise<void> {
  try {
    await action();
    await load();
    emit("toast", { tone: "success", message: successMessage });
  } catch (error) {
    showError(error);
  }
}

function showError(error: unknown): void {
  const message = error instanceof ApiError || error instanceof Error ? error.message : "操作失败。";
  emit("toast", { tone: "danger", message });
}
</script>

<template>
  <div class="admin-page">
    <section v-if="!unlocked" class="primary-panel admin-login">
      <h1>后台管理</h1>
      <p>输入后台密钥后访问管理能力。这个入口不属于普通权限体系。</p>
      <label class="field-label">
        <span>后台密钥</span>
        <input v-model="key" type="password" @keydown.enter="unlock" />
      </label>
      <button class="primary-button" type="button" @click="unlock">进入后台</button>
    </section>

    <template v-else>
      <div class="skill-nav-row admin-nav-row">
        <nav class="skill-tabs" aria-label="后台管理分类">
          <button
            v-for="tab in ADMIN_TABS"
            :key="tab.id"
            type="button"
            :class="['skill-tab', { active: activeTab === tab.id }]"
            @click="activeTab = tab.id"
          >
            {{ tab.label }}
          </button>
        </nav>
        <button class="secondary-button" type="button" :disabled="loading" @click="load">{{ loading ? "刷新中..." : "刷新" }}</button>
      </div>

      <AdminOverviewTab v-if="activeTab === 'overview'" :skills="skills" :groups="groups" :tag-groups="tagGroups" :roles="roles" />
      <AdminGroupsTab
        v-else-if="activeTab === 'groups'"
        :groups="groups"
        :selected-group-id="selectedGroupId"
        @select="selectedGroupId = $event"
        @create="createGroup"
        @update="updateGroup"
        @delete="deleteGroup"
        @add-member="addGroupMember"
        @remove-member="removeGroupMember"
      />
      <AdminTagGroupsTab
        v-else-if="activeTab === 'tag-groups'"
        :tag-groups="tagGroups"
        :selected-tag-group-id="selectedTagGroupId"
        @select="selectedTagGroupId = $event"
        @create-group="createTagGroup"
        @update-group="updateTagGroup"
        @delete-group="deleteTagGroup"
        @create-value="createTagValue"
        @update-value="updateTagValue"
        @delete-value="deleteTagValue"
      />
      <AdminRoleAssignmentsTab
        v-else-if="activeTab === 'roles'"
        :roles="roles"
        :tag-groups="tagGroups"
        :skills="skills"
        @assign="assignRole"
        @revoke="revokeRole"
        @toast="emit('toast', { tone: 'danger', message: $event })"
      />
      <AdminSkillTagsTab
        v-else
        :skills="skills"
        :tag-groups="tagGroups"
        :tag-drafts="tagDrafts"
        @update-draft="(skillId, tags) => { tagDrafts[skillId] = tags; }"
        @save="saveSkillTags"
      />
    </template>
  </div>
</template>
