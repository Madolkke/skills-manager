import { describe, expect, it } from "vitest";
import type { CollectionDefinition, CommandLibrarySearchResult, VersionedRef } from "../../../types";
import { collectionLibraryItems, findReusableCommandDefinition } from "./collectionLibrary";

describe("collectionLibraryItems", () => {
  it("命令行默认只显示系统搜索结果，不显示全局旧 CLI Catalog", () => {
    const current = definition("current-user", "display current", "user");
    const global = definition("global-user", "display global", "user");
    const system = command("system-1", "display system", "system");

    const items = collectionLibraryItems({
      type: "cli",
      definitions: [current, global],
      currentDefinitionRefs: [ref(current)],
      commandResults: [system],
      includeUser: false,
      query: "",
    });

    expect(items.map((item) => item.id)).toEqual(["system:system-1"]);
  });

  it("Toggle 开启后合并当前用户定义和远端用户命令", () => {
    const current = definition("current-user", "display current", "user");
    const remote = command("user-1", "display remote", "user", current.id, current.revision);
    const items = collectionLibraryItems({
      type: "cli",
      definitions: [current],
      currentDefinitionRefs: [ref(current)],
      commandResults: [remote],
      includeUser: true,
      query: "",
    });

    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ source: "user", current: true, definition: current });
  });

  it("日志和配置独立按类型显示，不读取命令搜索结果", () => {
    const log = definition("log-1", "日志", undefined, "log");
    const config = definition("config-1", "配置", undefined, "config");
    const commandResult = command("system-1", "display system", "system");

    expect(collectionLibraryItems({
      type: "log",
      definitions: [log, config],
      currentDefinitionRefs: [],
      commandResults: [commandResult],
      includeUser: false,
      query: "",
    }).map((item) => item.definition?.id)).toEqual(["log-1"]);
    expect(collectionLibraryItems({
      type: "config",
      definitions: [log, config],
      currentDefinitionRefs: [],
      commandResults: [commandResult],
      includeUser: false,
      query: "",
    }).map((item) => item.definition?.id)).toEqual(["config-1"]);
  });

  it("系统来源按 sourceSystemCommandId 合并并可复用当前定义", () => {
    const current = definition("current-system", "display system", "system");
    const result = command("system-1", "display system", "system");
    current.sourceSystemCommandId = result.id;

    const items = collectionLibraryItems({
      type: "cli",
      definitions: [current],
      currentDefinitionRefs: [ref(current)],
      commandResults: [result],
      includeUser: false,
      query: "",
    });

    expect(items).toHaveLength(1);
    expect(findReusableCommandDefinition(result, [current], [ref(current)])).toBe(current);
    expect(items[0]?.definition).toBe(current);
  });
});

function ref(definitionValue: CollectionDefinition): VersionedRef {
  return { id: definitionValue.id, revision: definitionValue.revision };
}

function command(
  id: string,
  expression: string,
  source: "system" | "user",
  collectionDefinitionId?: string,
  collectionRevision?: number,
): CommandLibrarySearchResult {
  return {
    id,
    source,
    key: id,
    expression,
    metadata: { name: expression },
    collectionDefinitionId,
    collectionRevision,
  };
}

function definition(
  id: string,
  expression: string,
  source?: "system" | "user",
  type: "cli" | "log" | "config" = "cli",
): CollectionDefinition {
  return {
    id,
    revision: 1,
    key: id,
    metadata: { name: id, description: "", industry: "", device: "", versions: [], tags: [] },
    spec: type === "cli"
      ? { collectionType: "cli", commandTemplate: expression, outputSamples: [] }
      : type === "log"
        ? { collectionType: "log", sqlDialect: "duckdb", queries: [], outputSamples: [] }
        : { collectionType: "config", config: { commands: [] } },
    inputs: [],
    outputs: [],
    ...(source === "system" ? { sourceSystemCommandId: "system-1" } : {}),
  };
}
