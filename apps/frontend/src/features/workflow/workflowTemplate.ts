import { scanWorkflowExpressionBoundary } from "./workflowExpressionLexing";

export type WorkflowTemplateDiagnostic = { code: string; message: string; start: number; end: number; severity?: "error" | "warning" };
export type WorkflowTemplateExpression = { expression: string; start: number; end: number };
type TemplateBlock = WorkflowTemplateExpression & { closed: boolean };

/** 使用相同词法边界生成模板诊断、表达式与补全范围。 */
function parseTemplate(source: string): { diagnostics: WorkflowTemplateDiagnostic[]; blocks: TemplateBlock[] } {
  const diagnostics: WorkflowTemplateDiagnostic[] = [];
  const blocks: TemplateBlock[] = [];
  let cursor = 0;
  while (cursor < source.length) {
    if (source.startsWith("}}", cursor)) {
      diagnostics.push({ code: "TEMPLATE_UNEXPECTED_CLOSE", message: "模板出现未匹配的结束标记。", start: cursor, end: cursor + 2, severity: "error" });
      cursor += 2;
      continue;
    }
    if (!source.startsWith("{{", cursor)) { cursor += 1; continue; }
    const start = cursor + 2;
    const closing = scanWorkflowExpressionBoundary(source, start).closing;
    const end = closing ?? source.length;
    const expression = source.slice(start, end);
    blocks.push({ expression, start, end, closed: closing !== null });
    if (closing === null) {
      diagnostics.push({ code: "TEMPLATE_UNCLOSED", message: "模板缺少结束标记“}}”。", start: cursor, end, severity: "error" });
      break;
    }
    if (!expression.trim()) diagnostics.push({ code: "TEMPLATE_EMPTY_EXPRESSION", message: "模板表达式不能为空。", start, end, severity: "error" });
    cursor = end + 2;
  }
  return { diagnostics, blocks };
}

/** 返回模板定界符错误，表达式语法交由表达式校验器处理。 */
export function scanWorkflowTemplate(source: string): WorkflowTemplateDiagnostic[] {
  return parseTemplate(source).diagnostics;
}

/** 提取完整模板块，保留 JavaScript UTF16 偏移。 */
export function workflowTemplateExpressions(source: string): WorkflowTemplateExpression[] {
  return parseTemplate(source).blocks.filter((block) => block.closed).map(({ expression, start, end }) => ({ expression, start, end }));
}

/** 找到光标所属的表达式，包括尚未闭合的模板块。 */
export function activeWorkflowTemplateExpression(source: string, cursor: number): WorkflowTemplateExpression | null {
  const block = parseTemplate(source).blocks.find((item) => cursor >= item.start && cursor <= item.end);
  return block ? { expression: source.slice(block.start, cursor), start: block.start, end: cursor } : null;
}
