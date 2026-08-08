<script setup lang="ts">
import { CirclePlus } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import type { CollectionDefinition, ConfigCollectionSpec, WorkflowConfigCommand, WorkflowValidationIssue } from "../../../types";
import { cloneWorkflow } from "../domain/utils";
import WorkflowConfigCommandEditor from "./WorkflowConfigCommandEditor.vue";
import WorkflowConfirmModal from "./WorkflowConfirmModal.vue";

const props = defineProps<{ definition: CollectionDefinition; readonly: boolean; issues?: WorkflowValidationIssue[] }>();
const emit = defineEmits<{ change: [spec: ConfigCollectionSpec] }>();
const pendingRemovalPath = ref<number[] | null>(null);
const commandKeys = new Map<string, string>();
let nextCommandKey = 0;

const spec = computed(() => props.definition.spec.collectionType === "config" ? props.definition.spec : { collectionType: "config", config: { commands: [] } } as ConfigCollectionSpec);

watch(() => `${props.definition.id}@${props.definition.revision}`, () => commandKeys.clear());

function update(recipe: (draft: ConfigCollectionSpec) => void): void {
  const draft = cloneWorkflow(spec.value);
  recipe(draft);
  emit("change", draft);
}

function addCommand(): void {
  const command: WorkflowConfigCommand = { name: "command", unique: true, pattern: "", captures: {}, children: [] };
  update((draft) => draft.config.commands.push(command));
}

function commandIssues(): WorkflowValidationIssue[] {
  return (props.issues ?? []).filter((item) => item.selection.type === "collection" && item.selection.id === props.definition.id && item.selection.revision === props.definition.revision);
}

function patchCommand(payload: { path: number[]; command: WorkflowConfigCommand }): void {
  update((draft) => {
    const target = commandAtPath(draft.config.commands, payload.path);
    if (target) Object.assign(target, payload.command);
  });
}

function removeAtPath(path: number[]): void {
  if (!path.length) return;
  removeCommandKeys(path);
  update((draft) => {
    const parent = path.length === 1 ? draft.config : commandAtPath(draft.config.commands, path.slice(0, -1));
    if (!parent) return;
    const list = "commands" in parent ? parent.commands : parent.children;
    list.splice(path[path.length - 1]!, 1);
  });
}

function moveAtPath(path: number[], direction: -1 | 1): void {
  if (!path.length) return;
  moveCommandKeys(path, direction);
  update((draft) => {
    const parent = path.length === 1 ? draft.config : commandAtPath(draft.config.commands, path.slice(0, -1));
    if (!parent) return;
    const list = "commands" in parent ? parent.commands : parent.children;
    const index = path[path.length - 1]!;
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= list.length) return;
    [list[index], list[nextIndex]] = [list[nextIndex]!, list[index]!];
  });
}

function requestRemove(path: number[]): void {
  pendingRemovalPath.value = [...path];
}

function confirmRemove(): void {
  if (!pendingRemovalPath.value) return;
  removeAtPath(pendingRemovalPath.value);
  pendingRemovalPath.value = null;
}

function commandAtPath(commands: WorkflowConfigCommand[], path: number[]): WorkflowConfigCommand | undefined {
  let list = commands;
  let current: WorkflowConfigCommand | undefined;
  path.forEach((index) => {
    current = list[index];
    list = current?.children ?? [];
  });
  return current;
}

function commandKey(path: number[]): string {
  const key = path.join(".");
  const existing = commandKeys.get(key);
  if (existing) return existing;
  const created = `config-command-${nextCommandKey++}`;
  commandKeys.set(key, created);
  return created;
}

function moveCommandKeys(path: number[], direction: -1 | 1): void {
  const index = path.at(-1)!;
  const replacement = index + direction;
  if (replacement < 0) return;
  remapCommandKeys(path.slice(0, -1), (current) => current === index ? replacement : current === replacement ? index : current);
}

function removeCommandKeys(path: number[]): void {
  const index = path.at(-1)!;
  const parent = path.slice(0, -1);
  remapCommandKeys(parent, (current) => current > index ? current - 1 : current, index);
}

function remapCommandKeys(parent: number[], mapIndex: (index: number) => number, removedIndex?: number): void {
  const prefix = parent.length ? `${parent.join(".")}.` : "";
  const next = new Map<string, string>();
  commandKeys.forEach((value, path) => {
    if (!path.startsWith(prefix)) {
      next.set(path, value);
      return;
    }
    const suffix = path.slice(prefix.length).split(".");
    const index = Number(suffix[0]);
    if (!Number.isInteger(index) || index === removedIndex) return;
    suffix[0] = String(mapIndex(index));
    next.set(`${prefix}${suffix.join(".")}`, value);
  });
  commandKeys.clear();
  next.forEach((value, path) => commandKeys.set(path, value));
}
</script>

<template>
  <section class="workflow-field-section workflow-config-spec">
    <div class="workflow-subhead"><div><h3>配置匹配命令</h3><p>执行器负责从设备完整配置中匹配命令块；SkillHub 只保存结构和表达式契约。</p></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addCommand()"><template #icon><CirclePlus /></template>添加根命令</UiButton></div>
    <div v-if="spec.config.commands.length === 0" class="workflow-inline-empty">尚未添加配置命令</div>
    <div v-for="(command, commandIndex) in spec.config.commands" :key="commandKey([commandIndex])" class="workflow-config-command">
      <WorkflowConfigCommandEditor :command="command" :readonly="props.readonly" :path="[commandIndex]" :sibling-count="spec.config.commands.length" :issues="commandIssues()" :command-key="commandKey" @change="patchCommand" @remove="requestRemove" @move="moveAtPath" />
    </div>
    <WorkflowConfirmModal
      v-if="pendingRemovalPath"
      title="删除配置命令"
      description="删除命令会同时移除它的捕获字段和全部子命令，是否继续？"
      confirm-label="删除命令"
      tone="danger"
      @close="pendingRemovalPath = null"
      @confirm="confirmRemove"
    />
  </section>
</template>

<script lang="ts">
export default { name: "WorkflowConfigSpecFields" };
</script>
