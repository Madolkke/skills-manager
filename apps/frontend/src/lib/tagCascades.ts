import type { SkillTagPayload, TagCascadeRelation, TagGroup, TagValueOption } from "../types";

export type ActiveTagGroup = { group: TagGroup; depth: number };
export type TagPathSegment = { kind: "group" | "value"; id: string; label: string };
export type TagPathIssue = "missing_group" | "missing_parent" | "cycle";
export type TagPathInfo = { segments: TagPathSegment[]; valid: boolean; issue: TagPathIssue | null };
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
  const selectedGroups = new Set(tags.map((tag) => tag.group_id));
  const children = new Map<string, TagGroup[]>();
  const roots: TagGroup[] = [];
  for (const group of groups) {
    if (!group.parent) roots.push(group);
    else {
      const key = group.parent.group_id;
      children.set(key, [...(children.get(key) ?? []), group]);
    }
  }

  const result: ActiveTagGroup[] = [];
  const visited = new Set<string>();
  const visit = (group: TagGroup, depth: number): void => {
    if (visited.has(group.id)) return;
    visited.add(group.id);
    result.push({ group, depth });
    for (const child of sortGroups(children.get(group.id) ?? [])) {
      const parent = child.parent;
      if (!parent || !selectedGroups.has(group.id)) continue;
      if (activationMode(parent) === "parent_value" && !selected.has(tagIdentity({ group_id: group.id, value: parent.value ?? "" }))) continue;
      visit(child, depth + 1);
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
  return sortGroups(groups.filter((group) => group.parent?.group_id === groupId && activationMode(group.parent) === "parent_value" && group.parent.value === value));
}

export function childGroupsForSelectedParent(groups: TagGroup[], groupId: string): TagGroup[] {
  return sortGroups(groups.filter((group) => group.parent?.group_id === groupId && activationMode(group.parent) === "parent_selected"));
}

export function rootTagGroups(groups: TagGroup[]): TagGroup[] {
  return sortGroups(groups.filter((group) => !group.parent));
}

export function tagGroupPath(groups: TagGroup[], groupId: string): TagPathSegment[] {
  return tagGroupPathInfo(groups, groupId).segments;
}

export function tagGroupPathInfo(groups: TagGroup[], groupId: string): TagPathInfo {
  const byId = new Map(groups.map((group) => [group.id, group]));
  const path: TagPathSegment[] = [];
  const visited = new Set<string>();
  let group = byId.get(groupId);
  if (!group) {
    return {
      segments: [{ kind: "group", id: groupId, label: groupId }],
      valid: false,
      issue: "missing_group",
    };
  }
  while (group) {
    if (visited.has(group.id)) return { segments: path, valid: false, issue: "cycle" };
    visited.add(group.id);
    path.unshift({ kind: "group", id: group.id, label: group.display_name });
    if (!group.parent) return { segments: path, valid: true, issue: null };
    const parent = byId.get(group.parent.group_id);
    path.unshift({
      kind: "value",
      id: group.parent.value ?? "parent-selected",
      label: activationMode(group.parent) === "parent_selected" ? "任意已选值" : valueDisplayName(parent, group.parent.value ?? ""),
    });
    if (!parent) return { segments: path, valid: false, issue: "missing_parent" };
    group = parent;
  }
  return { segments: path, valid: true, issue: null };
}

export function tagValuePath(groups: TagGroup[], groupId: string, value: string): TagPathSegment[] {
  return tagValuePathInfo(groups, groupId, value).segments;
}

export function tagValuePathInfo(groups: TagGroup[], groupId: string, value: string): TagPathInfo {
  const group = groups.find((item) => item.id === groupId);
  const path = tagGroupPathInfo(groups, groupId);
  return {
    ...path,
    segments: [...path.segments, { kind: "value", id: value, label: valueDisplayName(group, value) }],
  };
}

export function tagGroupPathLabel(groups: TagGroup[], groupId: string): string {
  return tagGroupPath(groups, groupId).map((segment) => segment.label).join(" / ");
}

export function tagValuePathLabel(groups: TagGroup[], groupId: string, value: string): string {
  return tagValuePath(groups, groupId, value).map((segment) => segment.label).join(" / ");
}

export function selectedLeafTags(tags: SkillTagPayload[], groups: TagGroup[]): SkillTagPayload[] {
  const selected = new Set(tags.map(tagIdentity));
  return tags.filter((tag) => {
    return !groups.some((group) => {
      if (group.parent?.group_id !== tag.group_id) return false;
      if (activationMode(group.parent) === "parent_value" && group.parent.value !== tag.value) return false;
      return tags.some((candidate) => candidate.group_id === group.id && selected.has(tagIdentity(candidate)));
    });
  });
}

export function withCascadeParents(groups: TagGroup[], relations: TagCascadeRelation[]): TagGroup[] {
  const parents = new Map(relations.map((relation) => [relation.child_group_id, relation]));
  return groups.map((group) => {
    const relation = parents.get(group.id);
    return {
      ...group,
      parent: relation ? { group_id: relation.parent_group_id, value: relation.parent_value, activation_mode: activationMode(relation) } : null,
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
    for (const value of sortTagValues(group)) {
      rows.push({ kind: "value", key: `value:${group.id}:${value.value}`, depth: depth + 1, group, value });
      for (const child of childGroupsForValue(groups, group.id, value.value)) visit(child, depth + 2);
    }
    for (const child of childGroupsForSelectedParent(groups, group.id)) visit(child, depth + 1);
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

export function sortTagValues(group: TagGroup): TagValueOption[] {
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

function valueDisplayName(group: TagGroup | undefined, value: string): string {
  return group?.values.find((item) => item.value === value)?.display_name || value;
}

function activationMode(relation: Pick<NonNullable<TagGroup["parent"]>, "activation_mode"> | TagCascadeRelation): "parent_value" | "parent_selected" {
  return relation.activation_mode ?? "parent_value";
}
