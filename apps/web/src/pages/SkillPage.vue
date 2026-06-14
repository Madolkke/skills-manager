<script setup lang="ts">
import { Upload } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import SkillTabs from "../components/Tabs.vue";
import type { RouteState, SkillTab } from "../lib/navigation";
import type { SkillDetail, ToastState } from "../types";
import EvalSetsPage from "./EvalSetsPage.vue";
import EvaluatePage from "./EvaluatePage.vue";
import HistoryPage from "./HistoryPage.vue";
import OverviewPage from "./OverviewPage.vue";
import UploadVersionModal from "./UploadVersionModal.vue";
import VersionsPage from "./VersionsPage.vue";

const props = defineProps<{ skill: SkillDetail; tab: SkillTab; route: RouteState }>();
const emit = defineEmits<{
  tab: [tab: SkillTab];
  refresh: [];
  navigate: [next: Partial<RouteState>];
  toast: [toast: ToastState];
}>();

const uploadOpen = ref(false);
const canUploadVersion = computed(() => props.tab === "overview" || props.tab === "versions");

watch(() => [props.skill.skill.id, props.tab] as const, () => {
  uploadOpen.value = false;
});

function finishUpload(): void {
  uploadOpen.value = false;
  emit("toast", { tone: "success", message: "版本已上传。" });
  emit("refresh");
}
</script>

<template>
  <div class="skill-page">
    <div class="skill-nav-row">
      <SkillTabs :active="tab" @change="emit('tab', $event)" />
      <button v-if="canUploadVersion" class="primary-button" type="button" @click="uploadOpen = true">
        <Upload :size="17" />
        上传版本
      </button>
    </div>

    <OverviewPage v-if="tab === 'overview'" :skill="skill" @navigate="emit('navigate', $event)" />
    <VersionsPage
      v-else-if="tab === 'versions'"
      :skill="skill"
      :selected-version-id="route.selectedVersionId"
      :upload-open="uploadOpen"
      @navigate="emit('navigate', $event)"
      @upload-close="uploadOpen = false"
      @uploaded="finishUpload"
      @refresh="emit('refresh')"
      @toast="emit('toast', $event)"
    />
    <EvalSetsPage
      v-else-if="tab === 'evalsets'"
      :skill="skill"
      :selected-case-id="route.selectedCaseId"
      @navigate="emit('navigate', $event)"
      @refresh="emit('refresh')"
      @toast="emit('toast', $event)"
    />
    <EvaluatePage
      v-else-if="tab === 'evaluate'"
      :skill="skill"
      @refresh="emit('refresh')"
      @navigate="emit('navigate', $event)"
      @toast="emit('toast', $event)"
    />
    <HistoryPage
      v-else-if="tab === 'history'"
      :skill="skill"
      :selected-run-id="route.selectedRunId"
      @navigate="emit('navigate', $event)"
      @toast="emit('toast', $event)"
    />

    <UploadVersionModal v-if="uploadOpen && tab === 'overview'" :skill="skill" @close="uploadOpen = false" @uploaded="finishUpload" />
  </div>
</template>
