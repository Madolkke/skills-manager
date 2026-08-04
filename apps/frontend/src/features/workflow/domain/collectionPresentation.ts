import type { CollectionDefinition, ConfigCollectionSpec, LogCollectionSpec } from "../../../types";

export function isLogCollection(definition?: CollectionDefinition): boolean {
  return definition?.spec.collectionType === "log";
}
export function isConfigCollection(definition?: CollectionDefinition): boolean {
  return definition?.spec.collectionType === "config";
}
export function collectionTypeLabel(definition?: CollectionDefinition): string {
  if (isLogCollection(definition)) return "日志聚合";
  if (isConfigCollection(definition)) return "配置匹配";
  return "CLI 命令";
}

export function collectionContentSummary(definition?: CollectionDefinition): string {
  if (!definition) return "采集定义不可用";
  if (definition.spec.collectionType === "cli") return definition.spec.commandTemplate || "未配置命令";
  if (definition.spec.collectionType === "log") {
    const firstQuery = definition.spec.queries.find((item) => item.sql.trim());
    return firstQuery?.sql.split(/\r?\n/, 1)[0]?.trim() || "未配置聚合 SQL";
  }
  const config = definition.spec as ConfigCollectionSpec;
  return config.config.commands.map((item) => item.pattern || item.name).join(" · ") || "未配置配置命令";
}

export function collectionSearchText(definition: CollectionDefinition): string {
  const content = definition.spec.collectionType === "cli"
    ? definition.spec.commandTemplate
    : definition.spec.collectionType === "log"
      ? (definition.spec as LogCollectionSpec).queries.map((item) => `${item.name} ${item.sql}`).join(" ")
      : (definition.spec as ConfigCollectionSpec).config.commands.map((item) => `${item.name} ${item.pattern}`).join(" ");
  return [definition.metadata.name, definition.key, definition.metadata.description, content].join(" ");
}
