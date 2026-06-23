<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { humanDate } from "../../lib/format";
import type { AdminGroup } from "../../lib/api";
import AdminGroupFormModal from "./AdminGroupFormModal.vue";
import AdminGroupMemberModal from "./AdminGroupMemberModal.vue";

const props = defineProps<{ groups: AdminGroup[]; selectedGroupId: string }>();
const emit = defineEmits<{
  select: [groupId: string];
  create: [payload: { name: string; description?: string }];
  update: [groupId: string, payload: { name: string; description?: string }];
  delete: [group: AdminGroup];
  addMember: [groupId: string, subjectId: string];
  removeMember: [groupId: string, subjectId: string];
}>();

const groupSearch = ref("");
const groupModalMode = ref<"create" | "edit" | null>(null);
const memberModalOpen = ref(false);

const selectedGroup = computed(() => props.groups.find((group) => group.id === props.selectedGroupId) ?? props.groups[0] ?? null);
const filteredGroups = computed(() => {
  const keyword = groupSearch.value.trim().toLowerCase();
  if (!keyword) return props.groups;
  return props.groups.filter((group) =>
    [group.id, group.name, group.description]
      .some((value) => value.toLowerCase().includes(keyword)),
  );
});
const selectedMembers = computed(() => [...(selectedGroup.value?.members ?? [])].sort((a, b) => a.subject_id.localeCompare(b.subject_id)));

watch(selectedGroup, () => {
  memberModalOpen.value = false;
});

function createGroup(payload: { name: string; description?: string }): void {
  emit("create", payload);
}

function updateGroup(payload: { name: string; description?: string }): void {
  if (!selectedGroup.value) return;
  emit("update", selectedGroup.value.id, payload);
}

function addMember(subjectId: string): void {
  if (!selectedGroup.value) return;
  emit("addMember", selectedGroup.value.id, subjectId);
}
</script>

<template>
  <div class="admin-directory-layout">
    <section class="primary-panel admin-card">
      <div class="panel-title-row">
        <div>
          <h2>用户组</h2>
          <p>{{ groups.length }} 个组 · {{ selectedGroup?.members.length ?? 0 }} 个当前成员</p>
        </div>
        <button class="primary-button" type="button" @click="groupModalMode = 'create'">新建用户组</button>
      </div>

      <label class="field-label compact">
        <span>搜索用户组</span>
        <input v-model="groupSearch" placeholder="输入 ID、名称或描述" />
      </label>
      <label class="field-label compact">
        <span>选择用户组</span>
        <select :value="selectedGroup?.id ?? ''" :disabled="!filteredGroups.length" @change="emit('select', ($event.target as HTMLSelectElement).value)">
          <option v-for="group in filteredGroups" :key="group.id" :value="group.id">
            {{ group.name }}（{{ group.members.length }} 个成员）
          </option>
        </select>
      </label>

      <div v-if="selectedGroup" class="admin-selected-summary">
        <strong>{{ selectedGroup.name }}</strong>
        <span>{{ selectedGroup.id }}</span>
        <p>{{ selectedGroup.description || "无描述" }}</p>
      </div>
      <template v-if="selectedGroup">
        <dl class="admin-detail-grid compact">
          <div>
            <dt>成员数量</dt>
            <dd>{{ selectedGroup.members.length }}</dd>
          </div>
          <div>
            <dt>创建时间</dt>
            <dd>{{ humanDate(selectedGroup.created_at) }}</dd>
          </div>
          <div>
            <dt>更新时间</dt>
            <dd>{{ humanDate(selectedGroup.updated_at) }}</dd>
          </div>
          <div>
            <dt>创建者</dt>
            <dd>{{ selectedGroup.created_by || "-" }}</dd>
          </div>
        </dl>
        <div class="button-row">
          <button class="secondary-button" type="button" @click="groupModalMode = 'edit'">编辑用户组</button>
          <button class="danger-button" type="button" @click="emit('delete', selectedGroup)">强制删除</button>
        </div>
      </template>
      <div v-else class="admin-selected-summary empty">
        <strong>暂无可选用户组</strong>
        <p>创建后可在右侧维护成员。</p>
      </div>
      <p v-if="groups.length && !filteredGroups.length" class="field-help">没有匹配的用户组。</p>
    </section>

    <section class="primary-panel admin-card">
      <template v-if="selectedGroup">
        <div class="panel-title-row compact">
          <div>
            <h3>成员</h3>
            <p>{{ selectedGroup.name }} 下的用户身份 ID。</p>
          </div>
          <button class="secondary-button" type="button" @click="memberModalOpen = true">添加成员</button>
        </div>

        <div class="admin-member-table">
          <div class="admin-member-table-head">
            <span>身份 ID</span>
            <span>主体类型</span>
            <span>操作</span>
          </div>
          <div v-for="member in selectedMembers" :key="member.subject_id" class="admin-member-table-row">
            <strong>{{ member.subject_id }}</strong>
            <span>{{ member.subject_type }}</span>
            <div class="button-row">
              <button class="danger-button" type="button" @click="emit('removeMember', selectedGroup.id, member.subject_id)">移除</button>
            </div>
          </div>
          <p v-if="!selectedGroup.members.length" class="field-help">这个用户组还没有成员。</p>
        </div>
      </template>
      <p v-else class="field-help">还没有用户组。</p>
    </section>

    <AdminGroupFormModal
      v-if="groupModalMode"
      :group="groupModalMode === 'edit' ? selectedGroup : null"
      @close="groupModalMode = null"
      @submit="groupModalMode === 'edit' ? updateGroup($event) : createGroup($event)"
    />
    <AdminGroupMemberModal
      v-if="memberModalOpen && selectedGroup"
      :group="selectedGroup"
      @close="memberModalOpen = false"
      @submit="addMember"
    />
  </div>
</template>
