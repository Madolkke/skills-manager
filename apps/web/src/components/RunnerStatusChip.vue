<script setup lang="ts">
import { CheckCircle2, Circle, Clock3, LoaderCircle, XCircle } from "lucide-vue-next";
import { computed } from "vue";

const props = defineProps<{
  kind: "not-run" | "queued" | "running" | "passed" | "failed" | "rejected";
  label: string;
}>();

const icon = computed(() => {
  if (props.kind === "queued") return Clock3;
  if (props.kind === "running") return LoaderCircle;
  if (props.kind === "passed") return CheckCircle2;
  if (props.kind === "failed" || props.kind === "rejected") return XCircle;
  return Circle;
});
</script>

<template>
  <span :class="['runner-status-chip', kind]">
    <component :is="icon" :size="14" aria-hidden="true" />
    {{ label }}
  </span>
</template>
