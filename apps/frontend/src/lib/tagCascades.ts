import type { SkillTagPayload, TagCascadeRelation, TagGroup, TagValueOption } from "../types";

export type ActiveTagGroup = { group: TagGroup; depth: number };
export type TagDiagnosticFocus = {
  groupId: string;
  kind: "orphaned" | "missing_required";
  skillIds: string[];
};
export type TagCascadeTreeRow =
  | { kind: "group"; key: string; depth: number; group: TagGroup }
  | { kind: "value"; key: string; depth: number; group: TagGroup; value: TagValueOption };

export function activeTagGroups(groups: TagGroup[], tags: SkillTagPayload[]): ActiveTagGroup[] {
  const selected = new Set(tags.map(tagIdentity));
  const children = new Map<string, TagGroup[]>();
  const roots: TagGroup[] = [];
  for (const group of groups) {
    if (!group.parent) roots.push(group);
    else {
      const key = tagIdentity({ group_id: group.parent.group_id, value: group.parent.value });
      children.set(key, [...(children.get(key) ?? []), group]);
    }
  }

  const result: ActiveTagGroup[] = [];
  const visited = new Set<string>();
  const visit = (group: TagGroup, depth: number): void => {
    if (visited.has(group.id)) return;
    visited.add(group.id);
    result.push({ group, depth });
    for (const value of sortValues(group)) {
      const key = tagIdentity({ group_id: group.id, value: value.value });
      if (!selected.has(key)) continue;
      for (const child of sortGroups(children.get(key) ?? [])) visit(child, depth + 1);
    }
  };
  for (const root of sortGroups(roots)) visit(root, 0);
  return result;
}

export function pruneInactiveTags(tags: SkillTagPayload[], groups: TagGroup[]): SkillTagPayload[] {
  let current = uniqueTags(tags);
  while (true) {
    const activeIds = new Set(activeTagGroups(groups, current).map((item) => item.group.id));
    const next = current.filter((tag) => activeIds.has(tag.group_id));
    if (next.length === current.length) return next;
    current = next;
  }
}

export function orphanedTags(tags: SkillTagPayload[], groups: TagGroup[]): SkillTagPayload[] {
  const activeIds = new Set(activeTagGroups(groups, tags).map((item) => item.group.id));
  return tags.filter((tag) => !activeIds.has(tag.group_id));
}

export function missingActiveRequiredGroups(tags: SkillTagPayload[], groups: TagGroup[]): TagGroup[] {
  const selectedGroupIds = new Set(tags.map((tag) => tag.group_id));
  return activeTagGroups(groups, tags)
    .map((item) => item.group)
    .filter((group) => group.required && !selectedGroupIds.has(group.id));
}

export function childGroupsForValue(groups: TagGroup[], groupId: string, value: string): TagGroup[] {
  return sortGroups(groups.filter((group) => group.parent?.group_id === groupId && group.parent.value === value));
}

export function rootTagGroups(groups: TagGroup[]): TagGroup[] {
  return sortGroups(groups.filter((group) => !group.parent));
}

export function withCascadeParents(groups: TagGroup[], relations: TagCascadeRelation[]): TagGroup[] {
  const parents = new Map(relations.map((relation) => [relation.child_group_id, relation]));
  return groups.map((group) => {
    const relation = parents.get(group.id);
    return {
      ...group,
      parent: relation ? { group_id: relation.parent_group_id, value: relation.parent_value } : null,
    };
  });
}

export function buildTagCascadeTreeRows(groups: TagGroup[]): TagCascadeTreeRow[] {
  const rows: TagCascadeTreeRow[] = [];
  const visited = new Set<string>();
  const visit = (group: TagGroup, depth: number): void => {
    if (visited.has(group.id)) return;
    visited.add(group.id);
    rows.push({ kind: "group", key: `group:${group.id}`, depth, group });
    for (const value of sortValues(group)) {
      rows.push({ kind: "value", key: `value:${group.id}:${value.value}`, depth: depth + 1, group, value });
      for (const child of childGroupsForValue(groups, group.id, value.value)) visit(child, depth + 2);
    }
  };
  for (const root of rootTagGroups(groups)) visit(root, 0);
  for (const group of sortGroups(groups)) visit(group, 0);
  return rows;
}

export function sortGroups(groups: TagGroup[]): TagGroup[] {
  return [...groups].sort(
    (left, right) => left.sort_order - right.sort_order || left.display_name.localeCompare(right.display_name) || left.id.localeCompare(right.id),
  );
}

function sortValues(group: TagGroup): TagValueOption[] {
  return [...group.values].sort((left, right) => left.sort_order - right.sort_order || left.value.localeCompare(right.value));
}

function uniqueTags(tags: SkillTagPayload[]): SkillTagPayload[] {
  const seen = new Set<string>();
  return tags.filter((tag) => {
    const key = tagIdentity(tag);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function tagIdentity(tag: SkillTagPayload): string {
  return `${tag.group_id}\u0000${tag.value}`;
}
