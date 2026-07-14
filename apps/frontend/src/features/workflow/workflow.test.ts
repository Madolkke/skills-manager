import { describe, expect, it, vi } from "vitest";
import { Position } from "@vue-flow/core";
import { api } from "../../lib/api";
import type { CollectionDefinition, WorkflowBundle, WorkflowDetail, WorkflowStep } from "../../types";
import { projectWorkflowGraph } from "./domain/graph";
import { graphAnimationStart, interpolatePosition, workflowGraphBranchColor, workflowGraphEdgeRoute, workflowGraphLabelMetrics, workflowGraphLayoutOptions, workflowGraphNodeSize, workflowGraphPorts } from "./domain/graphRouting";
import { workflowPredecessors } from "./domain/utils";
import { workflowStatusLabel } from "./domain/presentation";
import { parseWorkflowBundle } from "./domain/schema";
import { validateWorkflow } from "./domain/validation";
import { useWorkflowEditor } from "./useWorkflowEditor";

describe("workflow domain", () => {
  it("interpolates graph positions without overshooting their targets", () => {
    expect(interpolatePosition({ x: 10, y: 30 }, { x: 110, y: 230 }, 0)).toEqual({ x: 10, y: 30 });
    expect(interpolatePosition({ x: 10, y: 30 }, { x: 110, y: 230 }, 0.5)).toEqual({ x: 60, y: 130 });
    expect(interpolatePosition({ x: 10, y: 30 }, { x: 110, y: 230 }, 1)).toEqual({ x: 110, y: 230 });
  });

  it("keeps graph dimensions and ports aligned with the selected presentation", () => {
    expect(workflowGraphNodeSize(true, "step")).toEqual({ width: 180, height: 104 });
    expect(workflowGraphNodeSize(true, "conclusion")).toEqual({ width: 180, height: 92 });
    expect(workflowGraphNodeSize(false, "step")).toEqual({ width: 220, height: 104 });
    expect(workflowGraphPorts("RIGHT")).toEqual({ sourcePosition: Position.Right, targetPosition: Position.Left });
    expect(workflowGraphPorts("DOWN")).toEqual({ sourcePosition: Position.Bottom, targetPosition: Position.Top });
  });

  it("starts new graph nodes at their final position instead of their parent", () => {
    const target = { x: 420, y: 160 };

    expect(graphAnimationStart(undefined, target)).toEqual(target);
    expect(graphAnimationStart({ x: 20, y: 30 }, target)).toEqual({ x: 20, y: 30 });
  });

  it("renders ELK edge sections as independent rounded orthogonal paths", () => {
    const route = workflowGraphEdgeRoute({
      sections: [{
        startPoint: { x: 10, y: 20 },
        bendPoints: [{ x: 30, y: 20 }, { x: 30, y: 50 }],
        endPoint: { x: 60, y: 50 },
      }],
      labels: [{ x: 100, y: 40, width: 120, height: 24 }],
    });

    expect(route).toEqual({
      path: "M 10 20 L 24 20 Q 30 20 30 26 L 30 44 Q 30 50 36 50 L 60 50",
      labelPosition: { x: 160, y: 52 },
      labelSize: { width: 120, height: 24 },
    });
  });

  it("reserves bounded label space and disables ELK edge merging", () => {
    expect(workflowGraphLabelMetrics("接口状态正常", false)).toEqual({ width: 84, height: 24 });
    expect(workflowGraphLabelMetrics("这是一个非常长的跳转条件说明，需要占用两行空间避免遮挡节点", false)).toEqual({ width: 228, height: 38 });
    expect(workflowGraphLayoutOptions(false, "RIGHT")).toMatchObject({
      "elk.edgeLabels.inline": "true",
      "elk.layered.mergeEdges": "false",
      "elk.spacing.edgeEdge": "20",
      "elk.spacing.edgeNode": "30",
    });
  });

  it("assigns stable distinct colors to branches from the same step", () => {
    const bundle = workflowBundle();
    workflowStep(bundle).topology.push({
      id: "path-second",
      target: { id: "conclusion-done" },
      conditionText: "Fallback",
      conditionExpression: "",
    });
    const branches = projectWorkflowGraph(bundle).edges;

    expect(branches.map((item) => [item.branchIndex, item.branchCount])).toEqual([[0, 2], [1, 2]]);
    expect(workflowGraphBranchColor(0)).not.toBe(workflowGraphBranchColor(1));
    expect(workflowGraphBranchColor(6)).toBe(workflowGraphBranchColor(0));
  });

  it("validates and projects a connected workflow", () => {
    const bundle = workflowBundle();

    expect(validateWorkflow(bundle, bundle.collectionSnapshots)).toEqual([]);
    expect(projectWorkflowGraph(bundle)).toMatchObject({
      nodes: [
        { id: "step-start", type: "step", isStart: true },
        { id: "conclusion-done", type: "conclusion" },
      ],
      edges: [{ source: "step-start", target: "conclusion-done", loop: false }],
    });
  });

  it("tracks an explicit save baseline with undo, redo, and discard", () => {
    const editor = useWorkflowEditor(() => false);
    const detail = workflowDetail();
    editor.load(detail, detail.document.collectionSnapshots);

    expect(editor.dirty.value).toBe(false);
    editor.updateMetadata({ name: "Updated workflow" });
    expect(editor.dirty.value).toBe(true);
    editor.undo();
    expect(editor.dirty.value).toBe(false);
    editor.redo();
    expect(editor.dirty.value).toBe(true);
    editor.discard();
    expect(editor.bundle.value?.workflow.metadata.name).toBe("Interface workflow");
    expect(editor.dirty.value).toBe(false);
  });

  it("coalesces continuous edits to the same field into one undo entry", () => {
    const editor = useWorkflowEditor(() => false);
    const detail = workflowDetail();
    editor.load(detail, detail.document.collectionSnapshots);

    editor.updateMetadata({ name: "Updated" });
    editor.updateMetadata({ name: "Updated workflow" });
    editor.undo();

    expect(editor.bundle.value?.workflow.metadata.name).toBe("Interface workflow");
    expect(editor.dirty.value).toBe(false);
  });

  it("creates a step Collection draft with inherited metadata and empty inputs", () => {
    const editor = useWorkflowEditor(() => false);
    const detail = workflowDetail();
    detail.document.workflow.metadata.versions = ["V1", "V2"];
    editor.load(detail, detail.document.collectionSnapshots);

    const result = editor.addDraftCollectionCall("step-start");
    expect(result).not.toBeNull();
    const definition = editor.catalog.value.find((item) => item.id === result?.definitionId);
    expect(definition?.metadata).toMatchObject({ industry: "Network", device: "Switch", versions: ["V1", "V2"] });
    expect(definition?.inputs).toEqual([]);
    expect(editor.changes.value.find((item) => item.definition.id === result?.definitionId)?.operation).toBe("create");
    const call = workflowStep(editor.bundle.value!).collectionCalls.find((item) => item.id === result?.callId);
    expect(call).toMatchObject({ name: "", key: "", inputBindings: {} });

    editor.editDefinition({ id: result!.definitionId, revision: 1 }, (draft) => {
      draft.metadata.name = "Power status";
      draft.key = "power_status";
    });
    expect(workflowStep(editor.bundle.value!).collectionCalls.find((item) => item.id === result?.callId)).toMatchObject({ name: "", key: "" });

    editor.updateCall("step-start", result!.callId, { name: "Primary power status" });
    editor.editDefinition({ id: result!.definitionId, revision: 1 }, (draft) => {
      draft.metadata.name = "Power health";
      draft.key = "power_health";
    });
    expect(workflowStep(editor.bundle.value!).collectionCalls.find((item) => item.id === result?.callId)).toMatchObject({ name: "Primary power status", key: "" });
  });

  it("removes an unsaved definition only after its final call is removed", () => {
    const editor = useWorkflowEditor(() => false);
    const detail = workflowDetail();
    editor.load(detail, detail.document.collectionSnapshots);
    const draft = editor.addDraftCollectionCall("step-start")!;
    editor.addWorkflowStep();
    const secondStep = editor.bundle.value!.workflow.nodes.find((item) => "stepType" in item && item.id !== "step-start")!;
    const definition = editor.catalog.value.find((item) => item.id === draft.definitionId)!;
    const secondCallId = editor.addCall(secondStep.id, definition);

    editor.removeCall("step-start", draft.callId);
    expect(editor.changes.value.some((item) => item.definition.id === draft.definitionId)).toBe(true);
    editor.removeCall(secondStep.id, secondCallId);
    expect(editor.changes.value.some((item) => item.definition.id === draft.definitionId)).toBe(false);
    expect(editor.catalog.value.some((item) => item.id === draft.definitionId)).toBe(false);
  });

  it("reorders steps and calls without changing their identities", () => {
    const editor = useWorkflowEditor(() => false);
    const detail = workflowDetail();
    editor.load(detail, detail.document.collectionSnapshots);
    editor.addWorkflowStep();
    const stepIds = editor.bundle.value!.workflow.nodes.filter((item) => "stepType" in item).map((item) => item.id);
    editor.reorderWorkflowNodes("step", [...stepIds].reverse());
    expect(editor.bundle.value!.workflow.nodes.filter((item) => "stepType" in item).map((item) => item.id)).toEqual([...stepIds].reverse());

    const definition = detail.document.collectionSnapshots[0]!;
    const secondCall = editor.addCall("step-start", definition);
    editor.reorderCalls("step-start", [secondCall, "call-interface"]);
    expect(workflowStep(editor.bundle.value!).collectionCalls.map((item) => item.id)).toEqual([secondCall, "call-interface"]);
  });

  it("creates nodes and paths without author-facing keys", () => {
    const editor = useWorkflowEditor(() => false);
    const detail = workflowDetail();
    editor.load(detail, detail.document.collectionSnapshots);

    editor.addWorkflowStep();
    editor.addWorkflowConclusion();
    editor.addPath("step-start", { kind: "existing", id: "conclusion-done" });

    const nodes = editor.bundle.value!.workflow.nodes;
    expect(nodes.every((item) => !("key" in item))).toBe(true);
    expect(workflowStep(editor.bundle.value!).topology.every((item) => !("key" in item) && Object.keys(item.target).length === 1)).toBe(true);
  });

  it("creates a connected step after its source and undoes both together", () => {
    const editor = useWorkflowEditor(() => false);
    const detail = workflowDetail();
    editor.load(detail, detail.document.collectionSnapshots);

    const result = editor.addPath("step-start", { kind: "step", name: "Verify route", stepType: "script" });
    const nodes = editor.bundle.value!.workflow.nodes;
    const target = nodes.find((item) => item.id === result?.targetId);

    expect(target).toMatchObject({ name: "Verify route", stepType: "script" });
    expect(nodes.map((item) => item.id)).toEqual(["step-start", result?.targetId, "conclusion-done"]);
    expect(workflowStep(editor.bundle.value!).topology.at(-1)).toMatchObject({ id: result?.pathId, target: { id: result?.targetId } });

    editor.undo();
    expect(editor.bundle.value!.workflow.nodes.map((item) => item.id)).toEqual(["step-start", "conclusion-done"]);
    expect(workflowStep(editor.bundle.value!).topology).toHaveLength(1);
  });

  it("creates conclusions at the end and retargets paths without removing prior targets", () => {
    const editor = useWorkflowEditor(() => false);
    const detail = workflowDetail();
    editor.load(detail, detail.document.collectionSnapshots);
    const originalPath = workflowStep(editor.bundle.value!).topology[0]!;

    const result = editor.retargetPath("step-start", originalPath.id, { kind: "conclusion", name: "Escalate" });
    const nodes = editor.bundle.value!.workflow.nodes;

    expect(nodes.at(-1)).toMatchObject({ id: result?.targetId, name: "Escalate", nodeType: "conclusion" });
    expect(workflowStep(editor.bundle.value!).topology[0]?.target).toEqual({ id: result?.targetId });
    expect(nodes.some((item) => item.id === "conclusion-done")).toBe(true);
  });

  it("finds direct predecessor steps without traversing the full graph", () => {
    const bundle = workflowBundle();
    const secondStep = { ...structuredClone(workflowStep(bundle)), id: "step-second", name: "Second", isStart: false, topology: [{ id: "path-second", target: { id: "conclusion-done" }, conditionText: "Done", conditionExpression: "" }] };
    bundle.workflow.nodes.splice(1, 0, secondStep);

    expect(workflowPredecessors(bundle, "conclusion-done").map((item) => item.id)).toEqual(["step-start", "step-second"]);
  });

  it("reports unscoped output collisions and multiline commands", () => {
    const bundle = workflowBundle();
    const definition = bundle.collectionSnapshots[0]!;
    definition.outputs = [{ id: "output-version", key: "version", description: "Version", dataType: "string" }];
    definition.spec.commandTemplate = "display version\nverbose";
    bundle.workflow.inputs = [{ id: "workflow-version", key: "version", name: "Version", description: "", dataType: "string", required: true }];
    workflowStep(bundle).collectionCalls[0]!.key = "";

    expect(validateWorkflow(bundle, bundle.collectionSnapshots).map((item) => item.code)).toEqual(expect.arrayContaining(["MULTILINE_COLLECTION_COMMAND", "UNSCOPED_OUTPUT_CONFLICT"]));
  });

  it("rejects removed transition names and descriptions", () => {
    const legacy = structuredClone(workflowBundle()) as unknown as { workflow: { nodes: Array<Record<string, unknown>> } };
    const step = legacy.workflow.nodes[0]!;
    const paths = step.topology as Array<Record<string, unknown>>;
    paths[0]!.name = "legacy path";
    paths[0]!.description = "legacy description";

    expect(() => parseWorkflowBundle(legacy)).toThrow();
  });

  it("rejects legacy node and transition keys", () => {
    const legacy = structuredClone(workflowBundle()) as unknown as {
      workflow: { nodes: Array<Record<string, unknown>> };
    };
    const step = legacy.workflow.nodes[0]!;
    step.key = "legacy-step";
    const paths = step.topology as Array<Record<string, unknown>>;
    paths[0]!.key = "legacy-path";

    expect(() => parseWorkflowBundle(legacy)).toThrow();
  });

  it("reports field targets for incomplete Collection drafts", () => {
    const bundle = workflowBundle();
    bundle.collectionSnapshots[0]!.metadata.name = "";
    bundle.collectionSnapshots[0]!.spec.commandTemplate = "";

    const issues = validateWorkflow(bundle, bundle.collectionSnapshots);

    expect(issues).toEqual(expect.arrayContaining([
      expect.objectContaining({ code: "MISSING_COLLECTION_NAME", selection: expect.objectContaining({ field: "metadata.name" }) }),
      expect.objectContaining({ code: "MISSING_COLLECTION_COMMAND", selection: expect.objectContaining({ field: "spec.commandTemplate" }) }),
    ]));
  });

  it("forks a persisted Collection before editing a call definition", () => {
    const editor = useWorkflowEditor(() => false);
    const detail = workflowDetail();
    editor.load(detail, detail.document.collectionSnapshots);

    const updated = structuredClone(detail.document.collectionSnapshots[0]!);
    updated.metadata.name = "Interface status copy";
    editor.editCallDefinition("step-start", "call-interface", (definition) => Object.assign(definition, updated));

    expect(editor.changes.value).toHaveLength(1);
    expect(editor.changes.value[0]?.operation).toBe("fork");
    expect(editor.changes.value[0]?.definition.forkedFrom).toEqual({ id: "collection-interface", revision: 1 });
    expect(editor.changes.value[0]?.definition.id).not.toBe("collection-interface");
    expect(editor.changes.value[0]?.definition.key).toBe("interface_status_copy");
    editor.removeDraftDefinition(editor.changes.value[0]!.definition.id);
    expect(editor.changes.value).toHaveLength(1);
    expect(editor.bundle.value?.workflow.nodes[0]).toMatchObject({
      collectionCalls: [{ definition: { revision: 1 } }],
    });
    expect(editor.bundle.value?.workflow.nodes[0]).not.toMatchObject({
      collectionCalls: [{ definition: { id: "collection-interface" } }],
    });
  });

  it("edits the selected exact Collection revision", () => {
    const editor = useWorkflowEditor(() => false);
    const detail = workflowDetail();
    const latest = structuredClone(detail.document.collectionSnapshots[0]!);
    latest.revision = 2;
    latest.metadata.name = "Latest revision";
    editor.load(detail, [latest]);

    editor.editDefinition({ id: "collection-interface", revision: 1 }, (definition) => {
      definition.metadata.name = "Snapshot revision";
    });

    expect(editor.catalog.value.find((item) => item.revision === 1)?.metadata.name).toBe("Snapshot revision");
    expect(editor.catalog.value.find((item) => item.revision === 2)?.metadata.name).toBe("Latest revision");
  });

  it("serializes Workflow creation and sync requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ skill_id: "skill-1", workflow_id: "workflow-1", skill_version_id: "version-1", mode: "created", workflow_revision: 2 }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await api.createWorkflowSkill({ slug: "interface-check", owner_ref: "owner", description: "Check interfaces.", tags: [] });
    await api.syncWorkflow("skill-1", { version: "0.0.2", display_name: "Workflow v2", change_summary: "Sync workflow." });

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ slug: "interface-check", owner_ref: "owner", description: "Check interfaces.", tags: [] }),
    });
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ version: "0.0.2", display_name: "Workflow v2", change_summary: "Sync workflow." }),
    });
    fetchMock.mockRestore();
  });

  it("uses concise labels for sync status", () => {
    expect(workflowStatusLabel("never_synced")).toBe("尚未同步");
    expect(workflowStatusLabel("diverged")).toBe("两侧均有更新");
  });
});

function workflowDetail(): WorkflowDetail {
  return {
    id: "workflow-1",
    skill_id: "skill-1",
    revision: 1,
    document_schema_version: 3,
    document: workflowBundle(),
    validation: { errors: [], warnings: [] },
    sync: { status: "never_synced", last_synced_revision: null, last_synced_skill_version_id: null, last_synced_at: null },
    created_at: "2026-07-12T00:00:00Z",
    updated_at: "2026-07-12T00:00:00Z",
    created_by: "owner",
    last_saved_by: "owner",
    capabilities: {
      actor: "owner",
      subject_type: "user",
      groups: [],
      roles: ["owner"],
      effective_roles: ["owner"],
      permissions: { "skill.edit": true, "skill.version.create": true },
      permission_sources: [],
    },
  };
}

function workflowBundle(): WorkflowBundle {
  const definition = collectionDefinition();
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-1",
      revision: 1,
      metadata: { name: "Interface workflow", code: "IFACE", description: "Check interfaces.", symptom: "", industry: "Network", device: "Switch", versions: [] },
      inputs: [],
      deviceRoles: [],
      nodes: [
        {
          id: "step-start",
          name: "Check interface",
          description: "Collect interface status.",
          isStart: true,
          collectionCalls: [{ id: "call-interface", key: "interface", name: "Interface status", definition: { id: definition.id, revision: 1 }, sampleCount: 1, inputBindings: {} }],
          topology: [{ id: "path-done", target: { id: "conclusion-done" }, conditionText: "Collected", conditionExpression: "status != ''" }],
          stepType: "expression",
        },
        { id: "conclusion-done", name: "Done", rootCause: "Interface fault.", repairRecommendation: "Repair interface.", nodeType: "conclusion" },
      ],
    },
    collectionSnapshots: [definition],
  };
}

function collectionDefinition(): CollectionDefinition {
  return {
    id: "collection-interface",
    revision: 1,
    key: "interface_status",
    metadata: { name: "Interface status", description: "Collect interface status.", industry: "Network", device: "Switch", versions: [], tags: [] },
    spec: { collectionType: "cli", commandTemplate: "display interface", outputSamples: [] },
    inputs: [],
    outputs: [],
  };
}

function workflowStep(bundle: WorkflowBundle): WorkflowStep {
  return bundle.workflow.nodes.find((item) => "stepType" in item && item.id === "step-start") as WorkflowStep;
}
