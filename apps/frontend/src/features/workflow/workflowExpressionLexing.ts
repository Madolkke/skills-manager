const closingBrackets: Record<string, string> = { ")": "(", "]": "[", "}": "{" };

/** 扫描 Python 表达式中的引号、转义和括号，仅在顶层识别模板结束符。 */
export function scanWorkflowExpressionBoundary(source: string, start = 0, template = true): { closing: number | null; quoted: boolean } {
  const brackets: string[] = [];
  let quote = "";
  let cursor = start;
  while (cursor < source.length) {
    const character = source[cursor]!;
    if (character === "\\" && (quote || !template)) { cursor += 2; continue; }
    if (quote) {
      if (source.startsWith(quote, cursor)) { cursor += quote.length; quote = ""; }
      else cursor += 1;
      continue;
    }
    if (template && brackets.length === 0 && source.startsWith("}}", cursor)) return { closing: cursor, quoted: false };
    if (character === "'" || character === '"' || (!template && character === "`")) {
      quote = character !== "`" && source.startsWith(character.repeat(3), cursor) ? character.repeat(3) : character;
      cursor += quote.length;
      continue;
    }
    if ("([{".includes(character)) brackets.push(character);
    else if (Object.hasOwn(closingBrackets, character) && brackets.at(-1) === closingBrackets[character]) brackets.pop();
    cursor += 1;
  }
  return { closing: null, quoted: Boolean(quote) };
}
