<script setup lang="ts">
import { computed } from "vue";
import UiButton from "./UiButton.vue";
import type { UiButtonSize, UiButtonState, UiButtonVariant } from "./button";
import UiTooltip from "./UiTooltip.vue";

const props = withDefaults(defineProps<{
  label: string;
  tooltip?: string;
  variant?: UiButtonVariant;
  size?: UiButtonSize;
  state?: UiButtonState;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
  disabledReason?: string;
  pressed?: boolean;
}>(), {
  tooltip: undefined,
  variant: "ghost",
  size: "md",
  state: "idle",
  type: "button",
  disabled: false,
  disabledReason: undefined,
  pressed: undefined,
});
const emit = defineEmits<{ click: [event: MouseEvent] }>();
const tooltipLabel = computed(() => props.disabled && props.disabledReason
  ? props.disabledReason
  : props.tooltip ?? props.label);
</script>

<template>
  <UiTooltip :label="tooltipLabel">
    <template #default="{ describedby }">
      <UiButton
        icon-only
        :variant="props.variant"
        :size="props.size"
        :state="props.state"
        :type="props.type"
        :disabled="props.disabled"
        :disabled-reason="props.disabledReason"
        :pressed="props.pressed"
        :aria-label="props.label"
        :aria-describedby="describedby"
        @click="emit('click', $event)"
      >
        <template #icon><slot /></template>
      </UiButton>
    </template>
  </UiTooltip>
</template>
