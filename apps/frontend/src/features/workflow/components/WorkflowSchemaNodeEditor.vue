<script setup lang="ts">
import { Plus, Trash2 } from "lucide-vue-next";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { WorkflowJsonSchema } from "../../../types";
import { changeWorkflowSchemaType, newWorkflowSchema, type WorkflowSchemaType } from "../workflowJsonSchema";
import { cloneWorkflow } from "../domain/utils";
import { isWorkflowExpressionIdentifier } from "../workflowExpressionSyntax";

defineOptions({ name: "WorkflowSchemaNodeEditor" });
type NodeSchemaType = WorkflowSchemaType | "string-array";
const props = withDefaults(defineProps<{
  schema: WorkflowJsonSchema;
  readonly: boolean;
  depth?: number;
  allowedTypes?: NodeSchemaType[];
  showMetadata?: boolean;
  showRequired?: boolean;
  showAdditionalProperties?: boolean;
  required?: boolean;
  identifierOnly?: boolean;
}>(), { depth: 0, allowedTypes: () => ["string", "integer", "number", "boolean", "string-array", "object", "array"], showMetadata: true, showRequired: false, showAdditionalProperties: false, required: false });
const emit = defineEmits<{ change: [schema: WorkflowJsonSchema]; requiredChange: [required: boolean] }>();
const typeLabels: Record<NodeSchemaType, string> = {
  string: "string", integer: "integer", number: "number", boolean: "boolean",
  "string-array": "字符串数组（string[]）", object: "object", array: "array",
};

function update(recipe: (draft: WorkflowJsonSchema) => void): void {
  const draft = cloneWorkflow(props.schema);
  recipe(draft);
  emit("change", draft);
}

function selectedType(): NodeSchemaType | "" {
  if (props.schema.type === "array" && props.schema.items.type === "string") return "string-array";
  return props.schema.type ?? "";
}

function setType(type: NodeSchemaType): void {
  if (type === "string-array") {
    emit("change", newWorkflowSchema("array", props.schema.title ?? "", props.schema.description ?? ""));
    return;
  }
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
  if (!next || next === previous || props.schema.type !== "object" || next in props.schema.properties || (props.identifierOnly && (!isWorkflowExpressionIdentifier(next) || next.startsWith("_")))) {
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

function setRequired(required: boolean): void {
  emit("requiredChange", required);
}

function setPropertyRequired(key: string, required: boolean): void {
  update((draft) => {
    if (draft.type !== "object") return;
    draft.required = required
      ? Array.from(new Set([...draft.required, key]))
      : draft.required.filter((item) => item !== key);
  });
}

function setAdditionalProperties(allowed: boolean): void {
  update((draft) => {
    if (draft.type === "object") draft.additionalProperties = allowed;
  });
}

</script>

<template>
  <section class="workflow-schema-node" :style="{ '--schema-depth': props.depth }">
    <div :class="['workflow-schema-basics', !props.showMetadata && 'type-only']">
      <label><span>类型</span><select :value="selectedType()" :disabled="props.readonly" @change="setType(($event.target as HTMLSelectElement).value as NodeSchemaType)"><option v-if="!props.schema.type" value="">any（旧版）</option><option v-for="type in props.allowedTypes" :key="type" :value="type">{{ typeLabels[type] }}</option></select></label>
      <label v-if="props.showMetadata"><span>显示名称</span><input :value="props.schema.title ?? ''" :disabled="props.readonly" placeholder="字段名称" @input="update((draft) => { draft.title = ($event.target as HTMLInputElement).value; })" /></label>
      <label v-if="props.showMetadata" class="workflow-schema-description"><span>说明</span><input :value="props.schema.description ?? ''" :disabled="props.readonly" placeholder="字段用途（可选）" @input="update((draft) => { draft.description = ($event.target as HTMLInputElement).value; })" /></label>
      <label v-if="props.showAdditionalProperties && props.schema.type === 'object'" class="workflow-schema-required"><input type="checkbox" :checked="props.schema.additionalProperties" :disabled="props.readonly" @change="setAdditionalProperties(($event.target as HTMLInputElement).checked)" /><span>允许额外属性</span></label>
    </div>

    <div v-if="props.schema.type === 'object'" class="workflow-schema-children">
      <header><div><strong>对象属性</strong><small>{{ Object.keys(props.schema.properties).length }} 个字段</small></div><UiButton size="sm" variant="secondary" :disabled="props.readonly" @click="addProperty"><template #icon><Plus /></template>添加属性</UiButton></header>
      <article v-for="(child, key) in props.schema.properties" :key="key" class="workflow-schema-property">
        <div class="workflow-schema-property-head">
          <label><span>变量名</span><input :value="key" :disabled="props.readonly" @change="renameProperty(key, $event.target as HTMLInputElement)" /></label>
          <label v-if="props.showRequired" class="workflow-schema-required"><input type="checkbox" :checked="props.required" :disabled="props.readonly" @change="setRequired(($event.target as HTMLInputElement).checked)" /><span>必填</span></label>
          <UiIconButton label="删除属性" size="sm" variant="danger" :disabled="props.readonly" @click="removeProperty(key)"><Trash2 /></UiIconButton>
        </div>
        <WorkflowSchemaNodeEditor :schema="child" :readonly="props.readonly" :depth="props.depth + 1" :identifier-only="props.identifierOnly" :show-required="props.showRequired" :show-additional-properties="props.showAdditionalProperties" :required="props.schema.required.includes(key)" @change="updateProperty(key, $event)" @required-change="(value) => setPropertyRequired(key, value)" />
      </article>
      <p v-if="Object.keys(props.schema.properties).length === 0" class="workflow-inline-empty">对象还没有属性。</p>
    </div>

    <div v-else-if="props.schema.type === 'array'" class="workflow-schema-children workflow-schema-array-items">
      <header><div><strong>数组元素</strong><small>items</small></div></header>
      <WorkflowSchemaNodeEditor :schema="props.schema.items" :readonly="props.readonly" :depth="props.depth + 1" @change="update((draft) => { if (draft.type === 'array') draft.items = $event; })" />
    </div>
  </section>
</template>
