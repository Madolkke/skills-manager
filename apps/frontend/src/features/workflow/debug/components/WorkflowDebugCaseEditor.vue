<script setup lang="ts">
import { computed } from "vue";
import type { WorkflowBundle, WorkflowDebugCollectionFixture as DebugCollectionFixture, WorkflowDebugScalar, WorkflowStep } from "../../../../types";
import { findCollection } from "../../domain/utils";
import { cloneDebugValue, hasDebugValue, workflowDebugTargetName, type WorkflowDebugCaseDraft } from "../form";
import WorkflowDebugCollectionFixture from "./WorkflowDebugCollectionFixture.vue";
import WorkflowDebugScalarField from "./WorkflowDebugScalarField.vue";

const props = defineProps<{
  bundle: WorkflowBundle;
  step: WorkflowStep;
  draft: WorkflowDebugCaseDraft;
  disabled?: boolean;
}>();
const emit = defineEmits<{ change: [draft: WorkflowDebugCaseDraft] }>();
const directTargets = computed(() => [...new Set(props.step.topology.map((transition) => transition.target.id))]
  .filter((id) => props.bundle.workflow.nodes.some((node) => node.id === id)));

function patch(values: Partial<WorkflowDebugCaseDraft>): void {
  emit("change", { ...cloneDebugValue(props.draft), ...values });
}

function setInputPresence(id: string, present: boolean, initial: WorkflowDebugScalar): void {
  const inputs = cloneDebugValue(props.draft.workflow_inputs);
  if (present) inputs[id] = initial;
  else delete inputs[id];
  patch({ workflow_inputs: inputs });
}

function setInput(id: string, value: WorkflowDebugScalar): void {
  patch({ workflow_inputs: { ...props.draft.workflow_inputs, [id]: value } });
}

function setFixture(callId: string, fixture: DebugCollectionFixture | null): void {
  const fixtures = cloneDebugValue(props.draft.collection_fixtures);
  if (fixture) fixtures[callId] = fixture;
  else delete fixtures[callId];
  patch({ collection_fixtures: fixtures });
}
</script>

<template>
  <div class="workflow-debug-case-editor">
    <div class="workflow-debug-case-basics">
      <label class="field-label"><span>调试例名称</span><input :value="props.draft.name" :disabled="props.disabled" maxlength="160" @input="patch({ name: ($event.target as HTMLInputElement).value })" /></label>
      <label class="field-label"><span>预期跳转节点</span><select :value="props.draft.expected_target_id" :disabled="props.disabled" @change="patch({ expected_target_id: ($event.target as HTMLSelectElement).value })"><option value="" disabled>请选择直接下游节点</option><option v-for="targetId in directTargets" :key="targetId" :value="targetId">{{ workflowDebugTargetName(props.bundle, targetId) }}</option></select></label>
      <label class="field-label span-2"><span>说明</span><textarea rows="2" :value="props.draft.description" :disabled="props.disabled" placeholder="记录此调试例覆盖的场景（可选）" @input="patch({ description: ($event.target as HTMLTextAreaElement).value })" /></label>
    </div>

    <section class="workflow-debug-editor-section">
      <div class="workflow-debug-section-title"><div><h3>全局输入</h3><p>只有勾选“提供”的键会进入调试请求；可显式提交 null。</p></div></div>
      <div v-if="props.bundle.workflow.inputs.length" class="workflow-debug-value-list">
        <WorkflowDebugScalarField
          v-for="input in props.bundle.workflow.inputs"
          :key="input.id"
          :label="input.schema.title || input.key"
          :description="input.schema.description"
          :schema="input.schema"
          :present="hasDebugValue(props.draft.workflow_inputs, input.id)"
          :value="props.draft.workflow_inputs[input.id]"
          :disabled="props.disabled"
          @presence="(present, initial) => setInputPresence(input.id, present, initial)"
          @change="setInput(input.id, $event)"
        />
      </div>
      <p v-else class="workflow-debug-empty-inline">当前 Workflow 没有全局输入。</p>
    </section>

    <section class="workflow-debug-editor-section">
      <div class="workflow-debug-section-title"><div><h3>采集信息</h3><p>按当前步骤中的采集调用提供设备回显与结构化输出。</p></div></div>
      <div v-if="props.step.collectionCalls.length" class="workflow-debug-fixtures">
        <WorkflowDebugCollectionFixture
          v-for="call in props.step.collectionCalls"
          :key="call.id"
          :call="call"
          :definition="findCollection(props.bundle.collectionSnapshots, call.definition)"
          :fixture="props.draft.collection_fixtures[call.id]"
          :disabled="props.disabled"
          @change="setFixture(call.id, $event)"
        />
      </div>
      <p v-else class="workflow-debug-empty-inline">当前步骤没有采集调用。</p>
    </section>
  </div>
</template>
