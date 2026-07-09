<script setup lang="ts">
import { AlertTriangle, MessageSquarePlus } from "lucide-vue-next";
import Modal from "../../../components/Modal.vue";

defineProps<{ running?: boolean }>();

const emit = defineEmits<{
  close: [];
  confirm: [];
}>();
</script>

<template>
  <Modal title="新建会话" :description="running ? '这会取消当前运行并创建新的 AI 创建 Skill 会话。' : '这会覆盖当前 AI 创建 Skill 会话。'" @close="emit('close')">
    <div class="builder-confirm-content">
      <div class="builder-confirm-hero">
        <span class="builder-confirm-icon">
          <AlertTriangle :size="22" />
        </span>
        <div>
          <strong>{{ running ? "当前运行会被取消" : "当前对话和工作区文件会被删除" }}</strong>
          <p>{{ running ? "确认后只保留新的空白会话，旧运行的晚到结果会被忽略。" : "确认后只保留新的空白会话，该操作不可恢复。" }}</p>
        </div>
      </div>
      <div class="builder-confirm-summary">
        <span>{{ running ? "将停止等待当前 Agent 返回" : "将清空当前消息记录" }}</span>
        <span>将移除当前工作区快照</span>
        <span>不会影响已经提交的正式 Skill</span>
      </div>
      <div class="modal-actions builder-confirm-actions">
        <button class="secondary-button" type="button" @click="emit('close')">取消</button>
        <button class="primary-button" type="button" @click="emit('confirm')">
          <MessageSquarePlus :size="16" />
          新建空白会话
        </button>
      </div>
    </div>
  </Modal>
</template>
