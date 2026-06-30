<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { humanDate } from "../../lib/format";
import type { TagGroup, TagValueOption } from "../../types";
import AdminTagGroupFormModal from "./AdminTagGroupFormModal.vue";
import AdminTagValueFormModal from "./AdminTagValueFormModal.vue";

const props = defineProps<{ tagGroups: TagGroup[]; selectedTagGroupId: string }>();
const emit = defineEmits<{
  select: [groupId: string];
  createGroup: [payload: { id: string; display_name: string; description?: string; sort_order?: number; required?: boolean; initial_value?: string }];
  updateGroup: [groupId: string, payload: { display_name: string; description?: string; sort_order?: number; required?: boolean }];
  deleteGroup: [group: TagGroup];
  createValue: [groupId: string, payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }];
  updateValue: [groupId: string, value: string, payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }];
  deleteValue: [group: TagGroup, value: TagValueOption];
}>();

const groupModalMode = ref<"create" | "edit" | null>(null);
const valueModalMode = ref<"create" | "edit" | null>(null);
const editingValue = ref<TagValueOption | null>(null);
const groupSearch = ref("");

const selectedGroup = computed(() => props.tagGroups.find((group) => group.id === props.selectedTagGroupId) ?? props.tagGroups[0] ?? null);
const selectedGroupValues = computed(() => [...(selectedGroup.value?.values ?? [])].sort((a, b) => a.sort_order - b.sort_order || a.value.localeCompare(b.value)));
const filteredGroups = computed(() => {
  const keyword = groupSearch.value.trim().toLowerCase();
  if (!keyword) return props.tagGroups;
  return props.tagGroups.filter((group) =>
    [group.id, group.display_name, group.description]
      .some((value) => value.toLowerCase().includes(keyword)),
  );
});
const selectedGroupHiddenBySearch = computed(() => {
  if (!groupSearch.value.trim() || !selectedGroup.value) return false;
  return filteredGroups.value.every((group) => group.id !== selectedGroup.value?.id);
});

watch(selectedGroup, () => {
  valueModalMode.value = null;
  editingValue.value = null;
});

function createGroup(payload: { id?: string; display_name: string; description?: string; sort_order?: number; required?: boolean; initial_value?: string }): void {
  if (!payload.id) return;
  emit("createGroup", {
    id: payload.id,
    display_name: payload.display_name,
    description: payload.description,
    sort_order: payload.sort_order,
    required: payload.required,
    initial_value: payload.initial_value,
  });
}

function updateGroup(payload: { display_name: string; description?: string; sort_order?: number; required?: boolean }): void {
  if (!selectedGroup.value) return;
  emit("updateGroup", selectedGroup.value.id, payload);
}

function createValue(payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }): void {
  if (!selectedGroup.value) return;
  emit("createValue", selectedGroup.value.id, payload);
}

function updateValue(payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }): void {
  if (!selectedGroup.value || !editingValue.value) return;
  emit("updateValue", selectedGroup.value.id, editingValue.value.value, payload);
}

function openValueEdit(value: TagValueOption): void {
  editingValue.value = value;
  valueModalMode.value = "edit";
}
</script>

<template>
  <div class="admin-taggroup-layout">
    <section class="primary-panel admin-card">
      <div class="panel-title-row">
        <div>
          <h2>Tag Group</h2>
          <p>{{ tagGroups.length }} 组枚举 · {{ selectedGroup?.values.length ?? 0 }} 个当前 Tag</p>
        </div>
        <button class="primary-button" type="button" @click="groupModalMode = 'create'">新建 Tag Group</button>
      </div>

      <label class="field-label compact">
        <span>搜索 Tag Group</span>
        <input v-model="groupSearch" placeholder="输入 ID、显示名称或备注" />
      </label>
      <label class="field-label compact">
        <span>选择 Tag Group</span>
        <select :value="selectedGroup?.id ?? ''" :disabled="!filteredGroups.length" @change="emit('select', ($event.target as HTMLSelectElement).value)">
          <option v-for="group in filteredGroups" :key="group.id" :value="group.id">
            {{ group.display_name }}（{{ group.id }}）
          </option>
        </select>
      </label>

      <div v-if="selectedGroup" class="admin-selected-summary">
        <strong>{{ selectedGroup.display_name }}</strong>
        <div class="admin-chip-list">
          <span class="tag-chip muted">{{ selectedGroup.id }}</span>
          <span :class="['tag-chip', selectedGroup.required ? 'warning' : 'muted']">{{ selectedGroup.required ? "必选" : "可选" }}</span>
        </div>
        <p>{{ selectedGroup.description || "无备注" }}</p>
        <p v-if="selectedGroupHiddenBySearch" class="field-help">当前选中项被搜索条件隐藏；清空搜索可在下拉框中看到它。</p>
      </div>
      <template v-if="selectedGroup">
        <dl class="admin-detail-grid compact">
          <div>
            <dt>排序</dt>
            <dd>{{ selectedGroup.sort_order }}</dd>
          </div>
          <div>
            <dt>Tag 数量</dt>
            <dd>{{ selectedGroup.values.length }}</dd>
          </div>
          <div>
            <dt>保存要求</dt>
            <dd>{{ selectedGroup.required ? "至少选择一个 Tag" : "可不选择" }}</dd>
          </div>
          <div>
            <dt>创建时间</dt>
            <dd>{{ humanDate(selectedGroup.created_at) }}</dd>
          </div>
          <div>
            <dt>更新时间</dt>
            <dd>{{ humanDate(selectedGroup.updated_at) }}</dd>
          </div>
        </dl>
        <div class="button-row">
          <button class="secondary-button" type="button" @click="groupModalMode = 'edit'">编辑 Group</button>
          <button class="danger-button" type="button" @click="emit('deleteGroup', selectedGroup)">强制删除</button>
        </div>
      </template>
      <div v-else class="admin-selected-summary empty">
        <strong>暂无可选 Tag Group</strong>
        <p>创建后可在右侧维护该组下的 Tag 值。</p>
      </div>
      <p v-if="tagGroups.length && !filteredGroups.length" class="field-help">没有匹配的 Tag Group。</p>
    </section>

    <section class="primary-panel admin-card">
      <template v-if="selectedGroup">
        <div class="panel-title-row compact">
          <div>
            <h3>Tag 值</h3>
            <p>{{ selectedGroup.display_name }} 下的可选 Tag。</p>
          </div>
          <button class="secondary-button" type="button" @click="valueModalMode = 'create'">添加 Tag 值</button>
        </div>

        <div class="admin-value-table">
          <div class="admin-value-table-head">
            <span>Tag 值</span>
            <span>显示名称</span>
            <span>备注</span>
            <span>排序</span>
            <span>操作</span>
          </div>
          <div v-for="value in selectedGroupValues" :key="value.value" class="admin-value-table-row">
            <strong>{{ value.value }}</strong>
            <span>{{ value.display_name || "-" }}</span>
            <span>{{ value.description || "无备注" }}</span>
            <span>{{ value.sort_order }}</span>
            <div class="button-row">
              <button class="secondary-button" type="button" @click="openValueEdit(value)">编辑</button>
              <button class="danger-button" type="button" @click="emit('deleteValue', selectedGroup, value)">删除</button>
            </div>
          </div>
          <p v-if="!selectedGroup.values.length" class="field-help">这个 Tag Group 还没有 Tag 值。</p>
        </div>
      </template>
      <p v-else class="field-help">还没有 Tag Group。</p>
    </section>

    <AdminTagGroupFormModal
      v-if="groupModalMode"
      :group="groupModalMode === 'edit' ? selectedGroup : null"
      @close="groupModalMode = null"
      @submit="groupModalMode === 'edit' ? updateGroup($event) : createGroup($event)"
    />
    <AdminTagValueFormModal
      v-if="valueModalMode && selectedGroup"
      :group="selectedGroup"
      :value="valueModalMode === 'edit' ? editingValue : null"
      @close="valueModalMode = null; editingValue = null"
      @submit="valueModalMode === 'edit' ? updateValue($event) : createValue($event)"
    />
  </div>
</template>
