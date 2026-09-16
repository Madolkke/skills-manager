import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { CompletionContext } from "@codemirror/autocomplete";
import { EditorState } from "@codemirror/state";
import { describe, expect, it } from "vitest";
import type { WorkflowBundle } from "../../types";
import fixture from "./fixtures/complex-schema-workflow.json";
import { workflowExpressionVariables } from "./workflowExpressionVariables";
import { createWorkflowExpressionCompletionSource, createWorkflowTemplateCompletionSource } from "./workflowExpressionCompletion";

const bundle = fixture as unknown as WorkflowBundle;
const variables = workflowExpressionVariables(bundle, bundle.workflow.nodes[0]!.id);

describe("完整演示目录的数组补全", () => {
  it("隔离索引零失败匹配，外层超时可终止子进程", async () => {
    const path = fileURLToPath(new URL("./workflowArrayReference.ts", import.meta.url));
    const code = ts.transpileModule(readFileSync(path, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
    await new Promise<void>((resolve, reject) => {
      const child = spawn(process.execPath, ["-e", code + `
        const result = exports.findArrayReferenceMatch('outputs.interfaces.interfaces[0].up', 'outputs.interfaces.interfaces[0].addresses');
        if (result !== null) process.exit(1);
        const earlier = exports.findArrayReferenceMatch('outputs.x[0].nested + outputs.x[0].bad', 'outputs.x[0].nested');
        if (earlier?.start !== 0) process.exit(2);
      `]);
      const timer = setTimeout(() => { child.kill(); reject(new Error("数组路径匹配未终止")); }, 2000);
      child.on("error", (error) => { clearTimeout(timer); reject(error); });
      child.on("exit", (code) => { clearTimeout(timer); if (code === 0) resolve(); else reject(new Error(`子进程退出 ${code}`)); });
    });
  });

  it.each([
    ["outputs.interfaces.interfaces[0].", ["name", "up", "counters", "addresses"]],
    ["outputs.interfaces.interfaces[-1].counters.", ["rx", "tx", "errors"]],
    ["outputs.interfaces.interfaces[inputs.index].addresses[0].", ["address", "prefix_length"]],
    ["outputs.routes.routes[0].next_hops[-1].", ["address", "metric"]],
    ["outputs.bgp.peers[0].families[0].prefixes.", ["received", "accepted"]],
    ["outputs.fabric[0].matrix[0][0].", ["value", "healthy"]],
  ])("%s 限定对应层级并保留下标", async (path, fields) => {
    const source = createWorkflowExpressionCompletionSource(() => variables);
    const result = await source(new CompletionContext(EditorState.create({ doc: path }), path.length, true));
    expect(result?.options.map((item) => item.label).sort()).toEqual(fields.map((field) => path + field).sort());
    expect(result?.from).toBe(0);
  });

  it.each(["outputs.interfaces.interfaces[", "outputs.fabric[0].matrix[1.5].", "outputs.fabric[0].matrix['x'].", "outputs.fabric.matrix[0][0].", "outputs.interfaces.interfaces[inputs.vrf]."])('不提供误导候选 %s', async (path) => {
    const result = await createWorkflowExpressionCompletionSource(() => variables)(new CompletionContext(EditorState.create({ doc: path }), path.length, true));
    expect(result).toBeNull();
  });

  it("函数参数内部的数组路径不被关键字提示抢占", async () => {
    const path = "sum(outputs.interfaces.interfaces[0].counters.";
    const functions = { sum: { parameters: ["iterable", "start"], isBuiltin: true } };
    const result = await createWorkflowExpressionCompletionSource(() => variables, () => functions)(new CompletionContext(EditorState.create({ doc: path }), path.length, true));
    expect(result?.options.map(item => item.label).sort()).toEqual(["errors", "rx", "tx"].map(field => `outputs.interfaces.interfaces[0].counters.${field}`));
    expect(result?.from).toBe(4);
  });

  it("模板只替换当前引用，保留中文、分隔符和尾部文本", async () => {
    const before = "前文 {{ outputs.interfaces.interfaces[-1].addresses[inputs.index].addr";
    const after = " }} 后文";
    const result = await createWorkflowTemplateCompletionSource(() => variables)(new CompletionContext(EditorState.create({ doc: before + after }), before.length, true));
    expect(before.slice(0, result!.from) + result!.options[0]!.apply + after).toBe("前文 {{ outputs.interfaces.interfaces[-1].addresses[inputs.index].address }} 后文");
  });
});
