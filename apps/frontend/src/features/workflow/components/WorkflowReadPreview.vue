<script setup lang="ts">
import { ArrowRight, Flag, Play, Server, TerminalSquare } from "lucide-vue-next";
import type { CollectionDefinition, WorkflowBundle, WorkflowSelection } from "../../../types";
import { findCollection, workflowConclusions, workflowSteps } from "../domain/utils";

const props = defineProps<{ bundle: WorkflowBundle; catalog: CollectionDefinition[] }>();
const emit = defineEmits<{ select: [selection: WorkflowSelection] }>();
const roleName = (id?: string) => props.bundle.workflow.deviceRoles.find((item) => item.id === id)?.name ?? "单设备";
const targetName = (id: string) => props.bundle.workflow.nodes.find((item) => item.id === id)?.name ?? "无效目标";
</script>

<template>
  <div class="workflow-read-preview">
    <header><small>{{ props.bundle.workflow.metadata.code || "WORKFLOW" }}</small><h1>{{ props.bundle.workflow.metadata.name }}</h1><p>{{ props.bundle.workflow.metadata.description || "尚未填写工作流说明。" }}</p><div><span>{{ workflowSteps(props.bundle).filter((item) => item.isStart).length }} 个起点</span><span>{{ workflowSteps(props.bundle).length }} 个步骤</span><span>{{ workflowConclusions(props.bundle).length }} 个结论</span></div></header>
    <section v-if="props.bundle.workflow.inputs.length || props.bundle.workflow.deviceRoles.length" class="workflow-read-overview"><div><h2>全局输入</h2><p v-for="item in props.bundle.workflow.inputs" :key="item.id"><code>{{ item.key }}</code><span>{{ item.name }}</span><small>{{ item.dataType }} · {{ item.required ? "必填" : "可选" }}</small></p></div><div><h2>设备角色</h2><p v-for="item in props.bundle.workflow.deviceRoles" :key="item.id"><Server :size="13" /><span>{{ item.name }}</span><small>{{ item.description || item.key }}</small></p></div></section>
    <section class="workflow-read-steps"><h2>排查步骤</h2><article v-for="(step, index) in workflowSteps(props.bundle)" :key="step.id"><button type="button" @click="emit('select', { type: 'step', id: step.id })"><b>{{ String(index + 1).padStart(2, "0") }}</b><span><strong>{{ step.name }}</strong><small>{{ step.description || "尚未填写步骤说明" }}</small></span><i v-if="step.isStart"><Play :size="10" />起点</i></button><div class="workflow-read-step-body"><div v-for="call in step.collectionCalls" :key="call.id" class="workflow-read-call"><TerminalSquare :size="14" /><div><strong>{{ call.name }}</strong><small>{{ roleName(call.deviceRoleId) }} · 采集 {{ call.sampleCount }} 次</small><code>{{ findCollection(props.catalog, call.definition)?.spec.commandTemplate || "采集定义不可用" }}</code></div></div><div v-for="path in step.topology" :key="path.id" class="workflow-read-path"><span>{{ path.conditionText || "无条件" }}</span><ArrowRight :size="14" /><strong>{{ targetName(path.target.id) }}</strong></div></div></article></section>
    <section class="workflow-read-conclusions"><h2>排查结论</h2><button v-for="item in workflowConclusions(props.bundle)" :key="item.id" type="button" @click="emit('select', { type: 'conclusion', id: item.id })"><Flag :size="16" /><span><strong>{{ item.name }}</strong><small>故障根因：{{ item.rootCause || "尚未填写" }}</small><small>修复建议：{{ item.repairRecommendation || "尚未填写" }}</small></span></button></section>
  </div>
</template>
