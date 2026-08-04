// @vitest-environment jsdom

import { mount, type VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CollectionDefinition, LogCollectionSpec } from "../../types";
import { api } from "../../lib/api";
import WorkflowCollectionFields from "./components/WorkflowCollectionFields.vue";
import WorkflowConfirmModal from "./components/WorkflowConfirmModal.vue";
import { fallbackWorkflowLogSchema } from "./domain/logSchema";

afterEach(() => vi.restoreAllMocks());

describe("Workflow 日志 Collection 编辑", () => {
  it("确认或取消类型切换，并仅重置类型专属字段", async () => {
    const definition = cliDefinition();
    const wrapper = mountCollection(definition);

    await wrapper.get(".workflow-collection-type select").setValue("log");
    expect(wrapper.findComponent(WorkflowConfirmModal).exists()).toBe(true);
    expect(wrapper.emitted("change")).toBeUndefined();

    wrapper.findComponent(WorkflowConfirmModal).vm.$emit("close");
    await nextTick();
    expect(wrapper.emitted("change")).toBeUndefined();
    expect(wrapper.findComponent(WorkflowConfirmModal).exists()).toBe(false);

    await wrapper.get(".workflow-collection-type select").setValue("log");
    wrapper.findComponent(WorkflowConfirmModal).vm.$emit("confirm");
    await nextTick();

    const changed = lastDefinition(wrapper);
    expect(changed.spec).toEqual({
      collectionType: "log",
      sqlDialect: "duckdb",
      queries: [],
      outputSamples: [],
    });
    expect(changed.metadata).toEqual(definition.metadata);
    expect(changed.inputs).toEqual(definition.inputs);
    expect(changed.outputs).toEqual(definition.outputs);
  });

  it("编辑 query、输出归属和日志样例，并在删除输出时解除归属", async () => {
    const wrapper = mountCollection(logDefinition());
    await nextTick();

    expect(wrapper.findAll(".workflow-log-columns code").map((item) => item.text())).toEqual([
      "event_time", "device", "module", "severity", "brief", "body",
    ]);

    await wrapper.get(".workflow-log-query input").setValue("错误统计");
    expect(lastLogSpec(wrapper).queries[0]?.name).toBe("错误统计");

    await wrapper.get(".workflow-log-query select[multiple]").setValue(["output-errors", "output-device"]);
    expect(lastLogSpec(wrapper).queries[0]?.outputIds).toEqual(["output-errors", "output-device"]);

    await wrapper.get(".workflow-log-sql-input").setValue("SELECT count(*) AS error_count FROM logs");
    expect(lastLogSpec(wrapper).queries[0]?.sql).toBe("SELECT count(*) AS error_count FROM logs");

    await wrapper.get('input[aria-label="日志样例名称"]').setValue("告警日志");
    expect(lastLogSpec(wrapper).outputSamples[0]?.name).toBe("告警日志");
    await wrapper.get(".workflow-log-samples .workflow-sample-output").setValue("2026-08-04 ERROR board unavailable");
    expect(lastLogSpec(wrapper).outputSamples[0]?.text).toBe("2026-08-04 ERROR board unavailable");

    await wrapper.get('button[aria-label="删除聚合查询"]').trigger("click");
    expect(lastLogSpec(wrapper).queries).toEqual([]);
    await wrapper.get('button[aria-label="删除日志样例"]').trigger("click");
    expect(lastLogSpec(wrapper).outputSamples).toEqual([]);

    await wrapper.get('button[aria-label="删除输出"]').trigger("click");
    const withoutOutput = lastDefinition(wrapper);
    expect(withoutOutput.outputs.map((item) => item.id)).toEqual(["output-device"]);
    expect((withoutOutput.spec as LogCollectionSpec).queries[0]?.outputIds).toEqual([]);
  });

  it("日志输入输出仅提供四种标量类型", () => {
    const wrapper = mountCollection(logDefinition());

    expect(optionValues(wrapper.get('select[aria-label="参数类型"]'))).toEqual([
      "string", "integer", "number", "boolean",
    ]);
    expect(optionValues(wrapper.get('select[aria-label="字段类型"]'))).toEqual([
      "string", "integer", "number", "boolean",
    ]);
    expect(wrapper.text()).not.toContain("字符串数组（string[]）");
    expect(wrapper.text()).not.toContain("复杂对象");
  });

  it("只读态禁用日志配置及字段编辑控件", () => {
    const wrapper = mountCollection(logDefinition(), true);

    expect(wrapper.get(".workflow-collection-type select").attributes("disabled")).toBeDefined();
    expect(wrapper.findAll(".workflow-log-spec input, .workflow-log-spec select, .workflow-log-spec textarea, .workflow-log-spec button")
      .every((item) => item.attributes("disabled") !== undefined)).toBe(true);
    expect(wrapper.findAll(".workflow-log-samples input, .workflow-log-samples textarea, .workflow-log-samples button")
      .every((item) => item.attributes("disabled") !== undefined)).toBe(true);
    expect(wrapper.findAll(".workflow-schema-field-table input, .workflow-schema-field-table select, .workflow-schema-field-table button")
      .every((item) => item.attributes("disabled") !== undefined)).toBe(true);
  });
});

function mountCollection(definition: CollectionDefinition, readonly = false): VueWrapper {
  vi.spyOn(api, "getWorkflowLogSchema").mockResolvedValue(fallbackWorkflowLogSchema);
  return mount(WorkflowCollectionFields, {
    props: { definition, readonly },
    global: { stubs: { Teleport: true } },
  });
}

function lastDefinition(wrapper: VueWrapper): CollectionDefinition {
  return wrapper.emitted("change")?.at(-1)?.[0] as CollectionDefinition;
}

function lastLogSpec(wrapper: VueWrapper): LogCollectionSpec {
  return lastDefinition(wrapper).spec as LogCollectionSpec;
}

function optionValues(select: ReturnType<VueWrapper["get"]>): string[] {
  return select.findAll("option").map((option) => option.attributes("value") ?? "");
}

function cliDefinition(): CollectionDefinition {
  return {
    id: "collection-log", revision: 1, key: "log_summary",
    metadata: { name: "日志聚合", description: "统计关键日志", industry: "IP", device: "PTN", versions: ["V1"], tags: ["log"] },
    spec: { collectionType: "cli", commandTemplate: "display logbuffer", outputSamples: [{ id: "cli-sample", name: "CLI", stdout: "ok", inputValues: {} }] },
    inputs: [{ id: "input-window", key: "window", required: true, schema: { type: "integer", title: "时间窗口", description: "分钟" } }],
    outputs: [{ id: "output-errors", key: "error_count", required: true, schema: { type: "integer", title: "错误数", description: "" } }],
  };
}

function logDefinition(): CollectionDefinition {
  return {
    ...cliDefinition(),
    spec: {
      collectionType: "log", sqlDialect: "duckdb",
      queries: [{ id: "query-errors", name: "错误数", sql: "SELECT count(*) AS error_count FROM logs", outputIds: ["output-errors"] }],
      outputSamples: [{ id: "log-sample", name: "原始日志", text: "ERROR board unavailable" }],
    },
    outputs: [
      { id: "output-errors", key: "error_count", required: true, schema: { type: "integer", title: "错误数", description: "" } },
      { id: "output-device", key: "device", required: true, schema: { type: "string", title: "设备", description: "" } },
    ],
  };
}
