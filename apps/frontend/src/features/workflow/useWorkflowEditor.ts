import { computed, ref } from "vue";
import type { CollectionCall, CollectionDefinition, VersionedRef, WorkflowBundle, WorkflowCollectionChange, WorkflowDetail, WorkflowMetadata, WorkflowSelection, WorkflowStep } from "../../types";
import { cloneWorkflow, createWorkflowId, findCall, findCollection, mergeCatalog, nextUniqueKey, syncSnapshots, workflowConclusions, workflowSteps } from "./domain/utils";
import { validateWorkflow } from "./domain/validation";
import { newCollection, newConclusion, newParameter, newRole, newStep } from "./editorDefaults";
import { useWorkflowHistory } from "./useWorkflowHistory";
import { createWorkflowOrdering } from "./workflowOrdering";
import { createWorkflowPathEditing } from "./workflowPathEditing";
import { validWorkflowSelection } from "./workflowSelection";

export type WorkflowEditorSnapshot = { bundle: WorkflowBundle; catalog: CollectionDefinition[]; changes: WorkflowCollectionChange[] };

export function useWorkflowEditor(readonly: () => boolean) {
  const bundle = ref<WorkflowBundle | null>(null);
  const catalog = ref<CollectionDefinition[]>([]);
  const selection = ref<WorkflowSelection>({ type: "metadata" });
  const changes = ref<WorkflowCollectionChange[]>([]);
  const linkedCallFields = new Map<string, { name: boolean; key: boolean }>();
  const history = useWorkflowHistory(currentSnapshot, restore);
  const issues = computed(() => bundle.value ? validateWorkflow(bundle.value, catalog.value) : []);
  const ordering = createWorkflowOrdering(bundle, commit);
  const paths = createWorkflowPathEditing(bundle, commit);

  function load(detail: WorkflowDetail, definitions: CollectionDefinition[]): void {
    bundle.value = cloneWorkflow(detail.document);
    catalog.value = mergeCatalog(definitions, detail.document.collectionSnapshots);
    changes.value = [];
    linkedCallFields.clear();
    selection.value = { type: "metadata" };
    history.resetBaseline();
  }

  function commit(recipe: (draft: WorkflowEditorSnapshot) => void, historyGroup = ""): void {
    if (!bundle.value || readonly()) return;
    const before = currentSnapshot();
    if (!before) return;
    const draft = cloneWorkflow(before);
    recipe(draft);
    syncSnapshots(draft.bundle, draft.catalog);
    if (JSON.stringify(before) === JSON.stringify(draft)) return;
    history.record(before, historyGroup);
    restore(draft);
  }

  function accepted(detail: WorkflowDetail, definitions: CollectionDefinition[]): void {
    const previousSelection = selection.value;
    bundle.value = cloneWorkflow(detail.document);
    catalog.value = mergeCatalog(definitions, detail.document.collectionSnapshots);
    changes.value = [];
    linkedCallFields.clear();
    selection.value = validWorkflowSelection(previousSelection, bundle.value, catalog.value);
    history.resetBaseline();
  }

  function updateMetadata(patch: Partial<WorkflowMetadata>): void {
    commit((draft) => Object.assign(draft.bundle.workflow.metadata, patch), fieldGroup("metadata", patch));
  }

  function addInput(): void {
    commit((draft) => draft.bundle.workflow.inputs.push(newParameter()));
  }

  function updateInput(id: string, patch: Record<string, unknown>): void {
    commit((draft) => Object.assign(draft.bundle.workflow.inputs.find((item) => item.id === id) ?? {}, patch), fieldGroup(`input:${id}`, patch));
  }

  function removeInput(id: string): void {
    commit((draft) => { draft.bundle.workflow.inputs = draft.bundle.workflow.inputs.filter((item) => item.id !== id); });
  }

  function addDeviceRole(): void {
    commit((draft) => draft.bundle.workflow.deviceRoles.push(newRole(draft.bundle.workflow.deviceRoles.length + 1)));
  }

  function updateDeviceRole(id: string, patch: Record<string, unknown>): void {
    commit((draft) => Object.assign(draft.bundle.workflow.deviceRoles.find((item) => item.id === id) ?? {}, patch), fieldGroup(`role:${id}`, patch));
  }

  function removeDeviceRole(id: string): void {
    commit((draft) => { draft.bundle.workflow.deviceRoles = draft.bundle.workflow.deviceRoles.filter((item) => item.id !== id); });
  }

  function addWorkflowStep(): void {
    const step = newStep(workflowSteps(bundle.value!).length + 1);
    commit((draft) => draft.bundle.workflow.nodes.push(step));
    selection.value = { type: "step", id: step.id };
  }

  function duplicateStep(id: string): void {
    const source = workflowSteps(bundle.value!).find((item) => item.id === id);
    if (!source) return;
    const copy = cloneWorkflow(source);
    copy.id = createWorkflowId("step");
    copy.name = `${source.name} 副本`;
    copy.collectionCalls.forEach((call) => { call.id = createWorkflowId("call"); });
    copy.topology.forEach((item) => { item.id = createWorkflowId("transition"); });
    commit((draft) => draft.bundle.workflow.nodes.push(copy));
    selection.value = { type: "step", id: copy.id };
  }

  function updateStep(id: string, patch: Partial<WorkflowStep>): void {
    commit((draft) => Object.assign(workflowSteps(draft.bundle).find((item) => item.id === id) ?? {}, patch), fieldGroup(`step:${id}`, patch));
  }

  function removeStep(id: string): void {
    commit((draft) => {
      draft.bundle.workflow.nodes = draft.bundle.workflow.nodes.filter((item) => item.id !== id);
      workflowSteps(draft.bundle).forEach((step) => { step.topology = step.topology.filter((item) => item.target.id !== id); });
    });
    selection.value = { type: "metadata" };
  }

  function addWorkflowConclusion(): void {
    const item = newConclusion(workflowConclusions(bundle.value!).length + 1);
    commit((draft) => draft.bundle.workflow.nodes.push(item));
    selection.value = { type: "conclusion", id: item.id };
  }

  function updateConclusion(id: string, patch: Record<string, unknown>): void {
    commit((draft) => Object.assign(workflowConclusions(draft.bundle).find((item) => item.id === id) ?? {}, patch), fieldGroup(`conclusion:${id}`, patch));
  }

  function removeConclusion(id: string): void {
    commit((draft) => {
      draft.bundle.workflow.nodes = draft.bundle.workflow.nodes.filter((item) => item.id !== id);
      workflowSteps(draft.bundle).forEach((step) => { step.topology = step.topology.filter((item) => item.target.id !== id); });
    });
    selection.value = { type: "metadata" };
  }

  function addDefinition(): void {
    const definition = newCollection(catalog.value.length + 1);
    definition.key = nextUniqueKey(catalog.value.map((item) => item.key), definition.key);
    commit((draft) => { draft.catalog.push(definition); draft.changes.push({ operation: "create", definition }); });
    selection.value = { type: "collection", id: definition.id };
  }

  function editDefinition(reference: VersionedRef, mutate: (definition: CollectionDefinition) => void): void {
    commit((draft) => {
      const definition = findCollection(draft.catalog, reference);
      if (!definition) return;
      mutate(definition);
      upsertChange(draft, draft.changes.find((item) => item.definition.id === reference.id)?.operation ?? "revise", definition);
      workflowSteps(draft.bundle).forEach((step) => step.collectionCalls.forEach((call) => {
        if (call.definition.id !== definition.id) return;
        const linked = linkedCallFields.get(call.id);
        if (linked?.name) call.name = definition.metadata.name;
        if (linked?.key) call.key = nextUniqueKey(step.collectionCalls.filter((item) => item.id !== call.id).map((item) => item.key), definition.key);
      }));
    }, `definition:${reference.id}`);
  }

  function removeDraftDefinition(id: string): void {
    commit((draft) => {
      const change = draft.changes.find((item) => item.definition.id === id);
      const referenced = workflowSteps(draft.bundle).some((step) => step.collectionCalls.some((call) => call.definition.id === id));
      if (!change || change.operation === "revise" || referenced) return;
      draft.catalog = draft.catalog.filter((item) => item.id !== id);
      draft.changes = draft.changes.filter((item) => item.definition.id !== id);
    });
    selection.value = { type: "collections" };
  }

  function addCall(stepId: string, definition: CollectionDefinition): string {
    const callId = createWorkflowId("call");
    commit((draft) => {
      const step = workflowSteps(draft.bundle).find((item) => item.id === stepId);
      if (!step) return;
      step.collectionCalls.push({ id: callId, key: "", name: "", definition: { id: definition.id, revision: definition.revision }, sampleCount: 1, inputBindings: {} });
    });
    return callId;
  }

  function addDraftCollectionCall(stepId: string): { callId: string; definitionId: string } | null {
    if (!bundle.value) return null;
    const definition = newCollection(catalog.value.length + 1, bundle.value.workflow.metadata);
    definition.key = nextUniqueKey(catalog.value.map((item) => item.key), definition.key);
    const callId = createWorkflowId("call");
    commit((draft) => {
      const step = workflowSteps(draft.bundle).find((item) => item.id === stepId);
      if (!step) return;
      draft.catalog.push(definition);
      draft.changes.push({ operation: "create", definition });
      step.collectionCalls.push({
        id: callId,
        key: "",
        name: "",
        definition: { id: definition.id, revision: definition.revision },
        sampleCount: 1,
        inputBindings: {},
      });
    });
    linkedCallFields.set(callId, { name: false, key: false });
    return { callId, definitionId: definition.id };
  }

  function updateCall(stepId: string, callId: string, patch: Partial<CollectionCall>): void {
    const linked = linkedCallFields.get(callId);
    if (linked && Object.hasOwn(patch, "name")) linked.name = false;
    if (linked && Object.hasOwn(patch, "key")) linked.key = false;
    commit((draft) => Object.assign(findCall(draft.bundle, stepId, callId) ?? {}, patch), fieldGroup(`call:${stepId}:${callId}`, patch));
  }

  function removeCall(stepId: string, callId: string): void {
    commit((draft) => {
      const step = workflowSteps(draft.bundle).find((item) => item.id === stepId);
      const call = step?.collectionCalls.find((item) => item.id === callId);
      if (!step || !call) return;
      step.collectionCalls = step.collectionCalls.filter((item) => item.id !== callId);
      const stillReferenced = workflowSteps(draft.bundle).some((item) => item.collectionCalls.some((candidate) => candidate.definition.id === call.definition.id));
      const pending = draft.changes.find((item) => item.definition.id === call.definition.id);
      if (!stillReferenced && pending && pending.operation !== "revise") {
        draft.catalog = draft.catalog.filter((item) => item.id !== call.definition.id);
        draft.changes = draft.changes.filter((item) => item.definition.id !== call.definition.id);
      }
    });
  }

  function moveCall(stepId: string, callId: string, direction: -1 | 1): void {
    commit((draft) => {
      const items = workflowSteps(draft.bundle).find((item) => item.id === stepId)?.collectionCalls;
      const index = items?.findIndex((item) => item.id === callId) ?? -1;
      if (!items || index < 0 || index + direction < 0 || index + direction >= items.length) return;
      [items[index], items[index + direction]] = [items[index + direction], items[index]];
    });
  }

  function updateCallBinding(stepId: string, callId: string, inputId: string, binding: CollectionCall["inputBindings"][string] | null): void {
    commit((draft) => {
      const call = findCall(draft.bundle, stepId, callId);
      if (!call) return;
      if (binding) call.inputBindings[inputId] = binding;
      else delete call.inputBindings[inputId];
    }, `binding:${stepId}:${callId}:${inputId}`);
  }

  function editCallDefinition(stepId: string, callId: string, mutate: (definition: CollectionDefinition) => void): boolean {
    const call = findCall(bundle.value!, stepId, callId);
    const source = call && findCollection(catalog.value, call.definition);
    if (!call || !source) return false;
    const existingChange = changes.value.find((item) => item.definition.id === source.id);
    if (existingChange && existingChange.operation !== "revise") {
      editDefinition({ id: source.id, revision: source.revision }, mutate);
      return false;
    }
    const fork = cloneWorkflow(source);
    const forkId = createWorkflowId("collection");
    const defaultForkKey = nextUniqueKey(catalog.value.map((item) => item.key), `${source.key}_copy`);
    fork.id = forkId;
    fork.revision = 1;
    fork.key = defaultForkKey;
    fork.forkedFrom = { id: source.id, revision: source.revision };
    mutate(fork);
    fork.id = forkId;
    fork.revision = 1;
    fork.key = !fork.key.trim() || fork.key === source.key
      ? defaultForkKey
      : nextUniqueKey(catalog.value.map((item) => item.key), fork.key);
    fork.forkedFrom = { id: source.id, revision: source.revision };
    commit((draft) => {
      draft.catalog.push(fork);
      upsertChange(draft, "fork", fork);
      const draftCall = findCall(draft.bundle, stepId, callId);
      if (draftCall) draftCall.definition = { id: fork.id, revision: 1 };
    });
    return true;
  }

  function currentSnapshot(): WorkflowEditorSnapshot | null {
    if (!bundle.value) return null;
    return cloneWorkflow({ bundle: bundle.value, catalog: catalog.value, changes: changes.value });
  }

  function restore(value: WorkflowEditorSnapshot): void {
    bundle.value = cloneWorkflow(value.bundle);
    catalog.value = cloneWorkflow(value.catalog);
    changes.value = cloneWorkflow(value.changes);
  }

  return {
    bundle, catalog, selection, changes, issues, dirty: history.dirty, canUndo: history.canUndo, canRedo: history.canRedo,
    load, accepted, undo: history.undo, redo: history.redo, discard: history.discard, updateMetadata, addInput, updateInput, removeInput, addDeviceRole, updateDeviceRole, removeDeviceRole,
    addWorkflowStep, duplicateStep, updateStep, removeStep, addWorkflowConclusion, updateConclusion, removeConclusion,
    addPath: paths.addPath, retargetPath: paths.retargetPath, updatePath: paths.updatePath, removePath: paths.removePath, movePath: paths.movePath,
    moveWorkflowNode: ordering.moveWorkflowNode, reorderWorkflowNodes: ordering.reorderWorkflowNodes,
    addDefinition, editDefinition, removeDraftDefinition, addCall, addDraftCollectionCall, updateCall, removeCall, moveCall,
    reorderCalls: ordering.reorderCalls, updateCallBinding, editCallDefinition,
  };
}

function fieldGroup(prefix: string, patch: Record<string, unknown>): string {
  return `${prefix}:${Object.keys(patch).sort().join(",")}`;
}

function upsertChange(draft: WorkflowEditorSnapshot, operation: WorkflowCollectionChange["operation"], definition: CollectionDefinition): void {
  const index = draft.changes.findIndex((item) => item.definition.id === definition.id);
  const next = { operation, definition: cloneWorkflow(definition) };
  if (index >= 0) draft.changes[index] = next;
  else draft.changes.push(next);
}
