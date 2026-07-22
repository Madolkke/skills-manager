<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref, watch } from "vue";
import IdentitySettingsModal from "./components/IdentitySettingsModal.vue";
import TaskCenterPanel from "./components/TaskCenterPanel.vue";
import Toast from "./components/Toast.vue";
import TopBar from "./components/TopBar.vue";
import WorkflowConfirmModal from "./features/workflow/components/WorkflowConfirmModal.vue";
import { api, ApiError } from "./lib/api";
import { getActorId } from "./lib/identity";
import { readRoute, writeRoute, type RouteState, type SkillTab } from "./lib/navigation";
import { buildTaskCenterGroups, taskCenterBadgeCount, type TaskCenterGroup, type TaskCenterItem } from "./lib/taskCenter";
import AdminPage from "./pages/AdminPage.vue";
import HubPage from "./pages/HubPage.vue";
import NewSkillModal from "./pages/NewSkillModal.vue";
import MyReviewsPage from "./pages/MyReviewsPage.vue";
import SkillBuilderPage from "./pages/SkillBuilderPage.vue";
import SkillPage from "./pages/SkillPage.vue";
import type { SessionInfo, SkillDetail, SkillSummary, ToastState } from "./types";

const WorkflowPage = defineAsyncComponent(() => import("./pages/WorkflowPage.vue"));

const route = ref<RouteState>(readRoute());
const skills = ref<SkillSummary[]>([]);
const skill = ref<SkillDetail | null>(null);
const session = ref<SessionInfo | null>(null);
const loading = ref(true);
const toast = ref<ToastState>(null);
const newSkillOpen = ref(false);
const identityOpen = ref(false);
const taskCenterOpen = ref(false);
const taskCenterGroups = ref<TaskCenterGroup[]>([]);
const taskCenterLoading = ref(false);
const taskCenterError = ref("");
const workflowDirty = ref(false);
const pendingWorkflowRoute = ref<RouteState | null>(null);

const actor = computed(() => session.value?.actor ?? getActorId());
const sectionShell = computed(() => (route.value.section === "workflows" || route.value.section === "skill-builder" ? "workflow-shell" : route.value.skillId ? "skill-shell" : "hub-shell"));
const shellClass = computed(() => `app-shell ${sectionShell.value}`);
const currentSkill = computed(() => ((route.value.section === "skills" || route.value.section === "workflows") && route.value.skillId ? skill.value : null));
const mainClass = computed(() => (route.value.section === "workflows" || route.value.section === "skill-builder" ? "workflow-shell-page" : "page-shell"));
const taskCount = computed(() => taskCenterBadgeCount(taskCenterGroups.value));

watch(() => [route.value.section, route.value.skillId] as const, () => void load(), { immediate: true });
watch(() => [actor.value, currentSkill.value?.skill.id ?? ""] as const, () => void loadTaskCenter(), { immediate: true });

onMounted(() => {
  window.addEventListener("popstate", syncRoute);
});

onUnmounted(() => {
  window.removeEventListener("popstate", syncRoute);
});

async function load(): Promise<void> {
  loading.value = true;
  try {
    const targetRoute = route.value;
    const [, list] = await Promise.all([api.getSession(), api.listSkills()]);
    session.value = { actor: getActorId(), subject_type: "user" };
    skills.value = list;
    if ((targetRoute.section === "skills" || targetRoute.section === "workflows") && targetRoute.skillId) {
      try {
        skill.value = await api.getSkill(targetRoute.skillId);
      } catch (error) {
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
    toast.value = { tone: "danger", message: errorMessage(error) };
  } finally {
    loading.value = false;
  }
}

function syncRoute(): void {
  const next = readRoute();
  if (blocksWorkflowNavigation(next)) {
    pendingWorkflowRoute.value = next;
    route.value = writeRoute(route.value);
    return;
  }
  workflowDirty.value = false;
  route.value = next;
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
  navigate({ section: "skills", tab, selectedCaseId: null, selectedRunId: null, selectedVersionId: null });
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

async function openTaskCenter(): Promise<void> {
  taskCenterOpen.value = true;
  await loadTaskCenter();
}

async function loadTaskCenter(): Promise<void> {
  taskCenterLoading.value = true;
  taskCenterError.value = "";
  try {
    const publishOverviewPromise = currentSkill.value ? api.getSkillPublishOverview(currentSkill.value.skill.id) : Promise.resolve(null);
    const [reviews, notifications, publishOverview] = await Promise.all([
      api.listMyReviews(),
      api.listMyNotifications(),
      publishOverviewPromise,
    ]);
    taskCenterGroups.value = buildTaskCenterGroups({ reviews, notifications, skill: currentSkill.value, publishOverview });
  } catch (error) {
    taskCenterError.value = errorMessage(error);
  } finally {
    taskCenterLoading.value = false;
  }
}

function openTaskItem(item: TaskCenterItem): void {
  taskCenterOpen.value = false;
  if (item.target === "reviews" || item.target === "notifications") {
    goMyReviews();
    return;
  }
  if (!currentSkill.value) return;
  navigate({ section: "skills", skillId: currentSkill.value.skill.id, tab: item.target, selectedCaseId: null, selectedRunId: null, selectedVersionId: null });
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
  navigate({ section: "skills", skillId, tab: "overview", selectedCaseId: null, selectedEvalSetId: null, selectedRunId: null, selectedVersionId: null });
}

function handleSkillDeleted(): void {
  const deletedSkillId = skill.value?.skill.id;
  skill.value = null;
  if (deletedSkillId) skills.value = skills.value.filter((item) => item.skill.id !== deletedSkillId);
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
        <AdminPage v-if="route.section === 'admin'" @toast="toast = $event" />
        <SkillPage
          v-else-if="route.section === 'skills' && route.skillId && skill"
          :skill="skill"
          :tab="route.tab"
          :route="route"
          @tab="setTab"
          @refresh="load"
          @navigate="navigate"
          @dirty="workflowDirty = $event"
          @toast="toast = $event"
        />
        <WorkflowPage
          v-else-if="route.section === 'workflows' && route.skillId && skill"
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
        <HubPage
          v-else
          :skills="skills"
          :actor="actor"
          :loading="loading"
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
      @close="taskCenterOpen = false"
      @open="openTaskItem"
      @refresh="loadTaskCenter"
    />
    <WorkflowConfirmModal
      v-if="pendingWorkflowRoute"
      title="离开 Workflow 编辑器"
      description="当前 Workflow 有未保存修改，离开后这些修改将丢失。"
      confirm-label="放弃并离开"
      tone="danger"
      @close="pendingWorkflowRoute = null"
      @confirm="confirmWorkflowNavigation"
    />
    <Toast :toast="toast" @close="toast = null" />
  </div>
</template>
