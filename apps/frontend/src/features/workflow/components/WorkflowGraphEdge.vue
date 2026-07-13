<script setup lang="ts">
import { BaseEdge, EdgeLabelRenderer, type EdgeProps } from "@vue-flow/core";
import type { WorkflowGraphEdgeData } from "../useWorkflowGraphLayout";

const props = defineProps<EdgeProps<WorkflowGraphEdgeData>>();
</script>

<template>
  <BaseEdge
    :id="props.id"
    :path="props.data.path"
    :marker-start="props.markerStart"
    :marker-end="props.markerEnd"
    :interaction-width="props.interactionWidth"
    :style="props.style"
  />
  <EdgeLabelRenderer>
    <div
      :class="['workflow-graph-edge-label', props.data.loop && 'is-loop']"
      :style="{
        width: `${props.data.labelSize.width}px`,
        minHeight: `${props.data.labelSize.height}px`,
        transform: `translate(-50%, -50%) translate(${props.data.labelPosition.x}px, ${props.data.labelPosition.y}px)`,
        '--workflow-edge-color': props.data.color,
      }"
      :title="props.data.label"
    >
      {{ props.data.label }}
    </div>
  </EdgeLabelRenderer>
</template>
