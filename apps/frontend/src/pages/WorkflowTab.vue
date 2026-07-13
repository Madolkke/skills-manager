<script setup lang="ts">
import { AlertTriangle, CheckCircle2, GitBranch, RotateCcw, Save } from "lucide-vue-next";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import InlineLoading from "../components/InlineLoading.vue";
import { workflowStatusLabel, workflowStatusTone } from "../features/workflow/domain/presentation";
import { cloneWorkflow } from "../features/workflow/domain/utils";
import { api, ApiError } from "../lib/api";
import { humanDate } from "../lib/format";
import type { SkillDetail, ToastState, WorkflowDetail, WorkflowMetadata } from "../types";

const props = defineProps<{ skill: SkillDetail }>();
const emit = defineEmits<{ open: []; refresh: []; dirty: [dirty: boolean]; toast: [toast: ToastState] }>();

const detail = ref<WorkflowDetail | null>(null);
const draft = ref<WorkflowMetadata | null>(null);
const loading = ref(true);
const saving = ref(false);
const error = ref("");

const canEdit = computed(() => Boolean(detail.value?.capabilities.permissions["skill.edit"]));
const dirty = computed(() => Boolean(detail.value && draft.value && JSON.stringify(detail.value.document.workflow.metadata) !== JSON.stringify(draft.value)));
const errors = computed(() => detail.value?.validation.errors.length ?? 0);
const warnings = computed(() => detail.value?.validation.warnings.length ?? 0);

onMounted(() => {
  window.addEventListener("beforeunload", beforeUnload);
  void load();
});
onBeforeUnmount(() => {
  window.removeEventListener("beforeunload", beforeUnload);
  emit("dirty", false);
});
watch(() => props.skill.skill.id, () => void load());
watch(dirty, (value) => emit("dirty", value), { immediate: true });

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    detail.value = await api.getWorkflow(props.skill.skill.id);
    draft.value = cloneWorkflow(detail.value.document.workflow.metadata);
  } catch (caught) {
    error.value = message(caught);
  } finally {
    loading.value = false;
  }
}

async function save(): Promise<void> {
  if (!draft.value || !dirty.value || !canEdit.value) return;
  saving.value = true;
  error.value = "";
  try {
    detail.value = await api.updateWorkflowMetadata(props.skill.skill.id, draft.value);
    draft.value = cloneWorkflow(detail.value.document.workflow.metadata);
    emit("refresh");
    emit("toast", { tone: "success", message: "Workflow 元信息已保存。" });
  } catch (caught) {
    error.value = message(caught);
  } finally {
    saving.value = false;
  }
}

function update<K extends keyof WorkflowMetadata>(key: K, value: WorkflowMetadata[K]): void {
  if (draft.value) draft.value = { ...draft.value, [key]: value };
}

function parseVersions(value: string): string[] {
  return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
}

function discard(): void {
  if (detail.value) draft.value = cloneWorkflow(detail.value.document.workflow.metadata);
}

function beforeUnload(event: BeforeUnloadEvent): void {
  if (!dirty.value) return;
  event.preventDefault();
  event.returnValue = "";
}

function message(error: unknown): string {
  return error instanceof ApiError || error instanceof Error ? error.message : "Workflow 加载失败。";
}
</script>

<template>
  <section class="workflow-tab-page">
    <div class="panel-title-row workflow-tab-heading">
      <div>
        <h1>工作流</h1>
        <p>{{ skill.skill.slug }}</p>
      </div>
      <div class="button-row">
        <button class="icon-button" type="button" title="放弃未保存修改" aria-label="放弃未保存修改" :disabled="!dirty || saving" @click="discard"><RotateCcw :size="16" /></button>
        <button class="secondary-button" type="button" :disabled="!dirty || saving || !canEdit" @click="save">
          <Save :size="16" />{{ saving ? "保存中..." : "保存元信息" }}
        </button>
        <button class="primary-button" type="button" @click="emit('open')"><GitBranch :size="16" />打开编辑器</button>
      </div>
    </div>

    <InlineLoading v-if="loading" label="正在加载 Workflow" />
    <div v-else-if="error" class="form-error">{{ error }}</div>
    <template v-else-if="detail && draft">
      <section class="workflow-tab-status-band">
        <div><span>同步状态</span><strong :class="`tone-${workflowStatusTone(detail.sync.status)}`">{{ workflowStatusLabel(detail.sync.status) }}</strong></div>
        <div><span>工作流修订</span><strong>r{{ detail.revision }}</strong></div>
        <div><span>校验</span><strong><AlertTriangle v-if="errors" :size="14" />{{ errors }} 错误 · {{ warnings }} 提醒</strong></div>
        <div><span>最后保存</span><strong>{{ humanDate(detail.updated_at) }}</strong><small>{{ detail.last_saved_by }}</small></div>
      </section>

      <section class="primary-panel workflow-tab-form">
        <header><div><h2>元信息</h2><p v-if="dirty">有未保存更改</p><p v-else><CheckCircle2 :size="14" />已保存</p></div></header>
        <div class="workflow-form-grid workflow-tab-form-grid">
          <label class="field-label span-2"><span>名称</span><input :value="draft.name" :disabled="!canEdit" @input="update('name', ($event.target as HTMLInputElement).value)" /></label>
          <label class="field-label"><span>编码</span><input class="workflow-code-input" :value="draft.code" :disabled="!canEdit" @input="update('code', ($event.target as HTMLInputElement).value)" /></label>
          <label class="field-label"><span>产业</span><input :value="draft.industry" :disabled="!canEdit" @input="update('industry', ($event.target as HTMLInputElement).value)" /></label>
          <label class="field-label"><span>设备</span><input :value="draft.device" :disabled="!canEdit" @input="update('device', ($event.target as HTMLInputElement).value)" /></label>
          <label class="field-label"><span>适用版本</span><input :value="draft.versions.join(', ')" :disabled="!canEdit" placeholder="V8R22, V8R23" @change="update('versions', parseVersions(($event.target as HTMLInputElement).value))" /></label>
          <label class="field-label span-all"><span>说明</span><textarea rows="5" :value="draft.description" :disabled="!canEdit" @input="update('description', ($event.target as HTMLTextAreaElement).value)" /></label>
        </div>
      </section>
    </template>
  </section>
</template>
