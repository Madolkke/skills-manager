import { computed, ref, watch, type ComputedRef } from "vue";
import { api, ApiError } from "../../../lib/api";
import type { RouteState } from "../../../lib/navigation";
import { cleanCaseForm, filterCases, sortCases, type CaseSortKey } from "../lib/evalCaseManagement";
import type { EvalCaseFormData } from "../lib/evalCaseForm";
import type { EvalCaseLibraryItem, EvalSetCase, EvalSetDetail, EvalSetSummary, SkillDetail, ToastState } from "../../../types";

type UseEvalSetManagementInput = {
  skill: ComputedRef<SkillDetail>;
  selectedCaseId: ComputedRef<string | null>;
  selectedEvalSetId: ComputedRef<string | null>;
  navigate: (next: Partial<RouteState>) => void;
  refresh: () => void;
  toast: (toast: ToastState) => void;
};

export function useEvalSetManagement(input: UseEvalSetManagementInput) {
  const detail = ref<EvalSetDetail | null>(null);
  const evalSets = ref<EvalSetSummary[]>([...input.skill.value.eval_sets]);
  const query = ref("");
  const caseSort = ref<CaseSortKey>("position");
  const editingMode = ref<"create" | "edit" | null>(null);
  const editingCase = ref<EvalSetCase | null>(null);
  const draftSelected = ref(false);
  const lastSelectedCaseId = ref<string | null>(null);
  const busy = ref(false);
  const libraryOpen = ref(false);
  const libraryItems = ref<EvalCaseLibraryItem[]>([]);

  const fallbackEvalSetId = computed(() => input.skill.value.summary.primary_eval_set?.id ?? evalSets.value[0]?.id ?? "");
  const selectedEvalSetId = computed(() => {
    const requested = input.selectedEvalSetId.value;
    return evalSets.value.some((item) => item.id === requested) ? requested ?? "" : fallbackEvalSetId.value;
  });
  const evalSet = computed(() => evalSets.value.find((item) => item.id === selectedEvalSetId.value) ?? null);
  const cases = computed(() => sortCases(filterCases(detail.value?.cases ?? [], query.value), caseSort.value));
  const selected = computed(() => cases.value.find((item) => item.case.id === input.selectedCaseId.value) ?? null);
  const activeCaseRowId = computed(() => {
    if (draftSelected.value) return "__draft__";
    if (editingMode.value === "edit" && editingCase.value) return editingCase.value.case.id;
    return selected.value?.case.id ?? null;
  });
  const editorTitle = computed(() => editingMode.value === "create" ? "添加测试例" : "编辑测试例");
  const editorStatus = computed(() => editingMode.value === "create" ? "未保存" : "编辑中");

  watch(() => input.skill.value.eval_sets, (next) => {
    evalSets.value = mergeEvalSets(next, evalSets.value);
  }, { deep: true });

  watch(selectedEvalSetId, async (id) => {
    if (!id) {
      detail.value = null;
      return;
    }
    if (id !== input.selectedEvalSetId.value) input.navigate({ selectedEvalSetId: id, selectedCaseId: null, selectedRunId: null });
    await loadEvalSet(id);
  }, { immediate: true });

  watch(() => input.skill.value.skill.id, () => {
    resetEditor();
    libraryOpen.value = false;
  });

  /** 保存新建或编辑后的测试例版本。 */
  async function saveCase(form: EvalCaseFormData): Promise<void> {
    if (!selectedEvalSetId.value) return;
    busy.value = true;
    try {
      const basePayload = { eval_set_id: selectedEvalSetId.value, ...cleanCaseForm(form) };
      const saved = editingMode.value === "create"
        ? await api.createEvalCase({ skill_id: input.skill.value.skill.id, ...basePayload })
        : editingCase.value
          ? await api.updateEvalCase(editingCase.value.case.id, { ...basePayload, preserve_workspace: true, make_current: true })
          : null;
      await reloadAfterMutation();
      resetEditor();
      if (saved) input.navigate({ selectedCaseId: saved.eval_case_id, selectedEvalSetId: saved.eval_set_id });
      input.toast({ tone: "success", message: "测试例已保存。" });
    } catch (caught) {
      input.toast({ tone: "danger", message: errorMessage(caught) });
    } finally {
      busy.value = false;
    }
  }

  /** 创建新的测评集并切换过去。 */
  async function createEvalSet(payload: { name: string; description: string }): Promise<void> {
    busy.value = true;
    try {
      const created = await api.createEvalSet(input.skill.value.skill.id, payload);
      evalSets.value = [...evalSets.value, created];
      input.toast({ tone: "success", message: "测评集已创建。" });
      input.navigate({ selectedEvalSetId: created.id, selectedCaseId: null, selectedRunId: null });
      input.refresh();
    } catch (caught) {
      input.toast({ tone: "danger", message: errorMessage(caught) });
    } finally {
      busy.value = false;
    }
  }

  /** 更新当前测评集名称和描述。 */
  async function updateEvalSet(payload: { name: string; description: string }): Promise<void> {
    if (!selectedEvalSetId.value) return;
    busy.value = true;
    try {
      const updated = await api.updateEvalSet(selectedEvalSetId.value, payload);
      evalSets.value = evalSets.value.map((item) => item.id === updated.id ? updated : item);
      input.toast({ tone: "success", message: "测评集已保存。" });
      await loadEvalSet(selectedEvalSetId.value);
      input.refresh();
    } catch (caught) {
      input.toast({ tone: "danger", message: errorMessage(caught) });
    } finally {
      busy.value = false;
    }
  }

  /** 打开已有测试例库并加载可加入项。 */
  async function openLibrary(): Promise<void> {
    if (!selectedEvalSetId.value || !canLeaveEditor()) return;
    libraryOpen.value = true;
    busy.value = true;
    try {
      libraryItems.value = await api.listSkillEvalCases(input.skill.value.skill.id, selectedEvalSetId.value);
    } catch (caught) {
      input.toast({ tone: "danger", message: errorMessage(caught) });
    } finally {
      busy.value = false;
    }
  }

  /** 将 Skill 全局测试例加入当前测评集。 */
  async function addExistingCase(caseId: string): Promise<void> {
    if (!selectedEvalSetId.value) return;
    busy.value = true;
    try {
      detail.value = await api.addEvalSetCase(selectedEvalSetId.value, { case_id: caseId });
      libraryItems.value = libraryItems.value.filter((item) => item.case.id !== caseId);
      input.navigate({ selectedCaseId: caseId });
      input.toast({ tone: "success", message: "测试例已加入当前测评集。" });
      input.refresh();
    } catch (caught) {
      input.toast({ tone: "danger", message: errorMessage(caught) });
    } finally {
      busy.value = false;
    }
  }

  /** 从当前测评集移除测试例引用，不删除测试例本身。 */
  async function removeCase(item: EvalSetCase): Promise<void> {
    if (!selectedEvalSetId.value) return;
    const confirmed = window.confirm("只会从当前测评集中移除这个测试例，不会删除测试例和历史记录。是否继续？");
    if (!confirmed) return;
    busy.value = true;
    try {
      detail.value = await api.removeEvalSetCase(selectedEvalSetId.value, item.case.id);
      input.navigate({ selectedCaseId: null });
      input.toast({ tone: "success", message: "已从当前测评集移除。" });
      input.refresh();
    } catch (caught) {
      input.toast({ tone: "danger", message: errorMessage(caught) });
    } finally {
      busy.value = false;
    }
  }

  /** 调整当前测评集内测试例顺序。 */
  async function moveCase(item: EvalSetCase, direction: -1 | 1): Promise<void> {
    if (!selectedEvalSetId.value || caseSort.value !== "position") return;
    const ordered = [...(detail.value?.cases ?? [])].sort((left, right) => left.position - right.position);
    const index = ordered.findIndex((row) => row.case.id === item.case.id);
    const nextIndex = index + direction;
    if (index < 0 || nextIndex < 0 || nextIndex >= ordered.length) return;
    const [row] = ordered.splice(index, 1);
    if (!row) return;
    ordered.splice(nextIndex, 0, row);
    busy.value = true;
    try {
      detail.value = await api.reorderEvalSetCases(selectedEvalSetId.value, ordered.map((row) => row.case.id));
      input.refresh();
    } catch (caught) {
      input.toast({ tone: "danger", message: errorMessage(caught) });
    } finally {
      busy.value = false;
    }
  }

  function startCreate(): void {
    if (!selectedEvalSetId.value || !canLeaveEditor()) return;
    libraryOpen.value = false;
    lastSelectedCaseId.value = input.selectedCaseId.value ?? null;
    editingMode.value = "create";
    editingCase.value = null;
    draftSelected.value = true;
  }

  function startEdit(item: EvalSetCase): void {
    if (editingMode.value === "edit" && editingCase.value?.case.id === item.case.id) return;
    if (!canLeaveEditor()) return;
    libraryOpen.value = false;
    editingMode.value = "edit";
    editingCase.value = item;
    draftSelected.value = false;
    input.navigate({ selectedCaseId: item.case.id });
  }

  function selectCase(item: EvalSetCase): void {
    if (editingMode.value === "edit" && editingCase.value?.case.id === item.case.id) return;
    if (!canLeaveEditor()) return;
    resetEditor();
    input.navigate({ selectedCaseId: item.case.id });
  }

  function selectEvalSet(evalSetId: string): void {
    if (!canLeaveEditor()) return;
    resetEditor();
    libraryOpen.value = false;
    input.navigate({ selectedEvalSetId: evalSetId, selectedCaseId: null, selectedRunId: null });
  }

  function cancelEditor(): void {
    const fallbackId = editingMode.value === "create" ? lastSelectedCaseId.value : editingCase.value?.case.id ?? input.selectedCaseId.value;
    resetEditor();
    input.navigate({ selectedCaseId: fallbackId });
  }

  function resetEditor(): void {
    editingMode.value = null;
    editingCase.value = null;
    draftSelected.value = false;
  }

  function canLeaveEditor(): boolean {
    if (!editingMode.value) return true;
    return window.confirm("当前编辑内容尚未保存，是否放弃？");
  }

  async function loadEvalSet(evalSetId: string): Promise<void> {
    try {
      detail.value = await api.getEvalSet(evalSetId);
    } catch (caught) {
      input.toast({ tone: "danger", message: errorMessage(caught) });
    }
  }

  async function reloadAfterMutation(): Promise<void> {
    if (!selectedEvalSetId.value) return;
    detail.value = await api.getEvalSet(selectedEvalSetId.value);
    input.refresh();
  }

  return {
    activeCaseRowId,
    busy,
    caseSort,
    cases,
    detail,
    draftSelected,
    editingCase,
    editingMode,
    editorStatus,
    editorTitle,
    evalSet,
    evalSets,
    libraryItems,
    libraryOpen,
    query,
    selected,
    selectedEvalSetId,
    addExistingCase,
    cancelEditor,
    createEvalSet,
    moveCase,
    openLibrary,
    removeCase,
    saveCase,
    selectCase,
    selectEvalSet,
    startCreate,
    startEdit,
    updateEvalSet,
  };
}

function mergeEvalSets(source: EvalSetSummary[], current: EvalSetSummary[]): EvalSetSummary[] {
  const byId = new Map(current.map((item) => [item.id, item]));
  for (const item of source) byId.set(item.id, item);
  return [...byId.values()].sort((left, right) => left.name.localeCompare(right.name));
}

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiError || caught instanceof Error) return caught.message;
  return "操作失败。";
}
