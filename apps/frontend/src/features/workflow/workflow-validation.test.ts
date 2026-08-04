import { describe, expect, it } from "vitest";
import type { CliCollectionSpec, CollectionDefinition, WorkflowBundle, WorkflowStep } from "../../types";
import { validateWorkflow } from "./domain/validation";

describe("workflow validation consistency", () => {
  it("distinguishes empty required literals from valid falsey values", () => {
    const cases: Array<{ value: unknown; type: "string" | "integer" | "boolean"; missing: boolean; omit?: boolean }> = [
      { value: null, type: "string", missing: true },
      { value: undefined, type: "string", missing: true, omit: true },
      { value: "", type: "string", missing: true },
      { value: 0, type: "integer", missing: false },
      { value: false, type: "boolean", missing: false },
    ];
    cases.forEach(({ value, type, missing, omit }) => {
      const bundle = workflowBundle();
      bundle.collectionSnapshots[0]!.inputs = [{ id: "parameter-required", key: "required", required: true, schema: { type, title: "Required", description: "" } }];
      const binding = { kind: "literal" as const, reference: {}, ...(!omit && { value }) };
      workflowStep(bundle).collectionCalls[0]!.inputBindings = { "parameter-required": binding };

      expect(validateWorkflow(bundle).some((item) => item.code === "MISSING_REQUIRED_BINDING")).toBe(missing);
    });
  });

  it("uses missing codes for blank identities and keeps issue ids unique", () => {
    const bundle = workflowBundle();
    const step = workflowStep(bundle);
    const definition = bundle.collectionSnapshots[0]!;
    bundle.workflow.inputs = [{ id: "", key: "", required: true, schema: stringSchema("Input") }];
    bundle.workflow.deviceRoles = [{ id: "", key: "", name: "Device", description: "", required: true }];
    step.id = "";
    step.collectionCalls[0]!.id = "";
    step.topology[0]!.id = "";
    definition.inputs = [{ id: "", key: "", required: true, schema: stringSchema("Input") }];
    definition.outputs = [{ id: "", key: "", required: true, schema: stringSchema("Output") }];
    (definition.spec as CliCollectionSpec).outputSamples = [{ id: "", name: "Sample", stdout: "", inputValues: {} }];

    const issues = validateWorkflow(bundle);
    const codes = new Set(issues.map((item) => item.code));
    const expected = [
      "MISSING_NODE_ID", "MISSING_INPUT_ID", "MISSING_INPUT_KEY", "MISSING_ROLE_ID", "MISSING_ROLE_KEY", "MISSING_CALL_ID",
      "MISSING_TRANSITION_ID", "MISSING_COLLECTION_INPUT_ID", "MISSING_COLLECTION_INPUT_KEY", "MISSING_COLLECTION_OUTPUT_ID",
      "MISSING_COLLECTION_OUTPUT_KEY", "MISSING_COLLECTION_SAMPLE_ID",
    ];

    expected.forEach((code) => expect(codes.has(code)).toBe(true));
    expect(new Set(issues.map((item) => item.id)).size).toBe(issues.length);
    expected.forEach((code) => expect(codes.has(code.replace("MISSING_", "DUPLICATE_"))).toBe(false));
  });

  it("keeps non-empty duplicate codes", () => {
    const bundle = workflowBundle();
    const step = workflowStep(bundle);
    const definition = bundle.collectionSnapshots[0]!;
    bundle.workflow.nodes.push(structuredClone(bundle.workflow.nodes[1]!));
    const input = { id: "input-1", key: "input", required: true, schema: stringSchema("Input") };
    bundle.workflow.inputs = [input, structuredClone(input)];
    const role = { id: "role-1", key: "device", name: "Device", description: "", required: true };
    bundle.workflow.deviceRoles = [role, structuredClone(role)];
    step.collectionCalls.push(structuredClone(step.collectionCalls[0]!));
    step.topology.push(structuredClone(step.topology[0]!));
    const parameter = { id: "parameter-1", key: "parameter", required: true, schema: stringSchema("Parameter") };
    definition.inputs = [parameter, structuredClone(parameter)];
    const output = { id: "output-1", key: "status", required: true, schema: stringSchema("Output") };
    definition.outputs = [output, structuredClone(output)];
    const sample = { id: "sample-1", name: "Sample", stdout: "", inputValues: {} };
    (definition.spec as CliCollectionSpec).outputSamples = [sample, structuredClone(sample)];
    bundle.collectionSnapshots.push(structuredClone(definition));

    const codes = new Set(validateWorkflow(bundle).map((item) => item.code));
    [
      "DUPLICATE_NODE_ID", "DUPLICATE_INPUT_ID", "DUPLICATE_INPUT_KEY", "DUPLICATE_ROLE_ID", "DUPLICATE_ROLE_KEY",
      "DUPLICATE_CALL_ID", "DUPLICATE_CALL_KEY", "DUPLICATE_TRANSITION_ID", "DUPLICATE_COLLECTION_REFERENCE",
      "DUPLICATE_COLLECTION_INPUT_ID", "DUPLICATE_COLLECTION_INPUT_KEY", "DUPLICATE_COLLECTION_OUTPUT_ID",
      "DUPLICATE_COLLECTION_OUTPUT_KEY", "DUPLICATE_COLLECTION_SAMPLE_ID",
    ].forEach((code) => expect(codes.has(code)).toBe(true));
  });

  it("keeps issue ids stable when unrelated issues are inserted", () => {
    const bundle = workflowBundle();
    bundle.collectionSnapshots[0]!.inputs = [{ id: "parameter-required", key: "required", required: true, schema: stringSchema("Required") }];
    workflowStep(bundle).collectionCalls[0]!.inputBindings = {
      "parameter-required": { kind: "literal", reference: {}, value: null },
    };

    const first = validateWorkflow(bundle);
    const issue = first.find((item) => item.code === "MISSING_REQUIRED_BINDING")!;
    expect(first).toEqual(validateWorkflow(bundle));
    bundle.workflow.metadata.name = "";
    const unchanged = validateWorkflow(bundle).find((item) => item.code === "MISSING_REQUIRED_BINDING")!;

    expect(issue.id).toBe(unchanged.id);
    expect(issue.id).toBe("workflow-issue/missing_required_binding/step/step-start//collections/call-interface/binding.parameter-required/0");
    expect(issue.selection).toEqual({ type: "step", id: "step-start", section: "collections", itemId: "call-interface", field: "binding.parameter-required" });
  });
});

function workflowBundle(): WorkflowBundle {
  const definition = collectionDefinition();
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-1", revision: 1,
      metadata: { name: "Workflow", code: "WF", description: "Description", symptom: "", industry: "", device: "", versions: [] },
      inputs: [], deviceRoles: [],
      nodes: [
        { id: "step-start", name: "Step", description: "", isStart: true, collectionCalls: [{ id: "call-interface", key: "interface", name: "Interface status", definition: { id: definition.id, revision: 1 }, sampleCount: 1, inputBindings: {} }], topology: [{ id: "path-done", target: { id: "conclusion-done" }, conditionText: "Done", conditionExpression: "" }], stepType: "expression" },
        { id: "conclusion-done", name: "Done", rootCause: "Cause", repairRecommendation: "Repair", nodeType: "conclusion" },
      ],
    },
    collectionSnapshots: [definition],
  };
}

function collectionDefinition(): CollectionDefinition {
  return {
    id: "collection-interface", revision: 1, key: "interface_status",
    metadata: { name: "Interface status", description: "", industry: "", device: "", versions: [], tags: [] },
    spec: { collectionType: "cli", commandTemplate: "display interface", outputSamples: [] }, inputs: [], outputs: [],
  };
}

function workflowStep(bundle: WorkflowBundle): WorkflowStep {
  return bundle.workflow.nodes[0] as WorkflowStep;
}

function stringSchema(title: string) {
  return { type: "string" as const, title, description: "" };
}
