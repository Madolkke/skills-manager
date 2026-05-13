import { describe, expect, it, vi } from "vitest";

import { buildWorkbenchCommands } from "./workbench-command-config";

type CommandTestOverrides = Partial<Parameters<typeof buildWorkbenchCommands>[0]> & {
  onChooseComparisonRun?: ReturnType<typeof vi.fn>;
  onHistoryCase?: ReturnType<typeof vi.fn>;
  selection?: {
    selectedCase?: { id: string; title: string } | null;
    selectedRun?: { id: string; label: string; scoreLabel?: string } | null;
  };
};

function createCommands(overrides: CommandTestOverrides = {}) {
  const onAction = vi.fn();
  const onChooseComparisonRun = vi.fn();
  const onHistoryCase = vi.fn();
  const onOpenDiff = vi.fn();
  const onSetMode = vi.fn();
  const commands = buildWorkbenchCommands({
    canCompareVersions: true,
    casesCount: 2,
    currentMode: "overview",
    hasPersistedSkill: true,
    onAction,
    onChooseComparisonRun,
    onHistoryCase,
    onOpenDiff,
    onSetMode,
    ...overrides,
  } as Parameters<typeof buildWorkbenchCommands>[0]);
  return { commands, onAction, onChooseComparisonRun, onHistoryCase, onOpenDiff, onSetMode };
}

describe("buildWorkbenchCommands", () => {
  it("preserves command catalog labels, groups, shortcuts, and overview priority", () => {
    const { commands } = createCommands();

    expect(commands).toHaveLength(14);
    expect(commands.map((command) => command.id)).toEqual([
      "nav-overview",
      "import-skill",
      "new-skill",
      "nav-evals",
      "nav-variants",
      "nav-history",
      "nav-audit",
      "nav-diff",
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

  it("prioritizes eval actions when the current mode is evals", () => {
    const { commands } = createCommands({ currentMode: "evals" });

    expect(commands.slice(0, 4).map((command) => command.id)).toEqual([
      "record-run",
      "new-case",
      "batch-case",
      "nav-history",
    ]);
  });

  it("prioritizes variant maintenance when the current mode is variants", () => {
    const { commands } = createCommands({ currentMode: "variants" });

    expect(commands.slice(0, 4).map((command) => command.id)).toEqual([
      "new-variant",
      "new-version",
      "compare-version",
      "nav-evals",
    ]);
  });

  it("prioritizes creation entry points before a skill exists", () => {
    const { commands } = createCommands({
      canCompareVersions: false,
      casesCount: 0,
      currentMode: "overview",
      hasPersistedSkill: false,
    });

    expect(commands.slice(0, 3).map((command) => command.id)).toEqual([
      "import-skill",
      "new-skill",
      "nav-overview",
    ]);
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

  it("adds a selected case command that opens the case history", () => {
    const { commands, onHistoryCase } = createCommands({
      currentMode: "evals",
      selection: {
        selectedCase: { id: "case-123", title: "PR: missing owner filter" },
      },
    });

    const historyCommand = commands.find((command) => command.id === "selected-case-history");

    expect(commands.slice(0, 4).map((command) => command.id)).toContain("selected-case-history");
    expect(historyCommand).toMatchObject({
      title: "查看当前 case 历史",
      group: "当前选择",
      preview: {
        facts: expect.arrayContaining([{ label: "对象", value: "PR: missing owner filter" }]),
      },
    });

    historyCommand?.run();
    expect(onHistoryCase).toHaveBeenCalledWith("case-123");
  });

  it("adds selected run commands for run comparison setup", () => {
    const { commands, onChooseComparisonRun } = createCommands({
      currentMode: "history",
      selection: {
        selectedRun: { id: "run-456", label: "Strict reviewer v2", scoreLabel: "3/4 passed" },
      },
    });

    const baselineCommand = commands.find((command) => command.id === "selected-run-baseline");
    const candidateCommand = commands.find((command) => command.id === "selected-run-candidate");

    expect(commands.slice(0, 4).map((command) => command.id)).toEqual([
      "selected-run-baseline",
      "selected-run-candidate",
      "nav-history",
      "compare-version",
    ]);
    expect(baselineCommand).toMatchObject({
      title: "设为对照 run",
      preview: {
        facts: expect.arrayContaining([{ label: "对象", value: "Strict reviewer v2" }]),
      },
    });

    baselineCommand?.run();
    candidateCommand?.run();

    expect(onChooseComparisonRun).toHaveBeenCalledWith("baseline", "run-456");
    expect(onChooseComparisonRun).toHaveBeenCalledWith("candidate", "run-456");
  });
});
