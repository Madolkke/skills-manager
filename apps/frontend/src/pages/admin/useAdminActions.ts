import type { Ref } from "vue";
import { api, ApiError, type AdminGroup } from "../../lib/api";
import { toTagPayloads } from "../../lib/skillTags";
import type {
  OpencodeAgent,
  OpencodeAgentPayload,
  PublishGateExpression,
  PublishRecord,
  RoleAssignment,
  SkillSummary,
  SkillTagPayload,
  TagGroup,
  TagValueOption,
} from "../../types";
import type { AdminStateSync } from "./adminStateSync";

type Toast = { tone: "success" | "danger" | "info"; message: string };

type AdminActionsOptions = {
  tagDrafts: Ref<Record<string, SkillTagPayload[]>>;
  selectedGroupId: Ref<string>;
  selectedTagGroupId: Ref<string>;
  selectedOpencodeAgentId: Ref<string>;
  syncAdminState: AdminStateSync;
  load: () => Promise<void>;
  emitToast: (toast: Toast) => void;
};

export function useAdminActions(options: AdminActionsOptions) {
  const { tagDrafts, selectedGroupId, selectedTagGroupId, selectedOpencodeAgentId, syncAdminState, load, emitToast } = options;

  async function createGroup(payload: { name: string; description?: string }): Promise<void> {
    await runLocalAdminAction(async () => {
      const group = await api.adminCreateGroup(payload);
      syncAdminState.upsertGroup(group);
      selectedGroupId.value = group.id;
    }, "用户组已创建。");
  }

  async function updateGroup(groupId: string, payload: { name: string; description?: string }): Promise<void> {
    await runLocalAdminAction(async () => {
      syncAdminState.upsertGroup(await api.adminUpdateGroup(groupId, payload));
    }, "用户组已更新。");
  }

  async function deleteGroup(group: AdminGroup): Promise<void> {
    if (!confirm(`将强制删除用户组“${group.name}”，并移除其成员和相关授权。是否继续？`)) return;
    await runLocalAdminAction(async () => {
      await api.adminDeleteGroup(group.id);
      syncAdminState.removeGroup(group.id);
    }, "用户组已删除。");
  }

  async function addGroupMember(groupId: string, subjectId: string): Promise<void> {
    await runLocalAdminAction(async () => {
      syncAdminState.upsertGroup(await api.adminAddGroupMember(groupId, { subject_id: subjectId }));
    }, "成员已添加。");
  }

  async function removeGroupMember(groupId: string, subjectId: string): Promise<void> {
    await runLocalAdminAction(async () => {
      syncAdminState.upsertGroup(await api.adminRemoveGroupMember(groupId, subjectId));
    }, "成员已移除。");
  }

  async function createTagGroup(payload: { id: string; display_name: string; description?: string; sort_order?: number; required?: boolean; free_form?: boolean; initial_value?: string }): Promise<void> {
    try {
      let group = await api.adminCreateTagGroup({
        id: payload.id,
        display_name: payload.display_name,
        description: payload.description,
        sort_order: payload.sort_order,
        required: payload.free_form ? payload.required : false,
        free_form: payload.free_form,
      });
      if (payload.initial_value) {
        group = await api.adminCreateTagValue(group.id, { value: payload.initial_value, display_name: payload.initial_value, description: "", sort_order: 0 });
      }
      if (payload.required) {
        group = await api.adminUpdateTagGroup(group.id, {
          display_name: payload.display_name,
          description: payload.description,
          sort_order: payload.sort_order,
          required: true,
          free_form: false,
        });
      }
      syncAdminState.upsertTagGroup(group);
      selectedTagGroupId.value = group.id;
      emitToast({ tone: "success", message: "Tag Group 已创建。" });
    } catch (error) {
      if (isDuplicateTagGroupError(error, payload.id)) {
        selectedTagGroupId.value = payload.id;
        await load();
        emitToast({ tone: "info", message: `Tag Group“${payload.id}”已存在，已切换到现有项。` });
        return;
      }
      showError(error);
    }
  }

  async function updateTagGroup(groupId: string, payload: { display_name: string; description?: string; sort_order?: number; required?: boolean; free_form?: boolean }): Promise<void> {
    await runLocalAdminAction(async () => {
      syncAdminState.upsertTagGroup(await api.adminUpdateTagGroup(groupId, payload));
    }, "Tag Group 已更新。");
  }

  async function deleteTagGroup(group: TagGroup): Promise<void> {
    if (!confirm(`将删除 Tag Group“${group.display_name}”。仍有 Skill Tag、授权或级联引用时系统会拒绝删除。是否继续？`)) return;
    await runLocalAdminAction(async () => {
      await api.adminDeleteTagGroup(group.id);
      syncAdminState.removeTagGroup(group.id);
    }, "Tag Group 已删除。");
  }

  async function createTagValue(groupId: string, payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }): Promise<void> {
    await runLocalAdminAction(async () => {
      syncAdminState.upsertTagGroup(await api.adminCreateTagValue(groupId, payload));
    }, "Tag 值已创建。");
  }

  async function updateTagValue(groupId: string, value: string, payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }): Promise<void> {
    await runLocalAdminAction(async () => {
      syncAdminState.upsertTagGroup(await api.adminUpdateTagValue(groupId, value, payload));
    }, "Tag 值已更新。");
  }

  async function deleteTagValue(group: TagGroup, value: TagValueOption): Promise<void> {
    if (!confirm(`将删除 Tag 值“${value.display_name || value.value}”。仍有 Skill Tag、授权或级联引用时系统会拒绝删除。是否继续？`)) return;
    await runLocalAdminAction(async () => {
      await api.adminDeleteTagValue(group.id, value.value);
      syncAdminState.removeTagValue(group.id, value.value);
    }, "Tag 值已删除。");
  }

  async function assignRole(payload: { subject_type: "user" | "group"; subject_id: string; resource_type: "skill" | "skill_tag"; resource_id: string; role: string }): Promise<void> {
    await runLocalAdminAction(async () => {
      syncAdminState.upsertRole(await api.adminAssignRole(payload));
    }, "角色已授权。");
  }

  async function revokeRole(role: RoleAssignment): Promise<void> {
    if (!confirm(`将撤销 ${role.subject_type}:${role.subject_id} 的 ${role.role} 授权。是否继续？`)) return;
    await runLocalAdminAction(async () => {
      await api.adminDeleteRoleAssignment(role.id);
      syncAdminState.removeRole(role.id);
    }, "授权已撤销。");
  }

  async function updatePublishTarget(targetId: string, payload: { enabled: boolean; auto_publish_enabled: boolean; gate_expression: PublishGateExpression }): Promise<void> {
    await runLocalAdminAction(async () => {
      syncAdminState.upsertPublishTarget(await api.adminUpdatePublishTarget(targetId, payload));
    }, "发布源已更新。");
  }

  async function createOpencodeAgent(payload: OpencodeAgentPayload): Promise<void> {
    await runLocalAdminAction(async () => {
      const agent = await api.adminCreateOpencodeAgent(payload);
      syncAdminState.upsertOpencodeAgent(agent);
      selectedOpencodeAgentId.value = agent.id;
    }, "Opencode Agent 已创建。");
  }

  async function updateOpencodeAgent(agentId: string, payload: OpencodeAgentPayload): Promise<void> {
    await runLocalAdminAction(async () => {
      syncAdminState.upsertOpencodeAgent(await api.adminUpdateOpencodeAgent(agentId, payload));
    }, "Opencode Agent 已更新。");
  }

  async function deleteOpencodeAgent(agent: OpencodeAgent): Promise<void> {
    if (!confirm(`将软删除 Opencode Agent“${agent.name}”，测评页将不再显示。历史运行记录不会被清理。是否继续？`)) return;
    await runLocalAdminAction(async () => {
      await api.adminDeleteOpencodeAgent(agent.id);
      syncAdminState.removeOpencodeAgent(agent.id);
    }, "Opencode Agent 已删除。");
  }

  async function confirmPublishRecord(record: PublishRecord): Promise<void> {
    if (!confirm(`确认发布 ${record.skill?.slug ?? record.skill_id} 到 ${record.publish_target?.name ?? record.publish_target_id}？`)) return;
    await runLocalAdminAction(async () => {
      syncAdminState.upsertPublishRecord(await api.adminConfirmPublishRecord(record.id));
    }, "发布单已进入队列。");
  }

  async function cancelPublishRecord(record: PublishRecord): Promise<void> {
    if (!confirm("将取消该发布单及尚未执行的任务。是否继续？")) return;
    await runLocalAdminAction(async () => {
      syncAdminState.upsertPublishRecord(await api.adminCancelPublishRecord(record.id));
    }, "发布单已取消。");
  }

  async function retryPublishRecord(record: PublishRecord): Promise<void> {
    if (!confirm("请先核对外部发布状态。确认需要重新执行该发布单？")) return;
    await runLocalAdminAction(async () => {
      syncAdminState.upsertPublishRecord(await api.adminRetryPublishRecord(record.id));
    }, "发布单已重新进入队列。");
  }

  async function batchConfirmPublishRecords(records: PublishRecord[]): Promise<void> {
    if (!records.length) return;
    if (!confirm(`将批量确认 ${records.length} 条待确认发布单。是否继续？`)) return;
    await runBatchPublishAction(records, (record) => api.adminConfirmPublishRecord(record.id), "确认");
  }

  async function batchCancelPublishRecords(records: PublishRecord[]): Promise<void> {
    if (!records.length) return;
    if (!confirm(`将批量取消 ${records.length} 条待确认发布单。是否继续？`)) return;
    await runBatchPublishAction(records, (record) => api.adminCancelPublishRecord(record.id), "取消");
  }

  async function saveSkillTags(skill: SkillSummary, tags?: SkillTagPayload[]): Promise<void> {
    const nextTags = tags ?? tagDrafts.value[skill.skill.id] ?? [];
    tagDrafts.value[skill.skill.id] = nextTags;
    await runLocalAdminAction(async () => {
      const updated = await api.adminUpdateSkill(skill.skill.id, { tags: nextTags });
      syncAdminState.updateSkillTags(updated.id, updated.tags ?? []);
      tagDrafts.value[updated.id] = toTagPayloads(updated.tags ?? []);
    }, "Skill Tag 已更新。");
  }

  async function runLocalAdminAction(action: () => Promise<unknown>, successMessage: string): Promise<void> {
    try {
      await action();
      emitToast({ tone: "success", message: successMessage });
    } catch (error) {
      showError(error);
    }
  }

  async function runBatchPublishAction(records: PublishRecord[], action: (record: PublishRecord) => Promise<unknown>, verb: string): Promise<void> {
    let succeeded = 0;
    let failed = 0;
    for (const record of records) {
      try {
        await action(record);
        succeeded += 1;
      } catch {
        failed += 1;
      }
    }
    await load();
    emitToast({
      tone: failed ? "danger" : "success",
      message: `批量${verb}完成：成功 ${succeeded} 条，失败 ${failed} 条。`,
    });
  }

  function showError(error: unknown): void {
    const message = error instanceof ApiError || error instanceof Error ? error.message : "操作失败。";
    emitToast({ tone: "danger", message });
  }

  return {
    createGroup,
    updateGroup,
    deleteGroup,
    addGroupMember,
    removeGroupMember,
    createTagGroup,
    updateTagGroup,
    deleteTagGroup,
    createTagValue,
    updateTagValue,
    deleteTagValue,
    assignRole,
    revokeRole,
    updatePublishTarget,
    createOpencodeAgent,
    updateOpencodeAgent,
    deleteOpencodeAgent,
    confirmPublishRecord,
    cancelPublishRecord,
    retryPublishRecord,
    batchConfirmPublishRecords,
    batchCancelPublishRecords,
    saveSkillTags,
  };

  function isDuplicateTagGroupError(error: unknown, groupId: string): boolean {
    if (!(error instanceof ApiError)) return false;
    return error.message.includes("Tag Group already exists") && error.message.includes(groupId);
  }
}
