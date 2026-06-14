import { Plus, Settings, Workflow } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { slugTitle } from "../lib/format";
import type { SkillDetail } from "../types";

type TopBarProps = {
  actor?: string;
  currentSkill?: SkillDetail | null;
  onHome: () => void;
  onCreate: () => void;
  onWorkflows: () => void;
};

export function TopBar({ actor = "product-operator", currentSkill, onHome, onCreate, onWorkflows }: TopBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpen]);

  return (
    <header className="top-bar">
      <button className="breadcrumb-root" type="button" onClick={onHome}>
        SkillHub
      </button>
      {currentSkill ? (
        <>
          <span className="breadcrumb-separator">/</span>
          <strong className="breadcrumb-current">{slugTitle(currentSkill.skill.slug)}</strong>
        </>
      ) : null}
      <div className="top-spacer" />
      <div className="top-bar-actions">
        <button className="secondary-button" type="button" onClick={onWorkflows}>
          <Workflow size={16} />
          工作流编排
        </button>
        <button className="primary-button" type="button" onClick={onCreate}>
          <Plus size={16} />
          新建 Skill
        </button>
      </div>
      <div className="actor-menu" ref={menuRef}>
        <button className="actor-dot" type="button" title={actor} aria-label={`当前操作者 ${actor}`} onClick={() => setMenuOpen((open) => !open)}>
          {actor.slice(0, 1).toUpperCase()}
        </button>
        {menuOpen ? (
          <div className="actor-dropdown">
            <div className="actor-dropdown-header">{actor}</div>
            <button className="actor-dropdown-item" type="button" onClick={() => setMenuOpen(false)}>
              <Settings size={15} />
              设置
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
