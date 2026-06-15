<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import Toast from "./components/Toast.vue";
import TopBar from "./components/TopBar.vue";
import { api, ApiError } from "./lib/api";
import { readRoute, writeRoute, type RouteState, type SkillTab } from "./lib/navigation";
import HubPage from "./pages/HubPage.vue";
import NewSkillModal from "./pages/NewSkillModal.vue";
import SkillPage from "./pages/SkillPage.vue";
import WorkflowPage from "./pages/WorkflowPage.vue";
import type { SessionInfo, SkillDetail, SkillSummary, ToastState } from "./types";

const route = ref<RouteState>(readRoute());
const skills = ref<SkillSummary[]>([]);
const skill = ref<SkillDetail | null>(null);
const session = ref<SessionInfo | null>(null);
const loading = ref(true);
const toast = ref<ToastState>(null);
const newSkillOpen = ref(false);

const actor = computed(() => session.value?.actor ?? "product-operator");
const sectionShell = computed(() => (route.value.section === "workflows" ? "workflow-shell" : route.value.skillId ? "skill-shell" : "hub-shell"));
const shellClass = computed(() => `app-shell ${sectionShell.value}`);
const currentSkill = computed(() => (route.value.section === "skills" && route.value.skillId ? skill.value : null));
const mainClass = computed(() => (route.value.section === "workflows" ? "workflow-shell-page" : "page-shell"));

watch(() => [route.value.section, route.value.skillId] as const, () => void load(), { immediate: true });

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
    const [sessionInfo, list] = await Promise.all([api.getSession(), api.listSkills()]);
    session.value = sessionInfo;
    skills.value = list;
    if (targetRoute.section === "skills" && targetRoute.skillId) {
      try {
        skill.value = await api.getSkill(targetRoute.skillId);
      } catch (error) {
        if (isMissingSkillError(error)) {
          skill.value = null;
          toast.value = { tone: "info", message: "当前 Skill 已不存在，已返回列表。" };
          route.value = writeRoute({ section: "hub", skillId: null, tab: "overview", selectedCaseId: null, selectedVersionId: null, selectedRunId: null });
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
  route.value = readRoute();
}

function navigate(next: Partial<RouteState>): void {
  route.value = writeRoute(next);
}

function openSkill(skillId: string): void {
  navigate({ section: "skills", skillId, tab: "overview", selectedCaseId: null, selectedRunId: null, selectedVersionId: null });
}

function setTab(tab: SkillTab): void {
  navigate({ section: "skills", tab, selectedCaseId: null, selectedRunId: null, selectedVersionId: null });
}

function goHome(): void {
  navigate({ section: "hub", skillId: null, tab: "overview", selectedCaseId: null, selectedVersionId: null, selectedRunId: null });
}

function goWorkflows(): void {
  navigate({ section: "workflows", skillId: null, tab: "overview", selectedCaseId: null, selectedRunId: null, selectedVersionId: null });
}

function handleSkillCreated(skillId: string): void {
  newSkillOpen.value = false;
  toast.value = { tone: "success", message: "Skill 已创建。" };
  navigate({ section: "skills", skillId, tab: "overview", selectedCaseId: null, selectedRunId: null, selectedVersionId: null });
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
        @home="goHome"
        @create="newSkillOpen = true"
        @workflows="goWorkflows"
      />
      <main :class="mainClass">
        <SkillPage
          v-if="route.section === 'skills' && route.skillId && skill"
          :skill="skill"
          :tab="route.tab"
          :route="route"
          @tab="setTab"
          @refresh="load"
          @navigate="navigate"
          @toast="toast = $event"
        />
        <WorkflowPage v-else-if="route.section === 'workflows'" @back="goHome" />
        <HubPage
          v-else
          :skills="skills"
          :actor="actor"
          :loading="loading"
          @open-skill="openSkill"
          @create="newSkillOpen = true"
          @open-workflows="goWorkflows"
        />
      </main>
    </div>
    <NewSkillModal v-if="newSkillOpen" :actor="actor" @close="newSkillOpen = false" @created="handleSkillCreated" />
    <Toast :toast="toast" @close="toast = null" />
  </div>
</template>
