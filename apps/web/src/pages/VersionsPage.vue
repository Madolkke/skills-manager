<script setup lang="ts">
import clsx from "clsx";
import { FileText, SquarePen, X } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import BundleBrowser from "../components/BundleBrowser.vue";
import BundleDiffPanel from "../components/BundleDiffPanel.vue";
import { humanDate, versionName } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import type { SkillDetail, SkillVersion, ToastState } from "../types";
import SkillEditForm from "./SkillEditForm.vue";
import VersionUploadForm from "./VersionUploadForm.vue";

const props = defineProps<{ skill: SkillDetail; selectedVersionId: string | null; uploadOpen: boolean }>();
const emit = defineEmits<{
  navigate: [next: Partial<RouteState>];
  "upload-close": [];
  uploaded: [];
  refresh: [];
  toast: [toast: ToastState];
}>();

const editOpen = ref(false);
const selected = computed(() => props.skill.versions.find((version) => version.id === props.selectedVersionId) ?? props.skill.summary.current_version ?? props.skill.versions[0] ?? null);
const previous = computed(() => (selected.value ? previousSkillVersion(props.skill.versions, selected.value) : null));
const files = computed(() => selected.value?.bundle_files ?? []);

watch(() => props.uploadOpen, (open) => {
  if (open) editOpen.value = false;
});

function finishEdit(): void {
  editOpen.value = false;
  emit("toast", { tone: "success", message: "Skill 已保存为新版本。" });
  emit("refresh");
}

function previousSkillVersion(versions: SkillVersion[], current: SkillVersion): SkillVersion | null {
  return [...versions]
    .filter((version) => version.version_number < current.version_number)
    .sort((left, right) => right.version_number - left.version_number)[0] ?? null;
}

</script>

<template>
  <div v-if="!selected" class="quiet-panel">还没有版本。</div>
  <div v-else :class="clsx('versions-workspace', uploadOpen && 'with-upload-panel')">
    <section class="version-node-strip" aria-label="Skill 版本节点">
      <button
        v-for="version in skill.versions"
        :key="version.id"
        :class="clsx('version-node', selected.id === version.id && 'active')"
        type="button"
        @click="emit('navigate', { selectedVersionId: version.id })"
      >
        <span>{{ versionName(version) }}</span>
        <small>{{ version.id === skill.skill.current_version_id ? "当前" : humanDate(version.created_at) }}</small>
      </button>
    </section>

    <section v-if="uploadOpen" class="version-upload-panel" aria-label="上传新版本">
      <div class="version-upload-head">
        <div>
          <h2>上传新版本</h2>
          <p>上传标准 Skill bundle 后会追加一个不可变 SkillVersion。</p>
        </div>
        <button class="icon-button" type="button" aria-label="关闭上传面板" @click="emit('upload-close')">
          <X :size="18" />
        </button>
      </div>
      <VersionUploadForm :skill="skill" actions-class-name="version-upload-actions" @cancel="emit('upload-close')" @uploaded="emit('uploaded')" />
    </section>

    <section v-if="editOpen" class="version-upload-panel" aria-label="编辑 Skill 内容">
      <div class="version-upload-head">
        <div>
          <h2>编辑 Skill</h2>
          <p>基于当前选中的不可变版本创建新 SkillVersion。</p>
        </div>
        <button class="icon-button" type="button" aria-label="关闭编辑面板" @click="editOpen = false">
          <X :size="18" />
        </button>
      </div>
      <SkillEditForm
        :key="selected.id"
        :skill="skill"
        :version="selected"
        actions-class-name="version-upload-actions"
        @cancel="editOpen = false"
        @saved="finishEdit"
      />
    </section>

    <section class="version-files-panel">
      <div class="panel-title-row">
        <h2>Bundle 内容</h2>
        <div class="button-row">
          <span class="version-meta-line">
            <FileText :size="16" />
            {{ files.length }} 个文件 · {{ humanDate(selected.created_at) }}
          </span>
          <button class="secondary-button" type="button" @click="() => { emit('upload-close'); editOpen = true; }">
            <SquarePen :size="16" />
            编辑 Skill
          </button>
        </div>
      </div>
      <BundleBrowser :files="files" :root-label="skill.skill.slug" />
    </section>

    <BundleDiffPanel :current="selected" :previous="previous" :versions="skill.versions" />
  </div>
</template>
