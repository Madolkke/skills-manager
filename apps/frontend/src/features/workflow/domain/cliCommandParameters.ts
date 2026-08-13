import { isWorkflowExpressionIdentifier } from "../workflowExpressionSyntax";

export type CliCommandParameters = { names: string[]; error?: string };

export function parseCliCommandParameters(command: string): CliCommandParameters {
  const names: string[] = [];
  let index = 0;
  while (index < command.length) {
    const character = command[index];
    if (character === ">") return { names, error: "采集命令包含未配对的尖括号。" };
    if (character !== "<") {
      index += 1;
      continue;
    }
    const end = command.indexOf(">", index + 1);
    if (end < 0) return { names, error: "采集命令包含未闭合的参数。" };
    const name = command.slice(index + 1, end);
    if (!name || name.includes("<")) return { names, error: "采集命令参数必须使用 <name> 格式。" };
    if (!isWorkflowExpressionIdentifier(name)) return { names, error: `采集命令参数“${name}”必须是合法的 Python 标识符。` };
    if (!names.includes(name)) names.push(name);
    index = end + 1;
  }
  return { names };
}
