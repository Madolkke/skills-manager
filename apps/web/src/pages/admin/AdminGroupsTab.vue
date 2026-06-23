<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { AdminGroup } from "../../lib/api";

const props = defineProps<{ groups: AdminGroup[]; selectedGroupId: string }>();
const emit = defineEmits<{
  select: [groupId: string];
  create: [payload: { name: string; description?: string }];
  update: [groupId: string, payload: { name: string; description?: string }];
  delete: [group: AdminGroup];
  addMember: [groupId: string, subjectId: string];
  removeMember: [groupId: string, subjectId: string];
}>();

const createForm = ref({ name: "", description: "" });
const editForm = ref({ name: "", description: "" });
const memberId = ref("");
const selectedGroup = computed(() => props.groups.find((group) => group.id === props.selectedGroupId) ?? props.groups[0] ?? null);

watch(selectedGroup, (group) => {
  editForm.value = { name: group?.name ?? "", description: group?.description ?? "" };
}, { immediate: true });

function createGroup(): void {
  emit("create", { ...createForm.value });
  createForm.value = { name: "", description: "" };
}

function addMember(): void {
  if (!selectedGroup.value || !memberId.value.trim()) return;
  emit("addMember", selectedGroup.value.id, memberId.value);
  memberId.value = "";
}
</script>

<template>
  <div class="admin-split-layout">
    <section class="primary-panel admin-card">
      <h2>用户组</h2>
      <div class="admin-inline-form">
        <input v-model="createForm.name" placeholder="组名称" />
        <input v-model="createForm.description" placeholder="描述" />
        <button class="primary-button" type="button" :disabled="!createForm.name.trim()" @click="createGroup">新建组</button>
      </div>
      <div class="admin-list">
        <button v-for="group in groups" :key="group.id" type="button" :class="{ active: selectedGroup?.id === group.id }" @click="emit('select', group.id)">
          <strong>{{ group.name }}</strong>
          <small>{{ group.members.length }} 个成员</small>
        </button>
      </div>
    </section>

    <section class="primary-panel admin-card">
      <template v-if="selectedGroup">
        <div class="panel-title-row">
          <div>
            <h2>{{ selectedGroup.name }}</h2>
            <p>{{ selectedGroup.id }}</p>
          </div>
          <button class="danger-button" type="button" @click="emit('delete', selectedGroup)">强制删除</button>
        </div>
        <div class="admin-inline-form">
          <input v-model="editForm.name" placeholder="组名称" />
          <input v-model="editForm.description" placeholder="描述" />
          <button class="secondary-button" type="button" :disabled="!editForm.name.trim()" @click="emit('update', selectedGroup.id, editForm)">保存修改</button>
        </div>
        <h3>成员</h3>
        <div class="admin-inline-form">
          <input v-model="memberId" placeholder="用户身份 ID" />
          <button class="secondary-button" type="button" :disabled="!memberId.trim()" @click="addMember">添加成员</button>
        </div>
        <div class="admin-chip-list">
          <span v-for="member in selectedGroup.members" :key="member.subject_id" class="tag-chip editable">
            {{ member.subject_id }}
            <button type="button" @click="emit('removeMember', selectedGroup.id, member.subject_id)">×</button>
          </span>
          <p v-if="!selectedGroup.members.length" class="field-help">这个用户组还没有成员。</p>
        </div>
      </template>
      <p v-else class="field-help">还没有用户组。</p>
    </section>
  </div>
</template>
