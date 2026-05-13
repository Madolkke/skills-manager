"use client";

import { KeyboardEvent } from "react";

export type WorkbenchMode = "overview" | "variants" | "evals" | "diff" | "history" | "audit" | "promotion";

export type WorkbenchTabItem = {
  label: string;
  mode: WorkbenchMode;
  onActivate?: () => void;
};

export function workbenchTabId(mode: WorkbenchMode) {
  return `workbench-tab-${mode}`;
}

export function workbenchPanelId(mode: WorkbenchMode) {
  return `workbench-panel-${mode}`;
}

export function WorkbenchTabs({
  mode,
  onModeChange,
  tabs,
}: {
  mode: WorkbenchMode;
  onModeChange: (mode: WorkbenchMode) => void;
  tabs: WorkbenchTabItem[];
}) {
  function activate(tab: WorkbenchTabItem) {
    if (tab.onActivate) tab.onActivate();
    else onModeChange(tab.mode);
    window.requestAnimationFrame(() => {
      document.getElementById(workbenchTabId(tab.mode))?.focus();
    });
  }

  function moveFocus(event: KeyboardEvent<HTMLButtonElement>, targetIndex: number) {
    event.preventDefault();
    const index = (targetIndex + tabs.length) % tabs.length;
    activate(tabs[index]);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key === "ArrowRight") moveFocus(event, index + 1);
    if (event.key === "ArrowLeft") moveFocus(event, index - 1);
    if (event.key === "Home") moveFocus(event, 0);
    if (event.key === "End") moveFocus(event, tabs.length - 1);
  }

  return (
    <div aria-label="Workbench modes" className="linearTabs" role="tablist">
      {tabs.map((tab, index) => {
        const isActive = tab.mode === mode;
        return (
          <button
            aria-controls={workbenchPanelId(tab.mode)}
            aria-selected={isActive}
            className={isActive ? "linearTabActive" : ""}
            id={workbenchTabId(tab.mode)}
            key={tab.mode}
            onClick={() => activate(tab)}
            onKeyDown={(event) => handleKeyDown(event, index)}
            role="tab"
            tabIndex={isActive ? 0 : -1}
            type="button"
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
