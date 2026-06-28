<script setup lang="ts">
import clsx from "clsx";
import { ArrowDown, ArrowUp, Copy, Download, Link2, Plus, Search, Trash2 } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import DropdownSelect from "../components/DropdownSelect.vue";
import type { DropdownSelectOption } from "../components/dropdown";
import CaseStepTimeline from "../features/evaluation/components/CaseStepTimeline.vue";
import EvalCaseEditor from "../features/evaluation/components/EvalCaseEditor.vue";
import EvalCaseLibraryPanel from "../features/evaluation/components/EvalCaseLibraryPanel.vue";
import EvalSetSwitcher from "../features/evaluation/components/EvalSetSwitcher.vue";
import { useEvalSetManagement } from "../features/evaluation/composables/useEvalSetManagement";
import { workspaceFileName } from "../features/evaluation/lib/evalCaseManagement";
import { api, ApiError } from "../lib/api";
import { compactText, humanDate } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import type { SkillDetail, ToastState } from "../types";

const props = defineProps<{ skill: SkillDetail; selectedCaseId: string | null; selectedEvalSetId: string | null }>();
const emit = defineEmits<{ navigate: [next: Partial<RouteState>]; refresh: []; toast: [toast: ToastState] }>();

const skillRef = computed(() => props.skill);
const selectedCaseIdRef = computed(() => props.selectedCaseId);
const selectedEvalSetIdRef = computed(() => props.selectedEvalSetId);

const manager = useEvalSetManagement({
  skill: skillRef,
  selectedCaseId: selectedCaseIdRef,
  selectedEvalSetId: selectedEvalSetIdRef,
  navigate: (next) => emit("navigate", next),
  refresh: () => emit("refresh"),
  toast: (toast) => emit("toast", toast),
});
const sharedEvalSetNames = ref<string[]>([]);
const canManageEval = computed(() => Boolean(props.skill.capabilities?.permissions["eval.manage"]));

const caseSortOptions: DropdownSelectOption[] = [
  { value: "position", label: "按列表顺序" },
  { value: "title", label: "按标题排序" },
  { value: "version", label: "按版本排序" },
];

watch(() => manager.selected.value?.case.id, async (caseId) => {
  if (!caseId) {
    sharedEvalSetNames.value = [];
    return;
  }
  try {
    const history = await api.getEvalCaseHistory(caseId);
    const currentEvalSetId = manager.selectedEvalSetId.value;
    const memberships = history.versions[0]?.included_in_eval_sets ?? [];
    sharedEvalSetNames.value = memberships
      .filter((membership) => membership.eval_set_id !== currentEvalSetId)
      .map((membership) => membership.name);
  } catch {
    sharedEvalSetNames.value = [];
  }
}, { immediate: true });

/** 复制详情中的步骤、备注等文本内容。 */
async function copyText(value?: string | null): Promise<void> {
  const text = compactText(value, "无内容");
  try {
    await navigator.clipboard.writeText(text);
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  }
}

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiError || caught instanceof Error) return caught.message;
  return "操作失败。";
}
</script>

<template>
  <div class="evalset-layout">
    <aside class="case-sidebar">
      <label class="search-field compact">
        <Search :size="18" />
        <input v-model="manager.query.value" placeholder="搜索测试例">
      </label>
      <div class="case-toolbar">
        <label class="case-sort-control">
          <DropdownSelect v-model="manager.caseSort.value" :options="caseSortOptions" aria-label="测试例排序" compact />
        </label>
        <div class="case-toolbar-actions">
          <button class="primary-button" type="button" :disabled="!canManageEval" @click="manager.startCreate"><Plus :size="17" />新建测试例</button>
          <button class="secondary-button" type="button" :disabled="!canManageEval" @click="manager.openLibrary"><Link2 :size="17" />添加已有</button>
        </div>
      </div>
      <p v-if="!canManageEval" class="field-help permission-hint">当前身份没有管理测评集和测试例的权限。</p>
      <EvalCaseLibraryPanel
        v-if="manager.libraryOpen.value"
        :busy="manager.busy.value"
        :items="manager.libraryItems.value"
        @add="manager.addExistingCase"
        @close="manager.libraryOpen.value = false"
      />
      <div class="case-list">
        <button
          v-if="manager.editingMode.value === 'create'"
          type="button"
          :class="clsx('case-row', 'draft', manager.draftSelected.value && 'active')"
          @click="manager.draftSelected.value = true"
        >
          <span class="case-position-mark">新</span>
          <span class="case-row-copy">
            <span class="case-row-topline"><strong class="case-row-title">新测试例（未保存）</strong></span>
            <span class="case-row-metadata">
              <span class="case-current-chip">填写后保存到当前测评集</span>
              <span class="case-draft-chip"><span class="case-draft-dot" />草稿</span>
            </span>
          </span>
        </button>
        <button
          v-for="item in manager.cases.value"
          :key="item.case.id"
          :class="clsx('case-row', manager.activeCaseRowId.value === item.case.id && 'active')"
          type="button"
          @click="manager.selectCase(item)"
        >
          <span class="case-position-mark">#{{ item.position + 1 }}</span>
          <span class="case-row-copy">
            <span class="case-row-topline"><strong class="case-row-title">{{ item.case.title }}</strong></span>
            <span class="case-row-metadata">
              <span class="case-version-pill">测试例 v{{ item.case_version.version_number }}</span>
              <span class="case-time-chip">创建 {{ humanDate(item.case.created_at) }}</span>
              <span class="case-time-chip">更新 {{ humanDate(item.case.updated_at) }}</span>
            </span>
          </span>
        </button>
      </div>
      <p class="case-count">共 {{ manager.detail.value?.cases.length ?? 0 }} 个测试例</p>
    </aside>

    <section class="evalset-main">
      <EvalSetSwitcher
        :active="manager.evalSet.value"
        :busy="manager.busy.value"
        :case-count="manager.detail.value?.cases.length ?? 0"
        :disabled="!canManageEval"
        :eval-sets="manager.evalSets.value"
        :selected-id="manager.selectedEvalSetId.value"
        @create="manager.createEvalSet"
        @select="manager.selectEvalSet"
        @update="manager.updateEvalSet"
      />
      <section class="case-detail">
        <EvalCaseEditor
          v-if="manager.editingMode.value"
          :key="manager.editingMode.value === 'create' ? 'new' : manager.editingCase.value?.case.id"
          :case-item="manager.editingMode.value === 'edit' ? manager.editingCase.value : null"
          :busy="manager.busy.value"
          :title="manager.editorTitle.value"
          :status-label="manager.editorStatus.value"
          @cancel="manager.cancelEditor"
          @submit="manager.saveCase"
        />
        <template v-else-if="manager.selected.value">
          <header class="case-detail-head">
            <div>
              <h1>{{ manager.selected.value.case.title }}</h1>
              <div class="tag-row">
                <span class="tag-chip">测试例 v{{ manager.selected.value.case_version.version_number }}</span>
                <span class="tag-chip">位置 {{ manager.selected.value.position + 1 }}</span>
                <span class="tag-chip">创建 {{ humanDate(manager.selected.value.case.created_at) }}</span>
                <span class="tag-chip">更新 {{ humanDate(manager.selected.value.case.updated_at) }}</span>
                <a
                  v-if="manager.selected.value.case_version.workspace_artifact"
                  class="tag-chip"
                  :href="api.artifactDownloadUrl(manager.selected.value.case_version.workspace_artifact.id)"
                  :download="workspaceFileName(manager.selected.value.case_version.workspace_artifact.locator)"
                >
                  <Download :size="14" />
                  {{ workspaceFileName(manager.selected.value.case_version.workspace_artifact.locator) }}
                </a>
              </div>
              <p v-if="sharedEvalSetNames.length" class="case-shared-hint">
                这个测试例还被 {{ sharedEvalSetNames.join("、") }} 引用；编辑后会同步影响所有引用它的测评集。
              </p>
            </div>
            <div class="button-row">
              <button
                class="secondary-button"
                type="button"
                :disabled="!canManageEval || manager.caseSort.value !== 'position' || manager.selected.value.position === 0"
                @click="manager.moveCase(manager.selected.value, -1)"
              >
                <ArrowUp :size="16" />
                上移
              </button>
              <button
                class="secondary-button"
                type="button"
                :disabled="!canManageEval || manager.caseSort.value !== 'position' || manager.selected.value.position >= (manager.detail.value?.cases.length ?? 1) - 1"
                @click="manager.moveCase(manager.selected.value, 1)"
              >
                <ArrowDown :size="16" />
                下移
              </button>
              <button class="secondary-button" type="button" :disabled="!canManageEval" @click="manager.removeCase(manager.selected.value)">
                <Trash2 :size="16" />
                移除引用
              </button>
              <button class="secondary-button" type="button" :disabled="!canManageEval || manager.busy.value" @click="manager.copyCase(manager.selected.value)">
                <Copy :size="16" />
                复制测试例
              </button>
              <button class="primary-button" type="button" :disabled="!canManageEval" @click="manager.startEdit(manager.selected.value)">编辑测试例</button>
            </div>
          </header>
          <CaseStepTimeline :steps="manager.selected.value.case_version.steps" @copy="copyText" />
          <section class="case-block">
            <header>
              <h2>备注</h2>
              <button class="icon-button mini" type="button" aria-label="复制备注" @click="copyText(manager.selected.value.case_version.notes)"><Copy :size="16" /></button>
            </header>
            <pre>{{ compactText(manager.selected.value.case_version.notes, "无内容") }}</pre>
          </section>
        </template>
        <div v-else class="quiet-panel">
          <strong>选择一个测试例查看详情</strong>
          <p>也可以在左侧新建测试例，或把 Skill 中已有的测试例加入当前测评集。</p>
        </div>
      </section>
    </section>
  </div>
</template>
