<script setup lang="ts">
import type { SkillCore } from "../lib/api/paginationApi";

import clsx from "clsx";
import { Download, FileText, Rocket, SquarePen, X } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import BundleBrowser from "../components/BundleBrowser.vue";
import BundleDiffPanel from "../components/BundleDiffPanel.vue";
import { api, ApiError } from "../lib/api";
import { humanDate, versionName } from "../lib/format";
import PaginationBar from "../components/PaginationBar.vue";
import { usePagedQuery } from "../composables/usePagedQuery";
import { paginationApi } from "../lib/api/paginationApi";
import type { RouteState } from "../lib/navigation";
import type { SkillVersion, ToastState } from "../types";
import SkillEditForm from "./SkillEditForm.vue";
import VersionUploadForm from "./VersionUploadForm.vue";

const props = defineProps<{ skill: SkillCore; selectedVersionId: string | null; uploadOpen: boolean }>();
const emit = defineEmits<{
  navigate: [next: Partial<RouteState>];
  "upload-close": [];
  uploaded: [];
  refresh: [];
  toast: [toast: ToastState];
}>();

const editOpen = ref(false);
const bundleAction = ref<"download" | "publish" | null>(null);
const { page, pageSize, items: versions, total, loading, error, reload } = usePagedQuery("versions", () => ({ skill: props.skill.skill.id }),
  (params, signal) => paginationApi.versions(props.skill.skill.id, { page: params.page, page_size: params.page_size }, signal));
watch(() => [props.skill.version_count, props.skill.highest_version?.id], () => void reload());
const selected = ref<SkillVersion | null>(null);
const previous = ref<SkillVersion | null>(null);
const detailError = ref("");
const detailLoading = ref(false);
const detailRetry = ref(0);
watch(() => [props.selectedVersionId ?? props.skill.skill.current_version_id ?? versions.value[0]?.id, detailRetry.value] as const, async ([id], _, cleanup) => {
  selected.value = null; previous.value = null; detailError.value = "";
  const controller = new AbortController(); cleanup(() => controller.abort());
  if (!id) return;
  detailLoading.value = true;
  try { const detail = await paginationApi.version(id, controller.signal); if (!controller.signal.aborted) { selected.value = detail.version; previous.value = detail.previous; } }
  catch (e) { if (!controller.signal.aborted) detailError.value = e instanceof Error ? e.message : "版本加载失败"; }
  finally { if (!controller.signal.aborted) detailLoading.value = false; }
}, { immediate: true });
const files = computed(() => selected.value?.bundle_files ?? []);

watch(() => props.uploadOpen, (open) => {
  if (open) editOpen.value = false;
});

function finishEdit(): void {
  editOpen.value = false;
  emit("toast", { tone: "success", message: "Skill 已保存为新版本。" });
  emit("refresh");
}

async function downloadBundle(): Promise<void> {
  if (!selected.value || bundleAction.value) return;
  bundleAction.value = "download";
  try {
    const blob = await api.downloadSkillBundle(selected.value.id);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${props.skill.skill.slug}-${selected.value.version}.zip`;
    anchor.click();
    URL.revokeObjectURL(url);
    emit("toast", { tone: "success", message: "Skill 压缩包已开始下载。" });
  } catch (error) {
    emit("toast", { tone: "danger", message: errorMessage(error, "下载 Skill 失败。") });
  } finally {
    bundleAction.value = null;
  }
}

async function quickPublishBundle(): Promise<void> {
  if (!selected.value || bundleAction.value) return;
  bundleAction.value = "publish";
  try {
    const result = await api.quickPublishSkillBundle(selected.value.id);
    emit("toast", { tone: "success", message: `Skill 已发布至 ${result.destination}。` });
  } catch (error) {
    emit("toast", { tone: "danger", message: errorMessage(error, "快速发布 Skill 失败。") });
  } finally {
    bundleAction.value = null;
  }
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError || error instanceof Error ? error.message : fallback;
}

</script>

<template>
  <div class="versions-page">
    <PaginationBar v-model:page="page" v-model:page-size="pageSize" :total="total" :loading="loading" :error="error || detailError" @retry="() => { detailRetry++; reload(); }" />
    <div v-if="!selected" class="quiet-panel">{{ detailLoading ? "正在加载版本…" : detailError ? "版本读取失败，请重试。" : "还没有版本。" }}</div>
    <div v-else :class="clsx('versions-workspace', uploadOpen && 'with-upload-panel')">
      <section class="version-node-strip" aria-label="Skill 版本节点">
        <button
          v-for="version in versions"
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
            <p>上传标准 Skill内容后会追加一个不可变 Skill 版本。</p>
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
            <p>基于当前选中的不可变版本创建新 Skill 版本。</p>
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
          <h2>Skill内容</h2>
          <div class="button-row">
            <span class="version-meta-line">
              <FileText :size="16" />
              {{ files.length }} 个文件 · {{ humanDate(selected.created_at) }}
            </span>
            <button class="secondary-button" type="button" :disabled="bundleAction !== null" @click="downloadBundle">
              <Download :size="16" />
              {{ bundleAction === "download" ? "正在下载" : "下载 Skill" }}
            </button>
            <button class="secondary-button" type="button" :disabled="bundleAction !== null" @click="quickPublishBundle">
              <Rocket :size="16" />
              {{ bundleAction === "publish" ? "正在发布" : "快速发布" }}
            </button>
            <button class="secondary-button" type="button" @click="() => { emit('upload-close'); editOpen = true; }">
              <SquarePen :size="16" />
              编辑 Skill
            </button>
          </div>
        </div>
        <BundleBrowser :files="files" :root-label="skill.skill.slug" />
      </section>

      <BundleDiffPanel :current="selected" :previous="previous" :version-count="skill.version_count" />
    </div>
  </div>
</template>
