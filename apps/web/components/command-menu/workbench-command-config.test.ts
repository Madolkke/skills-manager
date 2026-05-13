import { describe, expect, it, vi } from "vitest";

import { buildWorkbenchCommands } from "./workbench-command-config";

function createCommands(overrides: Partial<Parameters<typeof buildWorkbenchCommands>[0]> = {}) {
  const onAction = vi.fn();
  const onOpenDiff = vi.fn();
  const onSetMode = vi.fn();
  const commands = buildWorkbenchCommands({
    canCompareVersions: true,
    casesCount: 2,
    hasPersistedSkill: true,
    onAction,
    onOpenDiff,
    onSetMode,
    ...overrides,
  });
  return { commands, onAction, onOpenDiff, onSetMode };
}

describe("buildWorkbenchCommands", () => {
  it("preserves command order, labels, groups, and shortcuts", () => {
    const { commands } = createCommands();

    expect(commands).toHaveLength(14);
    expect(commands.map((command) => command.id)).toEqual([
      "nav-overview",
      "nav-variants",
      "nav-evals",
      "nav-history",
      "nav-audit",
      "nav-diff",
      "import-skill",
      "new-skill",
      "new-variant",
      "new-version",
      "new-case",
      "batch-case",
      "record-run",
      "compare-version",
    ]);
    expect(commands.find((command) => command.id === "new-version")).toMatchObject({
      title: "追加版本",
      group: "创建",
      shortcut: "A",
    });
    expect(commands.find((command) => command.id === "compare-version")).toMatchObject({
      group: "证据",
      detail: "打开 bundle 文件级 diff。",
    });
  });

  it("disables skill-scoped commands before a skill exists and keeps creation entry points available", () => {
    const { commands } = createCommands({
      canCompareVersions: false,
      casesCount: 0,
      hasPersistedSkill: false,
    });

    expect(commands.find((command) => command.id === "import-skill")).toMatchObject({ disabled: false });
    expect(commands.find((command) => command.id === "new-skill")).toMatchObject({ disabled: false });
    expect(commands.find((command) => command.id === "nav-variants")).toMatchObject({
      disabled: true,
      disabledReason: "先创建或导入一个 skill。",
    });
    expect(commands.find((command) => command.id === "record-run")).toMatchObject({
      disabled: true,
      disabledReason: "当前测试集还没有 case。",
    });
    expect(commands.find((command) => command.id === "compare-version")).toMatchObject({
      disabled: true,
      disabledReason: "当前 variant 至少需要两个版本。",
    });
  });

  it("dispatches command callbacks without hiding command intent inside the workbench", () => {
    const { commands, onAction, onOpenDiff, onSetMode } = createCommands();

    commands.find((command) => command.id === "nav-evals")?.run();
    commands.find((command) => command.id === "new-case")?.run();
    commands.find((command) => command.id === "compare-version")?.run();

    expect(onSetMode).toHaveBeenCalledWith("evals");
    expect(onAction).toHaveBeenCalledWith("new-case");
    expect(onOpenDiff).toHaveBeenCalledTimes(1);
  });
});
