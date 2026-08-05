import { describe, expect, it } from "vitest";
import { parseConfigPattern, removeConfigCapture, syncConfigCaptures } from "./domain/configPattern";

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

  it("keeps the backend delimiter rules for regex groups and escaped backslashes", () => {
    expect(parseConfigPattern("value <text:[^>]+>").names).toEqual(["text"]);
    expect(parseConfigPattern("value <text:(?P<inner>[^ ]+)>").names).toEqual(["text"]);
    expect(parseConfigPattern("value \\\\<name>").names).toEqual(["name"]);
  });

  it("preserves capture schemas while a pattern is temporarily invalid", () => {
    const original = { name: { type: "integer" as const, title: "接口", description: "接口名" } };
    expect(syncConfigCaptures("interface <name", original)).toEqual(original);
  });

  it("removes a capture token without confusing nested angle brackets", () => {
    expect(removeConfigCapture("interface <name> <value:(?P<inner>[^>]+)>", "value")).toBe("interface <name>");
  });

  it("validates empty and malformed regex expressions", () => {
    expect(parseConfigPattern("x <name:>").error).toContain("正则不能为空");
    expect(parseConfigPattern("x <name:(a{2,1})>").error).toContain("正则无效");
    expect(parseConfigPattern("x <name:(?P<inner>[^>]+)>").names).toEqual(["name"]);
  });
});
