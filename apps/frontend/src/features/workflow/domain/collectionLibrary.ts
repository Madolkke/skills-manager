import type {
  CollectionDefinition,
  CollectionType,
  CommandLibrarySearchResult,
  VersionedRef,
} from "../../../types";
import { collectionContentSummary, collectionSearchText } from "./collectionPresentation";
import { refKey } from "./utils";

export type CollectionLibraryItem = {
  id: string;
  type: CollectionType;
  source?: "system" | "user";
  name: string;
  summary: string;
  definition?: CollectionDefinition;
  result?: CommandLibrarySearchResult;
  current: boolean;
};

export type CollectionLibraryItemsInput = {
  type: CollectionType;
  definitions: CollectionDefinition[];
  currentDefinitionRefs: VersionedRef[];
  commandResults: CommandLibrarySearchResult[];
  includeUser: boolean;
  query: string;
};

/** 统一生成 Library 与 Picker 使用的类型和来源候选列表。 */
export function collectionLibraryItems(input: CollectionLibraryItemsInput): CollectionLibraryItem[] {
  if (input.type !== "cli") return collectionItems(input);
  return commandItems(input);
}

export function findReusableCommandDefinition(
  result: CommandLibrarySearchResult,
  definitions: CollectionDefinition[],
  currentDefinitionRefs: VersionedRef[],
): CollectionDefinition | undefined {
  const current = currentDefinitions(definitions, currentDefinitionRefs).filter((item) => item.spec.collectionType === "cli");
  if (result.source === "system") {
    return current
      .filter((item) => item.sourceSystemCommandId === result.id)
      .sort((left, right) => right.revision - left.revision)[0];
  }
  if (!result.collectionDefinitionId) return undefined;
  const candidates = current.filter((item) => item.id === result.collectionDefinitionId);
  return candidates.find((item) => item.revision === result.collectionRevision)
    ?? candidates.sort((left, right) => right.revision - left.revision)[0];
}

function commandItems(input: CollectionLibraryItemsInput): CollectionLibraryItem[] {
  const current = currentDefinitions(input.definitions, input.currentDefinitionRefs)
    .filter((item) => item.spec.collectionType === "cli");
  const items = new Map<string, CollectionLibraryItem>();
  const usedDefinitions = new Set<string>();

  input.commandResults.filter((result) => result.source === "system").forEach((result) => {
    const definition = findReusableCommandDefinition(result, input.definitions, input.currentDefinitionRefs);
    if (definition) usedDefinitions.add(refKey(definition));
    const key = `system:${result.id}`;
    if (!items.has(key)) items.set(key, commandItem(key, "system", result, definition));
  });
  current.filter((definition) => definition.sourceSystemCommandId && !usedDefinitions.has(refKey(definition)))
    .filter((definition) => matchesDefinition(definition, input.query))
    .forEach((definition) => items.set(`system:${definition.sourceSystemCommandId}`, definitionItem(definition, "system", true)));

  if (input.includeUser) {
    input.commandResults.filter((result) => result.source === "user").forEach((result) => {
      const definition = findReusableCommandDefinition(result, input.definitions, input.currentDefinitionRefs);
      if (definition) usedDefinitions.add(refKey(definition));
      const key = definition ? `user:${refKey(definition)}` : `user:${result.id}`;
      if (!items.has(key)) items.set(key, commandItem(key, "user", result, definition));
    });
    current.filter((definition) => !definition.sourceSystemCommandId && !usedDefinitions.has(refKey(definition)))
      .filter((definition) => matchesDefinition(definition, input.query))
      .forEach((definition) => items.set(`user:${refKey(definition)}`, definitionItem(definition, "user", true)));
  }
  return sortItems([...items.values()]);
}

function collectionItems(input: CollectionLibraryItemsInput): CollectionLibraryItem[] {
  const currentKeys = new Set(input.currentDefinitionRefs.map(refKey));
  const selected = new Map<string, CollectionDefinition>();
  const latest = new Map<string, CollectionDefinition>();
  input.definitions.filter((item) => item.spec.collectionType === input.type).forEach((item) => {
    const existing = latest.get(item.id);
    if (!existing || item.revision > existing.revision) latest.set(item.id, item);
    if (currentKeys.has(refKey(item))) selected.set(refKey(item), item);
  });
  latest.forEach((item) => selected.set(refKey(item), item));
  return sortItems([...selected.values()]
    .filter((definition) => matchesDefinition(definition, input.query))
    .map((definition) => definitionItem(definition, undefined, currentKeys.has(refKey(definition)))));
}

function currentDefinitions(definitions: CollectionDefinition[], references: VersionedRef[]): CollectionDefinition[] {
  const keys = new Set(references.map(refKey));
  return definitions.filter((item) => keys.has(refKey(item)));
}

function commandItem(
  id: string,
  source: "system" | "user",
  result: CommandLibrarySearchResult,
  definition?: CollectionDefinition,
): CollectionLibraryItem {
  const metadata = result.metadata ?? {};
  return {
    id,
    type: "cli",
    source,
    name: definition?.metadata.name || String(metadata.name ?? result.name ?? result.key),
    summary: definition ? collectionContentSummary(definition) : result.expression,
    definition,
    result,
    current: Boolean(definition),
  };
}

function definitionItem(
  definition: CollectionDefinition,
  source: "system" | "user" | undefined,
  current: boolean,
): CollectionLibraryItem {
  return {
    id: `${source ?? definition.spec.collectionType}:${refKey(definition)}`,
    type: definition.spec.collectionType,
    source,
    name: definition.metadata.name || "未命名采集",
    summary: collectionContentSummary(definition),
    definition,
    current,
  };
}

function matchesDefinition(definition: CollectionDefinition, query: string): boolean {
  const needle = query.trim().toLocaleLowerCase();
  return !needle || collectionSearchText(definition).toLocaleLowerCase().includes(needle);
}

function sortItems(items: CollectionLibraryItem[]): CollectionLibraryItem[] {
  return items.sort((left, right) => (
    left.name.localeCompare(right.name, "zh-CN")
    || left.summary.localeCompare(right.summary, "zh-CN")
    || left.id.localeCompare(right.id)
  ));
}
