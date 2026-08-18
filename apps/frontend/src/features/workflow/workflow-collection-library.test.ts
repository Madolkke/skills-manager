// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import type { CollectionDefinition, CommandLibrarySearchResult } from "../../types";
import WorkflowCollectionLibrary from "./components/WorkflowCollectionLibrary.vue";
import WorkflowCollectionPicker from "./components/WorkflowCollectionPicker.vue";
import { resetCommandLibrarySession } from "./commandLibrarySession";

const system = result("system-1", "display system", "system");
const user = result("user-1", "display user", "user");
const legacy = definition("legacy", "display legacy");
const log = definition("log-1", "日志", "log");
const config = definition("config-1", "配置", "config");

describe("WorkflowCollectionLibrary", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    resetCommandLibrarySession();
    vi.useRealTimers();
  });

  it("默认只显示系统 CLI，Toggle 后追加用户 CLI，且不显示类型标签", async () => {
    vi.useFakeTimers();
    vi.spyOn(api, "searchCommandLibrary").mockImplementation(async (_query, includeUser) => ({
      results: includeUser ? [system, user] : [system],
    }));
    const wrapper = mount(WorkflowCollectionLibrary, {
      props: {
        definitions: [legacy, log, config],
        currentDefinitionRefs: [],
        changes: [],
        readonly: false,
      },
      global: { stubs: { WorkflowCollectionFields: true } },
    });

    await advanceSearch();
    expect(wrapper.text()).toContain("display system");
    expect(wrapper.text()).not.toContain("display legacy");
    expect(wrapper.text()).not.toContain("display user");

    await wrapper.get("input[type='checkbox']").setValue(true);
    await advanceSearch();
    expect(wrapper.text()).toContain("display user");
    expect(wrapper.findAll(".workflow-library-item").some((item) => item.text().includes("日志"))).toBe(false);
    expect(wrapper.findAll("button[role='tab']")).toHaveLength(0);
  });
});

describe("WorkflowCollectionPicker", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    resetCommandLibrarySession();
    vi.useRealTimers();
  });

  it("与 Library 共享系统默认和用户 Toggle 语义", async () => {
    vi.useFakeTimers();
    vi.spyOn(api, "searchCommandLibrary").mockImplementation(async (_query, includeUser) => ({
      results: includeUser ? [system, user] : [system],
    }));
    const wrapper = mount(WorkflowCollectionPicker, {
      props: { definitions: [legacy], currentDefinitionRefs: [], changes: [], readonly: false },
    });

    await wrapper.get("input").trigger("focus");
    await advanceSearch();
    expect(wrapper.text()).toContain("display system");
    expect(wrapper.text()).not.toContain("display legacy");

    await wrapper.get("input[type='checkbox']").setValue(true);
    await advanceSearch();
    expect(wrapper.text()).toContain("display user");
    expect(wrapper.findAll("button[role='tab']")).toHaveLength(0);
  });
});

async function advanceSearch(): Promise<void> {
  await vi.advanceTimersByTimeAsync(180);
  await flushPromises();
}

function result(id: string, expression: string, source: "system" | "user"): CommandLibrarySearchResult {
  return { id, source, key: id, expression, metadata: { name: expression } };
}

function definition(id: string, name: string, type: "cli" | "log" | "config" = "cli"): CollectionDefinition {
  return {
    id,
    revision: 1,
    key: id,
    metadata: { name, description: "", industry: "", device: "", versions: [], tags: [] },
    spec: type === "cli"
      ? { collectionType: "cli", commandTemplate: name, outputSamples: [] }
      : type === "log"
        ? { collectionType: "log", sqlDialect: "duckdb", queries: [], outputSamples: [] }
        : { collectionType: "config", config: { commands: [] } },
    inputs: [],
    outputs: [],
  };
}
