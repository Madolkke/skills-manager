import { describe, expect, it } from "vitest";
import type { CommandLibrarySearchResult } from "../../../types";
import { commandResultToDefinition } from "./commandLibrary";

describe("commandResultToDefinition", () => {
  it("将系统命令物化为带系统来源的只读 Collection 草稿", () => {
    const definition = commandResultToDefinition(commandResult({ source: "system", id: "system-command-1" }), 1);

    expect(definition).toMatchObject({
      key: "display_interface",
      sourceSystemCommandId: "system-command-1",
      spec: { collectionType: "cli", commandTemplate: "display interface <name>" },
      inputs: [{ id: "input_name", key: "name" }],
      outputs: [{ id: "output_status", key: "status", required: true, schema: { type: "string", title: "状态" } }],
    });
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
});

function commandResult(overrides: Partial<CommandLibrarySearchResult> = {}): CommandLibrarySearchResult {
  return {
    id: "system-command-1",
    source: "system",
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
