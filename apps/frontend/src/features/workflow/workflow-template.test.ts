import { describe, expect, it } from "vitest";
import { activeWorkflowTemplateExpression, scanWorkflowTemplate, workflowTemplateExpressions } from "./workflowTemplate";
import { shouldOpenWorkflowTemplateCompletion } from "./workflowExpressionCompletion";

describe("模板词法边界", () => {
  it.each([
    ' "}}" ', " '}}' ", ' {"outer": {"inner": 1}} ',
    ' [({"key": "}}"})] ', ' "escaped\\"}}" ',
    ' """double " quote }}""" ', " '''single ' quote }}''' ",
  ])("字符串和嵌套容器不提前结束：%s", (expression) => {
    const source = `前文 {{${expression}}} 后文`;
    expect(scanWorkflowTemplate(source)).toEqual([]);
    expect(workflowTemplateExpressions(source)).toEqual([{ expression, start: 5, end: 5 + expression.length }]);
  });

  it("报告孤立结束符、空表达式、未闭合模板并保留 UTF16 偏移", () => {
    expect(scanWorkflowTemplate("😀 }} {{}} {{").map(({ code, start }) => [code, start])).toEqual([
      ["TEMPLATE_UNEXPECTED_CLOSE", 3], ["TEMPLATE_EMPTY_EXPRESSION", 8], ["TEMPLATE_UNCLOSED", 11],
    ]);
    expect(scanWorkflowTemplate('{{ "unterminated }}').map((item) => item.code)).toEqual(["TEMPLATE_UNCLOSED"]);
  });

  it("补全使用扫描边界而非字符串中的模板标记", () => {
    const expression = ' "}} {{" + inputs.na';
    const source = `{{${expression}}}`;
    expect(activeWorkflowTemplateExpression(source, source.length - 2)).toEqual({ expression, start: 2, end: source.length - 2 });
    expect(activeWorkflowTemplateExpression(source, source.length)).toBeNull();
    expect(activeWorkflowTemplateExpression(source, 1)).toBeNull();
    const variables = [{ id: "name", reference: "inputs.name", kind: "global" as const, name: "名称", dataType: "string", source: "输入", aliases: [] }];
    expect(shouldOpenWorkflowTemplateCompletion(variables, source, source.length - 2)).toBe(true);
    const quoted = '{{ """an embedded " inputs.na';
    expect(shouldOpenWorkflowTemplateCompletion(variables, quoted, quoted.length)).toBe(false);
  });
});
