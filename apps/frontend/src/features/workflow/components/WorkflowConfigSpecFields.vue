<script setup lang="ts">
import { CirclePlus } from "lucide-vue-next";
import { computed } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import type { CollectionDefinition, ConfigCollectionSpec, WorkflowConfigCommand } from "../../../types";
import { cloneWorkflow } from "../domain/utils";
import WorkflowConfigCommandEditor from "./WorkflowConfigCommandEditor.vue";

const props = defineProps<{ definition: CollectionDefinition; readonly: boolean }>();
const emit = defineEmits<{ change: [spec: ConfigCollectionSpec] }>();

const spec = computed(() => props.definition.spec.collectionType === "config" ? props.definition.spec : { collectionType: "config", config: { commands: [] } } as ConfigCollectionSpec);

function update(recipe: (draft: ConfigCollectionSpec) => void): void {
  const draft = cloneWorkflow(spec.value);
  recipe(draft);
  emit("change", draft);
}

function addCommand(): void {
  const command: WorkflowConfigCommand = { name: "command", unique: true, pattern: "", captures: {}, children: [] };
  update((draft) => draft.config.commands.push(command));
}

function patchCommand(payload: { path: number[]; command: WorkflowConfigCommand }): void {
  update((draft) => {
    const target = commandAtPath(draft.config.commands, payload.path);
    if (target) Object.assign(target, payload.command);
  });
}

function removeAtPath(path: number[]): void {
  if (!path.length) return;
  update((draft) => {
    const parent = path.length === 1 ? draft.config : commandAtPath(draft.config.commands, path.slice(0, -1));
    if (!parent) return;
    const list = "commands" in parent ? parent.commands : parent.children;
    list.splice(path[path.length - 1]!, 1);
  });
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
</script>

<template>
  <section class="workflow-field-section workflow-config-spec">
    <div class="workflow-subhead"><div><h3>配置匹配命令</h3><p>执行器负责从设备完整配置中匹配命令块；SkillHub 只保存结构和表达式契约。</p></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addCommand()"><template #icon><CirclePlus /></template>添加根命令</UiButton></div>
    <div v-if="spec.config.commands.length === 0" class="workflow-inline-empty">尚未添加配置命令</div>
    <div v-for="(command, commandIndex) in spec.config.commands" :key="`${command.name}:${command.pattern}`" class="workflow-config-command">
      <WorkflowConfigCommandEditor :command="command" :readonly="props.readonly" :path="[commandIndex]" @change="patchCommand" @remove="removeAtPath" />
    </div>
  </section>
</template>

<script lang="ts">
export default { name: "WorkflowConfigSpecFields" };
</script>
