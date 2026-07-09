<script setup lang="ts">
import { computed } from "vue";
import { Ban, CircleAlert } from "lucide-vue-next";
import { builderProgressSteps, builderRecoveryNotice } from "../lib/builderUi";
import type { SkillBuilderSession } from "../../../types";

const props = defineProps<{
  session: SkillBuilderSession | null;
  cancelling: boolean;
}>();

const emit = defineEmits<{
  cancel: [];
}>();

const notice = computed(() => builderRecoveryNotice(props.session));
const progressSteps = computed(() => builderProgressSteps(props.session));
const canCancel = computed(() => props.session?.status === "running" && !props.cancelling);
</script>

<template>
  <section v-if="notice" :class="['builder-run-recovery', notice.tone]">
    <div class="builder-run-recovery-copy">
      <CircleAlert :size="18" />
      <div>
        <strong>{{ notice.title }}</strong>
        <p>{{ notice.message }}</p>
      </div>
    </div>
    <div v-if="progressSteps.length" class="builder-progress-steps" aria-label="AI 创建运行进度">
      <span v-for="step in progressSteps" :key="step.stage" :class="['builder-progress-step', step.state]">{{ step.label }}</span>
    </div>
    <button v-if="session?.status === 'running'" class="secondary-button" type="button" :disabled="!canCancel" @click="emit('cancel')">
      <Ban :size="16" />
      {{ cancelling ? "取消中..." : "取消本次运行" }}
    </button>
  </section>
</template>
