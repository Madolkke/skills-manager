<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import BuilderChatPanel from "../features/skill-builder/components/BuilderChatPanel.vue";
import BuilderLoadAlert from "../features/skill-builder/components/BuilderLoadAlert.vue";
import BuilderNewSessionConfirmModal from "../features/skill-builder/components/BuilderNewSessionConfirmModal.vue";
import BuilderSubmitSkillModal from "../features/skill-builder/components/BuilderSubmitSkillModal.vue";
import BuilderTopToolbar from "../features/skill-builder/components/BuilderTopToolbar.vue";
import BuilderWorkspaceDropdown from "../features/skill-builder/components/BuilderWorkspaceDropdown.vue";
import { useBuilderProviderSelection } from "../features/skill-builder/composables/useBuilderProviderSelection";
import { builderSessionStatusText, builderWorkspaceFilesFromSession, builderWorkspacePayload, validateBuilderWorkspaceFiles } from "../features/skill-builder/lib/builderUi";
import { api, ApiError } from "../lib/api";
import { defaultSkillBundleDraftFile, SKILL_ENTRY_PATH, type SkillBundleDraftFile } from "../lib/skillBundleDraft";
import type { SkillBuilderDraftFile, SkillBuilderSession, SkillTagPayload, TagGroup } from "../types";

const emit = defineEmits<{ created: [skillId: string]; toast: [toast: { tone: "success" | "danger" | "info"; message: string }] }>();

const session = ref<SkillBuilderSession | null>(null);
const tagGroups = ref<TagGroup[]>([]);
const workspaceFiles = ref<SkillBundleDraftFile[]>([]);
const tags = ref<SkillTagPayload[]>([]);
const version = ref("0.0.1");
const message = ref("");
const sending = ref(false);
const savingWorkspace = ref(false);
const workspaceDirty = ref(false);
const workspaceOpen = ref(false);
const confirmNewSessionOpen = ref(false);
const creating = ref(false);
const submitOpen = ref(false);
const error = ref("");
const loadFailed = ref(false);
const providerLoadError = ref("");
const pollTimer = ref<number | null>(null);
const { providerCatalog, selection, providerOptions, modelOptions, selectProvider, selectModel } = useBuilderProviderSelection();

const validation = computed(() => validateBuilderWorkspaceFiles(workspaceFiles.value));
const canSend = computed(() => Boolean(session.value && message.value.trim() && !sending.value && session.value.status !== "running" && session.value.status !== "created"));
const canSaveWorkspace = computed(() => Boolean(session.value && !savingWorkspace.value && workspaceDirty.value && validation.value.valid && session.value.status !== "running" && session.value.status !== "created"));
const canCreateSession = computed(() => !newSessionDisabledReason.value);
const canOpenWorkspace = computed(() => Boolean(session.value));
const canOpenSubmit = computed(() => Boolean(session.value && workspaceFiles.value.length > 0 && validation.value.valid && session.value.status !== "running" && session.value.status !== "created" && !savingWorkspace.value));
const submitDisabledReason = computed(() => {
  if (!session.value) return "当前没有可提交的会话。";
  if (session.value.status === "running") return "Agent 正在运行，完成后才能提交。";
  if (session.value.status === "created") return "该会话已经创建过 Skill。";
  if (savingWorkspace.value) return "工作区正在保存。";
  if (!workspaceFiles.value.length) return "工作区还没有可提交的文件。";
  if (!validation.value.valid) return validation.value.globalErrors[0] || Object.values(validation.value.errors)[0] || "工作区文件需要先修正。";
  return "";
});
const newSessionDisabledReason = computed(() => {
  if (session.value?.status === "running") return "Agent 正在运行，完成后才能覆盖会话。";
  if (sending.value) return "消息正在发送。";
  if (savingWorkspace.value) return "工作区正在保存。";
  if (creating.value) return "Skill 正在创建。";
  return "";
});
const workspaceButtonText = computed(() => {
  if (!session.value) return "查看工作区";
  if (!validation.value.valid) return "工作区 · 需修正";
  if (workspaceDirty.value) return "工作区 · 未保存";
  if (!workspaceFiles.value.some((file) => file.path.trim() === SKILL_ENTRY_PATH)) return "工作区 · 缺少 SKILL.md";
  return `工作区 · ${workspaceFiles.value.length} 个文件`;
});
const statusText = computed(() => builderSessionStatusText(session.value));
const runningSince = computed(() => (session.value?.status === "running" ? session.value.updated_at ?? null : null));

onMounted(loadInitial);
onUnmounted(stopPolling);
watch(() => session.value?.status, (status) => (status === "running" ? startPolling() : stopPolling()));

async function loadInitial(): Promise<void> {
  error.value = "";
  loadFailed.value = false;
  providerLoadError.value = "";
  try {
    const providersTask = api.listOpencodeProviders().then((providers) => {
      providerCatalog.value = providers;
    }).catch(() => {
      providerCatalog.value = { providers: [] };
      providerLoadError.value = "无法读取 provider/model，可继续使用 Opencode 默认配置。";
    });
    const [sessions, groups] = await Promise.all([api.listSkillBuilderSessions(), api.listTagGroups()]);
    tagGroups.value = groups;
    if (sessions[0]) applySession(await api.getSkillBuilderSession(sessions[0].id));
    else await createSession();
    await providersTask;
  } catch (caught) {
    loadFailed.value = true;
    error.value = errorMessage(caught, "无法加载 AI 创建会话，请确认 SkillHub 后端服务可用。");
  }
}

function requestCreateSession(): void {
  if (!canCreateSession.value) {
    error.value = newSessionDisabledReason.value;
    return;
  }
  if (session.value) confirmNewSessionOpen.value = true;
  else void createSession();
}

async function createSession(): Promise<void> {
  error.value = "";
  stopPolling();
  try {
    const created = await api.createSkillBuilderSession({ title: "新的 Skill 创建会话" });
    message.value = "";
    version.value = "0.0.1";
    tags.value = [];
    submitOpen.value = false;
    workspaceOpen.value = false;
    confirmNewSessionOpen.value = false;
    applySession(created);
  } catch (caught) {
    error.value = errorMessage(caught);
  }
}

async function send(): Promise<void> {
  if (!session.value || !message.value.trim()) return;
  if (!(await ensureWorkspaceSaved())) return;
  sending.value = true;
  error.value = "";
  try {
    const updated = await api.sendSkillBuilderMessage(session.value.id, {
      content: message.value.trim(),
      intent: "chat",
      provider_id: selection.value.provider_id || null,
      model_id: selection.value.model_id || null,
    });
    message.value = "";
    applySession(updated);
    startPolling();
  } catch (caught) {
    error.value = errorMessage(caught);
  } finally {
    sending.value = false;
  }
}

async function pollSession(): Promise<void> {
  if (!session.value) return;
  try {
    applySession(await api.getSkillBuilderSession(session.value.id));
  } catch (caught) {
    error.value = errorMessage(caught);
    stopPolling();
  }
}

async function saveWorkspace(options: { silent?: boolean } = {}): Promise<boolean> {
  if (!session.value) return false;
  savingWorkspace.value = true;
  error.value = "";
  try {
    applySession(await api.updateSkillBuilderWorkspace(session.value.id, { files: builderWorkspacePayload(workspaceFiles.value) }));
    workspaceDirty.value = false;
    if (!options.silent) emit("toast", { tone: "success", message: "工作区已保存。" });
    return true;
  } catch (caught) {
    error.value = errorMessage(caught);
    return false;
  } finally {
    savingWorkspace.value = false;
  }
}

async function openSubmitModal(): Promise<void> {
  if (!canOpenSubmit.value) {
    error.value = submitDisabledReason.value;
    return;
  }
  if (!(await ensureWorkspaceSaved())) return;
  submitOpen.value = true;
}

async function createSkill(payload: { version: string; tags: SkillTagPayload[]; files: SkillBuilderDraftFile[] }): Promise<void> {
  if (!session.value) return;
  creating.value = true;
  error.value = "";
  try {
    const result = await api.createSkillFromBuilder(session.value.id, payload);
    submitOpen.value = false;
    emit("toast", { tone: "success", message: "Skill 已创建。" });
    emit("created", result.skill_id);
  } catch (caught) {
    error.value = errorMessage(caught);
  } finally {
    creating.value = false;
  }
}

function applySession(next: SkillBuilderSession): void {
  session.value = next;
  selection.value = { ...next.run_selection };
  workspaceFiles.value = builderWorkspaceFilesFromSession(next);
  workspaceDirty.value = false;
}

function startPolling(): void {
  if (pollTimer.value !== null) return;
  pollTimer.value = window.setInterval(() => void pollSession(), 3000);
}

function stopPolling(): void {
  if (pollTimer.value === null) return;
  window.clearInterval(pollTimer.value);
  pollTimer.value = null;
}

function addFile(): void {
  workspaceFiles.value = [...workspaceFiles.value, defaultSkillBundleDraftFile(workspaceFiles.value, "references/notes.md")];
  workspaceDirty.value = true;
}

function removeFile(id: string): void {
  workspaceFiles.value = workspaceFiles.value.filter((file) => file.id !== id || file.path.trim() === SKILL_ENTRY_PATH);
  workspaceDirty.value = true;
}

function updatePath(id: string, path: string): void {
  workspaceFiles.value = workspaceFiles.value.map((file) => (file.id === id ? { ...file, path } : file));
  workspaceDirty.value = true;
}

function updateContent(id: string, content: string): void {
  workspaceFiles.value = workspaceFiles.value.map((file) => (file.id === id ? { ...file, content_text: content } : file));
  workspaceDirty.value = true;
}

async function ensureWorkspaceSaved(): Promise<boolean> {
  if (!workspaceDirty.value) return true;
  if (!validation.value.valid) {
    error.value = validation.value.globalErrors[0] || Object.values(validation.value.errors)[0] || "工作区文件需要先修正。";
    return false;
  }
  return saveWorkspace({ silent: true });
}

function errorMessage(caught: unknown, fallback = "操作失败。"): string {
  if (caught instanceof ApiError || caught instanceof Error) {
    if (caught.message === "Failed to fetch") return fallback;
    return caught.message;
  }
  return fallback;
}
</script>

<template>
  <div class="skill-builder-page">
    <main class="skill-builder-main">
      <BuilderLoadAlert v-if="error" :message="error" :retryable="loadFailed" @retry="loadInitial" />
      <BuilderTopToolbar
        :selection="selection"
        :provider-options="providerOptions"
        :model-options="modelOptions"
        :provider-load-error="providerLoadError"
        :can-create-session="canCreateSession"
        :new-session-disabled-reason="newSessionDisabledReason"
        :can-open-workspace="canOpenWorkspace"
        :workspace-open="workspaceOpen"
        :workspace-button-text="workspaceButtonText"
        :can-open-submit="canOpenSubmit"
        :submit-disabled-reason="submitDisabledReason"
        @provider="selectProvider"
        @model="selectModel"
        @new-session="requestCreateSession"
        @toggle-workspace="workspaceOpen = true"
        @submit="openSubmitModal"
      />

      <BuilderWorkspaceDropdown
        v-if="workspaceOpen"
        :files="workspaceFiles"
        :validation="validation"
        :dirty="workspaceDirty"
        :can-save="canSaveWorkspace"
        :saving="savingWorkspace"
        @add="addFile"
        @remove="removeFile"
        @path-change="updatePath"
        @content-change="updateContent"
        @save="saveWorkspace"
        @close="workspaceOpen = false"
      />

      <BuilderChatPanel
        :status-text="statusText"
        :message="message"
        :messages="session?.messages ?? []"
        :running="session?.status === 'running'"
        :running-since="runningSince"
        :can-send="canSend"
        :sending="sending"
        @update:message="message = $event"
        @starter="message = $event"
        @send="send"
      />

      <BuilderSubmitSkillModal
        v-if="submitOpen"
        :files="workspaceFiles"
        :version="version"
        :tags="tags"
        :tag-groups="tagGroups"
        :creating="creating"
        @close="submitOpen = false"
        @update:version="version = $event"
        @update:tags="tags = $event"
        @submit="createSkill"
      />

      <BuilderNewSessionConfirmModal v-if="confirmNewSessionOpen" @close="confirmNewSessionOpen = false" @confirm="createSession" />
    </main>
  </div>
</template>
