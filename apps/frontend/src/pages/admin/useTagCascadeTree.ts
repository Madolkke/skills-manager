import { computed, ref, watch, type Ref } from "vue";
import { buildTagCascadeTreeRows, sortGroups, withCascadeParents, type TagCascadeTreeRow } from "../../lib/tagCascades";
import type { TagCascadeOverview, TagGroup } from "../../types";

export function useTagCascadeTree(tagGroups: Ref<TagGroup[]>, overview: Ref<TagCascadeOverview | null>) {
  const selectedParent = ref<{ groupId: string; value: string } | null>(null);
  const childGroupId = ref("");
  const expandedGroups = ref(new Set<string>());
  const knownGroupIds = new Set<string>();
  const groups = computed(() => withCascadeParents(tagGroups.value, overview.value?.relations ?? []));
  const rows = computed(() => buildTagCascadeTreeRows(groups.value));
  const diagnostics = computed(() => new Map((overview.value?.diagnostics ?? []).map((item) => [item.group_id, item])));
  const selectedParentGroup = computed(() => groups.value.find((group) => group.id === selectedParent.value?.groupId) ?? null);
  const selectedParentValueLabel = computed(() => {
    if (!selectedParent.value || !selectedParentGroup.value) return "";
    return valueDisplayName(selectedParentGroup.value, selectedParent.value.value);
  });
  const summary = computed(() => ({
    groups: groups.value.length,
    roots: groups.value.filter((group) => !group.parent).length,
    relations: overview.value?.relations.length ?? 0,
  }));
  const issueTotals = computed(() => {
    const items = overview.value?.diagnostics ?? [];
    return {
      orphaned: items.reduce((total, item) => total + item.orphaned_skill_ids.length, 0),
      missing: items.reduce((total, item) => total + item.missing_required_skill_ids.length, 0),
    };
  });
  const childrenByValue = computed(() => {
    const result = new Map<string, number>();
    for (const group of groups.value) {
      if (!group.parent) continue;
      const key = parentValueKey(group.parent.group_id, group.parent.value);
      result.set(key, (result.get(key) ?? 0) + 1);
    }
    return result;
  });
  const visibleRows = computed<TagCascadeTreeRow[]>(() => {
    const visible: TagCascadeTreeRow[] = [];
    let hiddenBelowDepth: number | null = null;
    for (const row of rows.value) {
      if (hiddenBelowDepth !== null && row.depth > hiddenBelowDepth) continue;
      if (hiddenBelowDepth !== null) hiddenBelowDepth = null;
      visible.push(row);
      if (row.kind === "group" && row.group.values.length && !expandedGroups.value.has(row.group.id)) {
        hiddenBelowDepth = row.depth;
      }
    }
    return visible;
  });
  const allExpanded = computed(() => groups.value.filter((group) => group.values.length).every((group) => expandedGroups.value.has(group.id)));
  const availableChildren = computed(() => {
    if (!selectedParent.value) return [];
    const excluded = ancestorIds(selectedParent.value.groupId);
    excluded.add(selectedParent.value.groupId);
    return sortGroups(groups.value.filter((group) => !group.parent && !excluded.has(group.id)));
  });

  watch(groups, (currentGroups) => {
    const currentIds = new Set(currentGroups.map((group) => group.id));
    const next = new Set([...expandedGroups.value].filter((groupId) => currentIds.has(groupId)));
    for (const group of currentGroups) {
      if (!knownGroupIds.has(group.id)) next.add(group.id);
    }
    knownGroupIds.clear();
    for (const groupId of currentIds) knownGroupIds.add(groupId);
    expandedGroups.value = next;
  }, { immediate: true });

  watch(availableChildren, (children) => {
    if (!children.some((group) => group.id === childGroupId.value)) childGroupId.value = children[0]?.id ?? "";
  }, { immediate: true });

  function ancestorIds(groupId: string): Set<string> {
    const result = new Set<string>();
    let group = groups.value.find((item) => item.id === groupId);
    while (group?.parent && !result.has(group.parent.group_id)) {
      result.add(group.parent.group_id);
      group = groups.value.find((item) => item.id === group?.parent?.group_id);
    }
    return result;
  }

  function toggleGroup(groupId: string): void {
    const next = new Set(expandedGroups.value);
    if (next.has(groupId)) next.delete(groupId);
    else next.add(groupId);
    expandedGroups.value = next;
  }

  function expandAll(): void {
    expandedGroups.value = new Set(groups.value.map((group) => group.id));
  }

  function collapseAll(): void {
    expandedGroups.value = new Set();
  }

  function selectParent(group: TagGroup, value: string): void {
    if (!group.free_form) selectedParent.value = { groupId: group.id, value };
  }

  function parentLabel(group: TagGroup): string {
    if (!group.parent) return "根级 Group";
    const parentGroup = groups.value.find((item) => item.id === group.parent?.group_id);
    return `${parentGroup?.display_name ?? group.parent.group_id} / ${valueDisplayName(parentGroup, group.parent.value)}`;
  }

  function parentTitle(group: TagGroup): string {
    return group.parent ? `父级：${group.parent.group_id} / ${group.parent.value}` : "此 Group 位于级联根节点";
  }

  function childCount(groupId: string, value: string): number {
    return childrenByValue.value.get(parentValueKey(groupId, value)) ?? 0;
  }

  return {
    allExpanded, availableChildren, childCount, childGroupId, collapseAll, diagnostics, expandAll, expandedGroups,
    groups, issueTotals, parentLabel, parentTitle, rows, selectParent, selectedParent, selectedParentGroup,
    selectedParentValueLabel, summary, toggleGroup, visibleRows,
  };
}

function valueDisplayName(group: TagGroup | undefined, value: string): string {
  return group?.values.find((item) => item.value === value)?.display_name || value;
}

function parentValueKey(groupId: string, value: string): string {
  return `${groupId}\u0000${value}`;
}
