import { nextTick, onBeforeUnmount, ref, type Ref } from "vue";
import type { UiButtonState } from "../../components/ui/button";
import { api, ApiError } from "../../lib/api";
import type { ToastState, WorkflowDetail, WorkflowSyncPayload } from "../../types";
import type { useWorkflowEditor } from "./useWorkflowEditor";

type PersistenceEditor = Pick<
  ReturnType<typeof useWorkflowEditor>,
  "accepted" | "bundle" | "changes" | "dirty" | "load"
>;

type WorkflowPersistenceOptions = {
  skillId: () => string;
  detail: Ref<WorkflowDetail | null>;
  editor: PersistenceEditor;
  editorPane: Ref<HTMLElement | null>;
  readonly: () => boolean;
  refresh: () => void;
  closeSync: () => void;
  toast: (toast: ToastState) => void;
};

export function useWorkflowPersistence(options: WorkflowPersistenceOptions) {
  const loading = ref(true);
  const saving = ref(false);
  const saveFeedback = ref<UiButtonState>("idle");
  const syncing = ref(false);
  const loadError = ref("");
  const actionError = ref("");
  const syncError = ref("");
  const syncConflictKey = ref(0);
  let saveFeedbackTimer: number | null = null;

  async function load(preserveContext = false): Promise<void> {
    loading.value = true;
    loadError.value = "";
    try {
      const [nextDetail, response] = await Promise.all([
        api.getWorkflow(options.skillId()),
        api.listWorkflowCollections(options.skillId()),
      ]);
      options.detail.value = nextDetail;
      if (preserveContext && options.editor.bundle.value) {
        options.editor.accepted(nextDetail, response.definitions);
      } else {
        options.editor.load(nextDetail, response.definitions);
      }
    } catch (caught) {
      loadError.value = errorMessage(caught, "Workflow 加载失败。");
    } finally {
      loading.value = false;
    }
  }

  async function save(): Promise<void> {
    if (!options.editor.bundle.value || !options.editor.dirty.value || options.readonly()) return;
    const scrollTop = options.editorPane.value?.scrollTop ?? 0;
    saving.value = true;
    saveFeedback.value = "idle";
    actionError.value = "";
    try {
      const nextDetail = await api.saveWorkflow(options.skillId(), {
        document: options.editor.bundle.value,
        collection_changes: options.editor.changes.value,
      });
      const response = await api.listWorkflowCollections(options.skillId());
      options.detail.value = nextDetail;
      options.editor.accepted(nextDetail, response.definitions);
      await nextTick();
      if (options.editorPane.value) options.editorPane.value.scrollTop = scrollTop;
      options.refresh();
      options.toast({ tone: "success", message: `Workflow revision ${nextDetail.revision} 已保存。` });
      showSaveSuccess();
    } catch (caught) {
      actionError.value = errorMessage(caught, "Workflow 保存失败。");
      options.toast({ tone: "danger", message: actionError.value });
    } finally {
      saving.value = false;
    }
  }

  /**
   * Commits an explicitly confirmed preview and refreshes it after a conflict.
   */
  async function sync(payload: WorkflowSyncPayload): Promise<boolean> {
    syncing.value = true;
    syncError.value = "";
    try {
      const result = await api.syncWorkflow(options.skillId(), payload);
      options.closeSync();
      await load(true);
      options.refresh();
      const action = result.mode === "created"
        ? "已生成新版本"
        : result.mode === "reactivated"
          ? "已重新设为当前版本"
          : "当前版本已经是最新同步结果";
      options.toast({ tone: "success", message: action });
      return true;
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        syncError.value = "同步预览已失效，已加载最新 Workflow 并重新生成预览。";
        await load(true);
        syncConflictKey.value += 1;
      } else {
        syncError.value = errorMessage(caught, "Workflow 同步失败。");
      }
      return false;
    } finally {
      syncing.value = false;
    }
  }

  function showSaveSuccess(): void {
    saveFeedback.value = "success";
    if (saveFeedbackTimer !== null) window.clearTimeout(saveFeedbackTimer);
    saveFeedbackTimer = window.setTimeout(() => {
      saveFeedback.value = "idle";
      saveFeedbackTimer = null;
    }, 900);
  }

  onBeforeUnmount(() => {
    if (saveFeedbackTimer !== null) window.clearTimeout(saveFeedbackTimer);
  });

  return { loading, saving, saveFeedback, syncing, loadError, actionError, syncError, syncConflictKey, load, save, sync };
}

function errorMessage(caught: unknown, fallback: string): string {
  return caught instanceof ApiError || caught instanceof Error ? caught.message : fallback;
}
