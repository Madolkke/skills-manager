// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import { api } from "../../lib/api";
import type { WorkflowBundle, WorkflowStep } from "../../types";
import { useWorkflowExpressionValidation } from "./useWorkflowExpressionValidation";

type Response = Awaited<ReturnType<typeof api.validateWorkflowExpressions>>;

/** 建立可手动完成的请求，覆盖服务器忽略取消信号的情形。 */
function deferred() {
  let resolve!: (response: Response) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<Response>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

/** 生成独立的双路径文档，避免节点删除改变表达式环境。 */
function fixture() {
  const step: WorkflowStep = {
    id: "step", name: "检查", description: "", stepType: "expression", parallelBranches: false, isStart: true, collectionCalls: [],
    topology: ["first", "second"].map((id) => ({ id, conditionExpression: "True", conditionText: "", target: { id: "end" } })),
  };
  const bundle = ref<WorkflowBundle | null>({ documentType: "workflow_bundle", collectionSnapshots: [], workflow: {
    id: "workflow", revision: 1, inputs: [], deviceRoles: [], nodes: [step],
    metadata: { name: "文档", code: "", description: "说明", symptom: "", industry: "", device: "", versions: [] },
  } });
  return { bundle, step: bundle.value!.workflow.nodes[0] as WorkflowStep };
}

/** 返回带定位诊断的批次，便于观察过期响应是否污染当前状态。 */
function response(ids = ["first", "second"]): Response {
  return { validations: ids.map((id) => ({ id: `step:${id}`, inferredType: { kind: "boolean" }, diagnostics: [
    { code: "SAMPLE_INDEX_REQUIRED", severity: "warning", message: id, start: 0, end: 4 },
  ] })) };
}

describe("表达式校验请求生命周期", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it.each([false, true])("删除在途表达式后不恢复其诊断或缓存，删除全部：%s", async (all) => {
    const pending = deferred();
    const validation = vi.spyOn(api, "validateWorkflowExpressions").mockReturnValueOnce(pending.promise)
      .mockResolvedValue(response(["second"]));
    const { bundle, step } = fixture();
    const scope = effectScope();
    const result = scope.run(() => useWorkflowExpressionValidation(bundle))!;
    try {
      await vi.advanceTimersByTimeAsync(300);
      step.topology = all ? [] : step.topology.slice(0, 1);
      await nextTick();
      pending.resolve(response());
      await vi.advanceTimersByTimeAsync(0);
      expect(Object.keys(result.diagnostics.value)).toEqual(all ? [] : ["step:first"]);
      expect(result.issues.value).toHaveLength(all ? 0 : 1);
      step.topology.push({ id: "second", conditionExpression: "True", conditionText: "", target: { id: "end" } });
      await nextTick();
      await vi.advanceTimersByTimeAsync(300);
      expect(validation).toHaveBeenCalledTimes(2);
      expect(validation.mock.calls[1]![0].map((item) => item.id)).toEqual(["step:second"]);
    } finally { scope.stop(); }
  });

  it("在途请求失败后元数据编辑重新调度，不在请求未完成时重复发送", async () => {
    const pending = deferred();
    const validation = vi.spyOn(api, "validateWorkflowExpressions").mockReturnValueOnce(pending.promise)
      .mockResolvedValue(response());
    const { bundle } = fixture();
    const scope = effectScope();
    const result = scope.run(() => useWorkflowExpressionValidation(bundle))!;
    try {
      await vi.advanceTimersByTimeAsync(300);
      bundle.value!.workflow.metadata.name = "在途编辑";
      await nextTick();
      await vi.advanceTimersByTimeAsync(300);
      expect(validation).toHaveBeenCalledTimes(1);
      pending.reject(new Error("network unavailable"));
      await vi.advanceTimersByTimeAsync(0);
      bundle.value!.workflow.metadata.name = "失败后编辑";
      await nextTick();
      await vi.advanceTimersByTimeAsync(300);
      expect(validation).toHaveBeenCalledTimes(2);
      expect(Object.keys(result.diagnostics.value)).toEqual(["step:first", "step:second"]);
    } finally { scope.stop(); }
  });

  it.each([false, true])("卸载取消定时器及请求并忽略迟到响应，已发送：%s", async (started) => {
    const pending = deferred();
    const validation = vi.spyOn(api, "validateWorkflowExpressions").mockReturnValue(pending.promise);
    const { bundle } = fixture();
    const scope = effectScope();
    const result = scope.run(() => useWorkflowExpressionValidation(bundle))!;
    await vi.advanceTimersByTimeAsync(started ? 300 : 50);
    scope.stop();
    if (started) expect(validation.mock.calls[0]![2]?.aborted).toBe(true);
    pending.resolve(response());
    await vi.advanceTimersByTimeAsync(500);
    expect(validation).toHaveBeenCalledTimes(started ? 1 : 0);
    expect(result.diagnostics.value).toEqual({});
  });
});
