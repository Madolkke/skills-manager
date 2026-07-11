import type { SkillTag, SkillTagPayload, TagGroup } from "../types";
import { missingActiveRequiredGroups } from "./tagCascades";

export function tagLabel(tag: SkillTag | SkillTagPayload, groups: TagGroup[] = []): string {
  const group = groups.find((item) => item.id === tag.group_id);
  const groupName = "group_display_name" in tag && tag.group_display_name ? tag.group_display_name : (group?.display_name ?? tag.group_id);
  const value = "value_display_name" in tag && tag.value_display_name ? tag.value_display_name : tag.value;
  return `${groupName}: ${value}`;
}

export function toTagPayloads(tags: Array<SkillTag | SkillTagPayload>): SkillTagPayload[] {
  return tags.map((tag) => ({ group_id: tag.group_id, value: tag.value }));
}

export function tagKey(tag: SkillTag | SkillTagPayload): string {
  return `${tag.group_id}\u0000${tag.value}`;
}

export function sortTagGroupsForPicker(groups: TagGroup[]): TagGroup[] {
  return [...groups].sort((a, b) => Number(b.required) - Number(a.required) || a.sort_order - b.sort_order || a.display_name.localeCompare(b.display_name));
}

export function missingRequiredTagGroups(tags: SkillTagPayload[], groups: TagGroup[]): TagGroup[] {
  return missingActiveRequiredGroups(tags, groups);
}

export function requiredTagMissingMessage(tags: SkillTagPayload[], groups: TagGroup[]): string {
  const missing = missingRequiredTagGroups(tags, groups);
  if (!missing.length) return "";
  return `请为必选 Tag Group 选择 Tag：${missing.map((group) => group.display_name).join("、")}`;
}

export function encodeSkillTagResourceId(groupId: string, value: string): string {
  const bytes = new TextEncoder().encode(value.trim());
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return `${groupId.trim()}:${btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")}`;
}
