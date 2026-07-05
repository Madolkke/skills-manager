<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import type { SkillBuilderMessage } from "../../../types";
import BuilderRunningBubble from "./BuilderRunningBubble.vue";
import MarkdownContent from "./MarkdownContent.vue";

const props = defineProps<{
  messages: SkillBuilderMessage[];
  running: boolean;
  runningSince?: string | null;
}>();

const emit = defineEmits<{
  starter: [prompt: string];
}>();

const root = ref<HTMLElement | null>(null);
const starterPrompts = [
  "创建一个用于审查 PR 中权限问题和数据泄露风险的 Skill。",
  "创建一个用于检查部署前配置、环境变量和回滚步骤的 Skill。",
  "创建一个用于整理会议纪要并提取行动项的 Skill。",
];

watch(
  () => [props.messages.length, props.running],
  () => {
    void scrollToBottom();
  },
  { flush: "post" },
);

/** 等 DOM 更新后滚动到最新消息或运行占位。 */
async function scrollToBottom(): Promise<void> {
  await nextTick();
  const element = root.value;
  if (!element) return;
  element.scrollTo({ top: element.scrollHeight, behavior: prefersReducedMotion() ? "auto" : "smooth" });
}

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
</script>

<template>
  <div ref="root" class="builder-messages">
    <article v-for="item in messages" :key="item.id" :class="['builder-message', item.role]">
      <strong>{{ item.role === 'user' ? '你' : 'Skill 创建 Agent' }}</strong>
      <MarkdownContent :source="item.content" />
    </article>
    <BuilderRunningBubble v-if="running" :started-at="runningSince" />
    <div v-if="!messages.length && !running" class="builder-empty-state">
      <strong>准备开始创建 Skill</strong>
      <p>描述目标用户、触发场景、工作流程和需要参考的资料。也可以先选择一个示例填入输入框。</p>
      <div class="builder-starter-list">
        <button v-for="prompt in starterPrompts" :key="prompt" class="secondary-button" type="button" @click="emit('starter', prompt)">
          {{ prompt }}
        </button>
      </div>
    </div>
  </div>
</template>
