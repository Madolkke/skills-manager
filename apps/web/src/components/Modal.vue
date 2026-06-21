<script setup lang="ts">
import clsx from "clsx";
import { X } from "lucide-vue-next";
import { onBeforeUnmount, onMounted } from "vue";

const props = defineProps<{ title: string; description?: string; size?: "default" | "wide" }>();
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
    <section :class="clsx('modal-card', props.size === 'wide' && 'wide')" role="dialog" aria-modal="true" :aria-label="props.title">
      <header class="modal-head">
        <div>
          <h2 class="modal-title">{{ props.title }}</h2>
          <p v-if="props.description" class="modal-description">{{ props.description }}</p>
        </div>
        <button class="icon-button" type="button" aria-label="关闭" @click="emit('close')">
          <X :size="20" />
        </button>
      </header>
      <slot />
    </section>
  </Teleport>
</template>
