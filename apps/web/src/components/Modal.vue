<script setup lang="ts">
import { X } from "lucide-vue-next";
import { onBeforeUnmount, onMounted } from "vue";

defineProps<{ title: string; description?: string }>();
const emit = defineEmits<{ close: [] }>();

onMounted(() => document.addEventListener("keydown", handleKeydown));
onBeforeUnmount(() => document.removeEventListener("keydown", handleKeydown));

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") emit("close");
}
</script>

<template>
  <Teleport to="body">
    <div class="modal-backdrop" @click="emit('close')" />
    <section class="modal-card" role="dialog" aria-modal="true" :aria-label="title">
      <header class="modal-head">
        <div>
          <h2 class="modal-title">{{ title }}</h2>
          <p v-if="description" class="modal-description">{{ description }}</p>
        </div>
        <button class="icon-button" type="button" aria-label="关闭" @click="emit('close')">
          <X :size="20" />
        </button>
      </header>
      <slot />
    </section>
  </Teleport>
</template>
