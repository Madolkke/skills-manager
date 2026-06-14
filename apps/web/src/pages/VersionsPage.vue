<script setup lang="ts">
import clsx from "clsx";
import { FileText, Pencil, Save, SquarePen, X } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import BundleBrowser from "../components/BundleBrowser.vue";
import BundleDiffPanel from "../components/BundleDiffPanel.vue";
import { api, ApiError } from "../lib/api";
import { compactText, humanDate, scoreKind, scoreLabel, versionName } from "../lib/format";
import { compactDigest } from "../lib/history";
import type { RouteState } from "../lib/navigation";
import type { EvalRunRecord, SkillDetail, SkillVersion, ToastState } from "../types";
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
const evalSetName = computed(() => props.skill.summary.primary_eval_set?.name ?? "未绑定");
const latestRun = computed(() => (selected.value ? latestRunForVersion(selected.value, props.skill.latest_eval_runs) : null));
const files = computed(() => selected.value?.bundle_files ?? []);

watch(() => props.uploadOpen, (open) => {
  if (open) editOpen.value = false;
});

async function renameSelected(displayName: string | null): Promise<void> {
  if (!selected.value) return;
  try {
    await api.updateSkillVersionName(selected.value.id, displayName);
    emit("toast", { tone: "success", message: "Skill 版本名称已更新。" });
    emit("refresh");
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  }
}

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

function latestRunForVersion(version: SkillVersion, runs: EvalRunRecord[]): EvalRunRecord | null {
  return [...runs]
    .filter((run) => run.skill_version_id === version.id)
    .sort((left, right) => Date.parse(right.created_at ?? "") - Date.parse(left.created_at ?? ""))[0] ?? null;
}

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiError || caught instanceof Error) return caught.message;
  return "操作失败。";
}
</script>

<template>
  <div v-if="!selected" class="quiet-panel">还没有版本。</div>
  <div v-else :class="clsx('versions-workspace', uploadOpen && 'with-upload-panel')">
    <section class="skill-summary-panel version-summary-panel">
      <div class="skill-title-block">
        <dl class="skill-identity-card" aria-label="版本身份信息">
          <div>
            <dt>Skill</dt>
            <dd>{{ skill.skill.slug }}/</dd>
          </div>
          <div>
            <dt>内容 digest</dt>
            <dd>{{ compactDigest(selected.content_digest) }}</dd>
          </div>
          <div>
            <dt>创建者</dt>
            <dd>{{ selected.created_by }}</dd>
          </div>
        </dl>
        <div class="skill-title-copy">
          <VersionNameEditor :version="selected" @save="renameSelected" />
          <p>{{ compactText(selected.change_summary, "这个版本还没有说明。") }}</p>
        </div>
      </div>
      <div class="summary-metric">
        <span>节点</span>
        <strong>{{ versionName(selected) }}</strong>
        <small>{{ selected.id === skill.skill.current_version_id ? "当前版本" : "历史版本" }}</small>
      </div>
      <div class="summary-metric">
        <span>最新得分</span>
        <strong :class="scoreKind(latestRun)">{{ scoreLabel(latestRun) }}</strong>
        <small>{{ latestRun?.summary?.total ? `${latestRun.summary.passed ?? 0}/${latestRun.summary.total} 通过` : "尚无测评" }}</small>
      </div>
      <div class="summary-metric">
        <span>测评集</span>
        <strong class="summary-value-chip">{{ evalSetName }}</strong>
        <small>运行环境保存在 EvalRun</small>
      </div>
    </section>

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

<script lang="ts">
import { defineComponent } from "vue";

const VersionNameEditor = defineComponent({
  props: {
    version: { type: Object as () => SkillVersion, required: true },
  },
  emits: ["save"],
  setup(editorProps, { emit }) {
    const editing = ref(false);
    const draft = ref(editorProps.version.display_name ?? "");
    const busy = ref(false);

    async function save() {
      busy.value = true;
      try {
        await emit("save", cleanName(draft.value));
        editing.value = false;
      } finally {
        busy.value = false;
      }
    }

    return { editing, draft, busy, save, cleanName, versionName, Save, X, Pencil };
  },
  template: `
    <div v-if="editing" class="version-name-editor">
      <input v-model="draft" maxlength="80" :placeholder="\`v\${version.version_number}\`" />
      <button class="icon-button" type="button" aria-label="保存版本名称" :disabled="busy" @click="save">
        <Save :size="17" />
      </button>
      <button class="icon-button" type="button" aria-label="取消命名" @click="editing = false">
        <X :size="17" />
      </button>
    </div>
    <div v-else class="version-title-row">
      <h1>{{ versionName(version) }}</h1>
      <span v-if="version.display_name" class="version-number-badge">v{{ version.version_number }}</span>
      <button class="icon-button" type="button" aria-label="命名 Skill 版本" @click="editing = true">
        <Pencil :size="17" />
      </button>
    </div>
  `,
});

function cleanName(value: string): string | null {
  const clean = value.trim();
  return clean || null;
}
</script>
