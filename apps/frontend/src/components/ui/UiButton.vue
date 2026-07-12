<script setup lang="ts">
import { Check, LoaderCircle } from "lucide-vue-next";
import { computed, useAttrs } from "vue";
import type { UiButtonSize, UiButtonState, UiButtonVariant } from "./button";

defineOptions({ inheritAttrs: false });

const props = withDefaults(defineProps<{
  variant?: UiButtonVariant;
  size?: UiButtonSize;
  state?: UiButtonState;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
  disabledReason?: string;
  pressed?: boolean;
  ariaLabel?: string;
  loadingLabel?: string;
  successLabel?: string;
  iconOnly?: boolean;
}>(), {
  variant: "secondary",
  size: "md",
  state: "idle",
  type: "button",
  disabled: false,
  disabledReason: undefined,
  pressed: undefined,
  ariaLabel: undefined,
  loadingLabel: "处理中",
  successLabel: "已完成",
  iconOnly: false,
});
const emit = defineEmits<{ click: [event: MouseEvent] }>();
const attrs = useAttrs();

const interactionDisabled = computed(() => props.disabled || props.state !== "idle");
const nativeDisabled = computed(() => props.state !== "idle" || (props.disabled && !props.disabledReason));
const title = computed(() => props.disabled && props.disabledReason
  ? props.disabledReason
  : typeof attrs.title === "string" ? attrs.title : undefined);

function click(event: MouseEvent): void {
  if (interactionDisabled.value) {
    event.preventDefault();
    event.stopImmediatePropagation();
    return;
  }
  emit("click", event);
}
</script>

<template>
  <button
    v-bind="attrs"
    :class="['ui-button', `is-${props.variant}`, `is-${props.size}`, props.iconOnly && 'is-icon-only']"
    :type="props.type"
    :disabled="nativeDisabled"
    :data-state="props.state"
    :data-disabled="props.disabled || undefined"
    :title="title"
    :aria-label="props.ariaLabel"
    :aria-pressed="props.pressed"
    :aria-disabled="interactionDisabled || undefined"
    :aria-busy="props.state === 'loading' || undefined"
    @click="click"
  >
    <span class="ui-button-content ui-button-idle" :aria-hidden="props.state !== 'idle'">
      <span v-if="$slots.icon" class="ui-button-icon"><slot name="icon" /></span>
      <span v-if="!props.iconOnly" class="ui-button-label"><slot /></span>
    </span>
    <span class="ui-button-content ui-button-loading" :aria-hidden="props.state !== 'loading'">
      <LoaderCircle class="ui-button-spinner" aria-hidden="true" />
      <span v-if="!props.iconOnly" class="ui-button-label">{{ props.loadingLabel }}</span>
    </span>
    <span class="ui-button-content ui-button-success" :aria-hidden="props.state !== 'success'">
      <Check class="ui-button-check" aria-hidden="true" />
      <span v-if="!props.iconOnly" class="ui-button-label">{{ props.successLabel }}</span>
    </span>
  </button>
</template>
