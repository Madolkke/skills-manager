<script setup lang="ts">
withDefaults(defineProps<{ label?: string }>(), {
  label: "正在加载...",
});
</script>

<template>
  <div class="inline-loading" role="status" aria-live="polite">
    <span aria-hidden="true" />
    {{ label }}
  </div>
</template>
