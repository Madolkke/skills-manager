import { scoreKind } from "../../lib/format";
import { tagKey, tagLabel } from "../../lib/skillTags";
import type { SkillSummary, SkillTag, SkillTagPayload, TagGroup, TagValueOption } from "../../types";

export type FilterKey = "all" | "verified" | "untested" | "mine";
export type SortKey = "updated" | "score" | "name";
export type ViewMode = "grid" | "list";
export type TagCountMap = Record<string, number>;

export function filterSkills(
  skills: SkillSummary[],
  options: {
    query: string;
    filter: FilterKey;
    actor: string;
    selectedTags: SkillTagPayload[];
    tagGroups: TagGroup[];
  },
): SkillSummary[] {
  const normalized = options.query.trim().toLowerCase();
  const selectedByGroup = groupSelectedTags(options.selectedTags);
  return skills.filter((item) => {
    if (normalized && !skillSearchText(item, options.tagGroups).includes(normalized)) return false;
    if (!matchesSelectedTags(item, selectedByGroup)) return false;
    if (options.filter === "verified") return scoreKind(item.summary.latest_accepted_eval_run) !== "empty";
    if (options.filter === "untested") return scoreKind(item.summary.latest_accepted_eval_run) === "empty";
    if (options.filter === "mine") return item.skill.owner_ref === options.actor;
    return true;
  });
}

export function skillCounts(skills: SkillSummary[], actor: string) {
  return {
    all: skills.length,
    verified: skills.filter((item) => scoreKind(item.summary.latest_accepted_eval_run) !== "empty").length,
    untested: skills.filter((item) => scoreKind(item.summary.latest_accepted_eval_run) === "empty").length,
    mine: skills.filter((item) => item.skill.owner_ref === actor).length,
  };
}

export function sortSkills(skills: SkillSummary[], key: SortKey): SkillSummary[] {
  const copy = [...skills];
  if (key === "name") return copy.sort((left, right) => left.skill.slug.localeCompare(right.skill.slug));
  if (key === "score") return copy.sort((left, right) => scoreValue(right) - scoreValue(left) || updatedTime(right) - updatedTime(left));
  return copy.sort((left, right) => updatedTime(right) - updatedTime(left));
}

export function tagUsageCounts(skills: SkillSummary[]): TagCountMap {
  const counts: TagCountMap = {};
  for (const item of skills) {
    const unique = new Set((item.skill.tags ?? []).map(tagKey));
    for (const key of unique) counts[key] = (counts[key] ?? 0) + 1;
  }
  return counts;
}

export function tagValueLabel(value: TagValueOption): string {
  return value.display_name || value.value;
}

export function sortTagGroups(groups: TagGroup[]): TagGroup[] {
  return [...groups].sort((left, right) => left.sort_order - right.sort_order || left.display_name.localeCompare(right.display_name) || left.id.localeCompare(right.id));
}

export function sortTagValues(values: TagValueOption[]): TagValueOption[] {
  return [...values].sort((left, right) => left.sort_order - right.sort_order || tagValueLabel(left).localeCompare(tagValueLabel(right)) || left.value.localeCompare(right.value));
}

export function selectedTagLabel(tag: SkillTagPayload, groups: TagGroup[]): string {
  const group = groups.find((item) => item.id === tag.group_id);
  const value = group?.values.find((item) => item.value === tag.value);
  return tagLabel({ ...tag, value_display_name: value?.display_name ?? null }, groups);
}

function groupSelectedTags(tags: SkillTagPayload[]): Map<string, Set<string>> {
  const grouped = new Map<string, Set<string>>();
  for (const tag of tags) {
    const values = grouped.get(tag.group_id) ?? new Set<string>();
    values.add(tag.value);
    grouped.set(tag.group_id, values);
  }
  return grouped;
}

function matchesSelectedTags(item: SkillSummary, selectedByGroup: Map<string, Set<string>>): boolean {
  if (selectedByGroup.size === 0) return true;
  const tags = item.skill.tags ?? [];
  for (const [groupId, values] of selectedByGroup) {
    if (!tags.some((tag) => tag.group_id === groupId && values.has(tag.value))) return false;
  }
  return true;
}

function skillSearchText(item: SkillSummary, groups: TagGroup[]): string {
  const tags = (item.skill.tags ?? []).flatMap((tag) => tagSearchParts(tag, groups));
  return [item.skill.slug, item.skill.owner_ref, item.summary.current_version?.change_summary, item.summary.current_version?.content_digest, ...tags]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function tagSearchParts(tag: SkillTag, groups: TagGroup[]): string[] {
  const group = groups.find((item) => item.id === tag.group_id);
  const value = group?.values.find((item) => item.value === tag.value);
  return [
    tag.group_id,
    tag.group_display_name ?? "",
    group?.display_name ?? "",
    tag.value,
    tag.value_display_name ?? "",
    value?.display_name ?? "",
    tagLabel({ ...tag, value_display_name: value?.display_name ?? tag.value_display_name }, groups),
  ];
}

function scoreValue(item: SkillSummary): number {
  const run = item.summary.latest_accepted_eval_run;
  if (!run?.summary?.total) return -1;
  return ((run.summary.passed ?? 0) / run.summary.total) * 100;
}

function updatedTime(item: SkillSummary): number {
  const dates = [item.skill.updated_at, item.summary.current_version?.created_at, item.summary.latest_accepted_eval_run?.created_at]
    .map((date) => Date.parse(date ?? ""))
    .filter(Number.isFinite);
  return dates.length ? Math.max(...dates) : 0;
}
