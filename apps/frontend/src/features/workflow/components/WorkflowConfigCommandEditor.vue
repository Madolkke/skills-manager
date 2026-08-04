<script setup lang="ts">
import { CirclePlus, ChevronDown, Trash2 } from "lucide-vue-next";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { WorkflowConfigCapture, WorkflowConfigCommand } from "../../../types";
import { isConfigIdentifier, parseConfigPattern, syncConfigCaptures } from "../domain/configPattern";

defineOptions({ name: "WorkflowConfigCommandEditor" });
const props = defineProps<{ command: WorkflowConfigCommand; readonly: boolean; path?: number[] }>();
const emit = defineEmits<{
  change: [payload: { path: number[]; command: WorkflowConfigCommand }];
  remove: [path: number[]];
}>();
const patternError = () => parseConfigPattern(props.command.pattern).error ?? "";
function commit(patch: Partial<WorkflowConfigCommand>): void {
  const next = structuredClone(props.command);
  Object.assign(next, patch);
  if (patch.pattern !== undefined) next.captures = syncConfigCaptures(next.pattern, next.captures);
  emit("change", { path: props.path ?? [], command: next });
}
function addChild(): void { commit({ children: [...props.command.children, { name: "command", unique: true, pattern: "", captures: {}, children: [] }] }); }
function addCapture(): void { const name = `capture_${Object.keys(props.command.captures).length + 1}`; commit({ pattern: `${props.command.pattern}${props.command.pattern ? " " : ""}<${name}>` }); }
function removeCapture(name: string): void { commit({ pattern: props.command.pattern.replace(new RegExp(`\\s*<${name}(?::[^>\\\\]*(?:\\\\.[^>\\\\]*)*)?>`, "u"), "").trim() }); }
function patchCapture(name: string, patch: Partial<WorkflowConfigCapture>): void { const captures = structuredClone(props.command.captures); Object.assign(captures[name], patch); commit({ captures }); }
</script>

<template>
  <article class="workflow-config-command-editor">
    <header class="workflow-config-command-header">
      <div class="workflow-config-command-title"><ChevronDown :size="16" /><strong>命令节点</strong><code>{{ props.command.name || "未命名" }}</code></div>
      <div class="workflow-config-command-actions"><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addChild"><template #icon><CirclePlus /></template>子命令</UiButton><UiIconButton label="删除配置命令" size="sm" variant="danger" :disabled="props.readonly" @click="emit('remove', props.path ?? [])"><Trash2 /></UiIconButton></div>
    </header>
    <div class="workflow-form-grid workflow-config-command-fields">
      <label class="field-label"><span>命令名</span><input :value="props.command.name" :disabled="props.readonly" :aria-invalid="!isConfigIdentifier(props.command.name)" @input="commit({ name: ($event.target as HTMLInputElement).value })" /><small>必须是合法 Python 标识符，且不能使用保留名称。</small></label>
      <label class="field-label"><span>匹配模式</span><input class="workflow-monospace" :value="props.command.pattern" :disabled="props.readonly" :aria-invalid="Boolean(patternError())" @input="commit({ pattern: ($event.target as HTMLInputElement).value })" /><small v-if="patternError()" class="field-error">{{ patternError() }}</small></label>
      <label class="workflow-config-unique"><input type="checkbox" :checked="props.command.unique !== false" :disabled="props.readonly" @change="commit({ unique: ($event.target as HTMLInputElement).checked })" /><span>匹配唯一命令</span></label>
    </div>
    <div class="workflow-config-captures">
      <div class="workflow-subhead"><div><h4>捕获字段</h4><p>{{ Object.keys(props.command.captures).length }} 个字段</p></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addCapture"><template #icon><CirclePlus /></template>添加捕获</UiButton></div>
      <div v-if="Object.keys(props.command.captures).length === 0" class="workflow-inline-empty">该命令不捕获参数，匹配成功时结果为对象。</div>
      <div v-for="(capture, name) in props.command.captures" :key="name" class="workflow-config-capture-row">
        <code>{{ name }}</code>
        <select :value="capture.type" :disabled="props.readonly" @change="patchCapture(name, { type: ($event.target as HTMLSelectElement).value as WorkflowConfigCapture['type'] })"><option value="string">string</option><option value="integer">integer</option><option value="number">number</option><option value="boolean">boolean</option></select>
        <input :value="capture.title" aria-label="捕获字段显示名称" :disabled="props.readonly" @input="patchCapture(name, { title: ($event.target as HTMLInputElement).value })" />
        <input :value="capture.description" aria-label="捕获字段说明" :disabled="props.readonly" placeholder="说明（可选）" @input="patchCapture(name, { description: ($event.target as HTMLInputElement).value })" />
        <UiIconButton label="删除捕获字段" size="sm" variant="danger" :disabled="props.readonly" @click="removeCapture(name)"><Trash2 /></UiIconButton>
      </div>
    </div>
    <div v-if="props.command.children.length" class="workflow-config-children"><WorkflowConfigCommandEditor v-for="(child, childIndex) in props.command.children" :key="`${child.name}:${child.pattern}`" :command="child" :readonly="props.readonly" :path="[...(props.path ?? []), childIndex]" @change="emit('change', $event)" @remove="emit('remove', $event)" /></div>
  </article>
</template>
