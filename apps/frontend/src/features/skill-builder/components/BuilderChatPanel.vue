<script setup lang="ts">
import { computed } from "vue";
import { Send } from "lucide-vue-next";
import type { SkillBuilderMessage } from "../../../types";
import BuilderMessageList from "./BuilderMessageList.vue";

const props = defineProps<{
  statusText: string;
  message: string;
  messages: SkillBuilderMessage[];
  running: boolean;
  runningSince?: string | null;
  canSend: boolean;
  sending: boolean;
}>();

const emit = defineEmits<{
  "update:message": [message: string];
  starter: [prompt: string];
  send: [];
}>();

const messageModel = computed({
  get: () => props.message,
  set: (value: string) => emit("update:message", value),
});

const messageLength = computed(() => props.message.trim().length);
const composerState = computed(() => {
  if (props.running) return "Agent 运行中";
  if (props.sending) return "发送中";
  if (!messageLength.value) return "等待输入";
  if (!props.canSend) return "暂不可发送";
  return "准备发送";
});
</script>

<template>
  <section class="builder-chat-panel">
    <header class="builder-panel-head">
      <div>
        <span class="eyebrow">Conversation</span>
        <h2>{{ statusText }}</h2>
      </div>
    </header>

    <BuilderMessageList :messages="messages" :running="running" :running-since="runningSince" @starter="emit('starter', $event)" />

    <div class="builder-composer" :class="{ active: messageLength > 0, running }">
      <div class="builder-composer-top">
        <div>
          <span class="builder-composer-title">发送给 Skill 创建 Agent</span>
          <span class="builder-composer-subtitle">描述目标、补充约束，或要求 Agent 修改工作区文件。</span>
        </div>
        <span class="builder-composer-state">{{ composerState }}</span>
      </div>
      <textarea
        v-model="messageModel"
        class="builder-composer-input"
        rows="4"
        placeholder="例如：帮我创建一个用于审查 PR 中权限问题和数据泄露风险的 Skill。"
      />
      <div class="builder-composer-actions">
        <span class="builder-composer-count">{{ messageLength ? `${messageLength} 字` : "消息为空" }}</span>
        <button class="primary-button builder-send-button" type="button" :disabled="!canSend" @click="emit('send')">
          <Send :size="16" />
          {{ sending ? "发送中..." : "发送" }}
        </button>
      </div>
    </div>
  </section>
</template>
