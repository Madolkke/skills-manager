<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { ArrowDown, Bot } from "lucide-vue-next";
import UiButton from "../../../../components/ui/UiButton.vue";
import type { WorkflowAgentDescriptor, WorkflowAgentEvent, WorkflowAgentRun } from "../../../../types";
import { useTransientScrollbar } from "../../useTransientScrollbar";
import { projectWorkflowAgentEvents } from "../timelineEntries";
import WorkflowAgentRunItem from "./WorkflowAgentRunItem.vue";

const props = defineProps<{ runs: WorkflowAgentRun[]; currentRun: WorkflowAgentRun | null; events: WorkflowAgentEvent[]; agents: WorkflowAgentDescriptor[] }>();
const emit = defineEmits<{ select: [run: WorkflowAgentRun]; proposal: [run: WorkflowAgentRun] }>();
const timeline = ref<HTMLElement | null>(null);
const followsLatest = ref(true);
const showJumpToLatest = ref(false);
const timelineEntries = computed(() => projectWorkflowAgentEvents(props.events));
useTransientScrollbar(timeline);

function agentName(id: string): string {
  return props.agents.find((item) => item.id === id)?.name ?? id;
}

function handleScroll(): void {
  const element = timeline.value;
  if (!element) return;
  followsLatest.value = element.scrollHeight - element.scrollTop - element.clientHeight <= 64;
  showJumpToLatest.value = !followsLatest.value;
}

function scrollToLatest(behavior: ScrollBehavior = "smooth"): void {
  const element = timeline.value;
  if (!element) return;
  element.scrollTo?.({ top: element.scrollHeight, behavior });
  followsLatest.value = true;
  showJumpToLatest.value = false;
}

async function selectRun(run: WorkflowAgentRun): Promise<void> {
  emit("select", run);
  await nextTick();
  const item = Array.from(timeline.value?.querySelectorAll<HTMLElement>("[data-run-id]") ?? []).find((node) => node.dataset.runId === run.id);
  if (item && timeline.value) {
    timeline.value.scrollTo?.({ top: Math.max(0, item.offsetTop - 6), behavior: "smooth" });
    followsLatest.value = false;
    showJumpToLatest.value = true;
  }
}

async function jumpToLatest(): Promise<void> {
  const latest = props.runs.at(-1);
  if (latest && props.currentRun?.id !== latest.id) emit("select", latest);
  await nextTick();
  scrollToLatest();
}

watch(() => props.events.length, async () => {
  const shouldFollow = followsLatest.value;
  await nextTick();
  if (shouldFollow) scrollToLatest("auto");
  else showJumpToLatest.value = true;
});

watch(() => props.runs.length, async () => {
  await nextTick();
  scrollToLatest("auto");
});
</script>

<template>
  <div ref="timeline" class="workflow-agent-timeline" @scroll="handleScroll">
    <div v-if="!props.runs.length" class="workflow-agent-empty"><Bot :size="24" /><strong>从当前 Workflow 开始提问</strong><span>助手可读取草稿、校验结果、相关采集定义和已有调试例。</span></div>
    <WorkflowAgentRunItem
      v-for="run in props.runs"
      :key="run.id"
      :run="run"
      :current="props.currentRun?.id === run.id"
      :agent-name="agentName(run.agent_id)"
      :entries="props.currentRun?.id === run.id ? timelineEntries : []"
      @select="selectRun"
      @proposal="$emit('proposal', $event)"
    />
    <UiButton v-if="showJumpToLatest" class="workflow-agent-jump-latest" size="sm" @click="jumpToLatest"><template #icon><ArrowDown /></template>回到最新</UiButton>
  </div>
</template>
