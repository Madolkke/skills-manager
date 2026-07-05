<script setup lang="ts">
import { AlertTriangle, MessageSquarePlus } from "lucide-vue-next";
import Modal from "../../../components/Modal.vue";

const emit = defineEmits<{
  close: [];
  confirm: [];
}>();
</script>

<template>
  <Modal title="新建会话" description="这会覆盖当前 AI 创建 Skill 会话。" @close="emit('close')">
    <div class="builder-confirm-content">
      <div class="builder-confirm-hero">
        <span class="builder-confirm-icon">
          <AlertTriangle :size="22" />
        </span>
        <div>
          <strong>当前对话和工作区文件会被删除</strong>
          <p>确认后只保留新的空白会话，该操作不可恢复。</p>
        </div>
      </div>
      <div class="builder-confirm-summary">
        <span>将清空当前消息记录</span>
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
