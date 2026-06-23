<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import SkillTagPicker from "../components/SkillTagPicker.vue";
import { api, ApiError, type AdminGroup } from "../lib/api";
import { toTagPayloads } from "../lib/skillTags";
import AdminGroupFormModal from "./admin/AdminGroupFormModal.vue";
import AdminGroupMemberModal from "./admin/AdminGroupMemberModal.vue";
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

const permissions = computed(() => props.skill.capabilities?.permissions ?? {});
const canEditSkill = computed(() => Boolean(permissions.value["skill.edit"]));
const canManageRoles = computed(() => Boolean(permissions.value["role.manage"]));

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
        <SkillTagPicker :value="tags" :groups="tagGroups" :disabled="!canEditSkill || busy" @change="tags = $event" @done="saveTags" />
      </div>

      <div class="access-card">
        <div class="access-card-title">
          <h3>Skill 角色</h3>
          <span class="role-help" tabindex="0" aria-label="查看角色含义">?</span>
          <div class="role-help-popover" role="tooltip">
            <strong>角色含义</strong>
            <span>viewer：显式只读成员，当前等同公开查看。</span>
            <span>evaluator：可以运行测评和重试。</span>
            <span>maintainer：可以编辑 Skill、版本、测评集、测试例和普通 Tag。</span>
            <span>owner：可以管理普通角色授权。</span>
            <span>admin：拥有所有权限，并可管理受保护 Tag。</span>
          </div>
        </div>
        <section v-if="canManageRoles" class="access-group-manager">
          <div class="access-subhead">
            <div>
              <h4>用户组</h4>
              <p>这些用户组只属于当前 Skill。</p>
            </div>
            <button class="secondary-button" type="button" :disabled="busy" @click="openCreateGroup">创建用户组</button>
          </div>
          <div class="access-group-list">
            <div v-for="group in skillGroups" :key="group.id" class="access-group-row">
              <div>
                <strong>{{ group.name }}</strong>
                <small>{{ group.members.length }} 个成员</small>
                <p v-if="group.description">{{ group.description }}</p>
              </div>
              <div class="access-member-list">
                <span v-for="member in group.members" :key="member.subject_id" class="tag-chip editable">
                  {{ member.subject_id }}
                  <button type="button" :disabled="busy" @click="removeMember(group, member.subject_id)">×</button>
                </span>
                <span v-if="!group.members.length" class="tag-chip muted">暂无成员</span>
              </div>
              <div class="button-row">
                <button class="secondary-button" type="button" :disabled="busy" @click="memberGroup = group">添加成员</button>
                <button class="secondary-button" type="button" :disabled="busy" @click="openEditGroup(group)">编辑</button>
                <button class="danger-button" type="button" :disabled="busy" @click="deleteGroup(group)">删除</button>
              </div>
            </div>
            <p v-if="!skillGroups.length" class="field-help">还没有当前 Skill 的用户组。</p>
          </div>
        </section>
        <div v-if="canManageRoles" class="access-role-form">
          <select v-model="subjectType">
            <option value="user">用户</option>
            <option value="group">用户组</option>
          </select>
          <input v-if="subjectType === 'user'" v-model="subjectId" placeholder="身份 ID" />
          <select v-else v-model="subjectId">
            <option value="">选择用户组</option>
            <option v-for="group in skillGroups" :key="group.id" :value="group.id">{{ group.name }}</option>
          </select>
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
