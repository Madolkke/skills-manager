import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { type AdminTab } from "../../lib/admin";
import { api, ApiError, type AdminGroup } from "../../lib/api";
import { toTagPayloads } from "../../lib/skillTags";
import type {
  OpencodeAgent,
  OpencodeProviderCatalog,
  PublishGateCheckDefinition,
  PublishRecord,
  PublishTarget,
  RoleAssignment,
  SkillSummary,
  SkillTagPayload,
  TagGroup,
  WorkerStatusOverview,
  SystemCommand,
  ExpressionFunction,
} from "../../types";
import { createAdminStateSync } from "./adminStateSync";
import { useAdminActions } from "./useAdminActions";
import { useAdminTagCascades } from "./useAdminTagCascades";

type Toast = { tone: "success" | "danger" | "info"; message: string };

/** 管理后台的鉴权、数据加载和刷新生命周期。 */
export function useAdminPageState(emitToast: (toast: Toast) => void) {
  const key = ref(sessionStorage.getItem("skillhub.admin.key") || "");
  const unlocked = ref(false);
  const loading = ref(false);
  const activeTab = ref<AdminTab>("overview");
  const skills = ref<SkillSummary[]>([]);
  const groups = ref<AdminGroup[]>([]);
  const tagGroups = ref<TagGroup[]>([]);
  const roles = ref<RoleAssignment[]>([]);
  const publishTargets = ref<PublishTarget[]>([]);
  const publishGateChecks = ref<PublishGateCheckDefinition[]>([]);
  const publishRecords = ref<PublishRecord[]>([]);
  const workerStatus = ref<WorkerStatusOverview | null>(null);
  const opencodeAgents = ref<OpencodeAgent[]>([]);
  const opencodeProviderCatalog = ref<OpencodeProviderCatalog | null>(null);
  const systemCommands = ref<SystemCommand[]>([]);
  const selectedSystemCommandId = ref("");
  const expressionFunctions = ref<ExpressionFunction[]>([]);
  const selectedExpressionFunctionId = ref("");
  const selectedGroupId = ref("");
  const selectedTagGroupId = ref("");
  const selectedOpencodeAgentId = ref("");
  const tagDrafts = ref<Record<string, SkillTagPayload[]>>({});
  let workerRefreshTimer: number | undefined;
  let publishRefreshTimer: number | undefined;

  const tagCascadeActions = useAdminTagCascades({ activeTab, emitToast });
  const syncAdminState = createAdminStateSync({
    groups,
    tagGroups,
    roles,
    publishTargets,
    publishRecords,
    opencodeAgents,
    skills,
    tagDrafts,
    selectedGroupId,
    selectedTagGroupId,
    selectedOpencodeAgentId,
  });
  const adminActions = useAdminActions({
    tagDrafts,
    selectedGroupId,
    selectedTagGroupId,
    selectedOpencodeAgentId,
    systemCommands,
    selectedSystemCommandId,
    expressionFunctions,
    selectedExpressionFunctionId,
    syncAdminState,
    load,
    emitToast,
    onError: handleError,
  });

  watch(activeTab, (tab) => {
    if (tab === "workers") startWorkerRefresh();
    else stopWorkerRefresh();
  });
  watch([activeTab, publishRecords], ([tab, records]) => {
    if (tab === "publish" && records.some((record) => record.status === "queued" || record.status === "releasing")) startPublishRefresh();
    else stopPublishRefresh();
  });
  onMounted(() => {
    if (key.value) void unlock();
  });
  onBeforeUnmount(() => {
    stopWorkerRefresh();
    stopPublishRefresh();
  });

  async function unlock(): Promise<void> {
    if (loading.value) return;
    const candidate = key.value.trim();
    if (!candidate) {
      emitToast({ tone: "danger", message: "请输入后台密钥。" });
      return;
    }
    key.value = candidate;
    sessionStorage.setItem("skillhub.admin.key", candidate);
    if (await loadState()) {
      unlocked.value = true;
      return;
    }
    lock();
  }

  async function load(): Promise<void> {
    await loadState();
  }

  async function loadState(): Promise<boolean> {
    loading.value = true;
    try {
      const [
        nextSkills,
        nextGroups,
        nextTagGroups,
        nextTagCascades,
        nextRoles,
        nextPublishTargets,
        nextPublishGateChecks,
        nextPublishRecords,
        nextWorkerStatus,
        nextOpencodeAgents,
        nextProviderCatalog,
        nextSystemCommands,
        nextExpressionFunctions,
      ] = await Promise.all([
        api.adminListSkills(),
        api.adminListGroups(),
        api.adminListTagGroups(),
        api.adminListTagCascades(),
        api.adminListRoleAssignments(),
        api.adminListPublishTargets(),
        api.adminListPublishGateChecks(),
        api.adminListPublishRecords(),
        api.adminListWorkers(),
        api.adminListOpencodeAgents(),
        api.listOpencodeProviders().catch(() => null),
        api.adminListSystemCommands().then((response) => response.commands),
        api.adminListExpressionFunctions(),
      ]);
      skills.value = nextSkills;
      groups.value = nextGroups;
      tagGroups.value = nextTagGroups;
      tagCascadeActions.overview.value = nextTagCascades;
      roles.value = nextRoles;
      publishTargets.value = nextPublishTargets;
      publishGateChecks.value = nextPublishGateChecks;
      publishRecords.value = nextPublishRecords;
      workerStatus.value = nextWorkerStatus;
      opencodeAgents.value = nextOpencodeAgents;
      opencodeProviderCatalog.value = nextProviderCatalog;
      systemCommands.value = nextSystemCommands;
      expressionFunctions.value = nextExpressionFunctions;
      tagDrafts.value = Object.fromEntries(nextSkills.map((item) => [item.skill.id, toTagPayloads(item.skill.tags ?? [])]));
      if (!selectedGroupId.value && nextGroups.length) selectedGroupId.value = nextGroups[0].id;
      if (!selectedTagGroupId.value && nextTagGroups.length) selectedTagGroupId.value = nextTagGroups[0].id;
      if (!selectedOpencodeAgentId.value && nextOpencodeAgents.length) selectedOpencodeAgentId.value = nextOpencodeAgents[0].id;
      if (!nextSystemCommands.some((item) => item.id === selectedSystemCommandId.value)) {
        selectedSystemCommandId.value = nextSystemCommands[0]?.id ?? "";
      }
      if (!nextExpressionFunctions.some((item) => item.id === selectedExpressionFunctionId.value)) {
        selectedExpressionFunctionId.value = nextExpressionFunctions[0]?.id ?? "";
      }
      return true;
    } catch (error) {
      handleError(error);
      return false;
    } finally {
      loading.value = false;
    }
  }

  async function refreshWorkers(): Promise<void> {
    try {
      workerStatus.value = await api.adminListWorkers();
    } catch (error) {
      handleError(error);
    }
  }

  async function refreshPublishRecords(): Promise<void> {
    try {
      publishRecords.value = await api.adminListPublishRecords();
    } catch (error) {
      handleError(error);
    }
  }

  async function refreshOpencodeProviders(): Promise<void> {
    try {
      opencodeProviderCatalog.value = await api.listOpencodeProviders();
      emitToast({ tone: "success", message: "Provider/Model 列表已刷新。" });
    } catch (error) {
      handleError(error);
    }
  }

  async function selectAdminTab(tabId: AdminTab): Promise<void> {
    if (activeTab.value === tabId) return;
    activeTab.value = tabId;
    await load();
  }

  function handleError(error: unknown): void {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      lock();
      emitToast({ tone: "danger", message: "后台密钥无效，请重新输入。" });
      return;
    }
    const message = error instanceof ApiError || error instanceof Error ? error.message : "操作失败。";
    emitToast({ tone: "danger", message });
  }

  function lock(): void {
    sessionStorage.removeItem("skillhub.admin.key");
    unlocked.value = false;
    stopWorkerRefresh();
    stopPublishRefresh();
  }

  function startWorkerRefresh(): void {
    if (workerRefreshTimer !== undefined) return;
    workerRefreshTimer = window.setInterval(() => void refreshWorkers(), 5000);
  }

  function stopWorkerRefresh(): void {
    if (workerRefreshTimer === undefined) return;
    window.clearInterval(workerRefreshTimer);
    workerRefreshTimer = undefined;
  }

  function startPublishRefresh(): void {
    if (publishRefreshTimer !== undefined) return;
    publishRefreshTimer = window.setInterval(() => void refreshPublishRecords(), 3000);
  }

  function stopPublishRefresh(): void {
    if (publishRefreshTimer === undefined) return;
    window.clearInterval(publishRefreshTimer);
    publishRefreshTimer = undefined;
  }

  return {
    key, unlocked, loading, activeTab, skills, groups, tagGroups, roles, publishTargets, publishGateChecks,
    publishRecords, workerStatus, opencodeAgents, opencodeProviderCatalog, selectedGroupId, selectedTagGroupId,
    selectedOpencodeAgentId, tagDrafts, tagCascadeActions, adminActions, unlock, load, refreshWorkers,
    refreshPublishRecords, refreshOpencodeProviders, selectAdminTab, systemCommands, selectedSystemCommandId,
    expressionFunctions, selectedExpressionFunctionId,
  };
}
