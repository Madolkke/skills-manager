import { describe, expect, it } from "vitest";
import { parseConfigPattern, syncConfigCaptures } from "./domain/configPattern";

describe("config collection pattern", () => {
  it("extracts captures and preserves schemas", () => {
    const captures = syncConfigCaptures("interface <name> <address:\\S+>", { name: { type: "integer", title: "名称", description: "" } });
    expect(Object.keys(captures)).toEqual(["name", "address"]);
    expect(captures.name?.type).toBe("integer");
    expect(captures.address?.type).toBe("string");
  });

  it("rejects duplicate names and multiline patterns", () => {
    expect(parseConfigPattern("x <name> <name>").error).toContain("重复");
    expect(parseConfigPattern("x\ny").error).toContain("单行");
  });
});
