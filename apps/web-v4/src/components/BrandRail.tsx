import { ChevronsLeft, ChevronsRight, Home, Plus, Search } from "lucide-react";

type BrandRailProps = {
  collapsed: boolean;
  homeActive: boolean;
  onToggle: () => void;
  onHome: () => void;
  onCreate: () => void;
  onSearch: () => void;
};

export function BrandRail({ collapsed, homeActive, onToggle, onHome, onCreate, onSearch }: BrandRailProps) {
  return (
    <aside className="brand-rail" aria-label="SkillHub 导航">
      <button className="brand-mark" type="button" onClick={onHome} aria-label="返回首页">
        SH
      </button>
      <nav className="rail-nav">
        <button className={homeActive ? "rail-button active" : "rail-button"} type="button" onClick={onHome} aria-label="SkillHub 首页">
          <Home size={22} />
        </button>
        <button className="rail-button" type="button" onClick={onSearch} aria-label="搜索 Skill">
          <Search size={22} />
        </button>
        <button className="rail-button" type="button" onClick={onCreate} aria-label="新建 Skill">
          <Plus size={24} />
        </button>
      </nav>
      <div className="rail-footer">
        <button className="rail-collapse" type="button" onClick={onToggle} aria-label={collapsed ? "展开侧栏" : "收起侧栏"}>
          {collapsed ? <ChevronsRight size={19} /> : <ChevronsLeft size={19} />}
        </button>
      </div>
    </aside>
  );
}
