<script setup lang="ts">
import type { CollectionDefinition, FunctionCollectionSpec } from "../../../types";
import { cloneWorkflow } from "../domain/utils";

const props = defineProps<{ definition: CollectionDefinition; readonly: boolean }>();
const emit = defineEmits<{ change: [definition: CollectionDefinition] }>();

function update(source: string): void {
  if (props.definition.spec.collectionType !== "function") return;
  const draft = cloneWorkflow(props.definition);
  (draft.spec as FunctionCollectionSpec).source = source;
  emit("change", draft);
}
</script>

<template>
  <section class="workflow-field-section" data-workflow-field="spec.source">
    <div class="workflow-subhead">
      <div><h3>Python 函数</h3><p>代码仅作为文本保存，不在 SkillHub 中执行或校验。</p></div>
    </div>
    <textarea class="workflow-code-input" rows="16" spellcheck="false" :value="props.definition.spec.collectionType === 'function' ? props.definition.spec.source : ''" :disabled="props.readonly" aria-label="Python 函数源码" @input="update(($event.target as HTMLTextAreaElement).value)" />
  </section>
</template>
