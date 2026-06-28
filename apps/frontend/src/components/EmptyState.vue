<script setup lang="ts">
defineProps<{
  title: string;
  description: string;
  actionLabel?: string;
  secondaryLabel?: string;
}>();

const emit = defineEmits<{ action: []; secondary: [] }>();
</script>

<template>
  <div class="empty-state">
    <div class="empty-state-mark" aria-hidden="true">·</div>
    <div class="empty-state-copy">
      <strong>{{ title }}</strong>
      <p>{{ description }}</p>
    </div>
    <div v-if="actionLabel || secondaryLabel" class="empty-state-actions">
      <button v-if="actionLabel" class="primary-button" type="button" @click="emit('action')">{{ actionLabel }}</button>
      <button v-if="secondaryLabel" class="secondary-button" type="button" @click="emit('secondary')">{{ secondaryLabel }}</button>
    </div>
  </div>
</template>
