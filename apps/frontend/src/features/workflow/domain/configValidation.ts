import type { CollectionDefinition, WorkflowConfigCommand } from "../../../types";
import { isConfigIdentifier, parseConfigPattern } from "./configPattern";

export type ConfigIssue = { code: string; message: string; itemId?: string; field: string };

export function configCollectionIssues(definition: CollectionDefinition): ConfigIssue[] {
  if (definition.spec.collectionType !== "config") return [];
  const issues: ConfigIssue[] = [];
  validateCommands(definition.spec.config.commands, "spec.config.commands", issues);
  return issues;
}

function validateCommands(commands: WorkflowConfigCommand[], path: string, issues: ConfigIssue[]): void {
  const names = new Set<string>();
  commands.forEach((command, index) => {
    const itemPath = `${path}[${index}]`;
    if (!isConfigIdentifier(command.name)) issues.push({ code: "CONFIG_COMMAND_NAME_INVALID", message: `配置命令名“${command.name}”不是合法标识符。`, itemId: command.name, field: `${itemPath}.name` });
    if (names.has(command.name)) issues.push({ code: "CONFIG_COMMAND_NAME_DUPLICATE", message: `同一层级的配置命令名称“${command.name}”重复。`, itemId: command.name, field: `${itemPath}.name` });
    names.add(command.name);
    const parsed = parseConfigPattern(command.pattern);
    if (parsed.error) issues.push({ code: "CONFIG_COMMAND_PATTERN_INVALID", message: parsed.error, itemId: command.name, field: `${itemPath}.pattern` });
    if (parsed.names.slice().sort().join("\u0000") !== Object.keys(command.captures).sort().join("\u0000")) issues.push({ code: "CONFIG_CAPTURE_SCHEMA_MISMATCH", message: "配置命令模板中的捕获名称必须与 captures map 完全一致。", itemId: command.name, field: `${itemPath}.captures` });
    const captureNames = new Set(Object.keys(command.captures));
    command.children.forEach((child) => {
      if (captureNames.has(child.name)) issues.push({ code: "CONFIG_COMMAND_PROPERTY_CONFLICT", message: `配置命令“${command.name}”的捕获字段与子命令“${child.name}”重名。`, itemId: command.name, field: `${itemPath}.children` });
    });
    validateCommands(command.children, `${itemPath}.children`, issues);
  });
}
