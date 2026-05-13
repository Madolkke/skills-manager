"use client";

import { useMemo } from "react";

import { buildWorkbenchCommands, type WorkbenchCommandOptions } from "@/components/command-menu/workbench-command-config";

export function useWorkbenchCommands({
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
}: WorkbenchCommandOptions) {
  return useMemo(
    () => buildWorkbenchCommands({
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
    }),
    [
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
    ],
  );
}
