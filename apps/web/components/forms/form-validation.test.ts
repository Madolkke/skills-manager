import { describe, expect, it } from "vitest";

import { requiredFieldMessage } from "./form-validation-copy";

describe("requiredFieldMessage", () => {
  it("uses an action-oriented copy for text fields", () => {
    expect(requiredFieldMessage("Skill ID", "text")).toBe("填写 Skill ID");
  });

  it("uses selection copy for file fields", () => {
    expect(requiredFieldMessage("Skill 文件夹", "file")).toBe("选择 Skill 文件夹");
  });

  it("uses confirmation copy for checkbox fields", () => {
    expect(requiredFieldMessage("确认风险", "checkbox")).toBe("确认 确认风险");
  });
});
