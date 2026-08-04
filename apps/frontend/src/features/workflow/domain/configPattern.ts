import type { WorkflowConfigCapture } from "../../../types";

const RESERVED = new Set([
  "False", "None", "True", "and", "as", "assert", "async", "await", "break", "case", "class", "continue", "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda", "match", "nonlocal", "not", "or", "pass", "raise", "return", "try", "type", "while", "with", "yield",
  "clear", "copy", "fromkeys", "get", "items", "keys", "pop", "popitem", "setdefault", "update", "values",
]);

export type ConfigPatternParseResult = { names: string[]; error?: string };

export function parseConfigPattern(pattern: string): ConfigPatternParseResult {
  if (!pattern.trim()) return { names: [], error: "配置命令模式不能为空。" };
  if (/[\r\n]/u.test(pattern)) return { names: [], error: "配置命令模式必须为单行。" };
  const names: string[] = [];
  for (let index = 0; index < pattern.length; index += 1) {
    if (pattern[index] !== "<" || (index > 0 && pattern[index - 1] === "\\")) continue;
    const end = findEnd(pattern, index + 1);
    if (end < 0) return { names, error: "配置命令模式中的尖括号未闭合。" };
    const token = pattern.slice(index + 1, end);
    const [name] = token.split(":", 1);
    if (!isConfigIdentifier(name)) return { names, error: `捕获名“${name}”不是合法标识符。` };
    if (names.includes(name)) return { names, error: `捕获名“${name}”重复。` };
    names.push(name);
    index = end;
  }
  return { names };
}

export function syncConfigCaptures(pattern: string, captures: Record<string, WorkflowConfigCapture>): Record<string, WorkflowConfigCapture> {
  const parsed = parseConfigPattern(pattern);
  const next: Record<string, WorkflowConfigCapture> = {};
  parsed.names.forEach((name) => {
    next[name] = captures[name] ?? { type: "string", title: name, description: "" };
  });
  return next;
}

export function isConfigIdentifier(value: string): boolean {
  return /^\p{ID_Start}\p{ID_Continue}*$/u.test(value) && !value.startsWith("_") && !RESERVED.has(value);
}

function findEnd(pattern: string, start: number): number {
  for (let index = start; index < pattern.length; index += 1) {
    if (pattern[index] === "\\") { index += 1; continue; }
    if (pattern[index] === ">") return index;
  }
  return -1;
}
