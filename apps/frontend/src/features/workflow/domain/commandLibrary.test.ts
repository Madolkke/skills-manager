import { describe, expect, it } from "vitest";
import type { CommandLibrarySearchResult } from "../../../types";
import { commandResultToDefinition } from "./commandLibrary";

describe("commandResultToDefinition", () => {
  it("系统命令必须先确认具体命令", () => {
    expect(() => commandResultToDefinition(commandResult({ source: "system" }), 1)).toThrow("请先确认");
    const candidate = commandResultToDefinition(commandResult(), 1);
    candidate.sourceSystemCommandId = "system-command-1";
    candidate.sourceBindingMode = "concrete-command";
    candidate.inputs = [];
    candidate.spec = { collectionType: "cli", commandTemplate: "display interface eth0", commandParameterSyntax: "angle-v1", outputSamples: [] };
    const result = commandResultToDefinition(commandResult({ source: "system", instantiatedDefinition: candidate }), 1);
    expect(result.id).not.toBe(candidate.id);
    expect(result.inputs).toEqual([]);
    expect(result.sourceBindingMode).toBe("concrete-command");
    expect(result.spec).toEqual(candidate.spec);
  });

  it("不会为用户命令写入系统来源", () => {
    const definition = commandResultToDefinition(commandResult({ source: "user", id: "user-command-1" }), 1);

    expect(definition.sourceSystemCommandId).toBeUndefined();
  });

  it("按捕获描述生成可选字符串和重复字符串数组输入", () => {
    const definition = commandResultToDefinition(commandResult({
      captures: {
        interface: { optional: true, repeated: false },
        flags: { optional: false, repeated: true },
      },
    }), 1);

    expect(definition.inputs).toEqual([
      expect.objectContaining({
        key: "interface",
        required: false,
        schema: { type: "string", title: "interface", description: "" },
      }),
      expect.objectContaining({
        key: "flags",
        required: true,
        schema: {
          type: "array",
          title: "flags 列表",
          description: "",
          items: { type: "string", title: "flags", description: "" },
        },
      }),
    ]);
  });

  it("优先使用服务端参数定义而不是当前搜索捕获值", () => {
    const definition = commandResultToDefinition(commandResult({
      captures: { name: "ge0" },
      captureSchema: { name: { optional: false, repeated: false }, mode: { optional: true, repeated: false } },
    }), 1);

    expect(definition.inputs.map((item) => item.key)).toEqual(["name", "mode"]);
  });

  it("将命令根 Schema 属性展开为输出字段并保留嵌套对象", () => {
    const definition = commandResultToDefinition(commandResult({
      outputSchema: {
        type: "object",
        properties: {
          status: { type: "string", title: "状态" },
          details: { type: "object", properties: { uptime: { type: "integer", title: "运行时长" } }, required: ["uptime"], additionalProperties: false },
        },
        required: ["status"],
      },
    }), 1);

    expect(definition.outputs.map((item) => [item.key, item.required])).toEqual([["status", true], ["details", false]]);
    expect(definition.outputs.find((item) => item.key === "details")?.schema).toMatchObject({ type: "object", properties: { uptime: { type: "integer" } } });
  });
});

function commandResult(overrides: Partial<CommandLibrarySearchResult> = {}): CommandLibrarySearchResult {
  return {
    id: "system-command-1",
    source: "user",
    key: "display_interface",
    expression: "display interface <name>",
    metadata: { name: "接口状态", description: "读取接口状态", versions: ["V1"] },
    captures: { name: { optional: false, repeated: false } },
    outputSchema: {
      type: "object",
      properties: { status: { type: "string", title: "状态", description: "接口状态" } },
      required: ["status"],
    },
    ...overrides,
  };
}
