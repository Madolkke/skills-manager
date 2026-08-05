import type { WorkflowConfigCapture } from "../../../types";

const RESERVED = new Set([
  "False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
  "clear", "copy", "fromkeys", "get", "items", "keys", "pop", "popitem", "setdefault", "update", "values",
]);

export type ConfigPatternParseResult = { names: string[]; error?: string; code?: string };

export function parseConfigPattern(pattern: string): ConfigPatternParseResult {
  if (!pattern.trim()) return { names: [], error: "配置命令模式不能为空。", code: "CONFIG_COMMAND_PATTERN_INVALID" };
  if (/[\r\n]/u.test(pattern)) return { names: [], error: "配置命令模式必须为单行。", code: "CONFIG_COMMAND_PATTERN_MULTILINE" };
  const names: string[] = [];
  for (let index = 0; index < pattern.length; index += 1) {
    if (pattern[index] !== "<" || isEscaped(pattern, index)) continue;
    const end = findEnd(pattern, index + 1);
    if (end < 0) return { names, error: "配置命令模式中的尖括号未闭合。", code: "CONFIG_COMMAND_PATTERN_INVALID" };
    const token = pattern.slice(index + 1, end);
    const separator = token.indexOf(":");
    const name = separator < 0 ? token : token.slice(0, separator);
    const expression = separator < 0 ? "\\S+" : token.slice(separator + 1);
    if (!isConfigIdentifier(name)) return { names, error: `捕获名“${name}”不是合法标识符。`, code: isConfigReservedName(name) ? "CONFIG_COMMAND_NAME_RESERVED" : "CONFIG_CAPTURE_NAME_INVALID" };
    if (separator >= 0 && !expression) return { names, error: `捕获“${name}”的正则不能为空。`, code: "CONFIG_COMMAND_PATTERN_INVALID" };
    if (names.includes(name)) return { names, error: `捕获名“${name}”重复。`, code: "CONFIG_CAPTURE_NAME_DUPLICATE" };
    if (!validPythonRegex(expression)) return { names, error: `捕获“${name}”的正则无效。`, code: "CONFIG_COMMAND_PATTERN_INVALID" };
    names.push(name);
    index = end;
  }
  return { names };
}

export function syncConfigCaptures(pattern: string, captures: Record<string, WorkflowConfigCapture>): Record<string, WorkflowConfigCapture> {
  const parsed = parseConfigPattern(pattern);
  if (parsed.error) return structuredClone(captures);
  const next: Record<string, WorkflowConfigCapture> = {};
  parsed.names.forEach((name) => {
    next[name] = captures[name] ?? { type: "string", title: name, description: "" };
  });
  return next;
}

export function removeConfigCapture(pattern: string, name: string): string {
  for (let index = 0; index < pattern.length; index += 1) {
    if (pattern[index] !== "<" || isEscaped(pattern, index)) continue;
    const end = findEnd(pattern, index + 1);
    if (end < 0) return pattern;
    const token = pattern.slice(index + 1, end);
    const separator = token.indexOf(":");
    const tokenName = separator < 0 ? token : token.slice(0, separator);
    if (tokenName === name) return `${pattern.slice(0, index)}${pattern.slice(end + 1)}`.replace(/\s{2,}/gu, " ").trim();
    index = end;
  }
  return pattern;
}

export function isConfigIdentifier(value: string): boolean {
  return /^\p{ID_Start}\p{ID_Continue}*$/u.test(value) && !value.startsWith("_") && !RESERVED.has(value);
}

export function isConfigReservedName(value: string): boolean {
  return RESERVED.has(value);
}

function findEnd(pattern: string, start: number): number {
  let inCharacterClass = false;
  let groupDepth = 0;
  let escaped = false;
  for (let index = start; index < pattern.length; index += 1) {
    const character = pattern[index];
    if (escaped) { escaped = false; continue; }
    if (character === "\\") { escaped = true; continue; }
    if (character === "[") { inCharacterClass = true; continue; }
    if (character === "]" && inCharacterClass) { inCharacterClass = false; continue; }
    if (character === "(" && !inCharacterClass) { groupDepth += 1; continue; }
    if (character === ")" && !inCharacterClass && groupDepth > 0) { groupDepth -= 1; continue; }
    if (character === ">" && !inCharacterClass && groupDepth === 0) return index;
  }
  return -1;
}

function isEscaped(pattern: string, index: number): boolean {
  let slashes = 0;
  for (let cursor = index - 1; cursor >= 0 && pattern[cursor] === "\\"; cursor -= 1) slashes += 1;
  return slashes % 2 === 1;
}

function validPythonRegex(expression: string): boolean {
  // Python supports constructs that JavaScript cannot compile (named backrefs,
  // lookbehind variants, inline flags, atomic groups). The backend remains the
  // source of truth for those constructs; the browser still checks ordinary
  // regex syntax locally for immediate feedback.
  if (/\(\?[PaiLmsux-]|\(\?>|\\g<|\\k<|\(\?P=/u.test(expression)) return true;
  const javascriptExpression = expression.replace(/\(\?P<[^>]+>/gu, "(?:");
  try {
    // Python named groups are normalized only for the browser-side syntax check.
    new RegExp(javascriptExpression);
    return true;
  } catch {
    return false;
  }
}
