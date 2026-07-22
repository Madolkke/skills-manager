<script setup lang="ts">
import { AlertTriangle, ChevronDown, ChevronRight, GitBranch, Link2, Tags, Unlink } from "lucide-vue-next";
import { toRef } from "vue";
import type { TagDiagnosticFocus } from "../../lib/tagCascades";
import type { TagCascadeOverview, TagGroup } from "../../types";
import { useTagCascadeTree } from "./useTagCascadeTree";

const props = defineProps<{ tagGroups: TagGroup[]; overview: TagCascadeOverview | null }>();
const emit = defineEmits<{
  attach: [payload: { parent_group_id: string; parent_value: string; child_group_id: string }];
  detach: [childGroupId: string];
  inspect: [focus: TagDiagnosticFocus];
}>();

const {
  allExpanded, availableChildren, childCount, childGroupId, collapseAll, diagnostics, expandAll, expandedGroups,
  issueTotals, parentLabel, parentTitle, rows, selectParent, selectedParent, selectedParentGroup,
  selectedParentValueLabel, summary, toggleGroup, visibleRows,
} = useTagCascadeTree(toRef(props, "tagGroups"), toRef(props, "overview"));

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

    <div class="admin-metric-grid cascade-metric-grid" aria-label="Tag 级联概览">
      <div class="admin-metric-card">
        <span>Group 总数</span>
        <strong>{{ summary.groups }}</strong>
      </div>
      <div class="admin-metric-card">
        <span>根级 Group</span>
        <strong>{{ summary.roots }}</strong>
      </div>
      <div class="admin-metric-card">
        <span>级联关系</span>
        <strong>{{ summary.relations }}</strong>
      </div>
      <div :class="['admin-metric-card', 'cascade-issue-metric', { warning: issueTotals.orphaned + issueTotals.missing }]">
        <span>异常项</span>
        <strong>{{ issueTotals.orphaned + issueTotals.missing }}</strong>
      </div>
    </div>

    <div v-if="selectedParent && selectedParentGroup" class="cascade-link-editor">
      <div class="cascade-link-context">
        <span>挂载到父 Tag 值</span>
        <strong>{{ selectedParentGroup.display_name }} / {{ selectedParentValueLabel }}</strong>
        <small>{{ selectedParentGroup.id }} / {{ selectedParent.value }}</small>
      </div>
      <div class="cascade-link-selection">
        <select v-if="availableChildren.length" v-model="childGroupId" aria-label="选择子 Tag Group">
          <option v-for="group in availableChildren" :key="group.id" :value="group.id">
            {{ group.display_name }}（{{ group.id }}）
          </option>
        </select>
        <p v-else>没有可挂载的根级 Group。请先解绑已有关系或创建新的 Group。</p>
      </div>
      <button class="primary-button" type="button" :disabled="!childGroupId" @click="attach">
        <Link2 :size="16" />
        挂载
      </button>
      <button class="secondary-button" type="button" @click="selectedParent = null">取消</button>
    </div>

    <div class="cascade-tree-toolbar">
      <div>
        <strong>级联结构</strong>
        <span>点击枚举值右侧的“挂载子组”建立关系。</span>
      </div>
      <button class="secondary-button compact" type="button" @click="allExpanded ? collapseAll() : expandAll()">
        {{ allExpanded ? "全部折叠" : "全部展开" }}
      </button>
    </div>

    <div class="cascade-tree" role="tree" aria-label="Tag 级联树">
      <div
        v-for="row in visibleRows"
        :key="row.key"
        :class="[
          'cascade-tree-row',
          row.kind,
          { selected: row.kind === 'value' && selectedParent?.groupId === row.group.id && selectedParent.value === row.value.value },
        ]"
        :style="{ paddingLeft: `${8 + row.depth * 22}px` }"
        role="treeitem"
        :aria-level="row.depth + 1"
        :data-group-id="row.group.id"
        :data-value="row.kind === 'value' ? row.value.value : undefined"
      >
        <template v-if="row.kind === 'group'">
          <div class="cascade-node-main">
            <button
              v-if="row.group.values.length"
              class="cascade-expand-button"
              type="button"
              :aria-expanded="expandedGroups.has(row.group.id)"
              :aria-label="`${expandedGroups.has(row.group.id) ? '折叠' : '展开'} ${row.group.display_name}`"
              @click="toggleGroup(row.group.id)"
            >
              <ChevronDown v-if="expandedGroups.has(row.group.id)" :size="17" />
              <ChevronRight v-else :size="17" />
            </button>
            <span v-else class="cascade-expand-placeholder"><Tags :size="15" /></span>
            <div class="cascade-node-copy">
              <div class="cascade-node-title">
                <strong>{{ row.group.display_name }}</strong>
                <small>{{ row.group.id }}</small>
              </div>
              <div class="cascade-node-meta">
                <span class="cascade-parent-label" :title="parentTitle(row.group)">
                  <GitBranch :size="13" /> {{ parentLabel(row.group) }}
                </span>
                <span class="tag-chip muted">{{ row.group.free_form ? "自由输入" : `枚举 · ${row.group.values.length} 项` }}</span>
                <span v-if="row.group.required" class="tag-chip warning">必填</span>
              </div>
            </div>
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
            <span class="cascade-tree-branch" aria-hidden="true"></span>
            <div>
              <span class="tag-chip-label">{{ row.value.display_name || row.value.value }}</span>
              <small v-if="row.value.display_name">{{ row.value.value }}</small>
            </div>
          </div>
          <div class="cascade-value-actions">
            <span v-if="childCount(row.group.id, row.value.value)" class="tag-chip muted">
              {{ childCount(row.group.id, row.value.value) }} 个子 Group
            </span>
            <button
              v-if="!row.group.free_form"
              class="secondary-button compact cascade-attach-button"
              type="button"
              :aria-label="`在 ${row.value.value} 下挂载子 Group`"
              @click="selectParent(row.group, row.value.value)"
            >
              <Link2 :size="15" />
              挂载子组
            </button>
          </div>
        </template>
      </div>
      <div v-if="!rows.length" class="cascade-empty-state">
        <Tags :size="22" />
        <strong>还没有 Tag Group</strong>
        <p>请先在 Tag Group Tab 中创建 Group，再回来配置级联关系。</p>
      </div>
    </div>
  </section>
</template>
