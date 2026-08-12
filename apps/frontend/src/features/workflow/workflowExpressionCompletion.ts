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
  config: { name: "配置匹配", rank: 2 },
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
type IndexedArrayQuery = CompletionQuery | "blocked" | null;
type SampleIndexAnalysis = { end: number; slice: boolean; supported: boolean };
type ArrayReferenceMatch = { start: number; end: number };

function completionQuery(variables: WorkflowExpressionVariable[], beforeCursor: string): CompletionQuery | null {
  const indexed = indexedSampleQuery(variables, beforeCursor);
  if (indexed === "blocked") return null;
  if (indexed) return indexed;
  if (hasUnclosedSampleIndex(variables, beforeCursor)) return null;
  const fragment = beforeCursor.match(fragmentPattern)?.[0] ?? "";
  return {
    from: beforeCursor.length - fragment.length,
    fragment,
    matches: filterWorkflowExpressionVariables(variables, fragment),
  };
}

function indexedSampleQuery(variables: WorkflowExpressionVariable[], beforeCursor: string): IndexedArrayQuery {
  let blocked = false;
  const availableVariables = expandedArrayVariables(variables, beforeCursor);
  const indexable = availableVariables
    .filter((item) => item.indexable || (item.sampleCount ?? 1) > 1)
    .sort((left, right) => right.reference.length - left.reference.length);
  for (const variable of indexable) {
    const match = findArrayReferenceMatch(beforeCursor, variable.reference);
    if (!match || beforeCursor[match.end] !== "[") continue;
    const index = analyzeSampleIndex(beforeCursor, match.end);
    if (!index) {
      blocked = true;
      continue;
    }
    const suffix = beforeCursor.slice(index.end + 1);
    if (!index.supported || index.slice || (suffix && !/^(?:\.[A-Za-z_][A-Za-z0-9_]*)*\.?$/u.test(suffix))) {
      blocked = true;
      continue;
    }
    const indexedReference = beforeCursor.slice(match.start, index.end + 1);
    const childCandidates = (variable.sampleCount ?? 1) > 1
      ? expandWorkflowExpressionVariable(variable, indexedReference)
      : indexedSchemaVariables(availableVariables, variable, indexedReference);
    const matches = filterIndexedVariables(childCandidates, indexedReference, suffix);
    return { from: match.start, fragment: beforeCursor.slice(match.start), matches };
  }
  return blocked ? "blocked" : null;
}

function hasUnclosedSampleIndex(variables: WorkflowExpressionVariable[], beforeCursor: string): boolean {
  return expandedArrayVariables(variables, beforeCursor)
    .filter((item) => item.indexable || (item.sampleCount ?? 1) > 1)
    .some((variable) => {
      const match = findArrayReferenceMatch(beforeCursor, variable.reference);
      return Boolean(match && beforeCursor[match.end] === "[" && analyzeSampleIndex(beforeCursor, match.end) === null);
    });
}

function expandedArrayVariables(variables: WorkflowExpressionVariable[], beforeCursor: string): WorkflowExpressionVariable[] {
  return variables.flatMap((variable) => {
    if ((variable.sampleCount ?? 1) <= 1) return [variable];
    const match = findArrayReferenceMatch(beforeCursor, variable.reference);
    if (!match || beforeCursor[match.end] !== "[") return [variable];
    const index = analyzeSampleIndex(beforeCursor, match.end);
    if (!index || !index.supported || index.slice) return [variable];
    const indexedReference = beforeCursor.slice(match.start, index.end + 1);
    return [variable, ...expandWorkflowExpressionVariable(variable, indexedReference)];
  });
}

function indexedSchemaVariables(
  variables: WorkflowExpressionVariable[],
  variable: WorkflowExpressionVariable,
  indexedReference: string,
): WorkflowExpressionVariable[] {
  const templatePrefix = `${variable.reference}[0]`;
  return variables
    .filter((candidate) => candidate.reference.startsWith(templatePrefix))
    .map((candidate) => ({ ...candidate, reference: `${indexedReference}${candidate.reference.slice(templatePrefix.length)}` }));
}

function filterIndexedVariables(
  variables: WorkflowExpressionVariable[],
  indexedReference: string,
  suffix: string,
): WorkflowExpressionVariable[] {
  const candidates = suffix === "" || suffix === "."
    ? variables.filter((variable) => /^\.[A-Za-z_][A-Za-z0-9_]*$/u.test(variable.reference.slice(indexedReference.length)))
    : variables;
  return filterWorkflowExpressionVariables(candidates, `${indexedReference}${suffix}`);
}

function findArrayReferenceMatch(source: string, template: string): ArrayReferenceMatch | null {
  const prefix = template.split("[0]")[0] ?? template;
  let start = source.lastIndexOf(prefix);
  while (start >= 0) {
    if (isReferenceBoundary(source, start)) {
      const end = matchReferenceTemplate(source, start, template);
      if (end !== null) return { start, end };
    }
    start = source.lastIndexOf(prefix, start - 1);
  }
  return null;
}

function matchReferenceTemplate(source: string, start: number, template: string): number | null {
  let sourceIndex = start;
  let templateIndex = 0;
  while (templateIndex < template.length) {
    if (template.startsWith("[0]", templateIndex)) {
      if (source[sourceIndex] !== "[") return null;
      const index = analyzeSampleIndex(source, sourceIndex);
      if (!index || !index.supported || index.slice) return null;
      sourceIndex = index.end + 1;
      templateIndex += 3;
      continue;
    }
    if (source[sourceIndex] !== template[templateIndex]) return null;
    sourceIndex += 1;
    templateIndex += 1;
  }
  return sourceIndex;
}

function analyzeSampleIndex(source: string, start: number): SampleIndexAnalysis | null {
  const delimiters: string[] = [];
  const closingDelimiter: Record<string, string> = { "]": "[", ")": "(", "}": "{" };
  let quote = "";
  let escaped = false;
  let slice = false;
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
    } else if (character === "[" || character === "(" || character === "{") {
      delimiters.push(character);
    } else if (character in closingDelimiter) {
      if (delimiters.at(-1) !== closingDelimiter[character]) return null;
      delimiters.pop();
      if (delimiters.length === 0) {
        if (character !== "]") return null;
        const value = source.slice(start + 1, index).trim();
        return { end: index, slice, supported: isSupportedSampleIndex(value) };
      }
    } else if (character === ":" && delimiters.length === 1) {
      slice = true;
    }
  }
  return null;
}

function isSupportedSampleIndex(value: string): boolean {
  if (/^(?:true|false|null|none)$/iu.test(value)) return false;
  return /^-?\d+$/u.test(value) || /^-?[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$/u.test(value);
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
    type: variable.kind === "output" || variable.kind === "config" ? "property" : "variable",
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
