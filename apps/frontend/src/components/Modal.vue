<script setup lang="ts">
import clsx from "clsx";
import { X } from "lucide-vue-next";
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import UiIconButton from "./ui/UiIconButton.vue";

const props = withDefaults(defineProps<{
  title: string;
  description?: string;
  size?: "default" | "wide" | "workspace";
  open?: boolean;
  motion?: "default" | "workflow";
}>(), { open: true, motion: "default", size: "default", description: undefined });
const emit = defineEmits<{ close: []; afterLeave: [] }>();
const returnFocus = ref<HTMLElement | null>(null);

onBeforeUnmount(() => document.removeEventListener("keydown", handleKeydown));

watch(() => props.open, (open) => {
  if (open) {
    returnFocus.value = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    document.addEventListener("keydown", handleKeydown);
  } else {
    document.removeEventListener("keydown", handleKeydown);
  }
}, { immediate: true });

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") emit("close");
}

function afterLeave(): void {
  emit("afterLeave");
  void nextTick(() => returnFocus.value?.focus());
}
</script>

<template>
  <Teleport to="body">
    <Transition :name="props.motion === 'workflow' ? 'workflow-modal-backdrop' : undefined">
      <div v-if="props.open" :class="['modal-backdrop', props.motion === 'workflow' && 'motion-workflow']" @click="emit('close')" />
    </Transition>
    <Transition :name="props.motion === 'workflow' ? 'workflow-modal-surface' : undefined" @after-leave="afterLeave">
      <section v-if="props.open" :class="clsx('modal-card', props.size === 'wide' && 'wide', props.size === 'workspace' && 'workspace', props.motion === 'workflow' && 'motion-workflow')" role="dialog" aria-modal="true" :aria-label="props.title">
        <header class="modal-head">
          <div>
            <h2 class="modal-title">{{ props.title }}</h2>
            <p v-if="props.description" class="modal-description">{{ props.description }}</p>
          </div>
          <UiIconButton v-if="props.motion === 'workflow'" label="关闭" variant="ghost" @click="emit('close')">
            <X />
          </UiIconButton>
          <button v-else class="icon-button" type="button" aria-label="关闭" @click="emit('close')">
            <X :size="20" />
          </button>
        </header>
        <slot />
      </section>
    </Transition>
  </Teleport>
</template>
