"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";

import { loadRecentCommandIds, rankCommandsForMenu, rememberRecentCommandId, saveRecentCommandIds } from "@/components/command-menu/command-menu-recents";
import { CommandMenuPreview } from "@/components/command-menu/command-menu-preview";
import type { CommandMenuItem } from "@/components/command-menu/command-menu-types";

export function CommandMenu({ commands, scopeLabel }: { commands: CommandMenuItem[]; scopeLabel: string }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [recentCommandIds, setRecentCommandIds] = useState<string[]>([]);
  const menuId = sanitizeDomId(useId());
  const inputRef = useRef<HTMLInputElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const titleId = `${menuId}-title`;
  const inputId = `${menuId}-search`;
  const listboxId = `${menuId}-listbox`;

  const filteredCommands = useMemo(() => {
    return rankCommandsForMenu(commands, { query, recentCommandIds });
  }, [commands, query, recentCommandIds]);

  const activeCommand = filteredCommands[activeIndex];
  const activeOptionId = activeCommand ? commandOptionId(menuId, activeCommand.id) : undefined;

  function openCommandMenu() {
    openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setOpen(true);
    setQuery("");
    setActiveIndex(0);
  }

  function closeCommandMenu(restoreFocus = true) {
    setOpen(false);
    setQuery("");
    setActiveIndex(0);
    if (!restoreFocus) return;
    const opener = openerRef.current;
    if (!opener) return;
    window.requestAnimationFrame(() => opener.focus());
  }

  useEffect(() => {
    setRecentCommandIds(loadRecentCommandIds());
  }, []);

  useEffect(() => {
    function handleGlobalKeydown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTyping = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.isContentEditable;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        openCommandMenu();
        return;
      }
      if (event.key === "Escape" && open && !isTyping) {
        closeCommandMenu();
      }
    }

    window.addEventListener("skillhub:open-command-menu", openCommandMenu);
    window.addEventListener("keydown", handleGlobalKeydown);
    return () => {
      window.removeEventListener("skillhub:open-command-menu", openCommandMenu);
      window.removeEventListener("keydown", handleGlobalKeydown);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const frame = window.requestAnimationFrame(() => inputRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [open]);

  useEffect(() => {
    if (activeIndex < filteredCommands.length) return;
    setActiveIndex(Math.max(0, filteredCommands.length - 1));
  }, [activeIndex, filteredCommands.length]);

  if (!open) return null;

  function runCommand(command: CommandMenuItem | undefined) {
    if (!command || command.disabled) return;
    setRecentCommandIds((current) => {
      const next = rememberRecentCommandId(current, command.id);
      saveRecentCommandIds(next);
      return next;
    });
    command.run();
    closeCommandMenu(false);
  }

  function handleInputKeydown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeCommandMenu();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => nextEnabledIndex(filteredCommands, current, 1));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => nextEnabledIndex(filteredCommands, current, -1));
      return;
    }
    if (event.key === "Home") {
      event.preventDefault();
      setActiveIndex(firstEnabledIndex(filteredCommands));
      return;
    }
    if (event.key === "End") {
      event.preventDefault();
      setActiveIndex(lastEnabledIndex(filteredCommands));
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      runCommand(activeCommand);
    }
  }

  function handleDialogKeydown(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key !== "Tab") return;
    const focusables: HTMLElement[] = [];
    if (inputRef.current) focusables.push(inputRef.current);
    if (closeButtonRef.current) focusables.push(closeButtonRef.current);
    if (focusables.length === 0) return;
    event.preventDefault();
    const currentIndex = Math.max(0, focusables.indexOf(document.activeElement as HTMLElement));
    const offset = event.shiftKey ? -1 : 1;
    const nextIndex = (currentIndex + offset + focusables.length) % focusables.length;
    focusables[nextIndex].focus();
  }

  return (
    <div className="commandMenuBackdrop" onMouseDown={() => closeCommandMenu()}>
      <section
        aria-labelledby={titleId}
        aria-modal="true"
        className="commandMenuPanel"
        onKeyDown={handleDialogKeydown}
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="commandMenuScope">
          <div>
            <span>{scopeLabel}</span>
            <strong id={titleId}>Command menu</strong>
          </div>
          <button
            aria-label="关闭命令菜单"
            className="commandMenuClose"
            onClick={() => closeCommandMenu()}
            ref={closeButtonRef}
            type="button"
          >
            ×
          </button>
        </div>
        <label className="commandMenuSearch">
          <span>Search</span>
          <input
            aria-activedescendant={activeOptionId}
            aria-autocomplete="list"
            aria-controls={listboxId}
            aria-expanded="true"
            autoComplete="off"
            id={inputId}
            onChange={(event) => {
              setQuery(event.currentTarget.value);
              setActiveIndex(0);
            }}
            onKeyDown={handleInputKeydown}
            placeholder="搜索命令、页面或动作"
            ref={inputRef}
            role="combobox"
            spellCheck={false}
            value={query}
          />
        </label>
        <div className="commandMenuBody">
          <div className="commandMenuList" id={listboxId} role="listbox">
            {filteredCommands.map((command, index) => {
              const active = index === activeIndex;
              return (
                <button
                  aria-disabled={command.disabled ? "true" : undefined}
                  aria-selected={active}
                  className={`commandMenuItem ${active ? "commandMenuItemActive" : ""}`}
                  id={commandOptionId(menuId, command.id)}
                  key={command.id}
                  onClick={() => runCommand(command)}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseEnter={() => setActiveIndex(index)}
                  role="option"
                  tabIndex={-1}
                  type="button"
                >
                  <span className="commandMenuItemMain">
                    <b>{command.title}</b>
                    <small>{command.disabled ? command.disabledReason : command.detail}</small>
                  </span>
                  <span className="commandMenuMeta">
                    <i>{command.group}</i>
                    {command.shortcut ? <kbd>{command.shortcut}</kbd> : null}
                  </span>
                </button>
              );
            })}
            {filteredCommands.length === 0 ? (
              <div className="commandMenuEmpty">
                <strong>没有匹配命令</strong>
                <span>换一个关键词，例如“测评”“历史”或“导入”。</span>
              </div>
            ) : null}
          </div>
          <CommandMenuPreview command={activeCommand} />
        </div>
      </section>
    </div>
  );
}

function nextEnabledIndex(commands: CommandMenuItem[], current: number, direction: 1 | -1) {
  if (commands.length === 0) return 0;
  for (let offset = 1; offset <= commands.length; offset += 1) {
    const next = (current + offset * direction + commands.length) % commands.length;
    if (!commands[next].disabled) return next;
  }
  return current;
}

function firstEnabledIndex(commands: CommandMenuItem[]) {
  const index = commands.findIndex((command) => !command.disabled);
  return index >= 0 ? index : 0;
}

function lastEnabledIndex(commands: CommandMenuItem[]) {
  for (let index = commands.length - 1; index >= 0; index -= 1) {
    if (!commands[index].disabled) return index;
  }
  return 0;
}

function commandOptionId(menuId: string, commandId: string) {
  return `${menuId}-option-${sanitizeDomId(commandId)}`;
}

function sanitizeDomId(value: string) {
  return value.replace(/[^A-Za-z0-9_-]/g, "-");
}
