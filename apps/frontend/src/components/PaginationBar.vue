<script setup lang="ts">
import { computed } from "vue";
const props = defineProps<{ page: number; pageSize: number; total: number; loading?: boolean; error?: string }>();
const emit = defineEmits<{ "update:page": [value: number]; "update:pageSize": [value: number]; retry: [] }>();
const pages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)));
</script>

<template>
  <nav class="pagination-bar" aria-label="列表分页" :aria-busy="loading">
    <span v-if="error" role="alert">{{ error }} <button type="button" class="secondary-button" @click="emit('retry')">重试</button></span>
    <span v-else aria-live="polite">{{ loading ? '加载中…' : `共 ${total} 条` }}</span>
    <label>每页 <select :value="pageSize" aria-label="每页数量" @change="emit('update:pageSize', Number(($event.target as HTMLSelectElement).value))"><option v-for="size in [20, 50, 100]" :key="size" :value="size">{{ size }}</option></select></label>
    <button type="button" class="secondary-button" :disabled="page <= 1 || loading" @click="emit('update:page', page - 1)">上一页</button>
    <span>第 {{ page }} / {{ pages }} 页</span>
    <button type="button" class="secondary-button" :disabled="page >= pages || loading" @click="emit('update:page', page + 1)">下一页</button>
  </nav>
</template>

<style scoped>
.pagination-bar { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 10px; padding: 14px 0; font-size: 13px; }
.pagination-bar label { display: flex; align-items: center; gap: 6px; }
.pagination-bar select { width: auto; }
.pagination-bar [role="alert"] { color: var(--color-danger, #b42318); flex-basis: 100%; }
</style>
