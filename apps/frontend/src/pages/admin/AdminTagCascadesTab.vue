<script setup lang="ts">
import { AlertTriangle, Link2, Unlink } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import { buildTagCascadeTreeRows, sortGroups, withCascadeParents, type TagDiagnosticFocus } from "../../lib/tagCascades";
import type { TagCascadeOverview, TagGroup } from "../../types";

const props = defineProps<{ tagGroups: TagGroup[]; overview: TagCascadeOverview | null }>();
const emit = defineEmits<{
  attach: [payload: { parent_group_id: string; parent_value: string; child_group_id: string }];
  detach: [childGroupId: string];
  inspect: [focus: TagDiagnosticFocus];
}>();

const selectedParent = ref<{ groupId: string; value: string } | null>(null);
const childGroupId = ref("");
const groups = computed(() => withCascadeParents(props.tagGroups, props.overview?.relations ?? []));
const rows = computed(() => buildTagCascadeTreeRows(groups.value));
const diagnostics = computed(() => new Map((props.overview?.diagnostics ?? []).map((item) => [item.group_id, item])));
const selectedParentGroup = computed(() => groups.value.find((group) => group.id === selectedParent.value?.groupId) ?? null);
const availableChildren = computed(() => {
  if (!selectedParent.value) return [];
  const excluded = ancestorIds(selectedParent.value.groupId);
  excluded.add(selectedParent.value.groupId);
  return sortGroups(groups.value.filter((group) => !group.parent && !excluded.has(group.id)));
});
const issueTotals = computed(() => {
  const items = props.overview?.diagnostics ?? [];
  return {
    orphaned: items.reduce((total, item) => total + item.orphaned_skill_ids.length, 0),
    missing: items.reduce((total, item) => total + item.missing_required_skill_ids.length, 0),
  };
});

watch(availableChildren, (children) => {
  if (!children.some((group) => group.id === childGroupId.value)) childGroupId.value = children[0]?.id ?? "";
}, { immediate: true });

function selectParent(group: TagGroup, value: string): void {
  if (group.free_form) return;
  selectedParent.value = { groupId: group.id, value };
}

function attach(): void {
  if (!selectedParent.value || !childGroupId.value) return;
  emit("attach", {
    parent_group_id: selectedParent.value.groupId,
    parent_value: selectedParent.value.value,
    child_group_id: childGroupId.value,
  });
  selectedParent.value = null;
}

function inspect(groupId: string, kind: TagDiagnosticFocus["kind"]): void {
  const diagnostic = diagnostics.value.get(groupId);
  const skillIds = kind === "orphaned" ? diagnostic?.orphaned_skill_ids : diagnostic?.missing_required_skill_ids;
  if (!skillIds?.length) return;
  emit("inspect", { groupId, kind, skillIds });
}

function ancestorIds(groupId: string): Set<string> {
  const result = new Set<string>();
  let group = groups.value.find((item) => item.id === groupId);
  while (group?.parent && !result.has(group.parent.group_id)) {
    result.add(group.parent.group_id);
    group = groups.value.find((item) => item.id === group?.parent?.group_id);
  }
  return result;
}
</script>

<template>
  <section class="primary-panel admin-card admin-tag-cascades">
    <div class="panel-title-row">
      <div>
        <h2>Tag 级联</h2>
        <p>在父 Tag 值下挂载子 Group。子 Group 只能有一个父级，改挂前需要先解绑。</p>
      </div>
      <div class="admin-chip-list">
        <span :class="['tag-chip', issueTotals.orphaned ? 'warning' : 'muted']">路径失效 {{ issueTotals.orphaned }}</span>
        <span :class="['tag-chip', issueTotals.missing ? 'warning' : 'muted']">缺少必填 {{ issueTotals.missing }}</span>
      </div>
    </div>

    <div v-if="selectedParent && selectedParentGroup" class="cascade-link-editor">
      <div>
        <strong>{{ selectedParentGroup.display_name }}: {{ selectedParent.value }}</strong>
        <p>选择一个当前没有父级的 Group 挂到这个值下。</p>
      </div>
      <select v-model="childGroupId" aria-label="选择子 Tag Group">
        <option v-for="group in availableChildren" :key="group.id" :value="group.id">
          {{ group.display_name }}（{{ group.id }}）
        </option>
      </select>
      <button class="primary-button" type="button" :disabled="!childGroupId" @click="attach">
        <Link2 :size="16" />
        挂载
      </button>
      <button class="secondary-button" type="button" @click="selectedParent = null">取消</button>
    </div>

    <div class="cascade-tree" role="tree" aria-label="Tag 级联树">
      <div
        v-for="row in rows"
        :key="row.key"
        :class="['cascade-tree-row', row.kind]"
        :style="{ paddingLeft: `${8 + row.depth * 22}px` }"
        role="treeitem"
      >
        <template v-if="row.kind === 'group'">
          <div class="cascade-node-main">
            <strong>{{ row.group.display_name }}</strong>
            <small>{{ row.group.id }}</small>
            <span class="tag-chip muted">{{ row.group.free_form ? "自由" : "枚举" }}</span>
            <span v-if="row.group.required" class="tag-chip warning">必填</span>
          </div>
          <div class="cascade-node-actions">
            <button
              v-if="diagnostics.get(row.group.id)?.orphaned_skill_ids.length"
              class="cascade-issue-button"
              type="button"
              @click="inspect(row.group.id, 'orphaned')"
            >
              <AlertTriangle :size="14" /> 路径失效 {{ diagnostics.get(row.group.id)?.orphaned_skill_ids.length }}
            </button>
            <button
              v-if="diagnostics.get(row.group.id)?.missing_required_skill_ids.length"
              class="cascade-issue-button"
              type="button"
              @click="inspect(row.group.id, 'missing_required')"
            >
              <AlertTriangle :size="14" /> 缺少必填 {{ diagnostics.get(row.group.id)?.missing_required_skill_ids.length }}
            </button>
            <button
              v-if="row.group.parent"
              class="icon-button"
              type="button"
              :disabled="row.group.required"
              :title="row.group.required ? '必填子组需先改为可选' : '解除父级关系'"
              :aria-label="`解除 ${row.group.display_name} 的父级关系`"
              @click="emit('detach', row.group.id)"
            >
              <Unlink :size="16" />
            </button>
          </div>
        </template>
        <template v-else>
          <div class="cascade-value-label" :title="row.value.value">
            <span class="tag-chip-label">{{ row.value.display_name || row.value.value }}</span>
            <small v-if="row.value.display_name">{{ row.value.value }}</small>
          </div>
          <button
            v-if="!row.group.free_form"
            class="icon-button"
            type="button"
            title="在此 Tag 值下挂载子 Group"
            :aria-label="`在 ${row.value.value} 下挂载子 Group`"
            @click="selectParent(row.group, row.value.value)"
          >
            <Link2 :size="16" />
          </button>
        </template>
      </div>
      <p v-if="!rows.length" class="field-help">还没有 Tag Group。请先在 Tag Group Tab 中创建。</p>
    </div>
  </section>
</template>
