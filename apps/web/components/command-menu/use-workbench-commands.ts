"use client";

import { useMemo } from "react";

import type { CommandMenuItem } from "@/components/command-menu/command-menu";
import type { InspectorActionMode } from "@/components/inspector/workbench-inspector";
import type { WorkbenchMode } from "@/components/workbench-tabs";

type WorkbenchCommandOptions = {
  canCompareVersions: boolean;
  casesCount: number;
  hasPersistedSkill: boolean;
  onAction: (mode: InspectorActionMode) => void;
  onOpenDiff: () => void;
  onSetMode: (mode: WorkbenchMode) => void;
};

export function useWorkbenchCommands({
  canCompareVersions,
  casesCount,
  hasPersistedSkill,
  onAction,
  onOpenDiff,
  onSetMode,
}: WorkbenchCommandOptions) {
  return useMemo<CommandMenuItem[]>(() => {
    const canUseSkill = hasPersistedSkill;
    return [
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
  }, [canCompareVersions, casesCount, hasPersistedSkill, onAction, onOpenDiff, onSetMode]);
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
  };
}
