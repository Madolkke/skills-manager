<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { encodeSkillTagResourceId } from "../../lib/skillTags";
import { filterRoleAssignments, roleResourceLabel } from "../../lib/admin";
import type { RoleAssignment, SkillRole, SkillSummary, TagGroup } from "../../types";

const props = defineProps<{ roles: RoleAssignment[]; tagGroups: TagGroup[]; skills: SkillSummary[] }>();
const emit = defineEmits<{
  assign: [payload: { subject_type: "user" | "group"; subject_id: string; resource_type: "skill" | "skill_tag"; resource_id: string; role: string }];
  revoke: [role: RoleAssignment];
  toast: [message: string];
}>();

const form = ref({ subject_type: "group" as "user" | "group", subject_id: "", resource_type: "skill" as "skill" | "skill_tag", resource_id: "", tag_group_id: "", tag_value: "", role: "evaluator" as SkillRole });
const filters = ref({ subject: "", resource: "", resourceType: "", role: "" });
const filteredRoles = computed(() => filterRoleAssignments(props.roles, filters.value, props.tagGroups, props.skills));

watch(() => form.value.tag_group_id, () => {
  form.value.tag_value = "";
});

function assignRole(): void {
  if (form.value.resource_type === "skill_tag" && (!form.value.tag_group_id || !form.value.tag_value)) {
    emit("toast", "请先选择 Tag Group 和 Tag 值。");
    return;
  }
  const resourceId = form.value.resource_type === "skill_tag" ? encodeSkillTagResourceId(form.value.tag_group_id, form.value.tag_value) : form.value.resource_id;
  emit("assign", {
    subject_type: form.value.subject_type,
    subject_id: form.value.subject_id,
    resource_type: form.value.resource_type,
    resource_id: resourceId,
    role: form.value.role,
  });
}
</script>

<template>
  <div class="admin-tab-stack">
    <section class="primary-panel admin-card">
      <h2>新增授权</h2>
      <div class="admin-role-form">
        <select v-model="form.subject_type">
          <option value="user">用户</option>
          <option value="group">用户组</option>
        </select>
        <input v-model="form.subject_id" placeholder="主体 ID" />
        <select v-model="form.resource_type">
          <option value="skill">Skill</option>
          <option value="skill_tag">Skill Tag</option>
        </select>
        <template v-if="form.resource_type === 'skill_tag'">
          <select v-model="form.tag_group_id">
            <option disabled value="">选择 Tag Group</option>
            <option v-for="group in tagGroups" :key="group.id" :value="group.id">{{ group.display_name }} ({{ group.id }})</option>
          </select>
          <select v-model="form.tag_value">
            <option disabled value="">选择 Tag 值</option>
            <option v-for="value in tagGroups.find((group) => group.id === form.tag_group_id)?.values ?? []" :key="value.value" :value="value.value">
              {{ value.display_name || value.value }}
            </option>
          </select>
        </template>
        <select v-else v-model="form.resource_id">
          <option disabled value="">选择 Skill</option>
          <option v-for="item in skills" :key="item.skill.id" :value="item.skill.id">{{ item.skill.slug }}</option>
        </select>
        <select v-model="form.role">
          <option value="viewer">viewer</option>
          <option value="evaluator">evaluator</option>
          <option value="maintainer">maintainer</option>
          <option value="owner">owner</option>
          <option value="admin">admin</option>
        </select>
        <button class="primary-button" type="button" :disabled="!form.subject_id.trim()" @click="assignRole">授权</button>
      </div>
    </section>

    <section class="primary-panel admin-card">
      <div class="panel-title-row">
        <h2>权限列表</h2>
        <span class="tag-chip muted">{{ filteredRoles.length }} / {{ roles.length }}</span>
      </div>
      <div class="admin-role-form">
        <input v-model="filters.subject" placeholder="筛选主体" />
        <input v-model="filters.resource" placeholder="筛选资源" />
        <select v-model="filters.resourceType">
          <option value="">全部资源类型</option>
          <option value="skill">Skill</option>
          <option value="skill_tag">Skill Tag</option>
        </select>
        <select v-model="filters.role">
          <option value="">全部角色</option>
          <option value="viewer">viewer</option>
          <option value="evaluator">evaluator</option>
          <option value="maintainer">maintainer</option>
          <option value="owner">owner</option>
          <option value="admin">admin</option>
        </select>
      </div>
      <div class="admin-role-table">
        <div class="admin-role-table-head">
          <span>主体</span>
          <span>角色</span>
          <span>资源</span>
          <span></span>
        </div>
        <div v-for="role in filteredRoles" :key="role.id" class="admin-role-table-row">
          <span>{{ role.subject_type }}:{{ role.subject_id }}</span>
          <strong>{{ role.role }}</strong>
          <span>{{ roleResourceLabel(role, tagGroups, skills) }}</span>
          <button class="icon-button mini" type="button" @click="emit('revoke', role)">×</button>
        </div>
        <p v-if="!filteredRoles.length" class="field-help">没有匹配的授权记录。</p>
      </div>
    </section>
  </div>
</template>
