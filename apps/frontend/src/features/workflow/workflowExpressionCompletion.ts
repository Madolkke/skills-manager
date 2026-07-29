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
import { expandWorkflowExpressionVariable, filterWorkflowExpressionVariables } from "./workflowExpressionVariables";

const sections: Record<WorkflowExpressionVariableKind, CompletionSection> = {
  global: { name: "全局输入", rank: 0 },
  output: { name: "采集输出", rank: 1 },
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
  const query = completionQuery(variables, valueBeforeCursor);
  return Boolean(query?.fragment && query.matches.length);
}

export function createWorkflowExpressionCompletionSource(
  variables: () => WorkflowExpressionVariable[],
): CompletionSource {
  return (context: CompletionContext) => {
    if (context.state.readOnly) return null;
    const beforeCursor = context.state.doc.sliceString(0, context.pos);
    if (insideQuotedLiteral(beforeCursor)) return null;
    const query = completionQuery(variables(), beforeCursor);
    if (!query) return null;
    if (!context.explicit && !query.fragment) return null;
    if (!query.matches.length) return null;
    return {
      from: query.from,
      options: query.matches.map(toCompletion),
      filter: false,
    };
  };
}

type CompletionQuery = { from: number; fragment: string; matches: WorkflowExpressionVariable[] };

function completionQuery(variables: WorkflowExpressionVariable[], beforeCursor: string): CompletionQuery | null {
  const indexed = indexedSampleQuery(variables, beforeCursor);
  if (indexed) return indexed;
  if (hasUnclosedSampleIndex(variables, beforeCursor)) return null;
  const fragment = beforeCursor.match(fragmentPattern)?.[0] ?? "";
  return {
    from: beforeCursor.length - fragment.length,
    fragment,
    matches: filterWorkflowExpressionVariables(variables, fragment),
  };
}

function indexedSampleQuery(variables: WorkflowExpressionVariable[], beforeCursor: string): CompletionQuery | null {
  for (const variable of variables.filter((item) => (item.sampleCount ?? 1) > 1)) {
    const from = beforeCursor.lastIndexOf(variable.reference);
    if (from < 0 || !isReferenceBoundary(beforeCursor, from)) continue;
    const bracketStart = from + variable.reference.length;
    if (beforeCursor[bracketStart] !== "[") continue;
    const bracketEnd = matchingBracket(beforeCursor, bracketStart);
    if (bracketEnd < 0 || bracketEnd >= beforeCursor.length) continue;
    const suffix = beforeCursor.slice(bracketEnd + 1);
    if (suffix && !/^(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[^\]]*\])*(?:\.)?$/u.test(suffix)) continue;
    const sampleReference = beforeCursor.slice(from, bracketEnd + 1);
    const fragment = beforeCursor.slice(from);
    const matches = filterWorkflowExpressionVariables(
      expandWorkflowExpressionVariable(variable, sampleReference),
      fragment,
    );
    return { from, fragment, matches };
  }
  return null;
}

function hasUnclosedSampleIndex(variables: WorkflowExpressionVariable[], beforeCursor: string): boolean {
  return variables.some((variable) => {
    if ((variable.sampleCount ?? 1) <= 1) return false;
    const from = beforeCursor.lastIndexOf(variable.reference);
    if (from < 0 || !isReferenceBoundary(beforeCursor, from)) return false;
    const bracketStart = from + variable.reference.length;
    return beforeCursor[bracketStart] === "[" && matchingBracket(beforeCursor, bracketStart) < 0;
  });
}

function matchingBracket(source: string, start: number): number {
  let depth = 0;
  let quote = "";
  let escaped = false;
  for (let index = start; index < source.length; index += 1) {
    const character = source[index]!;
    if (escaped) {
      escaped = false;
    } else if (character === "\\") {
      escaped = true;
    } else if (quote) {
      if (character === quote) quote = "";
    } else if (character === "\"" || character === "'") {
      quote = character;
    } else if (character === "[") {
      depth += 1;
    } else if (character === "]" && --depth === 0) {
      return index;
    }
  }
  return -1;
}

function isReferenceBoundary(source: string, start: number): boolean {
  return start === 0 || !/[A-Za-z0-9_.]/u.test(source[start - 1]!);
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
