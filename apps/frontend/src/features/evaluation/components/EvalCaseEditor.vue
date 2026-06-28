<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../../../lib/api";
import type { EvalAssertionTemplate, EvalSetCase } from "../../../types";
import {
  artifactFileName,
  buildEvalCaseValidationSummary,
  createEvalCaseForm,
  defaultAssertion,
  defaultStep,
  formatBytes,
  nextAssertionIndex,
  validateStep,
  type EvalCaseFormData,
} from "../lib/evalCaseForm";
import {
  GENERATED_WORKSPACE_NAME,
  defaultWorkspaceFile,
  formatWorkspaceSize,
  workspaceDraftSize,
  workspaceFilesToBase64,
  type WorkspaceFileDraft,
} from "../lib/workspaceDraft";
import EvalCaseAdvancedSettings from "./EvalCaseAdvancedSettings.vue";
import EvalCaseScenarioBasics from "./EvalCaseScenarioBasics.vue";
import EvalCaseStepEditor from "./EvalCaseStepEditor.vue";
import EvalCaseStepList from "./EvalCaseStepList.vue";
import WorkspaceFileEditorModal from "./WorkspaceFileEditorModal.vue";

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
const advancedOpen = ref(Boolean(props.caseItem?.case_version.notes));
const workspaceEditorOpen = ref(false);
const workspaceLabel = ref(props.caseItem?.case_version.workspace_artifact ? artifactFileName(props.caseItem.case_version.workspace_artifact.locator) : "未选择压缩包");
const form = ref<EvalCaseFormData>(createEvalCaseForm(props.caseItem));

const groupedTemplates = computed(() => {
  const groups = new Map<string, EvalAssertionTemplate[]>();
  for (const template of templates.value) groups.set(template.category, [...(groups.get(template.category) ?? []), template]);
  return [...groups.entries()].map(([category, items]) => ({ category, items }));
});
const activeStep = computed(() => form.value.steps[selectedStepIndex.value] ?? form.value.steps[0]);
const stepValidations = computed(() => form.value.steps.map((step) => validateStep(step, templateFor)));
const validationSummary = computed(() => buildEvalCaseValidationSummary(form.value, stepValidations.value));
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

/** 根据模板 id 查找当前可用模板。 */
function templateFor(id: string): EvalAssertionTemplate | undefined {
  return templates.value.find((template) => template.id === id);
}

/** 新增步骤并自动切换到新步骤。 */
function addStep(): void {
  form.value.steps.push(defaultStep(form.value.steps.length));
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

/** 新增判断条件，并使用默认语义判定模板。 */
function addAssertion(): void {
  const step = activeStep.value;
  step.assertions.push(defaultAssertion(nextAssertionIndex(step.assertions)));
}

/** 删除判断条件，至少保留一个条件用于提交。 */
function removeAssertion(assertionId: string): void {
  const step = activeStep.value;
  if (step.assertions.length === 1) return;
  step.assertions = step.assertions.filter((assertion) => assertion.id !== assertionId);
}

/** 切换判断模板，并按模板 schema 重置参数。 */
function changeTemplate(payload: { assertionId: string; templateId: string }): void {
  const assertion = activeStep.value.assertions.find((item) => item.id === payload.assertionId);
  if (!assertion) return;
  assertion.assertion_template_id = payload.templateId;
  assertion.assertion_params = {};
  for (const param of templateFor(payload.templateId)?.params_schema ?? []) {
    assertion.assertion_params[param.name] = param.default ?? "";
  }
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
function updateActiveParam(payload: { assertionId: string; name: string; value: string | number }): void {
  const assertion = activeStep.value.assertions.find((item) => item.id === payload.assertionId);
  if (assertion) assertion.assertion_params[payload.name] = payload.value;
}

/** 读取 zip 文件并写入提交表单。 */
async function acceptZip(files: FileList | null): Promise<void> {
  const file = files?.[0] ?? null;
  if (!file) {
    form.value.workspace_name = undefined;
    form.value.workspace_base64 = undefined;
    form.value.workspace_files = undefined;
    workspaceLabel.value = props.caseItem?.case_version.workspace_artifact ? artifactFileName(props.caseItem.case_version.workspace_artifact.locator) : "未选择压缩包";
    return;
  }
  form.value.workspace_name = file.name;
  form.value.workspace_base64 = await fileToBase64(file);
  form.value.workspace_files = undefined;
  workspaceLabel.value = `${file.name} · ${formatBytes(file.size)}`;
}

/** 打开工作区文件布置弹窗，首个空白工作区默认包含 README.md。 */
function openWorkspaceEditor(): void {
  if (!form.value.workspace_files) {
    form.value.workspace_files = form.value.workspace_base64 ? [] : [defaultWorkspaceFile()];
  }
  workspaceEditorOpen.value = true;
}

/** 将弹窗里的文本文件打包成 workspace zip，并覆盖当前工作区字段。 */
async function saveWorkspaceFiles(files: WorkspaceFileDraft[]): Promise<void> {
  const cleanFiles = files.map((file) => ({ ...file, path: file.path.trim() }));
  form.value.workspace_files = cleanFiles;
  form.value.workspace_name = GENERATED_WORKSPACE_NAME;
  form.value.workspace_base64 = await workspaceFilesToBase64(cleanFiles);
  workspaceLabel.value = `已布置 ${cleanFiles.length} 个文件 · ${formatWorkspaceSize(workspaceDraftSize(cleanFiles))}`;
  workspaceEditorOpen.value = false;
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
  if (validationSummary.value.length) return;
  emit("submit", form.value);
}

/** 点击校验摘要项时，定位到对应步骤或工作区入口。 */
function focusValidation(item: { stepIndex?: number; id: string }): void {
  if (typeof item.stepIndex === "number") selectedStepIndex.value = item.stepIndex;
  if (item.id.startsWith("workspace-")) workspaceEditorOpen.value = true;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? "").split(",")[1] ?? "");
    reader.onerror = () => reject(new Error("读取压缩包失败。"));
    reader.readAsDataURL(file);
  });
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
    <EvalCaseScenarioBasics
      v-model:title="form.title"
      :workspace-label="workspaceLabel"
      :show-validation="attemptedSubmit"
      @configure-workspace="openWorkspaceEditor"
      @zip="acceptZip"
    />
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
        :validation="stepValidations[selectedStepIndex]"
        :show-validation="attemptedSubmit"
        @title="updateActiveTitle"
        @input="updateActiveInput"
        @add-assertion="addAssertion"
        @remove-assertion="removeAssertion"
        @template="changeTemplate"
        @param="updateActiveParam"
      />
    </section>
    <EvalCaseAdvancedSettings
      v-model:open="advancedOpen"
      v-model:notes="form.notes"
    />
    <section v-if="attemptedSubmit && validationSummary.length" class="scenario-validation-summary" aria-label="保存前校验摘要">
      <div>
        <strong>保存前需要处理 {{ validationSummary.length }} 项</strong>
        <p>点击问题可定位到对应步骤或工作区配置。</p>
      </div>
      <button
        v-for="item in validationSummary"
        :key="item.id"
        type="button"
        class="scenario-validation-item"
        @click="focusValidation(item)"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.message }}</strong>
      </button>
    </section>
    <WorkspaceFileEditorModal
      v-if="workspaceEditorOpen"
      :files="form.workspace_files ?? []"
      :existing-workspace-label="workspaceLabel"
      @close="workspaceEditorOpen = false"
      @save="saveWorkspaceFiles"
    />
    <footer class="scenario-action-bar">
      <div>
        <strong>{{ form.steps.length }} 个步骤</strong>
        <span>Opencode 外部配置 · {{ saveStatus }}</span>
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
