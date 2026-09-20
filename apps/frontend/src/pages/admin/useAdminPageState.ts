import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ADMIN_TABS, type AdminTab } from "../../lib/admin";
import { api, ApiError, type AdminGroup } from "../../lib/api";
import { paginationApi, type AdminOverview } from "../../lib/api/paginationApi";
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
  const requestedTab = new URLSearchParams(location.search).get("admin_tab");
  const activeTab = ref<AdminTab>(ADMIN_TABS.find(tab => tab.id === requestedTab)?.id ?? "overview");
  function restoreTab() { const requested = new URLSearchParams(location.search).get("admin_tab"); activeTab.value = ADMIN_TABS.find(tab => tab.id === requested)?.id ?? "overview"; }
  window.addEventListener("popstate", restoreTab);
  const skills = ref<SkillSummary[]>([]);
  const overview = ref<AdminOverview | null>(null);
  const refreshToken = ref(0);
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
  let authEpoch = 0;
  let requestEpoch = 0;
  const stale = Symbol("stale admin request");
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
    const url = new URL(location.href); url.searchParams.set("admin_tab", tab); if (url.href !== location.href) history.pushState(history.state, "", url);
    if (unlocked.value && tab !== "analytics") void load();
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
    authEpoch++; requestEpoch++;
    stopWorkerRefresh();
    stopPublishRefresh();
    window.removeEventListener("popstate", restoreTab);
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
    if (activeTab.value === "analytics") {
      const epoch = authEpoch;
      try { await paginationApi.overview(); if (epoch === authEpoch) unlocked.value = true; } catch (error) { if (epoch === authEpoch) handleError(error); }
      return;
    }
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
    const epoch = ++requestEpoch;
    /** 在赋值前拒绝过期响应，退出后台后不恢复缓存。 */
    async function current<T>(request: Promise<T>): Promise<T> {
      const result = await request;
      if (epoch !== requestEpoch) throw stale;
      return result;
    }
    loading.value = true;
    try {
      const tab = activeTab.value;
      if (tab === "overview") overview.value = await current(paginationApi.overview());
      if (["tag-groups", "tag-cascades", "skill-tags", "roles"].includes(tab)) tagGroups.value = await current(api.adminListTagGroups());
      if (tab === "groups") groups.value = await current(api.adminListGroups());
      if (tab === "tag-cascades") tagCascadeActions.overview.value = await current(api.adminListTagCascades());
      if (tab === "publish") publishRecords.value = await current(api.adminListPublishRecords());
      if (tab === "publish-targets") [publishTargets.value, publishGateChecks.value] = await current(Promise.all([api.adminListPublishTargets(), api.adminListPublishGateChecks()]));
      if (tab === "workers") workerStatus.value = await current(api.adminListWorkers());
      if (tab === "opencode-agents") {
        [opencodeAgents.value, opencodeProviderCatalog.value] = await current(Promise.all([api.adminListOpencodeAgents(), api.listOpencodeProviders().catch(() => null)]));
        if (!selectedOpencodeAgentId.value) selectedOpencodeAgentId.value = opencodeAgents.value[0]?.id ?? "";
      }
      if (tab === "system-commands") {
        systemCommands.value = (await current(api.adminListSystemCommands())).commands;
        if (!systemCommands.value.some(item => item.id === selectedSystemCommandId.value)) selectedSystemCommandId.value = systemCommands.value[0]?.id ?? "";
      }
      if (tab === "expression-functions") {
        expressionFunctions.value = await current(api.adminListExpressionFunctions());
        if (!expressionFunctions.value.some(item => item.id === selectedExpressionFunctionId.value)) selectedExpressionFunctionId.value = expressionFunctions.value[0]?.id ?? "";
      }
      if (!selectedGroupId.value) selectedGroupId.value = groups.value[0]?.id ?? "";
      if (!selectedTagGroupId.value) selectedTagGroupId.value = tagGroups.value[0]?.id ?? "";
      refreshToken.value++;
      return true;
    } catch (error) {
      if (epoch === requestEpoch && error !== stale) handleError(error);
      return false;
    } finally {
      if (epoch === requestEpoch) loading.value = false;
    }
  }

  async function refreshWorkers(): Promise<void> {
    const epoch = authEpoch;
    try {
      const result = await api.adminListWorkers();
      if (epoch !== authEpoch || !unlocked.value) return;
      workerStatus.value = result;
    } catch (error) {
      if (epoch === authEpoch && unlocked.value) handleError(error);
    }
  }

  async function refreshPublishRecords(): Promise<void> {
    const epoch = authEpoch;
    try {
      const result = await api.adminListPublishRecords();
      if (epoch !== authEpoch || !unlocked.value) return;
      publishRecords.value = result;
    } catch (error) {
      if (epoch === authEpoch && unlocked.value) handleError(error);
    }
  }

  async function refreshOpencodeProviders(): Promise<void> {
    const epoch = authEpoch;
    try {
      const result = await api.listOpencodeProviders();
      if (epoch !== authEpoch || !unlocked.value) return;
      opencodeProviderCatalog.value = result;
      emitToast({ tone: "success", message: "Provider/Model 列表已刷新。" });
    } catch (error) {
      if (epoch === authEpoch && unlocked.value) handleError(error);
    }
  }

  async function selectAdminTab(tabId: AdminTab): Promise<void> {
    if (activeTab.value === tabId) return;
    activeTab.value = tabId;
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
    authEpoch++; requestEpoch++; loading.value = false;
    unlocked.value = false;
    tagDrafts.value = {}; skills.value = []; roles.value = []; overview.value = null;
    groups.value = []; tagGroups.value = []; publishTargets.value = []; publishGateChecks.value = []; publishRecords.value = [];
    workerStatus.value = null; opencodeAgents.value = []; opencodeProviderCatalog.value = null;
    systemCommands.value = []; expressionFunctions.value = []; tagCascadeActions.overview.value = null; tagCascadeActions.focus.value = null;
    selectedGroupId.value = ""; selectedTagGroupId.value = ""; selectedOpencodeAgentId.value = "";
    selectedSystemCommandId.value = ""; selectedExpressionFunctionId.value = "";
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
    overview, refreshToken, key, unlocked, loading, activeTab, skills, groups, tagGroups, roles, publishTargets, publishGateChecks,
    publishRecords, workerStatus, opencodeAgents, opencodeProviderCatalog, selectedGroupId, selectedTagGroupId,
    selectedOpencodeAgentId, tagDrafts, tagCascadeActions, adminActions, unlock, load, refreshWorkers,
    refreshPublishRecords, refreshOpencodeProviders, selectAdminTab, systemCommands, selectedSystemCommandId,
    expressionFunctions, selectedExpressionFunctionId,
  };
}
