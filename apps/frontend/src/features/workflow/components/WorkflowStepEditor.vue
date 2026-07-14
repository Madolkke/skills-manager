<script setup lang="ts">
import { Braces, Code2, Copy, Trash2 } from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type {
  CollectionCall,
  CollectionDefinition,
  WorkflowBinding,
  WorkflowBundle,
  WorkflowCollectionChange,
  WorkflowEditorSection,
  WorkflowSelection,
  WorkflowStep,
  WorkflowValidationIssue,
} from "../../../types";
import type { WorkflowPathTargetChoice } from "../workflowPathEditing";
import WorkflowSectionNav from "./WorkflowSectionNav.vue";
import WorkflowPredecessors from "./WorkflowPredecessors.vue";
import WorkflowStepCollections from "./WorkflowStepCollections.vue";
import WorkflowTransitionList from "./WorkflowTransitionList.vue";

const props = defineProps<{
  step: WorkflowStep;
  bundle: WorkflowBundle;
  catalog: CollectionDefinition[];
  changes: WorkflowCollectionChange[];
  issues: WorkflowValidationIssue[];
  target: WorkflowSelection;
  readonly: boolean;
}>();
const emit = defineEmits<{
  change: [patch: Partial<WorkflowStep>];
  duplicate: [];
  remove: [];
  "add-call": [definition: CollectionDefinition];
  "add-draft": [];
  "call-change": [id: string, patch: Partial<CollectionCall>];
  "call-remove": [id: string];
  "call-move": [id: string, direction: -1 | 1];
  "call-reorder": [ids: string[]];
  "binding-change": [callId: string, inputId: string, binding: WorkflowBinding | null];
  "definition-change": [callId: string, definition: CollectionDefinition];
  "path-add": [choice: WorkflowPathTargetChoice];
  "path-retarget": [id: string, choice: WorkflowPathTargetChoice];
  "path-change": [id: string, patch: Record<string, unknown>];
  "path-remove": [id: string];
  "path-move": [id: string, direction: -1 | 1];
  "path-open-target": [id: string];
  "predecessor-open": [id: string];
}>();

const root = ref<HTMLElement | null>(null);
const activeSection = ref<WorkflowEditorSection>("overview");
const activeCallId = ref<string | null>(null);
let observer: IntersectionObserver | null = null;

const sections = computed(() => [
  { id: "overview" as const, label: "步骤信息", issues: sectionIssueCount("overview") },
  ...(props.step.stepType === "script" ? [{ id: "script" as const, label: "脚本", issues: sectionIssueCount("script") }] : []),
  { id: "collections" as const, label: "采集", issues: sectionIssueCount("collections") },
  { id: "paths" as const, label: "路径", issues: sectionIssueCount("paths") },
]);

onMounted(setupObserver);
onBeforeUnmount(() => observer?.disconnect());
watch(() => props.step.id, () => void nextTick(setupObserver));
watch(() => props.target, (target) => {
  if (target.type !== "step" || target.id !== props.step.id) return;
  if (target.itemId) activeCallId.value = target.itemId;
  const section = target.section;
  if (section) void nextTick(() => scrollTo(section, target.itemId));
}, { deep: true, immediate: true });

function scrollTo(section: WorkflowEditorSection, itemId?: string): void {
  activeSection.value = section;
  const target = itemId
    ? root.value?.querySelector<HTMLElement>(`[data-sort-id="${CSS.escape(itemId)}"]`)
    : root.value?.querySelector<HTMLElement>(`[data-workflow-section="${section}"]`);
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function setupObserver(): void {
  observer?.disconnect();
  const scrollRoot = root.value?.closest(".workflow-editor-pane") ?? null;
  const elements = root.value?.querySelectorAll<HTMLElement>("[data-workflow-section]") ?? [];
  observer = new IntersectionObserver((entries) => {
    const visible = entries.filter((entry) => entry.isIntersecting).sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
    const section = visible?.target.getAttribute("data-workflow-section") as WorkflowEditorSection | null;
    if (section) activeSection.value = section;
  }, { root: scrollRoot, rootMargin: "-80px 0px -65% 0px", threshold: [0, 0.2, 0.6] });
  elements.forEach((element) => observer?.observe(element));
}

function sectionIssueCount(section: WorkflowEditorSection): number {
  return props.issues.filter((issue) => {
    const selection = issue.selection;
    if (selection.type === "collection") {
      return section === "collections" && props.step.collectionCalls.some((call) => call.definition.id === selection.id);
    }
    if (selection.type !== "step" || selection.id !== props.step.id) return false;
    if (selection.section) return selection.section === section;
    if (issue.code.includes("TRANSITION") || issue.message.includes("跳转")) return section === "paths";
    return section === "overview";
  }).length;
}
</script>

<template>
  <section ref="root" class="workflow-document workflow-step-document">
    <header class="workflow-document-head">
      <div class="workflow-step-index">STEP</div>
      <div><h2>{{ props.step.name }}</h2><p>{{ props.step.description || "尚未填写步骤说明" }}</p></div>
      <div class="workflow-row-actions"><UiButton variant="secondary" :disabled="props.readonly" @click="emit('duplicate')"><template #icon><Copy /></template>复制</UiButton><UiIconButton label="删除步骤" variant="danger" :disabled="props.readonly" @click="emit('remove')"><Trash2 /></UiIconButton></div>
    </header>

    <WorkflowSectionNav :active="activeSection" :sections="sections" @select="scrollTo($event)" />

    <section id="workflow-step-overview" class="workflow-step-section workflow-step-overview" data-workflow-section="overview">
      <div class="workflow-section-title"><span>01</span><div><h3>步骤信息</h3><p>步骤的名称和执行类型。</p></div></div>
      <div class="workflow-form-grid workflow-step-overview-grid">
        <label class="field-label"><span>步骤名称</span><input :value="props.step.name" :disabled="props.readonly" @input="emit('change', { name: ($event.target as HTMLInputElement).value })" /></label>
        <div class="field-label">
          <span>步骤类型</span>
          <div :class="['workflow-step-type-toggle', props.step.stepType === 'script' && 'is-script']" role="radiogroup" aria-label="步骤类型">
            <button type="button" role="radio" :aria-checked="props.step.stepType === 'expression'" :disabled="props.readonly" @click="emit('change', { stepType: 'expression' })"><Braces :size="15" />表达式</button>
            <button type="button" role="radio" :aria-checked="props.step.stepType === 'script'" :disabled="props.readonly" @click="emit('change', { stepType: 'script' })"><Code2 :size="15" />脚本</button>
          </div>
        </div>
        <label class="workflow-check workflow-start-check"><input type="checkbox" :checked="props.step.isStart" :disabled="props.readonly" @change="emit('change', { isStart: ($event.target as HTMLInputElement).checked })" />设为起始步骤</label>
        <label class="field-label span-2"><span>步骤说明</span><textarea rows="4" :value="props.step.description" :disabled="props.readonly" @input="emit('change', { description: ($event.target as HTMLTextAreaElement).value })" /></label>
      </div>
      <WorkflowPredecessors :bundle="props.bundle" :target-id="props.step.id" @open="emit('predecessor-open', $event)" />
    </section>

    <section v-if="props.step.stepType === 'script'" id="workflow-step-script" class="workflow-step-section" data-workflow-section="script">
      <div class="workflow-section-title"><span>02</span><div><h3>脚本草稿</h3><p>同步时写入 Skill 的脚本说明。</p></div></div>
      <div class="workflow-form-grid"><label class="field-label"><span>语言</span><input :value="props.step.script?.language ?? 'python'" :disabled="props.readonly" @input="emit('change', { script: { language: ($event.target as HTMLInputElement).value, source: props.step.script?.source ?? '', options: props.step.script?.options ?? {} } })" /></label><label class="field-label span-2"><span>源码</span><textarea class="workflow-code-input workflow-script-input" rows="12" spellcheck="false" :value="props.step.script?.source ?? ''" :disabled="props.readonly" @input="emit('change', { script: { language: props.step.script?.language ?? 'python', source: ($event.target as HTMLTextAreaElement).value, options: props.step.script?.options ?? {} } })" /></label></div>
    </section>

    <WorkflowStepCollections
      v-model:active-call-id="activeCallId"
      data-workflow-section="collections"
      :section-number="props.step.stepType === 'script' ? '03' : '02'"
      :step="props.step"
      :bundle="props.bundle"
      :catalog="props.catalog"
      :changes="props.changes"
      :issues="props.issues"
      :readonly="props.readonly"
      @add-call="emit('add-call', $event)"
      @add-draft="emit('add-draft')"
      @call-change="(id, patch) => emit('call-change', id, patch)"
      @call-remove="emit('call-remove', $event)"
      @call-move="(id, direction) => emit('call-move', id, direction)"
      @call-reorder="emit('call-reorder', $event)"
      @binding-change="(callId, inputId, binding) => emit('binding-change', callId, inputId, binding)"
      @definition-change="(callId, definition) => emit('definition-change', callId, definition)"
    />

    <WorkflowTransitionList
      id="workflow-step-paths"
      data-workflow-section="paths"
      :section-number="props.step.stepType === 'script' ? '04' : '03'"
      :step="props.step"
      :bundle="props.bundle"
      :readonly="props.readonly"
      @add="emit('path-add', $event)"
      @retarget="(id, choice) => emit('path-retarget', id, choice)"
      @change="(id, patch) => emit('path-change', id, patch)"
      @remove="emit('path-remove', $event)"
      @move="(id, direction) => emit('path-move', id, direction)"
      @open-target="emit('path-open-target', $event)"
    />
  </section>
</template>
