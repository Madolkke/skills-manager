import { CompletionContext } from "@codemirror/autocomplete";
import { EditorState } from "@codemirror/state";
import { describe, expect, it } from "vitest";
import type { WorkflowJsonSchema } from "../../types";
import { createWorkflowExpressionCompletionSource } from "./workflowExpressionCompletion";
import type { WorkflowExpressionVariable, WorkflowExpressionVariableKind } from "./workflowExpressionVariables";

describe("Workflow complex expression completion", () => {
  it("replaces complete paths after ordinary, config, and multi-sample array indexes", async () => {
    const source = createWorkflowExpressionCompletionSource(() => complexVariables());

    await expectAcceptedCompletion(source, "inputs.request.interfaces[inputs.index].counters.err", "inputs.request.interfaces[inputs.index].counters.errors");
    await expectAcceptedCompletion(source, "inputs.matrix[-1][inputs.column].val", "inputs.matrix[-1][inputs.column].value");
    await expectAcceptedCompletion(source, "outputs.status.ports[-1].u", "outputs.status.ports[-1].up");
    await expectAcceptedCompletion(source, "outputs.multi[0].ports[inputs.index].spe", "outputs.multi[0].ports[inputs.index].speed");
    await expectAcceptedCompletion(source, "config.gateway.routes[0].next_", "config.gateway.routes[0].next_hop");
  });

  it("does not complete unsupported or unfinished ordinary array indexes", async () => {
    const source = createWorkflowExpressionCompletionSource(() => complexVariables());

    await expectAcceptedCompletion(source, "inputs.request.interfaces[1.5].", null);
    await expectAcceptedCompletion(source, "outputs.status.ports[0:].", null);
    await expectAcceptedCompletion(source, "config.gateway.routes[", null);
  });
});

async function expectAcceptedCompletion(
  source: ReturnType<typeof createWorkflowExpressionCompletionSource>,
  input: string,
  expected: string | null,
): Promise<void> {
  const state = EditorState.create({ doc: input, selection: { anchor: input.length } });
  const result = await source(new CompletionContext(state, input.length, true));
  if (expected === null) {
    expect(result).toBeNull();
    return;
  }
  expect(result).not.toBeNull();
  const option = result!.options[0]!;
  expect(typeof option.apply).toBe("string");
  expect(`${input.slice(0, result!.from)}${option.apply}`).toBe(expected);
}

function complexVariables(): WorkflowExpressionVariable[] {
  const error = scalar("integer", "错误数");
  const interfaceSchema = object({ counters: object({ errors: error }, "计数") }, "接口");
  const cell = object({ value: scalar("number", "值") }, "单元格");
  const port = object({ up: scalar("boolean", "运行") }, "端口");
  const route = object({ next_hop: scalar("string", "下一跳") }, "路由");
  const multi = object({ ports: array(object({ speed: scalar("number", "速率") }, "端口"), "端口列表") }, "多采样");

  return [
    variable("input-interfaces", "inputs.request.interfaces", array(interfaceSchema, "接口列表")),
    variable("input-errors", "inputs.request.interfaces[0].counters.errors", error),
    variable("input-matrix", "inputs.matrix", array(array(cell, "行"), "矩阵")),
    variable("input-matrix-row", "inputs.matrix[0]", array(cell, "行")),
    variable("input-matrix-value", "inputs.matrix[0][0].value", scalar("number", "值")),
    variable("output-ports", "outputs.status.ports", array(port, "端口列表"), "output"),
    variable("output-up", "outputs.status.ports[0].up", scalar("boolean", "运行"), "output"),
    { ...variable("multi", "outputs.multi", multi, "output"), sampleCount: 3 },
    variable("config-routes", "config.gateway.routes", array(route, "路由列表"), "config"),
    variable("config-hop", "config.gateway.routes[0].next_hop", scalar("string", "下一跳"), "config"),
  ];
}

function variable(
  id: string,
  reference: string,
  schema: WorkflowJsonSchema,
  kind: WorkflowExpressionVariableKind = "global",
): WorkflowExpressionVariable {
  return { id, reference, kind, name: id, dataType: schema.type ?? "any", source: "测试", aliases: [], schema, indexable: schema.type === "array" };
}

function scalar(type: "string" | "integer" | "number" | "boolean", title: string): WorkflowJsonSchema {
  return { type, title, description: "" };
}

function object(properties: Record<string, WorkflowJsonSchema>, title: string): WorkflowJsonSchema {
  return { type: "object", title, description: "", properties, required: [], additionalProperties: false };
}

function array(items: WorkflowJsonSchema, title: string): WorkflowJsonSchema {
  return { type: "array", title, description: "", items };
}
