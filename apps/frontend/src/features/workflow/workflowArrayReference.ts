/** 匹配数组引用，保留作者输入的静态及动态下标。 */
type SampleIndexAnalysis = { end: number; slice: boolean; supported: boolean };
type ArrayReferenceMatch = { start: number; end: number };

export function findArrayReferenceMatch(source: string, template: string): ArrayReferenceMatch | null {
  const prefix = template.split("[0]")[0] ?? template;
  let start = source.lastIndexOf(prefix);
  while (start >= 0) {
    if (isReferenceBoundary(source, start)) {
      const end = matchReferenceTemplate(source, start, template);
      if (end !== null) return { start, end };
    }
    start = start === 0 ? -1 : source.lastIndexOf(prefix, start - 1);
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

export function analyzeSampleIndex(source: string, start: number): SampleIndexAnalysis | null {
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
