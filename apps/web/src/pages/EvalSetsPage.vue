<script setup lang="ts">
import clsx from "clsx";
import { Copy, Plus, Search } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import EvalCaseModal, { type EvalCaseFormData } from "../components/EvalCaseModal.vue";
import { api, ApiError } from "../lib/api";
import { compactText, humanDate } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import type { EvalSetCase, EvalSetDetail, SkillDetail, ToastState } from "../types";

type CaseSortKey = "position" | "title" | "version";

const props = defineProps<{ skill: SkillDetail; selectedCaseId: string | null }>();
const emit = defineEmits<{ navigate: [next: Partial<RouteState>]; refresh: []; toast: [toast: ToastState] }>();

const evalSet = computed(() => props.skill.summary.primary_eval_set);
const detail = ref<EvalSetDetail | null>(null);
const query = ref("");
const caseFilter = ref<"all" | "active">("all");
const caseSort = ref<CaseSortKey>("position");
const editor = ref<EvalSetCase | "new" | null>(null);
const busy = ref(false);
const cases = computed(() => sortCases(filterCases(detail.value?.cases ?? [], query.value, caseFilter.value), caseSort.value));
const selected = computed(() => cases.value.find((item) => item.case.id === props.selectedCaseId) ?? cases.value[0] ?? null);

watch(() => evalSet.value?.id, async (id) => {
  if (!id) {
    detail.value = null;
    return;
  }
  try {
    detail.value = await api.getEvalSet(id);
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  }
}, { immediate: true });

watch(selected, (item) => {
  if (item && item.case.id !== props.selectedCaseId) emit("navigate", { selectedCaseId: item.case.id });
});

async function saveCase(form: EvalCaseFormData): Promise<void> {
  busy.value = true;
  try {
    const payload = cleanCaseForm(form);
    const saved = editor.value === "new"
      ? await api.createEvalCase({ skill_id: props.skill.skill.id, ...payload })
      : editor.value
        ? await api.updateEvalCase(editor.value.case.id, { ...payload, make_current: true })
        : null;
    if (saved) emit("navigate", { selectedCaseId: saved.eval_case_id });
    editor.value = null;
    emit("toast", { tone: "success", message: "Case 已保存。" });
    if (evalSet.value?.id) detail.value = await api.getEvalSet(evalSet.value.id);
    emit("refresh");
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  } finally {
    busy.value = false;
  }
}

async function copyText(value?: string | null): Promise<void> {
  const text = compactText(value, "无内容");
  try {
    await navigator.clipboard.writeText(text);
  } catch (caught) {
    emit("toast", { tone: "danger", message: errorMessage(caught) });
  }
}

function filterCases(items: EvalSetCase[], value: string, filter: "all" | "active"): EvalSetCase[] {
  const normalized = value.trim().toLowerCase();
  return items.filter((item) => {
    if (filter === "active" && item.case.lifecycle_status !== "active") return false;
    if (!normalized) return true;
    return [item.case.title, item.case_version.input_artifact.content_text, item.case_version.expected_output_artifact.content_text].join(" ").toLowerCase().includes(normalized);
  });
}

function sortCases(items: EvalSetCase[], sortKey: CaseSortKey): EvalSetCase[] {
  const copy = [...items];
  if (sortKey === "title") return copy.sort((left, right) => left.case.title.localeCompare(right.case.title) || left.position - right.position);
  if (sortKey === "version") return copy.sort((left, right) => right.case_version.version_number - left.case_version.version_number || left.position - right.position);
  return copy.sort((left, right) => left.position - right.position);
}

function caseLifecycleLabel(status: string): string {
  if (status === "active") return "活跃";
  if (status === "archived") return "归档";
  return status || "未知";
}

function cleanCaseForm(form: EvalCaseFormData) {
  return { title: form.title, input_text: form.input_text, expected_output: form.expected_output, notes: form.notes.trim() || undefined };
}

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiError || caught instanceof Error) return caught.message;
  return "操作失败。";
}
</script>

<template>
  <div class="evalset-layout">
    <aside class="case-sidebar">
      <span class="back-link">当前测评集</span>
      <div class="evalset-card">
        <div class="evalset-title-row"><span class="green-dot" /><span>当前测评集</span></div>
        <h1>{{ evalSet?.name ?? "Regression Set" }}</h1>
        <p>{{ evalSet?.description ?? "" }}</p>
        <div class="mini-grid">
          <span>Cases<b>{{ detail?.cases.length ?? 0 }}</b></span>
          <span>状态<b>{{ evalSet?.lifecycle_status ?? "-" }}</b></span>
          <span>更新时间<b>{{ humanDate(evalSet?.updated_at) }}</b></span>
        </div>
      </div>
      <label class="search-field compact">
        <Search :size="18" />
        <input v-model="query" placeholder="搜索 case">
      </label>
      <div class="case-toolbar">
        <button :class="clsx('select-button', caseFilter === 'all' && 'active')" type="button" @click="caseFilter = 'all'">全部</button>
        <button :class="clsx('select-button', caseFilter === 'active' && 'active')" type="button" @click="caseFilter = 'active'">仅活跃</button>
        <label class="case-sort-control">
          <select v-model="caseSort" aria-label="Case 排序">
            <option value="position">按列表顺序</option>
            <option value="title">按标题排序</option>
            <option value="version">按版本排序</option>
          </select>
        </label>
        <button class="primary-button" type="button" @click="editor = 'new'"><Plus :size="17" />添加</button>
      </div>
      <div class="case-list">
        <button
          v-for="item in cases"
          :key="item.case.id"
          :class="clsx('case-row', selected?.case.id === item.case.id && 'active')"
          type="button"
          @click="emit('navigate', { selectedCaseId: item.case.id })"
        >
          <span class="case-position-mark">#{{ item.position + 1 }}</span>
          <span class="case-row-copy">
            <span class="case-row-topline"><strong class="case-row-title">{{ item.case.title }}</strong></span>
            <span class="case-row-metadata">
              <span class="case-version-pill">case v{{ item.case_version.version_number }}</span>
              <span :class="clsx('case-current-chip', item.case.current_version_id !== item.case_version.id && 'muted')">{{ item.case.current_version_id === item.case_version.id ? "当前" : "历史" }}</span>
              <span :class="clsx('case-status-chip', item.case.lifecycle_status !== 'active' && 'muted')"><span class="case-status-dot" />{{ caseLifecycleLabel(item.case.lifecycle_status) }}</span>
            </span>
          </span>
        </button>
      </div>
      <p class="case-count">共 {{ detail?.cases.length ?? 0 }} 个 case</p>
    </aside>

    <section class="case-detail">
      <template v-if="selected">
        <header class="case-detail-head">
          <div>
            <h1>{{ selected.case.title }}</h1>
            <div class="tag-row">
              <span class="tag-chip">case v{{ selected.case_version.version_number }}</span>
              <span class="tag-chip">position {{ selected.position + 1 }}</span>
            </div>
          </div>
          <div class="button-row"><button class="primary-button" type="button" @click="editor = selected">编辑 case</button></div>
        </header>
        <section v-for="block in [
          { title: 'Input', text: selected.case_version.input_artifact.content_text },
          { title: 'Expected output', text: selected.case_version.expected_output_artifact.content_text },
          { title: 'Notes', text: selected.case_version.notes },
        ]" :key="block.title" class="case-block">
          <header>
            <h2>{{ block.title }}</h2>
            <button class="icon-button mini" type="button" :aria-label="`复制 ${block.title}`" @click="copyText(block.text)"><Copy :size="16" /></button>
          </header>
          <pre>{{ compactText(block.text, "无内容") }}</pre>
        </section>
      </template>
      <div v-else class="quiet-panel">还没有测试用例。</div>
    </section>

    <EvalCaseModal v-if="editor" :case-item="editor === 'new' ? null : editor" :busy="busy" @close="editor = null" @submit="saveCase" />
  </div>
</template>
