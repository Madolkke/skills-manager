<script setup lang="ts">
import { AlertTriangle, ChevronDown, ChevronRight, GitBranch, Link2, Search, Tags, Unlink } from "lucide-vue-next";
import { computed, ref, toRef, watch } from "vue";
import {
  childGroupsForValue,
  tagGroupPathInfo,
  tagValuePathInfo,
  type TagDiagnosticFocus,
  type TagCascadeTreeRow,
} from "../../lib/tagCascades";
import type { TagCascadeOverview, TagGroup } from "../../types";
import { useTagCascadeTree } from "./useTagCascadeTree";

const props = defineProps<{ tagGroups: TagGroup[]; overview: TagCascadeOverview | null }>();
const emit = defineEmits<{
  attach: [payload: { parent_group_id: string; parent_value: string; child_group_id: string }];
  detach: [childGroupId: string];
  inspect: [focus: TagDiagnosticFocus];
}>();
const search = ref("");
const childSearch = ref("");
const selectedKind = ref<"group" | "value">("group");
const selectedGroupId = ref("");
const {
  allExpanded, availableChildren, childGroupId, collapseAll, diagnostics, expandAll, expandedGroups,
  groups: cascadeGroups, issueTotals, rows, selectParent, selectedParent, selectedParentGroup, summary, toggleGroup, visibleRows,
} = useTagCascadeTree(toRef(props, "tagGroups"), toRef(props, "overview"));
const selectedGroup = computed(() => cascadeGroups.value.find((group) => group.id === selectedGroupId.value) ?? null);
const selectedValue = computed(() => selectedParent.value
  ? selectedParentGroup.value?.values.find((value) => value.value === selectedParent.value?.value) ?? null
  : null);
const selectedValueChildren = computed(() => selectedParent.value
  ? childGroupsForValue(cascadeGroups.value, selectedParent.value.groupId, selectedParent.value.value)
  : []);
const selectedGroupPath = computed(() => selectedGroup.value
  ? tagGroupPathInfo(cascadeGroups.value, selectedGroup.value.id)
  : null);
const selectedValuePath = computed(() => selectedParent.value
  ? tagValuePathInfo(cascadeGroups.value, selectedParent.value.groupId, selectedParent.value.value)
  : null);
const filteredChildren = computed(() => {
  const keyword = childSearch.value.trim().toLowerCase();
  if (!keyword) return availableChildren.value;
  return availableChildren.value.filter((group) => `${group.display_name} ${group.id} ${group.description}`.toLowerCase().includes(keyword));
});
const displayRows = computed(() => search.value.trim() ? searchedRows(rows.value, search.value) : visibleRows.value);

watch(() => props.tagGroups, (groups) => {
  if (!groups.some((group) => group.id === selectedGroupId.value)) selectedGroupId.value = groups[0]?.id ?? "";
}, { immediate: true });

function selectGroup(group: TagGroup): void {
  selectedKind.value = "group";
  selectedGroupId.value = group.id;
  selectedParent.value = null;
  childSearch.value = "";
}

function selectValue(group: TagGroup, value: string): void {
  selectedKind.value = "value";
  selectedGroupId.value = group.id;
  selectParent(group, value);
  childSearch.value = "";
}

function attach(): void {
  if (!selectedParent.value || !childGroupId.value) return;
  emit("attach", {
    parent_group_id: selectedParent.value.groupId,
    parent_value: selectedParent.value.value,
    child_group_id: childGroupId.value,
  });
}

function inspect(groupId: string, kind: TagDiagnosticFocus["kind"]): void {
  const diagnostic = diagnostics.value.get(groupId);
  const skillIds = kind === "orphaned" ? diagnostic?.orphaned_skill_ids : diagnostic?.missing_required_skill_ids;
  if (skillIds?.length) emit("inspect", { groupId, kind, skillIds });
}

function searchedRows(allRows: TagCascadeTreeRow[], rawQuery: string): TagCascadeTreeRow[] {
  const keyword = rawQuery.trim().toLowerCase();
  const includedGroups = new Set<string>();
  for (const group of cascadeGroups.value) {
    const path = tagGroupPathInfo(cascadeGroups.value, group.id).segments.map((segment) => segment.label).join(" / ");
    const values = group.values.map((value) => `${value.value} ${value.display_name ?? ""} ${value.description}`).join(" ");
    if (`${path} ${group.id} ${group.description} ${values}`.toLowerCase().includes(keyword)) addGroupAndAncestors(group.id, includedGroups);
  }
  return allRows.filter((row) => includedGroups.has(row.group.id));
}

function addGroupAndAncestors(groupId: string, result: Set<string>): void {
  let group = cascadeGroups.value.find((item) => item.id === groupId);
  while (group && !result.has(group.id)) {
    result.add(group.id);
    group = group.parent ? cascadeGroups.value.find((item) => item.id === group?.parent?.group_id) : undefined;
  }
}
</script>

<template>
  <section class="primary-panel admin-card admin-tag-cascades">
    <div class="panel-title-row">
      <div>
        <h2>Tag 级联</h2>
        <p>选择 Group 或 Tag 值，在右侧检查路径、诊断并维护挂载关系。</p>
      </div>
      <div class="admin-chip-list">
        <span :class="['tag-chip', issueTotals.orphaned ? 'warning' : 'muted']">路径失效 {{ issueTotals.orphaned }}</span>
        <span :class="['tag-chip', issueTotals.missing ? 'warning' : 'muted']">缺少必填 {{ issueTotals.missing }}</span>
      </div>
    </div>

    <div class="admin-metric-grid cascade-metric-grid" aria-label="Tag 级联概览">
      <div class="admin-metric-card"><span>Group 总数</span><strong>{{ summary.groups }}</strong></div>
      <div class="admin-metric-card"><span>根级 Group</span><strong>{{ summary.roots }}</strong></div>
      <div class="admin-metric-card"><span>级联关系</span><strong>{{ summary.relations }}</strong></div>
      <div :class="['admin-metric-card', 'cascade-issue-metric', { warning: issueTotals.orphaned + issueTotals.missing }]">
        <span>异常项</span><strong>{{ issueTotals.orphaned + issueTotals.missing }}</strong>
      </div>
    </div>

    <div class="cascade-workspace">
      <div class="cascade-navigator">
        <div class="cascade-tree-toolbar">
          <label class="search-field cascade-search">
            <Search :size="16" />
            <input v-model="search" placeholder="搜索 Group、Tag 或路径" aria-label="搜索 Tag 级联" />
          </label>
          <button class="secondary-button compact" type="button" :disabled="Boolean(search.trim())" @click="allExpanded ? collapseAll() : expandAll()">
            {{ allExpanded ? "全部折叠" : "全部展开" }}
          </button>
        </div>

        <div class="cascade-tree" role="tree" aria-label="Tag 级联树">
          <button
            v-for="row in displayRows"
            :key="row.key"
            :class="['cascade-tree-row', row.kind, {
              selected: row.kind === selectedKind && (row.kind === 'group'
                ? selectedGroupId === row.group.id
                : selectedParent?.groupId === row.group.id && selectedParent.value === row.value.value),
            }]"
            :style="{ paddingLeft: `${8 + row.depth * 18}px` }"
            type="button"
            role="treeitem"
            :aria-level="row.depth + 1"
            :data-group-id="row.group.id"
            :data-value="row.kind === 'value' ? row.value.value : undefined"
            @click="row.kind === 'group' ? selectGroup(row.group) : selectValue(row.group, row.value.value)"
          >
            <template v-if="row.kind === 'group'">
              <span
                v-if="row.group.values.length && !search.trim()"
                class="cascade-expand-button"
                role="button"
                :aria-label="`${expandedGroups.has(row.group.id) ? '折叠' : '展开'} ${row.group.display_name}`"
                @click.stop="toggleGroup(row.group.id)"
              >
                <ChevronDown v-if="expandedGroups.has(row.group.id)" :size="16" />
                <ChevronRight v-else :size="16" />
              </span>
              <span v-else class="cascade-expand-placeholder"><Tags :size="14" /></span>
              <span class="cascade-row-copy"><strong>{{ row.group.display_name }}</strong><small>{{ row.group.id }}</small></span>
              <span v-if="row.group.required" class="tag-chip warning">必填</span>
            </template>
            <template v-else>
              <span class="cascade-tree-branch" aria-hidden="true"></span>
              <span class="cascade-row-copy"><strong>{{ row.value.display_name || row.value.value }}</strong><small v-if="row.value.display_name">{{ row.value.value }}</small></span>
              <span v-if="childGroupsForValue(cascadeGroups, row.group.id, row.value.value).length" class="tag-chip muted">
                {{ childGroupsForValue(cascadeGroups, row.group.id, row.value.value).length }} 个子组
              </span>
            </template>
          </button>
          <div v-if="!displayRows.length" class="cascade-empty-state"><Tags :size="22" /><strong>没有匹配的级联节点</strong></div>
        </div>
      </div>

      <aside class="cascade-inspector" aria-label="级联节点检查器">
        <template v-if="selectedKind === 'group' && selectedGroup">
          <div class="cascade-inspector-title">
            <span>Tag Group</span>
            <h3>{{ selectedGroup.display_name }}</h3>
            <p>{{ selectedGroupPath?.segments.map((segment) => segment.label).join(" / ") }}</p>
            <small>{{ selectedGroup.id }}</small>
          </div>
          <div class="admin-chip-list">
            <span :class="['tag-chip', selectedGroup.required ? 'warning' : 'muted']">{{ selectedGroup.required ? "必填" : "可选" }}</span>
            <span class="tag-chip muted">{{ selectedGroup.free_form ? "自由输入" : `枚举 · ${selectedGroup.values.length} 项` }}</span>
            <span v-if="selectedGroupPath && !selectedGroupPath.valid" class="tag-chip warning">路径失效</span>
          </div>
          <p class="cascade-inspector-description">{{ selectedGroup.description || "无备注" }}</p>
          <div v-if="selectedGroup.parent" class="cascade-inspector-relation">
            <span><GitBranch :size="14" /> 当前父路径</span>
            <strong>{{ selectedGroupPath?.segments.map((segment) => segment.label).join(" / ") }}</strong>
            <button
              class="secondary-button compact"
              type="button"
              :disabled="selectedGroup.required"
              :title="selectedGroup.required ? '必填子组需先改为可选' : '解除父级关系'"
              @click="emit('detach', selectedGroup.id)"
            >
              <Unlink :size="15" />解绑
            </button>
          </div>
          <div class="cascade-inspector-issues">
            <button v-if="diagnostics.get(selectedGroup.id)?.orphaned_skill_ids.length" class="cascade-issue-button" type="button" @click="inspect(selectedGroup.id, 'orphaned')">
              <AlertTriangle :size="14" />路径失效 {{ diagnostics.get(selectedGroup.id)?.orphaned_skill_ids.length }}
            </button>
            <button v-if="diagnostics.get(selectedGroup.id)?.missing_required_skill_ids.length" class="cascade-issue-button" type="button" @click="inspect(selectedGroup.id, 'missing_required')">
              <AlertTriangle :size="14" />缺少必填 {{ diagnostics.get(selectedGroup.id)?.missing_required_skill_ids.length }}
            </button>
            <p v-if="!diagnostics.get(selectedGroup.id)?.orphaned_skill_ids.length && !diagnostics.get(selectedGroup.id)?.missing_required_skill_ids.length">当前节点没有数据诊断。</p>
          </div>
        </template>

        <template v-else-if="selectedKind === 'value' && selectedParent && selectedParentGroup && selectedValue">
          <div class="cascade-inspector-title">
            <span>Tag 值</span>
            <h3>{{ selectedValue.display_name || selectedValue.value }}</h3>
            <p>{{ selectedValuePath?.segments.map((segment) => segment.label).join(" / ") }}</p>
            <small>{{ selectedParentGroup.id }} / {{ selectedValue.value }}</small>
            <span v-if="selectedValuePath && !selectedValuePath.valid" class="tag-chip warning">路径失效</span>
          </div>
          <div class="cascade-child-list">
            <span>已挂载子 Group</span>
            <button v-for="child in selectedValueChildren" :key="child.id" type="button" @click="selectGroup(child)">
              <strong>{{ child.display_name }}</strong><small>{{ child.id }}</small>
            </button>
            <p v-if="!selectedValueChildren.length">尚未挂载子 Group。</p>
          </div>
          <div class="cascade-attach-editor">
            <label class="search-field cascade-child-search">
              <Search :size="15" />
              <input v-model="childSearch" placeholder="搜索可挂载 Group" aria-label="搜索可挂载子 Tag Group" />
            </label>
            <select v-if="filteredChildren.length" v-model="childGroupId" aria-label="选择子 Tag Group">
              <option v-for="group in filteredChildren" :key="group.id" :value="group.id">{{ group.display_name }}（{{ group.id }}）</option>
            </select>
            <p v-else>没有可挂载的根级 Group。</p>
            <button class="primary-button" type="button" :disabled="!childGroupId || !filteredChildren.some((group) => group.id === childGroupId)" @click="attach">
              <Link2 :size="16" />挂载子组
            </button>
          </div>
        </template>
        <div v-else class="cascade-inspector-empty"><GitBranch :size="24" /><strong>选择一个 Group 或 Tag 值</strong></div>
      </aside>
    </div>
  </section>
</template>
