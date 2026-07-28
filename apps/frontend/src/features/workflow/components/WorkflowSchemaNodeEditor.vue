<script setup lang="ts">
import { Plus, Trash2 } from "lucide-vue-next";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { WorkflowJsonSchema } from "../../../types";
import { changeWorkflowSchemaType, newWorkflowSchema, type WorkflowSchemaType } from "../workflowJsonSchema";
import { cloneWorkflow } from "../domain/utils";

defineOptions({ name: "WorkflowSchemaNodeEditor" });
const props = withDefaults(defineProps<{ schema: WorkflowJsonSchema; readonly: boolean; depth?: number }>(), { depth: 0 });
const emit = defineEmits<{ change: [schema: WorkflowJsonSchema] }>();
const schemaTypes: WorkflowSchemaType[] = ["string", "integer", "number", "boolean", "object", "array"];

function update(recipe: (draft: WorkflowJsonSchema) => void): void {
  const draft = cloneWorkflow(props.schema);
  recipe(draft);
  emit("change", draft);
}

function setType(type: WorkflowSchemaType): void {
  emit("change", changeWorkflowSchemaType(props.schema, type));
}

function addProperty(): void {
  if (props.schema.type !== "object") return;
  update((draft) => {
    if (draft.type !== "object") return;
    let index = Object.keys(draft.properties).length + 1;
    let key = `field_${index}`;
    while (key in draft.properties) key = `field_${++index}`;
    draft.properties[key] = newWorkflowSchema("string", key);
    draft.required.push(key);
  });
}

function renameProperty(previous: string, input: HTMLInputElement): void {
  const next = input.value.trim();
  if (!next || next === previous || props.schema.type !== "object" || next in props.schema.properties) {
    input.value = previous;
    return;
  }
  update((draft) => {
    if (draft.type !== "object") return;
    const entries = Object.entries(draft.properties).map(([key, child]) => [key === previous ? next : key, child] as const);
    draft.properties = Object.fromEntries(entries);
    draft.required = draft.required.map((key) => key === previous ? next : key);
  });
}

function updateProperty(key: string, schema: WorkflowJsonSchema): void {
  update((draft) => { if (draft.type === "object") draft.properties[key] = schema; });
}

function removeProperty(key: string): void {
  update((draft) => {
    if (draft.type !== "object") return;
    delete draft.properties[key];
    draft.required = draft.required.filter((item) => item !== key);
  });
}

function setRequired(key: string, required: boolean): void {
  update((draft) => {
    if (draft.type !== "object") return;
    draft.required = required ? [...new Set([...draft.required, key])] : draft.required.filter((item) => item !== key);
  });
}
</script>

<template>
  <section class="workflow-schema-node" :style="{ '--schema-depth': props.depth }">
    <div class="workflow-schema-basics">
      <label><span>类型</span><select :value="props.schema.type ?? ''" :disabled="props.readonly" @change="setType(($event.target as HTMLSelectElement).value as WorkflowSchemaType)"><option v-if="!props.schema.type" value="">any（旧版）</option><option v-for="type in schemaTypes" :key="type" :value="type">{{ type }}</option></select></label>
      <label><span>显示名称</span><input :value="props.schema.title ?? ''" :disabled="props.readonly" placeholder="字段名称" @input="update((draft) => { draft.title = ($event.target as HTMLInputElement).value; })" /></label>
      <label class="workflow-schema-description"><span>说明</span><input :value="props.schema.description ?? ''" :disabled="props.readonly" placeholder="字段用途（可选）" @input="update((draft) => { draft.description = ($event.target as HTMLInputElement).value; })" /></label>
    </div>

    <div v-if="props.schema.type === 'object'" class="workflow-schema-children">
      <header><div><strong>对象属性</strong><small>{{ Object.keys(props.schema.properties).length }} 个字段</small></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addProperty"><template #icon><Plus /></template>添加属性</UiButton></header>
      <article v-for="(child, key) in props.schema.properties" :key="key" class="workflow-schema-property">
        <div class="workflow-schema-property-head">
          <label><span>Property Key</span><input :value="key" :disabled="props.readonly" @change="renameProperty(key, $event.target as HTMLInputElement)" /></label>
          <label class="workflow-check"><input type="checkbox" :checked="props.schema.required.includes(key)" :disabled="props.readonly" @change="setRequired(key, ($event.target as HTMLInputElement).checked)" />必填</label>
          <UiIconButton label="删除属性" size="sm" variant="danger" :disabled="props.readonly" @click="removeProperty(key)"><Trash2 /></UiIconButton>
        </div>
        <WorkflowSchemaNodeEditor :schema="child" :readonly="props.readonly" :depth="props.depth + 1" @change="updateProperty(key, $event)" />
      </article>
      <p v-if="Object.keys(props.schema.properties).length === 0" class="workflow-inline-empty">对象还没有属性。</p>
    </div>

    <div v-else-if="props.schema.type === 'array'" class="workflow-schema-children workflow-schema-array-items">
      <header><div><strong>数组元素</strong><small>items</small></div></header>
      <WorkflowSchemaNodeEditor :schema="props.schema.items" :readonly="props.readonly" :depth="props.depth + 1" @change="update((draft) => { if (draft.type === 'array') draft.items = $event; })" />
    </div>
  </section>
</template>
