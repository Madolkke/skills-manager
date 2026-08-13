<script setup lang="ts">
import { Check, Copy } from "lucide-vue-next";
import { computed, ref } from "vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { CollectionDefinition, WorkflowBundle } from "../../../types";
import { findCollection, workflowSteps } from "../domain/utils";

const props = defineProps<{ bundle: WorkflowBundle; catalog: CollectionDefinition[] }>();
const emit = defineEmits<{ toast: [message: string, tone?: "success" | "error"] }>();
const copied = ref("");
let copiedTimer: ReturnType<typeof setTimeout> | undefined;

const commands = computed(() => {
  const seen = new Set<string>();
  return workflowSteps(props.bundle).flatMap((step) => step.collectionCalls.flatMap((call) => {
    const reference = `${call.definition.id}@${call.definition.revision}`;
    if (seen.has(reference)) return [];
    seen.add(reference);
    const definition = findCollection(props.catalog, call.definition);
    if (definition?.spec.collectionType !== "cli") return [];
    const references = workflowSteps(props.bundle).flatMap((candidate) => candidate.collectionCalls
      .filter((item) => item.definition.id === call.definition.id && item.definition.revision === call.definition.revision)
      .map(() => candidate.name));
    return [{ reference, definition, references, command: definition.spec.commandTemplate }];
  }));
});

async function copy(value: string, key: string): Promise<void> {
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
    copied.value = key;
    emit("toast", "命令已复制到剪贴板。", "success");
    if (copiedTimer) clearTimeout(copiedTimer);
    copiedTimer = setTimeout(() => { copied.value = ""; }, 1200);
  } catch {
    emit("toast", "复制失败，请检查浏览器剪贴板权限。", "error");
  }
}
</script>

<template>
  <section class="workflow-command-preview">
    <header>
      <div><strong>采集命令</strong><span>{{ commands.length }} 个 CLI 定义</span></div>
      <button type="button" :disabled="!commands.some((item) => item.command)" @click="copy(commands.map((item) => item.command).filter(Boolean).join('\n'), 'all')">
        <Check v-if="copied === 'all'" :size="15" /><Copy v-else :size="15" />{{ copied === "all" ? "已复制" : "复制全部" }}
      </button>
    </header>
    <div v-if="commands.length" class="workflow-command-list">
      <article v-for="(item, index) in commands" :key="item.reference" :class="!item.command && 'is-empty'">
        <div class="workflow-command-index">{{ String(index + 1).padStart(2, "0") }}</div>
        <div class="workflow-command-content">
          <div><strong>{{ item.definition.metadata.name || item.definition.key }}</strong><span>{{ item.references.join("、") }}</span></div>
          <code>{{ item.command || "未配置命令" }}</code>
        </div>
        <UiIconButton :label="`复制 ${item.definition.metadata.name || item.definition.key}`" size="sm" variant="secondary" :disabled="!item.command" @click="copy(item.command, item.reference)">
          <Check v-if="copied === item.reference" /><Copy v-else />
        </UiIconButton>
      </article>
    </div>
    <p v-else class="workflow-empty">当前 Workflow 没有 CLI 采集命令。</p>
  </section>
</template>
