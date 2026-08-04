import type { CollectionDefinition, LogCollectionSpec } from "../../../types";

export function isLogCollection(definition?: CollectionDefinition): boolean {
  return definition?.spec.collectionType === "log";
}
export function collectionTypeLabel(definition?: CollectionDefinition): string {
  return isLogCollection(definition) ? "日志聚合" : "CLI 命令";
}

export function collectionContentSummary(definition?: CollectionDefinition): string {
  if (!definition) return "采集定义不可用";
  if (definition.spec.collectionType === "cli") return definition.spec.commandTemplate || "未配置命令";
  const firstQuery = definition.spec.queries.find((item) => item.sql.trim());
  return firstQuery?.sql.split(/\r?\n/, 1)[0]?.trim() || "未配置聚合 SQL";
}

export function collectionSearchText(definition: CollectionDefinition): string {
  const content = definition.spec.collectionType === "cli"
    ? definition.spec.commandTemplate
    : (definition.spec as LogCollectionSpec).queries.map((item) => `${item.name} ${item.sql}`).join(" ");
  return [definition.metadata.name, definition.key, definition.metadata.description, content].join(" ");
}
