<script setup lang="ts">
import { Check, ChevronDown, Flag, Plus, Search, TerminalSquare } from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import type { WorkflowBundle, WorkflowNode, WorkflowStep } from "../../../types";
import type { WorkflowPathTargetChoice } from "../workflowPathEditing";

const props = defineProps<{
  bundle: WorkflowBundle;
  sourceStepId: string;
  currentTargetId?: string;
  variant: "add" | "target";
  readonly: boolean;
}>();
const emit = defineEmits<{ select: [choice: WorkflowPathTargetChoice] }>();
const root = ref<HTMLElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const queryInput = ref<HTMLInputElement | null>(null);
const nameInput = ref<HTMLInputElement | null>(null);
const open = ref(false);
const tab = ref<"existing" | "step" | "conclusion">("existing");
const query = ref("");
const name = ref("");
const stepType = ref<WorkflowStep["stepType"]>("expression");

const available = computed(() => props.bundle.workflow.nodes.filter((item) => item.id !== props.sourceStepId));
const filtered = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase();
  return available.value.filter((item) => !needle || item.name.toLocaleLowerCase().includes(needle));
});
const steps = computed(() => filtered.value.filter((item): item is WorkflowStep => "stepType" in item));
const conclusions = computed(() => filtered.value.filter((item) => "nodeType" in item));
const currentTarget = computed(() => props.bundle.workflow.nodes.find((item) => item.id === props.currentTargetId));

onMounted(() => document.addEventListener("pointerdown", closeOutside));
onBeforeUnmount(() => document.removeEventListener("pointerdown", closeOutside));
watch(tab, () => void nextTick(focusActiveInput));

function toggle(): void {
  if (props.readonly) return;
  if (open.value) return close();
  open.value = true;
  if (open.value) void nextTick(focusActiveInput);
}

function choose(node: WorkflowNode): void {
  select({ kind: "existing", id: node.id });
}

function create(): void {
  const cleanName = name.value.trim();
  if (!cleanName) return;
  select(tab.value === "step"
    ? { kind: "step", name: cleanName, stepType: stepType.value }
    : { kind: "conclusion", name: cleanName });
}

function select(choice: WorkflowPathTargetChoice): void {
  emit("select", choice);
  close(props.variant === "target");
}

function close(restoreFocus = false): void {
  open.value = false;
  query.value = "";
  name.value = "";
  stepType.value = "expression";
  tab.value = "existing";
  if (restoreFocus) void nextTick(() => trigger.value?.focus());
}

function closeOutside(event: PointerEvent): void {
  if (root.value && !root.value.contains(event.target as Node)) close();
}

function focusActiveInput(): void {
  if (tab.value === "existing") queryInput.value?.focus();
  else nameInput.value?.focus();
}
</script>

<template>
  <div ref="root" :class="['workflow-path-target-picker', `is-${props.variant}`]">
    <button ref="trigger" :class="['workflow-path-target-trigger', open && 'active']" type="button" :disabled="props.readonly" aria-haspopup="dialog" :aria-expanded="open" @click="toggle">
      <Plus v-if="props.variant === 'add'" :size="14" />
      <span>{{ props.variant === "add" ? "添加路径" : currentTarget?.name || "选择目标节点" }}</span>
      <ChevronDown :size="13" />
    </button>

    <Transition name="workflow-popover">
      <div v-if="open" class="workflow-path-target-popover" role="dialog" aria-label="选择后续路径目标" @keydown.escape.stop="close(true)">
        <div class="workflow-path-target-tabs" role="tablist">
          <button v-for="item in [{ id: 'existing', label: '已有节点' }, { id: 'step', label: '新建步骤' }, { id: 'conclusion', label: '新建结论' }]" :key="item.id" :class="tab === item.id && 'active'" type="button" role="tab" :aria-selected="tab === item.id" @click="tab = item.id as typeof tab">{{ item.label }}</button>
        </div>

        <div v-if="tab === 'existing'" class="workflow-path-existing-panel">
          <label class="workflow-path-search"><Search :size="14" /><input ref="queryInput" v-model="query" type="search" placeholder="搜索节点名称" /></label>
          <div class="workflow-path-node-list">
            <section v-if="steps.length"><strong>步骤</strong><button v-for="item in steps" :key="item.id" type="button" @click="choose(item)"><TerminalSquare :size="14" /><span>{{ item.name }}</span><Check v-if="item.id === props.currentTargetId" :size="14" /></button></section>
            <section v-if="conclusions.length"><strong>结论</strong><button v-for="item in conclusions" :key="item.id" type="button" @click="choose(item)"><Flag :size="14" /><span>{{ item.name }}</span><Check v-if="item.id === props.currentTargetId" :size="14" /></button></section>
            <p v-if="filtered.length === 0">没有匹配的可用节点</p>
          </div>
        </div>

        <form v-else class="workflow-path-create-panel" @submit.prevent="create">
          <label class="field-label"><span>{{ tab === "step" ? "步骤名称" : "结论名称" }}</span><input ref="nameInput" v-model="name" type="text" /></label>
          <div v-if="tab === 'step'" class="workflow-path-step-types" role="group" aria-label="步骤类型">
            <button type="button" :class="stepType === 'expression' && 'active'" @click="stepType = 'expression'">条件表达式</button>
            <button type="button" :class="stepType === 'script' && 'active'" @click="stepType = 'script'">脚本草稿</button>
          </div>
          <UiButton variant="primary" type="submit" :disabled="!name.trim()"><template #icon><Plus /></template>创建并连接</UiButton>
        </form>
      </div>
    </Transition>
  </div>
</template>
