<script setup lang="ts">
import { ChevronDown, ChevronRight } from "lucide-vue-next";
import type { WorkflowExpressionVariableTreeNode as VariableTreeNode } from "../workflowExpressionVariableTree";

const props = defineProps<{ node: VariableTreeNode; expanded: Set<string> }>();
const emit = defineEmits<{ toggle: [reference: string] }>();
</script>

<template>
  <li class="workflow-variable-tree-item">
    <div class="workflow-variable-tree-row">
      <button v-if="props.node.children.length" type="button" class="workflow-variable-tree-toggle" :aria-label="`${props.expanded.has(props.node.reference) ? '收起' : '展开'} ${props.node.reference}`" :aria-expanded="props.expanded.has(props.node.reference)" @click="emit('toggle', props.node.reference)">
        <ChevronDown v-if="props.expanded.has(props.node.reference)" :size="14" />
        <ChevronRight v-else :size="14" />
      </button>
      <span v-else class="workflow-variable-tree-spacer" aria-hidden="true" />
      <code>{{ props.node.reference }}</code>
      <span class="workflow-variable-tree-type">{{ props.node.dataType }}</span>
      <span v-if="props.node.source" class="workflow-variable-tree-source">{{ props.node.source }}</span>
    </div>
    <ul v-if="props.node.children.length && props.expanded.has(props.node.reference)" class="workflow-variable-tree-children">
      <WorkflowExpressionVariableTreeNode v-for="child in props.node.children" :key="child.id" :node="child" :expanded="props.expanded" @toggle="emit('toggle', $event)" />
    </ul>
  </li>
</template>
