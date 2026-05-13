import { describe, expect, it } from "vitest";

import { rankCommandsForMenu, rememberRecentCommandId } from "./command-menu-recents";
import type { CommandMenuItem } from "./command-menu-types";

function item(id: string, disabled = false): CommandMenuItem {
  return {
    id,
    title: id,
    group: "测试",
    detail: `${id} detail`,
    disabled,
    run: () => undefined,
  };
}

describe("command menu recents", () => {
  it("remembers recent command ids with newest first, dedupe, and limit", () => {
    expect(rememberRecentCommandId(["record-run", "new-case"], "new-case")).toEqual(["new-case", "record-run"]);
    expect(rememberRecentCommandId(["a", "b", "c", "d", "e"], "f")).toEqual(["f", "a", "b", "c", "d"]);
  });

  it("ranks recent commands first for empty queries while keeping disabled commands last", () => {
    const ranked = rankCommandsForMenu(
      [item("record-run"), item("new-case"), item("compare-version", true), item("nav-history")],
      { query: "", recentCommandIds: ["nav-history", "compare-version"] },
    );

    expect(ranked.map((command) => command.id)).toEqual([
      "nav-history",
      "record-run",
      "new-case",
      "compare-version",
    ]);
  });

  it("filters by query before ranking recents", () => {
    const ranked = rankCommandsForMenu([item("record-run"), item("new-case"), item("nav-history")], {
      query: "case",
      recentCommandIds: ["nav-history"],
    });

    expect(ranked.map((command) => command.id)).toEqual(["new-case"]);
  });
});
