<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { ADMIN_TABS, type AdminTab } from "../lib/admin";
import { api, ApiError, type AdminGroup } from "../lib/api";
import { toTagPayloads } from "../lib/skillTags";
import type { OpencodeAgent, OpencodeProviderCatalog, PublishGateCheckDefinition, PublishRecord, PublishTarget, RoleAssignment, SkillSummary, SkillTagPayload, TagGroup, WorkerStatusOverview } from "../types";
import { createAdminStateSync } from "./admin/adminStateSync";
import AdminGroupsTab from "./admin/AdminGroupsTab.vue";
import AdminOpencodeAgentsTab from "./admin/AdminOpencodeAgentsTab.vue";
import AdminOverviewTab from "./admin/AdminOverviewTab.vue";
import AdminPublishTab from "./admin/AdminPublishTab.vue";
import AdminPublishTargetsTab from "./admin/AdminPublishTargetsTab.vue";
import AdminRoleAssignmentsTab from "./admin/AdminRoleAssignmentsTab.vue";
import AdminSkillTagsTab from "./admin/AdminSkillTagsTab.vue";
import AdminTagGroupsTab from "./admin/AdminTagGroupsTab.vue";
import AdminTagCascadesTab from "./admin/AdminTagCascadesTab.vue";
import AdminWorkersTab from "./admin/AdminWorkersTab.vue";
import { useAdminActions } from "./admin/useAdminActions";
import { useAdminTagCascades } from "./admin/useAdminTagCascades";

const emit = defineEmits<{ toast: [toast: { tone: "success" | "danger" | "info"; message: string } | null] }>();

const key = ref(sessionStorage.getItem("skillhub.admin.key") || "");
const unlocked = ref(Boolean(key.value));
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
const selectedGroupId = ref("");
const selectedTagGroupId = ref("");
const selectedOpencodeAgentId = ref("");
const tagDrafts = ref<Record<string, SkillTagPayload[]>>({});
const tagCascadeActions = useAdminTagCascades({
  activeTab,
  emitToast: (toast) => emit("toast", toast),
});
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
  syncAdminState,
  load,
  emitToast: (toast) => emit("toast", toast),
});
let workerRefreshTimer: number | undefined;

watch(activeTab, (tab) => {
  if (tab === "workers") startWorkerRefresh();
  else stopWorkerRefresh();
});

onBeforeUnmount(stopWorkerRefresh);

async function unlock(): Promise<void> {
  sessionStorage.setItem("skillhub.admin.key", key.value.trim());
  unlocked.value = true;
  await load();
}

async function load(): Promise<void> {
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
    tagDrafts.value = Object.fromEntries(nextSkills.map((item) => [item.skill.id, toTagPayloads(item.skill.tags ?? [])]));
    if (!selectedGroupId.value && nextGroups.length) selectedGroupId.value = nextGroups[0].id;
    if (!selectedTagGroupId.value && nextTagGroups.length) selectedTagGroupId.value = nextTagGroups[0].id;
    if (!selectedOpencodeAgentId.value && nextOpencodeAgents.length) selectedOpencodeAgentId.value = nextOpencodeAgents[0].id;
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function refreshWorkers(): Promise<void> {
  try {
    workerStatus.value = await api.adminListWorkers();
  } catch (error) {
    showError(error);
  }
}

async function refreshOpencodeProviders(): Promise<void> {
  try {
    opencodeProviderCatalog.value = await api.listOpencodeProviders();
    emit("toast", { tone: "success", message: "Provider/Model 列表已刷新。" });
  } catch (error) {
    showError(error);
  }
}

async function selectAdminTab(tabId: AdminTab): Promise<void> {
  if (activeTab.value === tabId) return;
  activeTab.value = tabId;
  await load();
}

function startWorkerRefresh(): void {
  if (workerRefreshTimer !== undefined) return;
  workerRefreshTimer = window.setInterval(() => {
    void refreshWorkers();
  }, 5000);
}

function stopWorkerRefresh(): void {
  if (workerRefreshTimer === undefined) return;
  window.clearInterval(workerRefreshTimer);
  workerRefreshTimer = undefined;
}

function showError(error: unknown): void {
  const message = error instanceof ApiError || error instanceof Error ? error.message : "操作失败。";
  emit("toast", { tone: "danger", message });
}
</script>

<template>
  <div class="admin-page">
    <section v-if="!unlocked" class="primary-panel admin-login">
      <h1>后台管理</h1>
      <p>输入后台密钥后访问管理能力。这个入口不属于普通权限体系。</p>
      <label class="field-label">
        <span>后台密钥</span>
        <input v-model="key" type="password" @keydown.enter="unlock" />
      </label>
      <button class="primary-button" type="button" @click="unlock">进入后台</button>
    </section>

    <template v-else>
      <div class="skill-nav-row admin-nav-row">
        <nav class="skill-tabs" aria-label="后台管理分类">
          <button
            v-for="tab in ADMIN_TABS"
            :key="tab.id"
            type="button"
            :class="['skill-tab', { active: activeTab === tab.id }]"
            @click="selectAdminTab(tab.id)"
          >
            {{ tab.label }}
          </button>
        </nav>
        <button class="secondary-button" type="button" :disabled="loading" @click="load">{{ loading ? "刷新中..." : "刷新" }}</button>
      </div>

      <Transition name="fade-slide" mode="out-in">
        <AdminOverviewTab v-if="activeTab === 'overview'" key="overview" :skills="skills" :groups="groups" :tag-groups="tagGroups" :roles="roles" />
        <AdminGroupsTab
          v-else-if="activeTab === 'groups'"
          key="groups"
          :groups="groups"
          :selected-group-id="selectedGroupId"
          @select="selectedGroupId = $event"
          @create="adminActions.createGroup"
          @update="adminActions.updateGroup"
          @delete="adminActions.deleteGroup"
          @add-member="adminActions.addGroupMember"
          @remove-member="adminActions.removeGroupMember"
        />
        <AdminTagGroupsTab
          v-else-if="activeTab === 'tag-groups'"
          key="tag-groups"
          :tag-groups="tagGroups"
          :selected-tag-group-id="selectedTagGroupId"
          @select="selectedTagGroupId = $event"
          @create-group="adminActions.createTagGroup"
          @update-group="adminActions.updateTagGroup"
          @delete-group="adminActions.deleteTagGroup"
          @create-value="adminActions.createTagValue"
          @update-value="adminActions.updateTagValue"
          @delete-value="adminActions.deleteTagValue"
        />
        <AdminRoleAssignmentsTab
          v-else-if="activeTab === 'roles'"
          key="roles"
          :roles="roles"
          :tag-groups="tagGroups"
          :skills="skills"
          @assign="adminActions.assignRole"
          @revoke="adminActions.revokeRole"
          @toast="emit('toast', { tone: 'danger', message: $event })"
        />
        <AdminTagCascadesTab
          v-else-if="activeTab === 'tag-cascades'"
          key="tag-cascades"
          :tag-groups="tagGroups"
          :overview="tagCascadeActions.overview.value"
          @attach="tagCascadeActions.attach"
          @detach="tagCascadeActions.detach"
          @inspect="tagCascadeActions.inspect"
        />
        <AdminSkillTagsTab
          v-else-if="activeTab === 'skill-tags'"
          key="skill-tags"
          :skills="skills"
          :tag-groups="tagGroups"
          :tag-drafts="tagDrafts"
          :focus="tagCascadeActions.focus.value"
          @update-draft="(skillId, tags) => { tagDrafts[skillId] = tags; }"
          @save="adminActions.saveSkillTags"
          @clear-focus="tagCascadeActions.focus.value = null"
        />
        <AdminWorkersTab
          v-else-if="activeTab === 'workers'"
          key="workers"
          :overview="workerStatus"
          :loading="loading"
          @refresh="refreshWorkers"
        />
        <AdminOpencodeAgentsTab
          v-else-if="activeTab === 'opencode-agents'"
          key="opencode-agents"
          :agents="opencodeAgents"
          :providers="opencodeProviderCatalog"
          :selected-agent-id="selectedOpencodeAgentId"
          @select="selectedOpencodeAgentId = $event"
          @refresh-providers="refreshOpencodeProviders"
          @create="adminActions.createOpencodeAgent"
          @update="adminActions.updateOpencodeAgent"
          @delete="adminActions.deleteOpencodeAgent"
        />
        <AdminPublishTargetsTab
          v-else-if="activeTab === 'publish-targets'"
          key="publish-targets"
          :targets="publishTargets"
          :checks="publishGateChecks"
          @update="adminActions.updatePublishTarget"
        />
        <AdminPublishTab
          v-else
          key="publish"
          :records="publishRecords"
          @confirm-record="adminActions.confirmPublishRecord"
          @cancel-record="adminActions.cancelPublishRecord"
          @batch-confirm="adminActions.batchConfirmPublishRecords"
          @batch-cancel="adminActions.batchCancelPublishRecords"
        />
      </Transition>
    </template>
  </div>
</template>
