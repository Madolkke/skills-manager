export type WorkflowTemplateDiagnostic = { code: string; message: string; start: number; end: number; severity?: "error" | "warning" };

export type WorkflowTemplateExpression = { expression: string; start: number; end: number };

export function scanWorkflowTemplate(source: string): WorkflowTemplateDiagnostic[] {
  const diagnostics: WorkflowTemplateDiagnostic[] = [];
  let cursor = 0;
  while (cursor < source.length) {
    const opening = source.indexOf("{{", cursor);
    const closing = source.indexOf("}}", cursor);
    if (closing >= 0 && (opening < 0 || closing < opening)) {
      diagnostics.push({ code: "TEMPLATE_UNEXPECTED_CLOSE", message: "模板出现未匹配的结束标记。", start: closing, end: closing + 2, severity: "error" });
      cursor = closing + 2;
      continue;
    }
    if (opening < 0) break;
    const end = source.indexOf("}}", opening + 2);
    if (end < 0) {
      diagnostics.push({ code: "TEMPLATE_UNCLOSED", message: "模板缺少结束标记“}}”。", start: opening, end: source.length, severity: "error" });
      if (!source.slice(opening + 2).trim()) diagnostics.push({ code: "TEMPLATE_EMPTY_EXPRESSION", message: "模板表达式不能为空。", start: opening + 2, end: source.length, severity: "error" });
      break;
    }
    if (!source.slice(opening + 2, end).trim()) diagnostics.push({ code: "TEMPLATE_EMPTY_EXPRESSION", message: "模板表达式不能为空。", start: opening + 2, end, severity: "error" });
    cursor = end + 2;
  }
  return diagnostics;
}

export function workflowTemplateExpressions(source: string): WorkflowTemplateExpression[] {
  const values: WorkflowTemplateExpression[] = [];
  let cursor = 0;
  while (cursor < source.length) {
    const opening = source.indexOf("{{", cursor);
    if (opening < 0) break;
    const end = source.indexOf("}}", opening + 2);
    if (end < 0) break;
    values.push({ expression: source.slice(opening + 2, end), start: opening + 2, end });
    cursor = end + 2;
  }
  return values;
}

export function activeWorkflowTemplateExpression(source: string, cursor: number): WorkflowTemplateExpression | null {
  const opening = source.lastIndexOf("{{", cursor);
  if (opening < 0 || source.lastIndexOf("}}", cursor) > opening) return null;
  const closing = source.indexOf("}}", opening + 2);
  if (closing >= 0 && closing < cursor) return null;
  return { expression: source.slice(opening + 2, cursor), start: opening + 2, end: cursor };
}
