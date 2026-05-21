import { slugTitle } from "../lib/format";
import type { SkillDetail } from "../types";

type TopBarProps = {
  actor?: string;
  currentSkill?: SkillDetail | null;
  onHome: () => void;
};

export function TopBar({ actor = "product-operator", currentSkill, onHome }: TopBarProps) {
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
      <div className="actor-menu" aria-label={`当前操作者 ${actor}`}>
        <span className="actor-dot">{actor.slice(0, 1).toUpperCase()}</span>
        <span>{actor}</span>
      </div>
    </header>
  );
}
