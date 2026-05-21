import clsx from "clsx";
import { CheckCircle2, Circle, Grid2X2, List, Plus, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { humanDate, scoreKind, scoreLabel, slugTitle, versionName } from "../lib/format";
import type { SkillSummary } from "../types";

type HubPageProps = {
  skills: SkillSummary[];
  actor: string;
  loading: boolean;
  searchFocusSignal: number;
  onOpenSkill: (skillId: string) => void;
  onCreate: () => void;
};

type FilterKey = "all" | "verified" | "untested" | "mine";
type SortKey = "updated" | "score" | "name";
type ViewMode = "grid" | "list";
const RECENT_COLLAPSED_LIMIT = 6;

export function HubPage({ skills, actor, loading, searchFocusSignal, onOpenSkill, onCreate }: HubPageProps) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<FilterKey>("all");
  const [sortKey, setSortKey] = useState<SortKey>("updated");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [showAllRecent, setShowAllRecent] = useState(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const filtered = useMemo(() => filterSkills(skills, query, filter, actor), [skills, query, filter, actor]);
  const sorted = useMemo(() => sortSkills(filtered, sortKey), [filtered, sortKey]);
  const counts = useMemo(() => skillCounts(skills, actor), [skills, actor]);
  const recentRuns = useMemo(() => recentEvalSkills(skills), [skills]);
  const canExpandRecent = recentRuns.length > RECENT_COLLAPSED_LIMIT;
  const visibleRecentRuns = showAllRecent || !canExpandRecent ? recentRuns : recentRuns.slice(0, RECENT_COLLAPSED_LIMIT);

  useEffect(() => {
    if (searchFocusSignal > 0) searchInputRef.current?.focus();
  }, [searchFocusSignal]);

  useEffect(() => {
    if (!canExpandRecent && showAllRecent) setShowAllRecent(false);
  }, [canExpandRecent, showAllRecent]);

  return (
    <div className="hub-page">
      <section className="hub-main">
        <header className="hub-hero">
          <div>
            <h1>SkillHub</h1>
            <p>发现、管理和验证你的 AI 技能库</p>
          </div>
          <button className="primary-button hero-action" type="button" onClick={onCreate}>
            <Plus size={18} />
            新建 Skill
          </button>
        </header>

        <label className="search-field">
          <Search size={22} />
          <input ref={searchInputRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索 skill、owner、tag" aria-label="搜索 Skill" />
        </label>

        <div className="hub-toolbar">
          <div className="filter-tabs">
            <FilterButton active={filter === "all"} label="全部" count={counts.all} onClick={() => setFilter("all")} />
            <FilterButton active={filter === "verified"} label="已验证" count={counts.verified} onClick={() => setFilter("verified")} />
            <FilterButton active={filter === "untested"} label="未测" count={counts.untested} onClick={() => setFilter("untested")} />
            <FilterButton active={filter === "mine"} label="我维护的" count={counts.mine} onClick={() => setFilter("mine")} />
          </div>
          <div className="view-tools">
            <label className="sort-control">
              <span>排序</span>
              <select value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)}>
                <option value="updated">最近更新</option>
                <option value="score">验证得分</option>
                <option value="name">名称</option>
              </select>
            </label>
            <button className={clsx("icon-button", viewMode === "grid" && "active")} type="button" aria-label="卡片视图" aria-pressed={viewMode === "grid"} onClick={() => setViewMode("grid")}>
              <Grid2X2 size={19} />
            </button>
            <button className={clsx("icon-button", viewMode === "list" && "active")} type="button" aria-label="列表视图" aria-pressed={viewMode === "list"} onClick={() => setViewMode("list")}>
              <List size={19} />
            </button>
          </div>
        </div>

        {loading ? <div className="quiet-panel">正在加载 Skill...</div> : null}
        {!loading && sorted.length === 0 ? (
          <div className="empty-state-panel">
            <strong>没有匹配的 Skill</strong>
            <p>换一个关键词，或新建一个标准 skill bundle 开始验证。</p>
            <button className="primary-button" type="button" onClick={onCreate}>
              <Plus size={17} />
              新建 Skill
            </button>
          </div>
        ) : (
          <div className={clsx("skill-grid", viewMode === "list" && "list-view")}>
            {sorted.map((item) => (
              <SkillCard item={item} key={item.skill.id} onClick={() => onOpenSkill(item.skill.id)} />
            ))}
          </div>
        )}
      </section>

      <aside className="recent-panel">
        <div className="panel-head">
          <h2>最近测评</h2>
          {canExpandRecent ? (
            <button type="button" aria-label={showAllRecent ? "收起最近测评" : "查看全部最近测评"} onClick={() => setShowAllRecent((value) => !value)}>
              {showAllRecent ? "收起" : "查看全部"}
            </button>
          ) : null}
        </div>
        <div className="recent-list" role="list" aria-label={`最近测评，显示 ${visibleRecentRuns.length} / ${recentRuns.length} 条`}>
          {recentRuns.length === 0 ? <div className="recent-empty">还没有测评记录。</div> : null}
          {visibleRecentRuns.map((item) => (
            <RecentRunRow item={item} key={item.skill.id} onClick={() => onOpenSkill(item.skill.id)} />
          ))}
        </div>
      </aside>
    </div>
  );
}

function SkillCard({ item, onClick }: { item: SkillSummary; onClick: () => void }) {
  const status = scoreKind(item.latest_accepted_eval_run);
  const tags = item.default_variant?.tags ?? [];
  const extraTags = Math.max(0, tags.length - 3);
  return (
    <button className="skill-card" type="button" onClick={onClick}>
      <div className="card-body">
        <div className="card-context">
          <span>维护者 {item.skill.owner_ref}</span>
          <span>更新 {humanDate(item.skill.updated_at)}</span>
        </div>
        <div className="skill-card-head">
          <h3>{slugTitle(item.skill.slug)}</h3>
          <span className={clsx("score-chip", status)}>{scoreLabel(item.latest_accepted_eval_run)}</span>
        </div>
        <p>{item.default_variant?.summary ?? "尚未写入说明。"}</p>
        <div className="tag-row">
          {tags.slice(0, 3).map((tag) => (
            <span className="tag-chip" key={tag}>
              {tag}
            </span>
          ))}
          {extraTags > 0 ? <span className="tag-chip muted">+{extraTags}</span> : null}
        </div>
      </div>
      <div className="card-metrics">
        <Metric label="验证得分" value={scoreLabel(item.latest_accepted_eval_run)} tone={status} />
        <Metric label="测评集版本" value={item.primary_eval_set?.current_version ? `v${item.primary_eval_set.current_version.version_number}` : "-"} />
        <Metric label="当前版本" value={versionName(item.default_variant?.current_version)} />
        {status === "empty" ? <Circle className="status-ring empty" size={23} /> : <CheckCircle2 className="status-ring verified" size={23} />}
      </div>
    </button>
  );
}

function FilterButton({ active, label, count, onClick }: { active: boolean; label: string; count: number; onClick: () => void }) {
  return (
    <button className={clsx("filter-button", active && "active")} type="button" onClick={onClick}>
      {label}
      <span>{count}</span>
    </button>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <span className="metric-cell">
      <small>{label}</small>
      <strong className={tone}>{value}</strong>
    </span>
  );
}

function RecentRunRow({ item, onClick }: { item: SkillSummary; onClick: () => void }) {
  const run = item.latest_accepted_eval_run;
  return (
    <button className="recent-row" type="button" onClick={onClick}>
      <div className="recent-row-main">
        <div className="recent-title-line">
          <strong>{slugTitle(item.skill.slug)}</strong>
          <b className={scoreKind(run)}>{scoreLabel(run)}</b>
        </div>
        <span className="recent-version-line">
          当前 {versionName(item.default_variant?.current_version)} · {evalSetVersionLabel(item)}
        </span>
        <small className="recent-actor-line">
          <span>操作者 {run?.created_by ?? item.skill.owner_ref}</span>
          <span>{humanDate(run?.created_at)}</span>
        </small>
      </div>
    </button>
  );
}

function filterSkills(skills: SkillSummary[], query: string, filter: FilterKey, actor: string): SkillSummary[] {
  const normalized = query.trim().toLowerCase();
  return skills.filter((item) => {
    const text = [item.skill.slug, item.skill.owner_ref, item.default_variant?.summary, ...(item.default_variant?.tags ?? [])].join(" ").toLowerCase();
    if (normalized && !text.includes(normalized)) return false;
    if (filter === "verified") return scoreKind(item.latest_accepted_eval_run) !== "empty";
    if (filter === "untested") return scoreKind(item.latest_accepted_eval_run) === "empty";
    if (filter === "mine") return item.skill.owner_ref === actor;
    return true;
  });
}

function skillCounts(skills: SkillSummary[], actor: string) {
  return {
    all: skills.length,
    verified: skills.filter((item) => scoreKind(item.latest_accepted_eval_run) !== "empty").length,
    untested: skills.filter((item) => scoreKind(item.latest_accepted_eval_run) === "empty").length,
    mine: skills.filter((item) => item.skill.owner_ref === actor).length,
  };
}

function sortSkills(skills: SkillSummary[], sortKey: SortKey): SkillSummary[] {
  const copy = [...skills];
  if (sortKey === "name") return copy.sort((left, right) => left.skill.slug.localeCompare(right.skill.slug));
  if (sortKey === "score") return copy.sort((left, right) => scoreValue(right) - scoreValue(left) || updatedTime(right) - updatedTime(left));
  return copy.sort((left, right) => updatedTime(right) - updatedTime(left));
}

function recentEvalSkills(skills: SkillSummary[]): SkillSummary[] {
  return skills
    .filter((item) => item.latest_accepted_eval_run)
    .sort((left, right) => Date.parse(right.latest_accepted_eval_run?.created_at ?? "") - Date.parse(left.latest_accepted_eval_run?.created_at ?? ""))
}

function evalSetVersionLabel(item: SkillSummary): string {
  const name = item.primary_eval_set?.name ?? "未绑定测评集";
  const version = item.primary_eval_set?.current_version?.version_number;
  return version ? `${name} v${version}` : name;
}

function scoreValue(item: SkillSummary): number {
  const run = item.latest_accepted_eval_run;
  if (!run?.summary?.total) return -1;
  return ((run.summary.passed ?? 0) / run.summary.total) * 100;
}

function updatedTime(item: SkillSummary): number {
  const dates = [item.skill.updated_at, item.default_variant?.updated_at, item.default_variant?.current_version?.created_at, item.latest_accepted_eval_run?.created_at]
    .map((date) => Date.parse(date ?? ""))
    .filter(Number.isFinite);
  return dates.length ? Math.max(...dates) : 0;
}
