import type { CommandMenuItem, CommandMenuPreview } from "@/components/command-menu/command-menu-types";
import type { InspectorActionMode } from "@/components/inspector/workbench-inspector";
import type { WorkbenchMode } from "@/components/workbench-tabs";

export type WorkbenchCommandSelection = {
  selectedCase?: { id: string; title: string } | null;
  selectedRun?: { id: string; label: string; scoreLabel?: string } | null;
};

export type WorkbenchCommandOptions = {
  canCompareVersions: boolean;
  casesCount: number;
  currentMode: WorkbenchMode;
  hasPersistedSkill: boolean;
  onAction: (mode: InspectorActionMode) => void;
  onChooseComparisonRun?: (role: "baseline" | "candidate", runId: string) => void;
  onHistoryCase?: (caseId: string) => void;
  onOpenDiff: () => void;
  onSetMode: (mode: WorkbenchMode) => void;
  selection?: WorkbenchCommandSelection;
};

export function buildWorkbenchCommands({
  canCompareVersions,
  casesCount,
  currentMode,
  hasPersistedSkill,
  onAction,
  onChooseComparisonRun,
  onHistoryCase,
  onOpenDiff,
  onSetMode,
  selection,
}: WorkbenchCommandOptions): CommandMenuItem[] {
  const canUseSkill = hasPersistedSkill;
  const commands: CommandMenuItem[] = [
    ...selectionCommands({ canUseSkill, onChooseComparisonRun, onHistoryCase, selection }),
    command("nav-overview", "打开概览", "导航", "查看 skill 说明、当前验证和 bundle 文件。", () => onSetMode("overview"), "G O"),
    command("nav-variants", "打开变体", "导航", "查看 variant map 和历史版本。", () => onSetMode("variants"), "G V", !canUseSkill, "先创建或导入一个 skill。"),
    command("nav-evals", "打开测评", "导航", "管理测试用例并记录手工测评。", () => onSetMode("evals"), "G E", !canUseSkill, "先创建或导入一个 skill。"),
    command("nav-history", "打开历史", "导航", "查看 run history、比较 run 和 accepted verification。", () => onSetMode("history"), "G H", !canUseSkill, "先创建或导入一个 skill。"),
    command("nav-audit", "打开审计", "导航", "过滤当前 skill 的治理和发布事件。", () => onSetMode("audit"), "G A", !canUseSkill, "先创建或导入一个 skill。"),
    command("nav-diff", "打开差异", "导航", "比较当前 variant 的两个 bundle version。", onOpenDiff, "G D", !canCompareVersions, "当前 variant 至少需要两个版本。"),
    command("import-skill", "导入标准 Skill bundle", "创建", "上传包含 SKILL.md 的文件夹或 zip。", () => onAction("import-skill"), "I"),
    command("new-skill", "新建 skill", "创建", "创建一个空白 skill 和默认 variant。", () => onAction("new-skill"), "N"),
    command("new-variant", "新建 variant", "创建", "为当前 skill 新增一组 tag 约束下的最优解。", () => onAction("new-variant"), "V", !canUseSkill, "先创建或导入一个 skill。"),
    command("new-version", "追加版本", "创建", "上传新的标准 skill bundle，形成不可变 VariantVersion。", () => onAction("new-version"), "A", !canUseSkill, "先创建或导入一个 skill。"),
    command("new-case", "添加 case", "测评", "新增测试用例并生成新的 EvalSetVersion。", () => onAction("new-case"), "C", !canUseSkill, "先创建或导入一个 skill。"),
    command("batch-case", "批量添加 case", "测评", "打开测评页的快速批量粘贴入口。", () => onSetMode("evals"), "B", !canUseSkill, "先创建或导入一个 skill。"),
    command("record-run", "记录本次测评", "测评", "进入 pass/fail 手工测评确认区。", () => onAction("run"), "R", !canUseSkill || casesCount === 0, casesCount === 0 ? "当前测试集还没有 case。" : "先创建或导入一个 skill。"),
    command("compare-version", "比较版本", "证据", "打开 bundle 文件级 diff。", onOpenDiff, "D", !canCompareVersions, "当前 variant 至少需要两个版本。"),
  ];
  return prioritizeCommands(commands, { currentMode, hasPersistedSkill });
}

const modePriorities: Record<WorkbenchMode, string[]> = {
  audit: ["nav-audit", "nav-history", "nav-overview", "new-case"],
  diff: ["compare-version", "nav-diff", "new-version", "nav-variants", "nav-evals"],
  evals: ["selected-case-history", "record-run", "new-case", "batch-case", "nav-history"],
  history: ["selected-run-baseline", "selected-run-candidate", "nav-history", "compare-version", "record-run", "nav-evals"],
  overview: ["nav-overview", "import-skill", "new-skill", "nav-evals"],
  promotion: ["compare-version", "nav-diff", "record-run", "nav-evals", "nav-variants"],
  variants: ["new-variant", "new-version", "compare-version", "nav-evals"],
};

function selectionCommands({
  canUseSkill,
  onChooseComparisonRun,
  onHistoryCase,
  selection,
}: {
  canUseSkill: boolean;
  onChooseComparisonRun?: (role: "baseline" | "candidate", runId: string) => void;
  onHistoryCase?: (caseId: string) => void;
  selection?: WorkbenchCommandSelection;
}) {
  const commands: CommandMenuItem[] = [];
  const selectedCase = selection?.selectedCase ?? null;
  if (canUseSkill && selectedCase) {
    commands.push(
      command(
        "selected-case-history",
        "查看当前 case 历史",
        "当前选择",
        "打开当前测试用例的版本时间线。",
        () => onHistoryCase?.(selectedCase.id),
        "H C",
        !onHistoryCase,
        "当前工作区暂不能打开 case 历史。",
        {
          body: "查看这个测试用例的历史版本，确认 input、expected output 和 notes 的变更来源。",
          facts: [
            { label: "对象", value: selectedCase.title },
            { label: "Case ID", value: selectedCase.id },
          ],
        },
      ),
    );
  }

  const selectedRun = selection?.selectedRun ?? null;
  if (canUseSkill && selectedRun) {
    const previewFacts = [
      { label: "对象", value: selectedRun.label },
      { label: "Run ID", value: selectedRun.id },
    ];
    if (selectedRun.scoreLabel) previewFacts.unshift({ label: "结果", value: selectedRun.scoreLabel });
    commands.push(
      command(
        "selected-run-baseline",
        "设为对照 run",
        "当前选择",
        "把当前 run 填入 run comparison 的 baseline。",
        () => onChooseComparisonRun?.("baseline", selectedRun.id),
        "B",
        !onChooseComparisonRun,
        "当前工作区暂不能选择 comparison run。",
        {
          body: "把当前 run 作为对照基线，用来判断候选 run 是否修复或回退。",
          facts: previewFacts,
        },
      ),
      command(
        "selected-run-candidate",
        "设为候选 run",
        "当前选择",
        "把当前 run 填入 run comparison 的 candidate。",
        () => onChooseComparisonRun?.("candidate", selectedRun.id),
        "K",
        !onChooseComparisonRun,
        "当前工作区暂不能选择 comparison run。",
        {
          body: "把当前 run 作为候选结果，与 baseline 比较通过率和逐 case 变化。",
          facts: previewFacts,
        },
      ),
    );
  }

  return commands;
}

function prioritizeCommands(
  commands: CommandMenuItem[],
  options: { currentMode: WorkbenchMode; hasPersistedSkill: boolean },
) {
  const priorityIds = options.hasPersistedSkill
    ? modePriorities[options.currentMode]
    : ["import-skill", "new-skill", "nav-overview"];
  const priorityRank = new Map(priorityIds.map((id, index) => [id, index]));
  return commands
    .map((command, index) => ({ command, index }))
    .sort((left, right) => {
      const leftRank = priorityRank.get(left.command.id) ?? Number.POSITIVE_INFINITY;
      const rightRank = priorityRank.get(right.command.id) ?? Number.POSITIVE_INFINITY;
      if (leftRank !== rightRank) return leftRank - rightRank;
      return left.index - right.index;
    })
    .map(({ command }) => command);
}

function command(
  id: string,
  title: string,
  group: string,
  detail: string,
  run: () => void,
  shortcut?: string,
  disabled = false,
  disabledReason = "",
  preview?: CommandMenuPreview,
): CommandMenuItem {
  return {
    id,
    title,
    group,
    detail,
    run,
    shortcut,
    disabled,
    disabledReason,
    preview,
  };
}
