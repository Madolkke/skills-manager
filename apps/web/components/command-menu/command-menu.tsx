"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export type CommandMenuItem = {
  id: string;
  title: string;
  group: string;
  detail: string;
  shortcut?: string;
  disabled?: boolean;
  disabledReason?: string;
  run: () => void;
};

export function CommandMenu({ commands, scopeLabel }: { commands: CommandMenuItem[]; scopeLabel: string }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filteredCommands = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const filtered = normalizedQuery
      ? commands.filter((command) =>
          `${command.title} ${command.group} ${command.detail}`.toLowerCase().includes(normalizedQuery),
        )
      : commands;
    return [...filtered].sort((left, right) => Number(Boolean(left.disabled)) - Number(Boolean(right.disabled)));
  }, [commands, query]);

  useEffect(() => {
    function openCommandMenu() {
      setOpen(true);
      setQuery("");
      setActiveIndex(0);
    }

    function handleGlobalKeydown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTyping = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.isContentEditable;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        openCommandMenu();
        return;
      }
      if (event.key === "Escape" && open && !isTyping) {
        setOpen(false);
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

  const activeCommand = filteredCommands[activeIndex];

  function runCommand(command: CommandMenuItem | undefined) {
    if (!command || command.disabled) return;
    command.run();
    setOpen(false);
    setQuery("");
    setActiveIndex(0);
  }

  function handleInputKeydown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
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
    if (event.key === "Enter") {
      event.preventDefault();
      runCommand(activeCommand);
    }
  }

  return (
    <div className="commandMenuBackdrop" onMouseDown={() => setOpen(false)}>
      <section
        aria-label="Command menu"
        aria-modal="true"
        className="commandMenuPanel"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="commandMenuScope">
          <span>SkillHub command</span>
          <strong>{scopeLabel}</strong>
        </div>
        <label className="commandMenuSearch">
          <span>Search</span>
          <input
            onChange={(event) => {
              setQuery(event.currentTarget.value);
              setActiveIndex(0);
            }}
            onKeyDown={handleInputKeydown}
            placeholder="搜索命令、页面或动作"
            ref={inputRef}
            value={query}
          />
        </label>
        <div className="commandMenuList" role="listbox">
          {filteredCommands.map((command, index) => {
            const active = index === activeIndex;
            return (
              <button
                aria-selected={active}
                className={`commandMenuItem ${active ? "commandMenuItemActive" : ""}`}
                disabled={command.disabled}
                key={command.id}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => runCommand(command)}
                role="option"
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
