import { ref } from "vue";
import { api, ApiError } from "../../lib/api";
import type { CollectionDefinition, ToastState, WorkflowImportDetail } from "../../types";
import { downloadWorkflowBundle, parseWorkflowImportFile, type WorkflowImportCandidate } from "./workflowTransfer";

type WorkflowTransferOptions = {
  skillId: () => string;
  skillSlug: () => string;
  dirty: () => boolean;
  readonly: () => boolean;
  imported: (detail: WorkflowImportDetail, definitions: CollectionDefinition[]) => void;
  toast: (toast: ToastState) => void;
};

export function useWorkflowTransfer(options: WorkflowTransferOptions) {
  const candidate = ref<WorkflowImportCandidate | null>(null);
  const importing = ref(false);
  const exporting = ref(false);
  const importError = ref("");

  async function exportWorkflow(): Promise<void> {
    if (options.dirty() || exporting.value) return;
    exporting.value = true;
    try {
      const bundle = await api.exportWorkflow(options.skillId());
      downloadWorkflowBundle(bundle, `${options.skillSlug()}-workflow.json`);
      options.toast({ tone: "success", message: "Workflow 导出完成。" });
    } catch (caught) {
      options.toast({ tone: "danger", message: errorMessage(caught, "Workflow 导出失败。") });
    } finally {
      exporting.value = false;
    }
  }

  async function selectFile(files: FileList | null): Promise<void> {
    if (!files?.[0] || options.dirty() || options.readonly() || importing.value) return;
    importError.value = "";
    try {
      candidate.value = parseWorkflowImportFile(await files[0].text(), files[0].name);
    } catch (caught) {
      candidate.value = null;
      options.toast({ tone: "danger", message: errorMessage(caught, "Workflow 导入文件读取失败。") });
    }
  }

  async function confirmImport(): Promise<void> {
    if (!candidate.value || importing.value || options.dirty() || options.readonly()) return;
    importing.value = true;
    importError.value = "";
    try {
      const detail = await api.importWorkflow(options.skillId(), candidate.value.payload);
      let definitions = detail.document.collectionSnapshots;
      let catalogRefreshed = true;
      try {
        definitions = (await api.listWorkflowCollections(options.skillId())).definitions;
      } catch {
        catalogRefreshed = false;
      }
      options.imported(detail, definitions);
      const count = detail.import_result.collection_mappings.length;
      candidate.value = null;
      options.toast({ tone: "success", message: `Workflow 已导入，并创建 ${count} 个独立 Collection。` });
      if (!catalogRefreshed) {
        options.toast({ tone: "info", message: "Collection Catalog 刷新失败，当前编辑器已使用导入快照；重新加载页面可再次获取完整 Catalog。" });
      }
    } catch (caught) {
      importError.value = errorMessage(caught, "Workflow 导入失败。");
    } finally {
      importing.value = false;
    }
  }

  function closeImport(): void {
    if (!importing.value) candidate.value = null;
    importError.value = "";
  }

  return { candidate, importing, exporting, importError, exportWorkflow, selectFile, confirmImport, closeImport };
}

function errorMessage(caught: unknown, fallback: string): string {
  return caught instanceof ApiError || caught instanceof Error ? caught.message : fallback;
}
