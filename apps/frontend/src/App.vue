<script setup lang="ts">
import { computed, nextTick, defineAsyncComponent, onMounted, onUnmounted, ref, watch } from "vue";
import IdentitySettingsModal from "./components/IdentitySettingsModal.vue";
import TaskCenterPanel from "./components/TaskCenterPanel.vue";
import Toast from "./components/Toast.vue";
import TopBar from "./components/TopBar.vue";
import { useTaskCenter } from "./composables/useTaskCenter";
import WorkflowConfirmModal from "./features/workflow/components/WorkflowConfirmModal.vue";
import { paginationApi, type SkillCore } from "./lib/api/paginationApi";
import { api, ApiError } from "./lib/api";
import { appFeatures } from "./lib/appFeatures";
import { getActorId } from "./lib/identity";
import { readRoute, replaceRoute, writeRoute, type RouteState, type SkillTab } from "./lib/navigation";
import AdminPage from "./pages/AdminPage.vue";
import HubPage from "./pages/HubPage.vue";
import NewSkillModal from "./pages/NewSkillModal.vue";
import MyReviewsPage from "./pages/MyReviewsPage.vue";
import SkillBuilderPage from "./pages/SkillBuilderPage.vue";
import { useSkillVisit } from "./features/analytics/useSkillVisit";
import SkillPage from "./pages/SkillPage.vue";
import type { SessionInfo, ToastState } from "./types";

const WorkflowPage = defineAsyncComponent(() => import("./pages/WorkflowPage.vue"));

const evaluationsVisible = appFeatures.evaluationsVisible;
const route = ref<RouteState>(routeFromLocation());

const skill = ref<SkillCore | null>(null);
const session = ref<SessionInfo | null>(null);
const loading = ref(true);
const toast = ref<ToastState>(null);
const newSkillOpen = ref(false);
const identityOpen = ref(false);
const workflowDirty = ref(false);
const pendingWorkflowRoute = ref<RouteState | null>(null);

const actor = computed(() => session.value?.actor ?? getActorId());
const sectionShell = computed(() => (route.value.section === "workflows" || route.value.section === "skill-builder" ? "workflow-shell" : route.value.skillId ? "skill-shell" : "hub-shell"));
const shellClass = computed(() => `app-shell ${sectionShell.value}`);
const currentSkill = computed(() => ((route.value.section === "skills" || route.value.section === "workflows") && route.value.skillId ? skill.value : null));
const mainClass = computed(() => (route.value.section === "workflows" || route.value.section === "skill-builder" ? "workflow-shell-page" : "page-shell"));
const {
  open: taskCenterOpen,
  groups: taskCenterGroups,
  loading: taskCenterLoading,
  error: taskCenterError,
  badgeCount: taskCount,
  show: openTaskCenter,
  load: loadTaskCenter,
  openItem: openTaskItem,
} = useTaskCenter({
  actor,
  currentSkill,
  evaluationsVisible,
  errorMessage,
  openReviews: goMyReviews,
  openSkillTab: (skillId, tab) => navigate({ section: "skills", skillId, tab, selectedCaseId: null, selectedRunId: null, selectedVersionId: null }),
});

const visits = useSkillVisit(route);
let loadSequence = 0;

watch(() => [route.value.section, route.value.skillId] as const, () => void load(), { immediate: true });

onMounted(() => {
  window.addEventListener("popstate", syncRoute);
});

onUnmounted(() => {
  window.removeEventListener("popstate", syncRoute);
});

async function load(): Promise<void> {
  const sequence = ++loadSequence;
  const entryToken = visits.token();
  const targetRoute = route.value;
  loading.value = true;
  if (skill.value?.skill.id !== targetRoute.skillId) skill.value = null;
  try {
    await api.getSession();
    if (sequence !== loadSequence) return;
    session.value = { actor: getActorId(), subject_type: "user" };
    if ((targetRoute.section === "skills" || targetRoute.section === "workflows") && targetRoute.skillId) {
      try {
        const detail = await paginationApi.core(targetRoute.skillId);
        if (sequence !== loadSequence) return;
        skill.value = detail;
        await nextTick();
        if (sequence === loadSequence) void visits.displayed(detail.skill.id, entryToken);
      } catch (error) {
        if (sequence !== loadSequence) return;
        if (isMissingSkillError(error)) {
          skill.value = null;
          toast.value = { tone: "info", message: "当前 Skill 已不存在，已返回列表。" };
          route.value = writeRoute({
            section: "hub",
            skillId: null,
            tab: "overview",
            selectedCaseId: null,
            selectedEvalSetId: null,
            selectedVersionId: null,
            selectedRunId: null,
          });
          return;
        }
        throw error;
      }
    } else {
      skill.value = null;
    }
  } catch (error) {
    if (sequence === loadSequence) toast.value = { tone: "danger", message: errorMessage(error) };
  } finally {
    if (sequence === loadSequence) loading.value = false;
  }
}

function syncRoute(): void {
  const next = routeFromLocation();
  if (blocksWorkflowNavigation(next)) {
    pendingWorkflowRoute.value = next;
    route.value = writeRoute(route.value);
    return;
  }
  workflowDirty.value = false;
  route.value = next;
}

function routeFromLocation(): RouteState {
  const next = readRoute(evaluationsVisible);
  return evaluationsVisible ? next : replaceRoute(next, evaluationsVisible);
}

function navigate(next: Partial<RouteState>): void {
  const target = { ...route.value, ...next };
  if (blocksWorkflowNavigation(target)) {
    pendingWorkflowRoute.value = target;
    return;
  }
  workflowDirty.value = false;
  route.value = writeRoute(next);
}

function confirmWorkflowNavigation(): void {
  const target = pendingWorkflowRoute.value;
  pendingWorkflowRoute.value = null;
  if (!target) return;
  workflowDirty.value = false;
  route.value = writeRoute(target);
}

function blocksWorkflowNavigation(next: RouteState): boolean {
  const inWorkflowEditor = route.value.section === "workflows";
  const inWorkflowTab = route.value.section === "skills" && route.value.tab === "workflow";
  return workflowDirty.value
    && (inWorkflowEditor || inWorkflowTab)
    && (next.section !== route.value.section || next.skillId !== route.value.skillId || next.tab !== route.value.tab);
}

function openSkill(skillId: string): void {
  navigate({ section: "skills", skillId, tab: "overview", selectedCaseId: null, selectedEvalSetId: null, selectedRunId: null, selectedVersionId: null });
}

function setTab(tab: SkillTab): void {
  navigate({ section: "skills", tab, selectedCaseId: null, selectedRunId: null, selectedVersionId: null, selectedReviewId: null });
}

function goHome(): void {
  navigate({ section: "hub", skillId: null, tab: "overview", selectedCaseId: null, selectedEvalSetId: null, selectedVersionId: null, selectedRunId: null });
}

function openWorkflow(skillId: string): void {
  navigate({ section: "workflows", skillId, tab: "workflow", selectedCaseId: null, selectedEvalSetId: null, selectedRunId: null, selectedVersionId: null });
}

function goSkillBuilder(): void {
  navigate({ section: "skill-builder", skillId: null, tab: "overview", selectedCaseId: null, selectedEvalSetId: null, selectedRunId: null, selectedVersionId: null });
}

function goMyReviews(): void {
  navigate({ section: "my-reviews", skillId: null, tab: "overview", selectedCaseId: null, selectedEvalSetId: null, selectedRunId: null, selectedVersionId: null });
}

function handleIdentityChanged(nextActor: string): void {
  session.value = { actor: nextActor, subject_type: "user" };
  identityOpen.value = false;
  toast.value = { tone: "success", message: "身份已切换。" };
  void load();
}

function handleSkillCreated(skillId: string): void {
  newSkillOpen.value = false;
  toast.value = { tone: "success", message: "Skill 已创建。" };
  navigate({ section: "skills", skillId, tab: "overview", selectedCaseId: null, selectedEvalSetId: null, selectedRunId: null, selectedVersionId: null, selectedReviewId: null });
}

function handleSkillDeleted(): void {
  skill.value = null;

  taskCenterOpen.value = false;
  taskCenterGroups.value = [];
  workflowDirty.value = false;
  toast.value = { tone: "success", message: "Skill 已永久删除。" };
  goHome();
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "操作失败，请稍后重试。";
}

function isMissingSkillError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404 && error.message.startsWith("Skill not found:");
}
</script>

<template>
  <div :class="shellClass">
    <div class="app-main">
      <TopBar
        :actor="actor"
        :current-skill="currentSkill"
        :task-count="taskCount"
        @home="goHome"
        @create="newSkillOpen = true"
        @builder="goSkillBuilder"
        @settings="identityOpen = true"
        @reviews="goMyReviews"
        @tasks="openTaskCenter"
      />
      <main :class="mainClass">
        <AdminPage v-if="route.section === 'admin'" :key="actor" @toast="toast = $event" />
        <SkillPage
          v-else-if="route.section === 'skills' && route.skillId && skill"
          :key="skill.skill.id"
          :skill="skill"
          :tab="route.tab"
          :route="route"
          :evaluations-visible="evaluationsVisible"
          @tab="setTab"
          @refresh="load"
          @navigate="navigate"
          @dirty="workflowDirty = $event"
          @toast="toast = $event"
        />
        <WorkflowPage
          v-else-if="route.section === 'workflows' && route.skillId && skill"
          :key="skill.skill.id"
          :skill="skill"
          @back="navigate({ section: 'skills', skillId: skill.skill.id, tab: 'workflow' })"
          @refresh="load"
          @dirty="workflowDirty = $event"
          @toast="toast = $event"
          @deleted="handleSkillDeleted"
        />
        <SkillBuilderPage
          v-else-if="route.section === 'skill-builder'"
          @created="handleSkillCreated"
          @toast="toast = $event"
        />
        <MyReviewsPage
          v-else-if="route.section === 'my-reviews'"
          :actor="actor"
          @open-skill="openSkill"
          @toast="toast = $event"
        />
        <section v-else-if="route.skillId && (route.section === 'skills' || route.section === 'workflows')" class="primary-panel" aria-live="polite">
          <p>{{ loading ? '正在加载 Skill…' : 'Skill 加载失败，请重试。' }}</p>
          <button v-if="!loading" class="secondary-button" type="button" @click="load">重试</button>
        </section>
        <HubPage
          v-else
          :actor="actor"
          :loading="loading"
          :evaluations-visible="evaluationsVisible"
          @open-skill="openSkill"
          @open-workflow="openWorkflow"
          @create="newSkillOpen = true"
        />
      </main>
    </div>
    <NewSkillModal v-if="newSkillOpen" :actor="actor" @close="newSkillOpen = false" @created="handleSkillCreated" />
    <IdentitySettingsModal v-if="identityOpen" :actor="actor" @close="identityOpen = false" @changed="handleIdentityChanged" />
    <TaskCenterPanel
      v-if="taskCenterOpen"
      :badge-count="taskCount"
      :error="taskCenterError"
      :groups="taskCenterGroups"
      :loading="taskCenterLoading"
      :evaluations-visible="evaluationsVisible"
      @close="taskCenterOpen = false"
      @open="openTaskItem"
      @refresh="loadTaskCenter"
    />
    <WorkflowConfirmModal
      v-if="pendingWorkflowRoute"
      title="离开 Workflow 编辑器"
      description="当前 Workflow 的修改尚未保存。离开后将无法恢复这些内容。"
      confirm-label="放弃并离开"
      tone="danger"
      @close="pendingWorkflowRoute = null"
      @confirm="confirmWorkflowNavigation"
    />
    <Toast :toast="toast" @close="toast = null" />
  </div>
</template>
