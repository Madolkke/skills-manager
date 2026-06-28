<script setup lang="ts">
import { Bell, RefreshCw, X } from "lucide-vue-next";
import EmptyState from "./EmptyState.vue";
import type { TaskCenterGroup, TaskCenterItem } from "../lib/taskCenter";

defineProps<{
  groups: TaskCenterGroup[];
  loading: boolean;
  error: string;
  badgeCount: number;
}>();

const emit = defineEmits<{ close: []; refresh: []; open: [item: TaskCenterItem] }>();

function dateText(value?: string): string {
  if (!value) return "";
  return new Date(value).toLocaleString();
}
</script>

<template>
  <div class="task-center-popover" role="dialog" aria-label="任务中心">
    <header class="task-center-head">
      <div>
        <span>任务中心</span>
        <h2>{{ badgeCount ? `${badgeCount} 项待处理` : "暂无待处理任务" }}</h2>
      </div>
      <button class="icon-button mini" type="button" :disabled="loading" aria-label="刷新任务中心" @click="emit('refresh')">
        <RefreshCw :size="15" />
      </button>
      <button class="icon-button mini" type="button" aria-label="关闭任务中心" @click="emit('close')">
        <X :size="15" />
      </button>
    </header>
    <div v-if="error" class="task-center-error">{{ error }}</div>
    <div v-else-if="loading" class="task-center-loading">正在加载任务...</div>
    <EmptyState
      v-else-if="!groups.length"
      title="当前没有需要处理的任务"
      description="新的评审、通知、运行中测评和待确认发布会出现在这里。"
    />
    <div v-else class="task-center-groups">
      <section v-for="group in groups" :key="group.id" class="task-center-group">
        <h3>{{ group.label }}</h3>
        <button
          v-for="item in group.items"
          :key="item.id"
          :class="['task-center-item', item.tone]"
          type="button"
          @click="emit('open', item)"
        >
          <span class="task-center-item-icon" aria-hidden="true"><Bell :size="15" /></span>
          <span class="task-center-item-copy">
            <strong>{{ item.title }}</strong>
            <small>{{ item.description }}</small>
            <time v-if="dateText(item.createdAt)">{{ dateText(item.createdAt) }}</time>
          </span>
          <span class="task-center-item-action">{{ item.actionLabel }}</span>
        </button>
      </section>
    </div>
  </div>
</template>
