<script setup lang="ts">
import type { AdminGroup } from "../../lib/api";

defineProps<{
  groups: AdminGroup[];
  busy: boolean;
  canManage: boolean;
}>();

const emit = defineEmits<{
  create: [];
  edit: [group: AdminGroup];
  delete: [group: AdminGroup];
  addMember: [group: AdminGroup];
  removeMember: [group: AdminGroup, subjectId: string];
}>();
</script>

<template>
  <section class="settings-section">
    <div class="settings-section-header">
      <div>
        <h3>用户组</h3>
        <p>这些用户组只属于当前 Skill，用于给一批身份统一授权。</p>
      </div>
      <button v-if="canManage" class="secondary-button" type="button" :disabled="busy" @click="emit('create')">创建用户组</button>
    </div>

    <div v-if="!canManage" class="settings-notice muted">只有 owner 或 admin 可以管理当前 Skill 的用户组。</div>

    <div class="settings-list">
      <article v-for="group in groups" :key="group.id" class="settings-list-row group-row">
        <div class="settings-row-main">
          <div class="settings-row-title">
            <strong>{{ group.name }}</strong>
            <span class="tag-chip muted">{{ group.members.length }} 个成员</span>
          </div>
          <p v-if="group.description">{{ group.description }}</p>
          <div class="access-member-list">
            <span v-for="member in group.members" :key="member.subject_id" class="tag-chip editable">
              {{ member.subject_id }}
              <button v-if="canManage" type="button" :disabled="busy" @click="emit('removeMember', group, member.subject_id)">×</button>
            </span>
            <span v-if="!group.members.length" class="tag-chip muted">暂无成员</span>
          </div>
        </div>
        <div v-if="canManage" class="settings-row-actions">
          <button class="secondary-button" type="button" :disabled="busy" @click="emit('addMember', group)">添加成员</button>
          <button class="secondary-button" type="button" :disabled="busy" @click="emit('edit', group)">编辑</button>
          <button class="danger-button" type="button" :disabled="busy" @click="emit('delete', group)">删除</button>
        </div>
      </article>
      <div v-if="!groups.length" class="settings-empty">还没有当前 Skill 的用户组。</div>
    </div>
  </section>
</template>
