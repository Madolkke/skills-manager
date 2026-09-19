<script setup lang="ts">
import { humanDate } from "../../lib/format";
import type { AdminOverview } from "../../lib/api/paginationApi";
defineProps<{ overview: AdminOverview | null }>();
</script>

<template>
  <div class="admin-tab-stack">
    <section class="admin-metric-grid">
      <div class="admin-metric-card">
        <span>Skill</span>
        <strong>{{ overview?.counts.skills ?? 0 }}</strong>
      </div>
      <div class="admin-metric-card">
        <span>用户组</span>
        <strong>{{ overview?.counts.groups ?? 0 }}</strong>
      </div>
      <div class="admin-metric-card">
        <span>Tag Group</span>
        <strong>{{ overview?.counts.tag_groups ?? 0 }}</strong>
      </div>
      <div class="admin-metric-card">
        <span>授权</span>
        <strong>{{ overview?.counts.roles ?? 0 }}</strong>
      </div>
    </section>

    <div class="admin-two-column">
      <section class="primary-panel admin-card">
        <h2>最近 Tag Group</h2>
        <div class="admin-list">
          <div v-for="group in overview?.recent_tag_groups ?? []" :key="group.id" class="admin-summary-row">
            <strong>{{ group.display_name }}</strong>
            <span>{{ group.id }} · {{ group.value_count }} 个 Tag · {{ humanDate(group.updated_at || group.created_at) }}</span>
          </div>
          <p v-if="!overview?.counts.tag_groups" class="field-help">还没有 Tag Group。</p>
        </div>
      </section>

      <section class="primary-panel admin-card">
        <h2>权限摘要</h2>
        <div class="admin-list">
          <div v-for="role in overview?.recent_roles ?? []" :key="role.id" class="admin-role-row">
            <span>{{ role.subject_type }}:{{ role.subject_id }}</span>
            <strong>{{ role.role }}</strong>
            <span>{{ role.resource_label }}</span>
          </div>
          <p v-if="!overview?.counts.roles" class="field-help">还没有授权记录。</p>
        </div>
      </section>
    </div>
  </div>
</template>
