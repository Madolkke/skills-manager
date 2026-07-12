import {
  acceptCompletion,
  type Completion,
  type CompletionContext,
  type CompletionSection,
  type CompletionSource,
  completionStatus,
} from "@codemirror/autocomplete";
import type { EditorView } from "@codemirror/view";
import type { WorkflowExpressionVariable, WorkflowExpressionVariableKind } from "./workflowExpressionVariables";
import { filterWorkflowExpressionVariables } from "./workflowExpressionVariables";

const sections: Record<WorkflowExpressionVariableKind, CompletionSection> = {
  global: { name: "全局输入", rank: 0 },
  step: { name: "当前步骤输入", rank: 1 },
  output: { name: "采集输出", rank: 2 },
};
const fragmentPattern = /[^\s()[\]{}"'`,;:+*/%&|!?=<>]+$/u;

export function normalizeWorkflowExpressionInput(value: string): string {
  return value.replace(/\r\n?|\n/g, " ");
}

export function acceptWorkflowExpressionCompletion(view: EditorView): boolean {
  return completionStatus(view.state) === "active" && acceptCompletion(view);
}

export function shouldOpenWorkflowExpressionCompletion(
  variables: WorkflowExpressionVariable[],
  valueBeforeCursor: string,
): boolean {
  if (insideQuotedLiteral(valueBeforeCursor)) return false;
  const fragment = valueBeforeCursor.match(fragmentPattern)?.[0] ?? "";
  return Boolean(fragment && filterWorkflowExpressionVariables(variables, fragment).length);
}

export function createWorkflowExpressionCompletionSource(
  variables: () => WorkflowExpressionVariable[],
): CompletionSource {
  return (context: CompletionContext) => {
    if (context.state.readOnly) return null;
    if (insideQuotedLiteral(context.state.doc.sliceString(0, context.pos))) return null;
    const token = context.matchBefore(fragmentPattern);
    if (!context.explicit && (!token || !token.text)) return null;
    const fragment = token?.text ?? "";
    const matches = filterWorkflowExpressionVariables(variables(), fragment);
    if (!matches.length) return null;
    return {
      from: token?.from ?? context.pos,
      options: matches.map(toCompletion),
      filter: false,
    };
  };
}

function toCompletion(variable: WorkflowExpressionVariable): Completion {
  return {
    label: variable.reference,
    apply: variable.reference,
    detail: `${variable.dataType} · ${variable.source}`,
    info: variable.name,
    type: variable.kind === "output" ? "property" : "variable",
    section: sections[variable.kind],
  };
}

function insideQuotedLiteral(value: string): boolean {
  let quote = "";
  let escaped = false;
  for (const character of value) {
    if (escaped) {
      escaped = false;
      continue;
    }
    if (character === "\\") {
      escaped = true;
      continue;
    }
    if (quote) {
      if (character === quote) quote = "";
    } else if (character === "\"" || character === "'" || character === "`") {
      quote = character;
    }
  }
  return Boolean(quote);
}
