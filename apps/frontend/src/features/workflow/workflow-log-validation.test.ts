import { describe, expect, it } from "vitest";
import type { CollectionDefinition, WorkflowBundle, WorkflowStep } from "../../types";
import { validateWorkflow } from "./domain/validation";

describe("Workflow 日志 Collection 校验", () => {
  it("要求每个输出恰好归属一条 query，并拒绝失效 output 引用", () => {
    const bundle = logWorkflowBundle();
    const definition = bundle.collectionSnapshots[0]!;
    if (definition.spec.collectionType !== "log") throw new Error("expected log collection");
    definition.spec.queries = [
      { id: "query-errors", name: "错误数", sql: "SELECT count(*) AS error_count FROM logs", outputIds: ["output-errors", "output-missing"] },
      { id: "query-duplicate", name: "重复归属", sql: "SELECT count(*) AS error_count FROM logs", outputIds: ["output-errors"] },
    ];

    const logIssues = validateWorkflow(bundle).filter((item) => item.code.startsWith("LOG_QUERY_OUTPUT"));
    expect(logIssues.map((item) => item.code)).toEqual([
      "LOG_QUERY_OUTPUT_NOT_UNIQUE",
      "LOG_QUERY_OUTPUT_NOT_ASSIGNED",
      "LOG_QUERY_OUTPUT_NOT_ASSIGNED",
    ]);
    expect(logIssues.map((item) => item.selection)).toEqual([
      { type: "collection", id: "collection-log", revision: 1, itemId: "query-duplicate", field: "spec.queries.query-duplicate.outputIds" },
      { type: "collection", id: "collection-log", revision: 1, itemId: "output-device", field: "outputs.output-device" },
      { type: "collection", id: "collection-log", revision: 1, itemId: "query-errors", field: "spec.queries.query-errors.outputIds" },
    ]);
  });

  it("完整且唯一的输出归属不产生归属错误", () => {
    const bundle = logWorkflowBundle();
    const definition = bundle.collectionSnapshots[0]!;
    if (definition.spec.collectionType !== "log") throw new Error("expected log collection");
    definition.spec.queries[0]!.outputIds = ["output-errors", "output-device"];

    expect(validateWorkflow(bundle).filter((item) => item.code.startsWith("LOG_QUERY_OUTPUT"))).toEqual([]);
  });

  it("日志输入和输出只接受四种标量 Schema", () => {
    const bundle = logWorkflowBundle();
    const definition = bundle.collectionSnapshots[0]!;
    definition.inputs[0]!.schema = {
      type: "array", title: "模块", description: "", items: { type: "string", title: "模块", description: "" },
    };
    definition.outputs[0]!.schema = {
      type: "object", title: "统计", description: "", properties: {}, required: [], additionalProperties: false,
    };

    const issues = validateWorkflow(bundle);
    expect(issues.find((item) => item.code === "LOG_INPUT_SCHEMA_NOT_SCALAR")?.selection).toEqual({
      type: "collection", id: "collection-log", revision: 1, itemId: "input-module", field: "inputs.input-module.schema",
    });
    expect(issues.find((item) => item.code === "LOG_OUTPUT_SCHEMA_NOT_SCALAR")?.selection).toEqual({
      type: "collection", id: "collection-log", revision: 1, itemId: "output-errors", field: "outputs.output-errors.schema",
    });
  });

  it("日志调用固定一次采集且不能绑定设备角色", () => {
    const bundle = logWorkflowBundle();
    const call = workflowStep(bundle).collectionCalls[0]!;
    call.sampleCount = 2;
    call.deviceRoleId = "role-device";

    const issues = validateWorkflow(bundle);
    expect(issues.find((item) => item.code === "LOG_CALL_SAMPLE_COUNT_UNSUPPORTED")?.selection).toEqual({
      type: "step", id: "step-start", section: "collections", itemId: "call-log", field: "sampleCount",
    });
    expect(issues.find((item) => item.code === "LOG_CALL_DEVICE_ROLE_UNSUPPORTED")?.selection).toEqual({
      type: "step", id: "step-start", section: "collections", itemId: "call-log", field: "deviceRoleId",
    });

    call.sampleCount = 1;
    delete call.deviceRoleId;
    const validCodes = validateWorkflow(bundle).map((item) => item.code);
    expect(validCodes).not.toContain("LOG_CALL_SAMPLE_COUNT_UNSUPPORTED");
    expect(validCodes).not.toContain("LOG_CALL_DEVICE_ROLE_UNSUPPORTED");
  });
});

function logWorkflowBundle(): WorkflowBundle {
  const definition = logDefinition();
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-log", revision: 1,
      metadata: { name: "日志诊断", code: "LOG", description: "日志聚合", symptom: "", industry: "", device: "", versions: [] },
      inputs: [],
      deviceRoles: [{ id: "role-device", key: "device", name: "设备", description: "", required: true }],
      nodes: [
        {
          id: "step-start", name: "聚合日志", description: "", isStart: true, stepType: "expression",
          collectionCalls: [{ id: "call-log", key: "log", name: "日志统计", definition: { id: definition.id, revision: definition.revision }, sampleCount: 1, inputBindings: { "input-module": { kind: "literal", reference: {}, value: "alarm" } } }],
          topology: [{ id: "path-done", target: { id: "conclusion-done" }, conditionText: "完成", conditionExpression: "true" }],
        },
        { id: "conclusion-done", name: "完成", rootCause: "", repairRecommendation: "", nodeType: "conclusion" },
      ],
    },
    collectionSnapshots: [definition],
  };
}

function logDefinition(): CollectionDefinition {
  return {
    id: "collection-log", revision: 1, key: "log_summary",
    metadata: { name: "日志统计", description: "", industry: "", device: "", versions: [], tags: [] },
    spec: {
      collectionType: "log", sqlDialect: "duckdb",
      queries: [{ id: "query-errors", name: "错误数", sql: "SELECT count(*) AS error_count FROM logs", outputIds: ["output-errors"] }],
      outputSamples: [],
    },
    inputs: [{ id: "input-module", key: "module", required: true, schema: { type: "string", title: "模块", description: "" } }],
    outputs: [
      { id: "output-errors", key: "error_count", required: true, schema: { type: "integer", title: "错误数", description: "" } },
      { id: "output-device", key: "device", required: true, schema: { type: "string", title: "设备", description: "" } },
    ],
  };
}

function workflowStep(bundle: WorkflowBundle): WorkflowStep {
  return bundle.workflow.nodes[0] as WorkflowStep;
}
