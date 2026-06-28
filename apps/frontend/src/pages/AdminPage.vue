<script setup lang="ts">
import { ref } from "vue";
import { ADMIN_TABS, type AdminTab } from "../lib/admin";
import { api, ApiError, type AdminGroup } from "../lib/api";
import { toTagPayloads } from "../lib/skillTags";
import type { PublishGateCheckDefinition, PublishGateExpression, PublishRecord, PublishTarget, RoleAssignment, SkillSummary, SkillTagPayload, TagGroup, TagValueOption } from "../types";
import AdminGroupsTab from "./admin/AdminGroupsTab.vue";
import AdminOverviewTab from "./admin/AdminOverviewTab.vue";
import AdminPublishTab from "./admin/AdminPublishTab.vue";
import AdminPublishTargetsTab from "./admin/AdminPublishTargetsTab.vue";
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
const publishTargets = ref<PublishTarget[]>([]);
const publishGateChecks = ref<PublishGateCheckDefinition[]>([]);
const publishRecords = ref<PublishRecord[]>([]);
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
    const [nextSkills, nextGroups, nextTagGroups, nextRoles, nextPublishTargets, nextPublishGateChecks, nextPublishRecords] = await Promise.all([
      api.adminListSkills(),
      api.adminListGroups(),
      api.adminListTagGroups(),
      api.adminListRoleAssignments(),
      api.adminListPublishTargets(),
      api.adminListPublishGateChecks(),
      api.adminListPublishRecords(),
    ]);
    skills.value = nextSkills;
    groups.value = nextGroups;
    tagGroups.value = nextTagGroups;
    roles.value = nextRoles;
    publishTargets.value = nextPublishTargets;
    publishGateChecks.value = nextPublishGateChecks;
    publishRecords.value = nextPublishRecords;
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

async function updatePublishTarget(targetId: string, payload: { enabled: boolean; gate_expression: PublishGateExpression }): Promise<void> {
  await runAdminAction(() => api.adminUpdatePublishTarget(targetId, payload), "发布源已更新。");
}

async function confirmPublishRecord(record: PublishRecord): Promise<void> {
  if (!confirm(`确认发布 ${record.skill?.slug ?? record.skill_id} 到 ${record.publish_target?.name ?? record.publish_target_id}？`)) return;
  await runAdminAction(() => api.adminConfirmPublishRecord(record.id), "发布单已确认。");
}

async function cancelPublishRecord(record: PublishRecord): Promise<void> {
  if (!confirm("将取消该待确认发布单。是否继续？")) return;
  await runAdminAction(() => api.adminCancelPublishRecord(record.id), "发布单已取消。");
}

async function batchConfirmPublishRecords(records: PublishRecord[]): Promise<void> {
  if (!records.length) return;
  if (!confirm(`将批量确认 ${records.length} 条待确认发布单。是否继续？`)) return;
  await runBatchPublishAction(records, (record) => api.adminConfirmPublishRecord(record.id), "确认");
}

async function batchCancelPublishRecords(records: PublishRecord[]): Promise<void> {
  if (!records.length) return;
  if (!confirm(`将批量取消 ${records.length} 条待确认发布单。是否继续？`)) return;
  await runBatchPublishAction(records, (record) => api.adminCancelPublishRecord(record.id), "取消");
}

async function saveSkillTags(skill: SkillSummary, tags?: SkillTagPayload[]): Promise<void> {
  const nextTags = tags ?? tagDrafts.value[skill.skill.id] ?? [];
  tagDrafts.value[skill.skill.id] = nextTags;
  await runAdminAction(() => api.adminUpdateSkill(skill.skill.id, { tags: nextTags }), "Skill Tag 已更新。");
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

async function runBatchPublishAction(records: PublishRecord[], action: (record: PublishRecord) => Promise<unknown>, verb: string): Promise<void> {
  let succeeded = 0;
  let failed = 0;
  for (const record of records) {
    try {
      await action(record);
      succeeded += 1;
    } catch {
      failed += 1;
    }
  }
  await load();
  emit("toast", {
    tone: failed ? "danger" : "success",
    message: `批量${verb}完成：成功 ${succeeded} 条，失败 ${failed} 条。`,
  });
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
        v-else-if="activeTab === 'skill-tags'"
        :skills="skills"
        :tag-groups="tagGroups"
        :tag-drafts="tagDrafts"
        @update-draft="(skillId, tags) => { tagDrafts[skillId] = tags; }"
        @save="saveSkillTags"
      />
      <AdminPublishTargetsTab
        v-else-if="activeTab === 'publish-targets'"
        :targets="publishTargets"
        :checks="publishGateChecks"
        @update="updatePublishTarget"
      />
      <AdminPublishTab
        v-else
        :records="publishRecords"
        @confirm-record="confirmPublishRecord"
        @cancel-record="cancelPublishRecord"
        @batch-confirm="batchConfirmPublishRecords"
        @batch-cancel="batchCancelPublishRecords"
      />
    </template>
  </div>
</template>
