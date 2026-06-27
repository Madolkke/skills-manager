<script setup lang="ts">
import { computed } from "vue";
import DropdownSelect from "../../components/DropdownSelect.vue";
import type { DropdownSelectOption } from "../../components/dropdown";
import type { AdminGroup } from "../../lib/api";
import type { RoleAssignment, SkillRole } from "../../types";

const props = defineProps<{
  assignments: RoleAssignment[];
  groups: AdminGroup[];
  busy: boolean;
  canManage: boolean;
  subjectType: "user" | "group";
  subjectId: string;
  role: string;
}>();

const emit = defineEmits<{
  "update:subjectType": [value: "user" | "group"];
  "update:subjectId": [value: string];
  "update:role": [value: string];
  assign: [];
}>();

const subjectTypeOptions: DropdownSelectOption[] = [
  { value: "user", label: "用户", description: "按身份 ID 授权" },
  { value: "group", label: "用户组", description: "授权当前 Skill 用户组" },
];

const roleOptions: DropdownSelectOption[] = [
  { value: "viewer", label: "viewer", description: "显式只读成员" },
  { value: "evaluator", label: "evaluator", description: "运行测评和重试" },
  { value: "reviewer", label: "reviewer", description: "接收评审并提交意见" },
  { value: "maintainer", label: "maintainer", description: "编辑 Skill 和测评内容" },
  { value: "owner", label: "owner", description: "管理普通角色授权" },
  { value: "admin", label: "admin", description: "所有权限和受保护 Tag" },
];

const groupOptions = computed<DropdownSelectOption[]>(() =>
  props.groups.map((group) => ({
    value: group.id,
    label: group.name,
    description: group.description || `${group.members.length} 个成员`,
  })),
);

const groupNameById = computed(() => new Map(props.groups.map((group) => [group.id, group.name])));

/** 展示主体名称，避免把 user/group 前缀直接暴露给用户。 */
function subjectDisplayName(assignment: RoleAssignment): string {
  if (assignment.subject_type === "group") return groupNameById.value.get(assignment.subject_id) ?? assignment.subject_id;
  return assignment.subject_id;
}

/** 用户组名称可变，因此列表同时保留 ID 辅助辨识。 */
function subjectMeta(assignment: RoleAssignment): string {
  if (assignment.subject_type === "group" && groupNameById.value.has(assignment.subject_id)) return `ID ${assignment.subject_id}`;
  return assignment.subject_type === "group" ? "当前 Skill 用户组" : "身份 ID";
}

function subjectKindLabel(subjectType: RoleAssignment["subject_type"]): string {
  return subjectType === "group" ? "用户组" : "用户";
}

function roleLabel(role: SkillRole): string {
  return role;
}
</script>

<template>
  <section class="settings-section">
    <div class="settings-section-header">
      <div class="settings-title-help">
        <div>
          <h3>角色授权</h3>
          <p>为用户或当前 Skill 的用户组授予操作权限。</p>
        </div>
        <span class="role-help" tabindex="0" aria-label="查看角色含义">i</span>
        <div class="role-help-popover" role="tooltip">
          <strong>角色含义</strong>
          <span>viewer：显式只读成员，当前等同公开查看。</span>
          <span>evaluator：可以运行测评和重试。</span>
          <span>reviewer：可以接收评审、提交评分和意见。</span>
          <span>maintainer：可以编辑 Skill、版本、测评集、测试例和普通 Tag。</span>
          <span>owner：可以管理普通角色授权。</span>
          <span>admin：拥有所有权限，并可管理受保护 Tag。</span>
        </div>
      </div>
    </div>

    <div v-if="canManage" class="access-role-form">
      <label class="access-role-field">
        <span>授权对象</span>
        <DropdownSelect
          :model-value="subjectType"
          :options="subjectTypeOptions"
          aria-label="选择授权对象类型"
          compact
          @update:model-value="emit('update:subjectType', $event as 'user' | 'group')"
        />
      </label>
      <label class="access-role-field">
        <span>{{ subjectType === "group" ? "用户组" : "身份 ID" }}</span>
        <input v-if="subjectType === 'user'" :value="subjectId" placeholder="例如 product-operator" @input="emit('update:subjectId', ($event.target as HTMLInputElement).value)" />
        <DropdownSelect
          v-else
          :model-value="subjectId"
          :options="groupOptions"
          :disabled="busy || groupOptions.length === 0"
          placeholder="选择用户组"
          aria-label="选择用户组"
          compact
          @update:model-value="emit('update:subjectId', $event)"
        />
      </label>
      <label class="access-role-field">
        <span>角色</span>
        <DropdownSelect
          :model-value="role"
          :options="roleOptions"
          aria-label="选择角色"
          compact
          @update:model-value="emit('update:role', $event)"
        />
      </label>
      <button class="primary-button" type="button" :disabled="busy || !subjectId.trim()" @click="emit('assign')">授权</button>
    </div>
    <div v-else class="settings-notice muted">只有 owner 或 admin 可以管理 Skill 角色。</div>

    <div class="settings-list compact">
      <article v-for="assignment in assignments" :key="assignment.id" class="settings-list-row role-row">
        <div class="role-subject">
          <span class="role-subject-main">
            <span class="role-subject-name">{{ subjectDisplayName(assignment) }}</span>
            <span class="role-subject-meta">{{ subjectMeta(assignment) }}</span>
          </span>
          <span class="role-subject-badge" :class="assignment.subject_type">{{ subjectKindLabel(assignment.subject_type) }}</span>
        </div>
        <strong class="role-chip">{{ roleLabel(assignment.role) }}</strong>
      </article>
      <div v-if="!assignments.length" class="settings-empty">还没有显式角色授权。</div>
    </div>
  </section>
</template>
