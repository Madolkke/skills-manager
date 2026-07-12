<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId } from "vue";

const props = withDefaults(defineProps<{
  label: string;
  delay?: number;
  disabled?: boolean;
}>(), {
  delay: 350,
  disabled: false,
});

const trigger = ref<HTMLElement | null>(null);
const tooltip = ref<HTMLElement | null>(null);
const visible = ref(false);
const placement = ref<"top" | "bottom">("top");
const left = ref(0);
const top = ref(0);
const id = useId();
let timer: number | null = null;

const style = computed(() => ({ left: `${left.value}px`, top: `${top.value}px` }));

function schedule(): void {
  if (props.disabled || !props.label) return;
  clearTimer();
  timer = window.setTimeout(() => void show(), props.delay);
}

async function show(): Promise<void> {
  const anchor = trigger.value;
  if (!anchor) return;
  visible.value = true;
  await nextTick();
  const anchorRect = anchor.getBoundingClientRect();
  const tooltipRect = tooltip.value?.getBoundingClientRect();
  const width = tooltipRect?.width ?? 0;
  placement.value = anchorRect.top > 52 ? "top" : "bottom";
  left.value = Math.min(window.innerWidth - width / 2 - 8, Math.max(width / 2 + 8, anchorRect.left + anchorRect.width / 2));
  top.value = placement.value === "top" ? anchorRect.top - 8 : anchorRect.bottom + 8;
  window.addEventListener("scroll", hide, true);
  window.addEventListener("resize", hide);
}

function hide(): void {
  clearTimer();
  visible.value = false;
  window.removeEventListener("scroll", hide, true);
  window.removeEventListener("resize", hide);
}

function clearTimer(): void {
  if (timer === null) return;
  window.clearTimeout(timer);
  timer = null;
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") hide();
}

onBeforeUnmount(hide);
</script>

<template>
  <span
    ref="trigger"
    class="ui-tooltip-trigger"
    @mouseenter="schedule"
    @mouseleave="hide"
    @focusin="schedule"
    @focusout="hide"
    @keydown="handleKeydown"
    @click="hide"
  >
    <slot :describedby="visible ? id : undefined" />
  </span>
  <Teleport to="body">
    <Transition name="ui-tooltip">
      <span
        v-if="visible"
        :id="id"
        ref="tooltip"
        :class="['ui-tooltip', `is-${placement}`]"
        :style="style"
        role="tooltip"
      >{{ props.label }}</span>
    </Transition>
  </Teleport>
</template>
