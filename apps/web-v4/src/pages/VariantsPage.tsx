import clsx from "clsx";
import { CheckCircle2, Grid2X2, List, X } from "lucide-react";
import { useMemo, useState } from "react";
import { VariantInspector } from "../components/VariantInspector";
import { scoreKind, scoreLabel, variantName, versionName } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import type { EvalRunRecord, SkillDetail, VariantDetail } from "../types";
import { VariantUploadForm } from "./VariantUploadForm";

type VariantsPageProps = {
  skill: SkillDetail;
  selectedVariantId: string | null;
  knownTags: string[];
  uploadOpen: boolean;
  onNavigate: (next: Partial<RouteState>) => void;
  onUploadClose: () => void;
  onUploaded: () => Promise<void>;
};

export function VariantsPage({ skill, selectedVariantId, knownTags, uploadOpen, onNavigate, onUploadClose, onUploaded }: VariantsPageProps) {
  const [activeTag, setActiveTag] = useState("all");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const tags = useMemo(() => variantFilters(skill.variants), [skill.variants]);
  const variants = activeTag === "all" ? skill.variants : skill.variants.filter((variant) => variant.tags.includes(activeTag));
  const selected = variants.find((variant) => variant.id === selectedVariantId) ?? variants[0] ?? null;
  const evalSetName = skill.summary.primary_eval_set?.name ?? "未绑定";

  return (
    <div className={clsx("variants-layout", uploadOpen && "with-upload-panel")}>
      <section className="variant-board">
        <header className="section-heading">
          <div>
            <h1>变体</h1>
            <p>变体由 tag 约束组合定义，每个组合维护自己的当前版本和历史版本。</p>
          </div>
        </header>
        <div className="variant-toolbar">
          <div className="filter-tabs">
            {tags.map((tag) => (
              <button className={clsx("filter-button", activeTag === tag.value && "active")} type="button" key={tag.value} onClick={() => setActiveTag(tag.value)}>
                {tag.label}
                <span>{tag.count}</span>
              </button>
            ))}
          </div>
          <div className="view-tools">
            <button className={clsx("icon-button", viewMode === "grid" && "active")} type="button" aria-label="卡片视图" onClick={() => setViewMode("grid")}>
              <Grid2X2 size={18} />
            </button>
            <button className={clsx("icon-button", viewMode === "list" && "active")} type="button" aria-label="列表视图" onClick={() => setViewMode("list")}>
              <List size={18} />
            </button>
          </div>
        </div>
        {viewMode === "grid" ? (
          <div className="variant-grid">
            {variants.map((variant) => (
              <VariantCard
                key={variant.id}
                variant={variant}
                evalSetName={evalSetName}
                latestRun={latestRunForVariant(variant, skill.latest_eval_runs)}
                active={selected?.id === variant.id}
                onClick={() => onNavigate({ selectedVariantId: variant.id })}
              />
            ))}
          </div>
        ) : (
          <div className="variant-list-view">
            {variants.map((variant) => (
              <VariantListRow
                key={variant.id}
                variant={variant}
                evalSetName={evalSetName}
                latestRun={latestRunForVariant(variant, skill.latest_eval_runs)}
                active={selected?.id === variant.id}
                onClick={() => onNavigate({ selectedVariantId: variant.id })}
              />
            ))}
          </div>
        )}
      </section>
      {uploadOpen ? (
        <aside className="variant-upload-panel" aria-label="上传新版本">
          <div className="variant-upload-head">
            <div>
              <h2>上传新版本</h2>
              <p>默认使用当前选中变体的 tags；修改 tags 会创建或更新对应变体。</p>
            </div>
            <button className="icon-button" type="button" aria-label="关闭上传面板" onClick={onUploadClose}>
              <X size={18} />
            </button>
          </div>
          <VariantUploadForm
            key={selected?.id ?? "new-variant"}
            skill={skill}
            knownTags={knownTags}
            initialTags={selected?.tags}
            actionsClassName="variant-upload-actions"
            onCancel={onUploadClose}
            onUploaded={onUploaded}
          />
        </aside>
      ) : null}
      <aside className="variant-detail-panel">
        {selected ? (
          <VariantInspector
            variant={selected}
            evalSetName={evalSetName}
            latestRun={latestRunForVariant(selected, skill.latest_eval_runs)}
          />
        ) : (
          <div className="quiet-panel">还没有变体。</div>
        )}
      </aside>
    </div>
  );
}

function VariantCard({
  variant,
  evalSetName,
  latestRun,
  active,
  onClick,
}: {
  variant: VariantDetail;
  evalSetName: string;
  latestRun: EvalRunRecord | null;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={clsx("variant-card", active && "active")} type="button" onClick={onClick}>
      <div className="variant-card-head">
        <h3>{variantName(variant)}</h3>
        {active ? <CheckCircle2 size={23} /> : null}
      </div>
      <span className="version-pill">当前 {versionName(variant.current_version)}</span>
      <div className="variant-card-metrics">
        <span>
          <small>最新得分</small>
          <strong className={scoreKind(latestRun)}>{scoreLabel(latestRun)}</strong>
        </span>
        <span>
          <small>绑定测评集</small>
          <strong>{evalSetName}</strong>
        </span>
      </div>
      <VersionLine variant={variant} />
    </button>
  );
}

function VariantListRow({
  variant,
  evalSetName,
  latestRun,
  active,
  onClick,
}: {
  variant: VariantDetail;
  evalSetName: string;
  latestRun: EvalRunRecord | null;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={clsx("variant-list-row", active && "active")} type="button" onClick={onClick}>
      <strong>{variantName(variant)}</strong>
      <span className="version-pill">当前 {versionName(variant.current_version)}</span>
      <span className={scoreKind(latestRun)}>{scoreLabel(latestRun)}</span>
      <span>{evalSetName}</span>
      <small>{variant.versions.length} 个历史版本</small>
    </button>
  );
}

function VersionLine({ variant }: { variant: VariantDetail }) {
  return (
    <div className="version-line">
      {variant.versions.map((version) => (
        <span className={version.id === variant.current_version_id ? "active" : ""} key={version.id}>
          v{version.version_number}
        </span>
      ))}
    </div>
  );
}

function latestRunForVariant(variant: VariantDetail, runs: EvalRunRecord[]): EvalRunRecord | null {
  const versionIds = new Set(variant.versions.map((version) => version.id));
  return [...runs]
    .filter((run) => versionIds.has(run.variant_version_id))
    .sort((left, right) => Date.parse(right.created_at ?? "") - Date.parse(left.created_at ?? ""))[0] ?? null;
}

function variantFilters(variants: VariantDetail[]) {
  const counts = new Map<string, number>();
  for (const variant of variants) for (const tag of variant.tags) counts.set(tag, (counts.get(tag) ?? 0) + 1);
  return [
    { value: "all", label: "全部", count: variants.length },
    ...Array.from(counts, ([value, count]) => ({ value, label: value, count })).sort((left, right) => right.count - left.count),
  ];
}
