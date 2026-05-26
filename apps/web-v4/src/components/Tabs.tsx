import clsx from "clsx";
import type { SkillTab } from "../lib/navigation";

const labels: Record<SkillTab, string> = {
  overview: "概览",
  versions: "版本",
  evalsets: "测评集",
  evaluate: "测评",
  history: "历史",
};

type TabsProps = {
  active: SkillTab;
  onChange: (tab: SkillTab) => void;
};

export function SkillTabs({ active, onChange }: TabsProps) {
  const tabs = Object.keys(labels) as SkillTab[];
  return (
    <div className="skill-tabs" role="tablist" aria-label="Skill 页面">
      {tabs.map((tab) => (
        <button
          className={clsx("skill-tab", active === tab && "active")}
          key={tab}
          type="button"
          role="tab"
          aria-selected={active === tab}
          onClick={() => onChange(tab)}
        >
          {labels[tab]}
        </button>
      ))}
    </div>
  );
}
