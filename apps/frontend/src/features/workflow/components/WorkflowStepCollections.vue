<script setup lang="ts">
import { Plus } from "lucide-vue-next";
import { computed, ref } from "vue";
import type { CollectionCall, CollectionDefinition, WorkflowBinding, WorkflowBundle, WorkflowCollectionChange, WorkflowStep, WorkflowValidationIssue } from "../../../types";
import { useSortableList } from "../useSortableList";
import WorkflowCallEditor from "./WorkflowCallEditor.vue";
import WorkflowCollectionPicker from "./WorkflowCollectionPicker.vue";

const props = defineProps<{
  step: WorkflowStep;
  bundle: WorkflowBundle;
  catalog: CollectionDefinition[];
  changes: WorkflowCollectionChange[];
  issues: WorkflowValidationIssue[];
  readonly: boolean;
}>();
const emit = defineEmits<{
  "add-call": [definition: CollectionDefinition];
  "add-draft": [];
  "call-change": [id: string, patch: Partial<CollectionCall>];
  "call-remove": [id: string];
  "call-move": [id: string, direction: -1 | 1];
  "call-reorder": [ids: string[]];
  "binding-change": [callId: string, inputId: string, binding: WorkflowBinding | null];
  "definition-change": [callId: string, definition: CollectionDefinition];
}>();
const activeCallId = defineModel<string | null>("activeCallId", { default: null });
const list = ref<HTMLElement | null>(null);

useSortableList(list, {
  disabled: () => props.readonly,
  onReorder: (ids) => emit("call-reorder", ids),
});

function definition(call: CollectionCall): CollectionDefinition | undefined {
  return props.catalog.find((item) => item.id === call.definition.id && item.revision === call.definition.revision)
    ?? props.catalog.filter((item) => item.id === call.definition.id).sort((left, right) => right.revision - left.revision)[0];
}

function operation(call: CollectionCall): WorkflowCollectionChange["operation"] | undefined {
  return props.changes.find((item) => item.definition.id === call.definition.id)?.operation;
}

function callIssues(call: CollectionCall): WorkflowValidationIssue[] {
  return props.issues.filter((item) => (
    item.selection.type === "step" && item.selection.id === props.step.id && item.selection.itemId === call.id
  ) || (
    item.selection.type === "collection" && item.selection.id === call.definition.id
  ));
}

const hasCalls = computed(() => props.step.collectionCalls.length > 0);
</script>

<template>
  <section id="workflow-step-collections" class="workflow-step-section workflow-step-collections">
    <div class="workflow-subhead workflow-collection-actions">
      <div><h3>采集信息</h3><p>{{ props.step.collectionCalls.length }} 个采集调用，顺序用于生成和阅读。</p></div>
      <div class="workflow-add-call">
        <WorkflowCollectionPicker :definitions="props.catalog" :changes="props.changes" :readonly="props.readonly" @select="emit('add-call', $event)" />
        <button class="secondary-button" type="button" :disabled="props.readonly" @click="emit('add-draft')"><Plus :size="14" />新建采集</button>
      </div>
    </div>
    <div v-if="hasCalls" ref="list" class="workflow-call-list">
      <WorkflowCallEditor
        v-for="(call, index) in props.step.collectionCalls"
        :key="call.id"
        :call="call"
        :definition="definition(call)"
        :workflow-inputs="props.bundle.workflow.inputs"
        :roles="props.bundle.workflow.deviceRoles"
        :readonly="props.readonly"
        :expanded="activeCallId === call.id"
        :index="index"
        :total="props.step.collectionCalls.length"
        :pending-operation="operation(call)"
        :issues="callIssues(call)"
        @toggle="activeCallId = activeCallId === call.id ? null : call.id"
        @change="emit('call-change', call.id, $event)"
        @binding="(inputId, binding) => emit('binding-change', call.id, inputId, binding)"
        @definition="emit('definition-change', call.id, $event)"
        @remove="emit('call-remove', call.id)"
        @move="emit('call-move', call.id, $event)"
      />
    </div>
    <div v-else class="workflow-empty workflow-collection-empty">
      <strong>这个步骤还没有采集信息</strong>
      <span>从共享采集库选择，或直接新建一项。</span>
    </div>
  </section>
</template>
