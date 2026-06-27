<script setup lang="ts">
import type { PublishGateCheckDefinition, PublishGateExpression } from "../../types";

const props = defineProps<{
  node: PublishGateExpression;
  checks: PublishGateCheckDefinition[];
  checkById: Map<string, PublishGateCheckDefinition>;
  root?: boolean;
}>();

const emit = defineEmits<{
  addCheck: [group: PublishGateExpression];
  addGroup: [group: PublishGateExpression];
  removeChild: [group: PublishGateExpression, index: number];
  updateGroupOp: [node: PublishGateExpression, value: "and" | "or"];
  updateCheckId: [node: PublishGateExpression, value: string];
  updateParam: [node: PublishGateExpression, name: string, value: number];
}>();

function updateOp(event: Event): void {
  if (props.node.type !== "group") return;
  emit("updateGroupOp", props.node, (event.target as HTMLSelectElement).value as "and" | "or");
}

function updateParam(name: string, event: Event): void {
  if (props.node.type !== "check") return;
  emit("updateParam", props.node, name, Number((event.target as HTMLInputElement).value));
}
</script>

<template>
  <div :class="['gate-node', node.type, { root }]">
    <template v-if="node.type === 'group'">
      <div class="gate-node-head">
        <select :value="node.op" @change="updateOp">
          <option value="and">全部满足 AND</option>
          <option value="or">任一满足 OR</option>
        </select>
        <div class="button-row compact">
          <button class="secondary-button" type="button" @click="emit('addCheck', node)">添加门禁</button>
          <button class="secondary-button" type="button" @click="emit('addGroup', node)">添加条件组</button>
        </div>
      </div>
      <div class="gate-children">
        <div v-for="(child, index) in node.children" :key="index" class="gate-child-row">
          <AdminGateNodeEditor
            :node="child"
            :checks="checks"
            :check-by-id="checkById"
            @add-check="emit('addCheck', $event)"
            @add-group="emit('addGroup', $event)"
            @remove-child="(group, childIndex) => emit('removeChild', group, childIndex)"
            @update-group-op="(group, value) => emit('updateGroupOp', group, value)"
            @update-check-id="(checkNode, value) => emit('updateCheckId', checkNode, value)"
            @update-param="(checkNode, name, value) => emit('updateParam', checkNode, name, value)"
          />
          <button
            class="danger-button gate-delete-button"
            type="button"
            :disabled="node.children.length <= 1"
            title="删除"
            @click="emit('removeChild', node, index)"
          >
            x
          </button>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="gate-check-row">
        <select :value="node.check_id" @change="emit('updateCheckId', node, ($event.target as HTMLSelectElement).value)">
          <option v-for="check in checks" :key="check.id" :value="check.id">{{ check.label }}</option>
        </select>
        <p>{{ checkById.get(node.check_id)?.description || node.check_id }}</p>
      </div>
      <div v-if="checkById.get(node.check_id)?.params_schema.length" class="gate-param-grid">
        <label v-for="param in checkById.get(node.check_id)?.params_schema" :key="param.name" class="field-label">
          <span>{{ param.label }}</span>
          <input
            type="number"
            :min="param.min"
            :max="param.max"
            :step="param.step || 1"
            :value="node.params?.[param.name] ?? param.default ?? param.min ?? 0"
            @input="updateParam(param.name, $event)"
          />
        </label>
      </div>
    </template>
  </div>
</template>
