<script setup lang="ts">
import { computed } from "vue";
import type { WorkflowDebugScalar, WorkflowJsonSchema } from "../../../../types";
import { defaultWorkflowDebugScalar, workflowDebugScalarSupported } from "../form";

const props = defineProps<{
  label: string;
  description?: string;
  schema: WorkflowJsonSchema;
  present: boolean;
  value?: WorkflowDebugScalar;
  disabled?: boolean;
}>();
const emit = defineEmits<{
  presence: [present: boolean, initial: WorkflowDebugScalar];
  change: [value: WorkflowDebugScalar];
}>();

const supported = computed(() => workflowDebugScalarSupported(props.schema));

function updateInput(event: Event): void {
  const target = event.target as HTMLInputElement;
  if (props.schema.type === "integer") emit("change", target.value === "" ? 0 : Number.parseInt(target.value, 10));
  else if (props.schema.type === "number") emit("change", Number(target.value));
  else emit("change", target.value);
}
</script>

<template>
  <div class="workflow-debug-value-row">
    <div class="workflow-debug-value-label">
      <strong>{{ props.label }}</strong>
      <small v-if="props.description">{{ props.description }}</small>
    </div>
    <label class="workflow-debug-presence">
      <input
        type="checkbox"
        :checked="props.present"
        :disabled="props.disabled || (!supported && !props.present)"
        @change="emit('presence', ($event.target as HTMLInputElement).checked, defaultWorkflowDebugScalar(props.schema))"
      />
      提供
    </label>
    <template v-if="supported && props.present">
      <label class="workflow-debug-null-toggle">
        <input type="checkbox" :checked="props.value === null" :disabled="props.disabled" @change="emit('change', ($event.target as HTMLInputElement).checked ? null : defaultWorkflowDebugScalar(props.schema))" />
        null
      </label>
      <span v-if="props.value === null" class="workflow-debug-null-value">null</span>
      <label v-else-if="props.schema.type === 'boolean'" class="workflow-debug-boolean-value">
        <input type="checkbox" :checked="props.value === true" :disabled="props.disabled" @change="emit('change', ($event.target as HTMLInputElement).checked)" />
        {{ props.value === true ? "true" : "false" }}
      </label>
      <input
        v-else
        class="workflow-debug-scalar-input"
        :type="props.schema.type === 'string' ? 'text' : 'number'"
        :step="props.schema.type === 'integer' ? '1' : props.schema.type === 'number' ? 'any' : undefined"
        :value="props.value ?? ''"
        :disabled="props.disabled"
        :aria-label="`${props.label} 的值`"
        @input="updateInput"
      />
    </template>
    <span v-else-if="!supported" class="workflow-debug-unsupported">复杂类型暂不支持</span>
    <span v-else class="workflow-debug-missing">未提供</span>
  </div>
</template>
