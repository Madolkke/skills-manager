import type { Ref } from "vue";
import type { AdminGroup } from "../../lib/api";
import { encodeSkillTagResourceId } from "../../lib/skillTags";
import type { OpencodeAgent, PublishRecord, PublishTarget, RoleAssignment, SkillSummary, SkillTagPayload, TagGroup } from "../../types";

type AdminStateSyncCollections = {
  groups: Ref<AdminGroup[]>;
  tagGroups: Ref<TagGroup[]>;
  roles: Ref<RoleAssignment[]>;
  publishTargets: Ref<PublishTarget[]>;
  publishRecords: Ref<PublishRecord[]>;
  opencodeAgents: Ref<OpencodeAgent[]>;
  skills: Ref<SkillSummary[]>;
  tagDrafts: Ref<Record<string, SkillTagPayload[]>>;
  selectedGroupId: Ref<string>;
  selectedTagGroupId: Ref<string>;
  selectedOpencodeAgentId: Ref<string>;
};

export function createAdminStateSync(state: AdminStateSyncCollections) {
  return {
    upsertGroup(group: AdminGroup): void {
      state.groups.value = upsertById(state.groups.value, group);
    },
    removeGroup(groupId: string): void {
      const currentIndex = state.groups.value.findIndex((group) => group.id === groupId);
      state.groups.value = state.groups.value.filter((group) => group.id !== groupId);
      state.selectedGroupId.value = nextSelectedId(state.groups.value, state.selectedGroupId.value, currentIndex);
      state.roles.value = state.roles.value.filter((role) => role.subject_type !== "group" || role.subject_id !== groupId);
    },
    upsertTagGroup(group: TagGroup): void {
      state.tagGroups.value = upsertById(state.tagGroups.value, group);
    },
    removeTagGroup(groupId: string): void {
      const removed = state.tagGroups.value.find((group) => group.id === groupId);
      const currentIndex = state.tagGroups.value.findIndex((group) => group.id === groupId);
      state.tagGroups.value = state.tagGroups.value.filter((group) => group.id !== groupId);
      state.selectedTagGroupId.value = nextSelectedId(state.tagGroups.value, state.selectedTagGroupId.value, currentIndex);
      if (removed) state.roles.value = state.roles.value.filter((role) => role.resource_type !== "skill_tag" || !roleTargetsTagGroup(role, removed));
      clearSkillTagsForGroup(state, groupId);
    },
    removeTagValue(groupId: string, value: string): void {
      state.tagGroups.value = state.tagGroups.value.map((group) => {
        if (group.id !== groupId) return group;
        return { ...group, values: group.values.filter((item) => item.value !== value) };
      });
      state.roles.value = state.roles.value.filter((role) => role.resource_type !== "skill_tag" || role.resource_id !== encodeSkillTagResourceId(groupId, value));
      clearSkillTagsForValue(state, groupId, value);
    },
    upsertRole(role: RoleAssignment): void {
      state.roles.value = upsertById(state.roles.value, role);
    },
    removeRole(roleId: string): void {
      state.roles.value = state.roles.value.filter((role) => role.id !== roleId);
    },
    upsertPublishTarget(target: PublishTarget): void {
      state.publishTargets.value = upsertById(state.publishTargets.value, target);
    },
    upsertPublishRecord(record: PublishRecord): void {
      state.publishRecords.value = upsertById(state.publishRecords.value, record);
    },
    upsertOpencodeAgent(agent: OpencodeAgent): void {
      state.opencodeAgents.value = upsertById(state.opencodeAgents.value, agent);
    },
    removeOpencodeAgent(agentId: string): void {
      const currentIndex = state.opencodeAgents.value.findIndex((agent) => agent.id === agentId);
      state.opencodeAgents.value = state.opencodeAgents.value.filter((agent) => agent.id !== agentId);
      state.selectedOpencodeAgentId.value = nextSelectedId(state.opencodeAgents.value, state.selectedOpencodeAgentId.value, currentIndex);
    },
    updateSkillTags(skillId: string, tags: SkillSummary["skill"]["tags"]): void {
      state.skills.value = state.skills.value.map((item) => updateSkillSummaryTags(item, skillId, tags));
    },
  };
}

export type AdminStateSync = ReturnType<typeof createAdminStateSync>;

function clearSkillTagsForGroup(state: AdminStateSyncCollections, groupId: string): void {
  state.skills.value = state.skills.value.map((item) => withoutSkillTags(item, (tag) => tag.group_id === groupId));
  state.tagDrafts.value = Object.fromEntries(Object.entries(state.tagDrafts.value).map(([skillId, tags]) => [skillId, tags.filter((tag) => tag.group_id !== groupId)]));
}

function clearSkillTagsForValue(state: AdminStateSyncCollections, groupId: string, value: string): void {
  state.skills.value = state.skills.value.map((item) => withoutSkillTags(item, (tag) => tag.group_id === groupId && tag.value === value));
  state.tagDrafts.value = Object.fromEntries(
    Object.entries(state.tagDrafts.value).map(([skillId, tags]) => [skillId, tags.filter((tag) => tag.group_id !== groupId || tag.value !== value)]),
  );
}

function withoutSkillTags(item: SkillSummary, predicate: (tag: SkillSummary["skill"]["tags"][number]) => boolean): SkillSummary {
  const tags = item.skill.tags.filter((tag) => !predicate(tag));
  return updateSkillSummaryTags(item, item.skill.id, tags);
}

function updateSkillSummaryTags(item: SkillSummary, skillId: string, tags: SkillSummary["skill"]["tags"]): SkillSummary {
  if (item.skill.id !== skillId) return item;
  const skill = { ...item.skill, tags };
  return { ...item, skill, summary: { ...item.summary, skill } };
}

function roleTargetsTagGroup(role: RoleAssignment, group: TagGroup): boolean {
  return group.values.some((value) => role.resource_id === encodeSkillTagResourceId(group.id, value.value));
}

function upsertById<T extends { id: string }>(items: T[], item: T): T[] {
  const index = items.findIndex((current) => current.id === item.id);
  if (index === -1) return [...items, item];
  return items.map((current) => (current.id === item.id ? item : current));
}

function nextSelectedId(items: Array<{ id: string }>, currentId: string, removedIndex: number): string {
  if (currentId && items.some((item) => item.id === currentId)) return currentId;
  if (!items.length) return "";
  return items[Math.max(0, Math.min(removedIndex, items.length - 1))]?.id ?? "";
}
