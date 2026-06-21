<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../../../lib/api";
import type { EvalAssertionTemplate, EvalCaseStep, EvalRunnerConfig, EvalSetCase } from "../../../types";
import EvalCaseAdvancedSettings from "./EvalCaseAdvancedSettings.vue";
import EvalCaseScenarioBasics from "./EvalCaseScenarioBasics.vue";
import EvalCaseStepEditor from "./EvalCaseStepEditor.vue";
import EvalCaseStepList from "./EvalCaseStepList.vue";

export type EvalCaseFormData = {
  title: string;
  steps: EvalCaseStep[];
  workspace_name?: string;
  workspace_base64?: string;
  runner_config: EvalRunnerConfig;
  notes: string;
};

export type StepValidation = {
  complete: boolean;
  message: string;
};

const props = defineProps<{
  caseItem?: EvalSetCase | null;
  busy: boolean;
  title?: string;
  statusLabel?: string;
}>();
const emit = defineEmits<{ cancel: []; submit: [data: EvalCaseFormData] }>();

const editing = Boolean(props.caseItem);
const templates = ref<EvalAssertionTemplate[]>([]);
const selectedStepIndex = ref(0);
const attemptedSubmit = ref(false);
const advancedOpen = ref(Boolean(props.caseItem?.case_version.notes || props.caseItem?.case_version.runner_config.model_provider_id));
const workspaceLabel = ref(props.caseItem?.case_version.workspace_artifact ? artifactFileName(props.caseItem.case_version.workspace_artifact.locator) : "未选择压缩包");
const form = ref<EvalCaseFormData>({
  title: props.caseItem?.case.title ?? "",
  steps: props.caseItem?.case_version.steps.length ? props.caseItem.case_version.steps.map(cloneStep) : [defaultStep()],
  workspace_name: undefined,
  workspace_base64: undefined,
  runner_config: { ...(props.caseItem?.case_version.runner_config ?? {}) },
  notes: props.caseItem?.case_version.notes ?? "",
});

const groupedTemplates = computed(() => {
  const groups = new Map<string, EvalAssertionTemplate[]>();
  for (const template of templates.value) groups.set(template.category, [...(groups.get(template.category) ?? []), template]);
  return [...groups.entries()].map(([category, items]) => ({ category, items }));
});
const activeStep = computed(() => form.value.steps[selectedStepIndex.value] ?? form.value.steps[0]);
const modelLabel = computed(() => {
  const provider = form.value.runner_config.model_provider_id;
  const model = form.value.runner_config.model_id;
  return provider && model ? `${provider}/${model}` : "Opencode 默认模型";
});
const stepValidations = computed(() => form.value.steps.map(validateStep));
const invalidStepCount = computed(() => stepValidations.value.filter((item) => !item.complete).length);
const titleValid = computed(() => Boolean(form.value.title.trim()));
const saveStatus = computed(() => {
  if (!titleValid.value) return "标题待补全";
  if (invalidStepCount.value) return `${invalidStepCount.value} 个步骤待补全`;
  return "可保存";
});

onMounted(async () => {
  templates.value = await api.listEvalAssertionTemplates();
});

/** 创建一个最小可保存的默认测试步骤。 */
function defaultStep(): EvalCaseStep {
  return {
    id: "",
    title: "步骤 1",
    input: "",
    assertion_template_id: "agent_output_semantic",
    assertion_params: { expected: "", threshold: 0.85 },
  };
}

/** 复制步骤数据，避免编辑表单直接修改父级列表对象。 */
function cloneStep(step: EvalCaseStep): EvalCaseStep {
  return { ...step, assertion_params: { ...step.assertion_params } };
}

/** 根据模板 id 查找当前可用模板。 */
function templateFor(id: string): EvalAssertionTemplate | undefined {
  return templates.value.find((template) => template.id === id);
}

/** 新增步骤并自动切换到新步骤。 */
function addStep(): void {
  form.value.steps.push({ ...defaultStep(), title: `步骤 ${form.value.steps.length + 1}` });
  selectedStepIndex.value = form.value.steps.length - 1;
}

/** 选中左侧步骤导航中的目标步骤。 */
function selectStep(index: number): void {
  selectedStepIndex.value = index;
}

/** 删除步骤，至少保留一个步骤用于提交。 */
function removeStep(index: number): void {
  if (form.value.steps.length === 1) return;
  form.value.steps.splice(index, 1);
  selectedStepIndex.value = Math.min(selectedStepIndex.value, form.value.steps.length - 1);
}

/** 调整步骤顺序，并保持选中项跟随移动。 */
function moveStep(index: number, direction: -1 | 1): void {
  const nextIndex = index + direction;
  if (nextIndex < 0 || nextIndex >= form.value.steps.length) return;
  const [step] = form.value.steps.splice(index, 1);
  if (!step) return;
  form.value.steps.splice(nextIndex, 0, step);
  selectedStepIndex.value = nextIndex;
}

/** 切换判断模板，并按模板 schema 重置参数。 */
function changeTemplate(templateId: string): void {
  const step = activeStep.value;
  step.assertion_template_id = templateId;
  step.assertion_params = {};
  for (const param of templateFor(templateId)?.params_schema ?? []) {
    step.assertion_params[param.name] = param.default ?? "";
  }
}

/** 更新模型服务商，清空服务商时同步清空模型。 */
function updateProvider(value: string): void {
  form.value.runner_config.model_provider_id = value || null;
  if (!value) form.value.runner_config.model_id = null;
  if (value && !form.value.runner_config.model_id) form.value.runner_config.model_id = "deepseek-v4-flash";
}

/** 更新模型配置。 */
function updateModel(value: string | null): void {
  form.value.runner_config.model_id = value;
}

/** 更新当前步骤标题。 */
function updateActiveTitle(value: string): void {
  activeStep.value.title = value;
}

/** 更新当前步骤输入。 */
function updateActiveInput(value: string): void {
  activeStep.value.input = value;
}

/** 更新当前步骤判断模板参数。 */
function updateActiveParam(payload: { name: string; value: string | number }): void {
  activeStep.value.assertion_params[payload.name] = payload.value;
}

/** 读取 zip 文件并写入提交表单。 */
async function acceptZip(files: FileList | null): Promise<void> {
  const file = files?.[0] ?? null;
  if (!file) {
    form.value.workspace_name = undefined;
    form.value.workspace_base64 = undefined;
    workspaceLabel.value = props.caseItem?.case_version.workspace_artifact ? artifactFileName(props.caseItem.case_version.workspace_artifact.locator) : "未选择压缩包";
    return;
  }
  form.value.workspace_name = file.name;
  form.value.workspace_base64 = await fileToBase64(file);
  workspaceLabel.value = `${file.name} · ${formatBytes(file.size)}`;
}

/** 提交前校验标题和步骤参数，定位到第一个不完整步骤。 */
function submit(): void {
  attemptedSubmit.value = true;
  if (!titleValid.value) return;
  const firstInvalid = stepValidations.value.findIndex((item) => !item.complete);
  if (firstInvalid >= 0) {
    selectedStepIndex.value = firstInvalid;
    return;
  }
  emit("submit", form.value);
}

/** 校验单个步骤是否满足保存条件。 */
function validateStep(step: EvalCaseStep): StepValidation {
  if (!step.input.trim()) return { complete: false, message: "缺少输入" };
  const template = templateFor(step.assertion_template_id);
  for (const param of template?.params_schema ?? []) {
    if (!param.required) continue;
    const value = step.assertion_params[param.name];
    if (value === null || value === undefined || (typeof value === "string" && !value.trim())) return { complete: false, message: `缺少${param.label}` };
  }
  return { complete: true, message: "完整" };
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? "").split(",")[1] ?? "");
    reader.onerror = () => reject(new Error("读取压缩包失败。"));
    reader.readAsDataURL(file);
  });
}

function artifactFileName(locator: string): string {
  return locator.split(":").at(-1) || "workspace.zip";
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}
</script>

<template>
  <form class="scenario-editor" @submit.prevent="submit">
    <header v-if="title || statusLabel" class="scenario-editor-shell-head">
      <div>
        <span>测试场景编辑器</span>
        <h2>{{ title ?? (editing ? "编辑测试例" : "添加测试例") }}</h2>
      </div>
      <strong>{{ statusLabel ?? (editing ? "编辑中" : "未保存") }}</strong>
    </header>
    <EvalCaseScenarioBasics v-model:title="form.title" :workspace-label="workspaceLabel" :show-validation="attemptedSubmit" @zip="acceptZip" />
    <section class="scenario-workspace">
      <EvalCaseStepList
        :steps="form.steps"
        :selected-index="selectedStepIndex"
        :templates="templates"
        :validations="stepValidations"
        :show-validation="attemptedSubmit"
        @select="selectStep"
        @add="addStep"
        @remove="removeStep"
        @move="moveStep"
      />
      <EvalCaseStepEditor
        v-if="activeStep"
        :step="activeStep"
        :index="selectedStepIndex"
        :grouped-templates="groupedTemplates"
        :template="templateFor(activeStep.assertion_template_id)"
        :validation="stepValidations[selectedStepIndex]"
        :show-validation="attemptedSubmit"
        @title="updateActiveTitle"
        @input="updateActiveInput"
        @template="changeTemplate"
        @param="updateActiveParam"
      />
    </section>
    <EvalCaseAdvancedSettings
      v-model:open="advancedOpen"
      v-model:notes="form.notes"
      :runner-config="form.runner_config"
      @provider="updateProvider"
      @model="updateModel"
    />
    <footer class="scenario-action-bar">
      <div>
        <strong>{{ form.steps.length }} 个步骤</strong>
        <span>{{ modelLabel }} · {{ saveStatus }}</span>
      </div>
      <div class="modal-actions">
        <button class="secondary-button" type="button" @click="emit('cancel')">取消</button>
        <button class="primary-button" type="submit" :disabled="busy">
          {{ busy ? "保存中..." : editing ? "保存测试例版本" : "保存" }}
        </button>
      </div>
    </footer>
  </form>
</template>
