import type { CommandMenuItem } from "@/components/command-menu/command-menu-types";

export const COMMAND_MENU_RECENTS_KEY = "skillhub.commandMenu.recent.v1";
const RECENT_LIMIT = 5;

export function rememberRecentCommandId(current: string[], commandId: string, limit = RECENT_LIMIT) {
  return [commandId, ...current.filter((id) => id !== commandId)].slice(0, limit);
}

export function normalizeRecentCommandIds(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.filter((id): id is string => typeof id === "string" && id.length > 0).slice(0, RECENT_LIMIT);
}

export function loadRecentCommandIds(storage: Storage | null | undefined = safeStorage()) {
  if (!storage) return [];
  try {
    return normalizeRecentCommandIds(JSON.parse(storage.getItem(COMMAND_MENU_RECENTS_KEY) ?? "[]"));
  } catch {
    return [];
  }
}

export function saveRecentCommandIds(ids: string[], storage: Storage | null | undefined = safeStorage()) {
  if (!storage) return;
  try {
    storage.setItem(COMMAND_MENU_RECENTS_KEY, JSON.stringify(normalizeRecentCommandIds(ids)));
  } catch {
    // localStorage may be unavailable in private or locked-down browser contexts.
  }
}

export function rankCommandsForMenu(
  commands: CommandMenuItem[],
  options: { query: string; recentCommandIds: string[] },
) {
  const query = options.query.trim().toLowerCase();
  const filtered = query ? commands.filter((command) => commandMatchesQuery(command, query)) : commands;
  const recentRank = new Map(options.recentCommandIds.map((id, index) => [id, index]));
  return filtered
    .map((command, index) => ({ command, index }))
    .sort((left, right) => {
      const disabledDelta = Number(Boolean(left.command.disabled)) - Number(Boolean(right.command.disabled));
      if (disabledDelta !== 0) return disabledDelta;
      if (!query) {
        const leftRecent = recentRank.get(left.command.id) ?? Number.POSITIVE_INFINITY;
        const rightRecent = recentRank.get(right.command.id) ?? Number.POSITIVE_INFINITY;
        if (leftRecent !== rightRecent) return leftRecent - rightRecent;
      }
      return left.index - right.index;
    })
    .map(({ command }) => command);
}

function commandMatchesQuery(command: CommandMenuItem, query: string) {
  return `${command.title} ${command.group} ${command.detail}`.toLowerCase().includes(query);
}

function safeStorage() {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
