<script setup lang="ts">
import { humanDate } from "../../lib/format";
import { recentTagGroups, roleResourceLabel } from "../../lib/admin";
import type { AdminGroup } from "../../lib/api";
import type { RoleAssignment, SkillSummary, TagGroup } from "../../types";

const props = defineProps<{
  skills: SkillSummary[];
  groups: AdminGroup[];
  tagGroups: TagGroup[];
  roles: RoleAssignment[];
}>();
</script>

<template>
  <div class="admin-tab-stack">
    <section class="admin-metric-grid">
      <div class="admin-metric-card">
        <span>Skill</span>
        <strong>{{ skills.length }}</strong>
      </div>
      <div class="admin-metric-card">
        <span>用户组</span>
        <strong>{{ groups.length }}</strong>
      </div>
      <div class="admin-metric-card">
        <span>Tag Group</span>
        <strong>{{ tagGroups.length }}</strong>
      </div>
      <div class="admin-metric-card">
        <span>授权</span>
        <strong>{{ roles.length }}</strong>
      </div>
    </section>

    <div class="admin-two-column">
      <section class="primary-panel admin-card">
        <h2>最近 Tag Group</h2>
        <div class="admin-list">
          <div v-for="group in recentTagGroups(tagGroups)" :key="group.id" class="admin-summary-row">
            <strong>{{ group.display_name }}</strong>
            <span>{{ group.id }} · {{ group.values.length }} 个 Tag · {{ humanDate(group.updated_at || group.created_at) }}</span>
          </div>
          <p v-if="!tagGroups.length" class="field-help">还没有 Tag Group。</p>
        </div>
      </section>

      <section class="primary-panel admin-card">
        <h2>权限摘要</h2>
        <div class="admin-list">
          <div v-for="role in roles.slice(0, 8)" :key="role.id" class="admin-role-row">
            <span>{{ role.subject_type }}:{{ role.subject_id }}</span>
            <strong>{{ role.role }}</strong>
            <span>{{ roleResourceLabel(role, tagGroups, skills) }}</span>
          </div>
          <p v-if="!roles.length" class="field-help">还没有授权记录。</p>
        </div>
      </section>
    </div>
  </div>
</template>
