import clsx from "clsx";
import { CheckCircle2, Grid2X2, List, X } from "lucide-react";
import { useState } from "react";
import { VersionInspector } from "../components/VersionInspector";
import { scoreKind, scoreLabel, versionName } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import type { EvalRunRecord, SkillDetail, SkillVersion } from "../types";
import { VersionUploadForm } from "./VersionUploadForm";

type VersionsPageProps = {
  skill: SkillDetail;
  selectedVersionId: string | null;
  uploadOpen: boolean;
  onNavigate: (next: Partial<RouteState>) => void;
  onUploadClose: () => void;
  onUploaded: () => Promise<void>;
};

export function VersionsPage({ skill, selectedVersionId, uploadOpen, onNavigate, onUploadClose, onUploaded }: VersionsPageProps) {
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const selected = skill.versions.find((version) => version.id === selectedVersionId) ?? skill.summary.current_version ?? skill.versions[0] ?? null;
  const evalSetName = skill.summary.primary_eval_set?.name ?? "未绑定";

  return (
    <div className={clsx("versions-layout", uploadOpen && "with-upload-panel")}>
      <section className="version-board">
        <header className="section-heading">
          <div>
            <h1>版本</h1>
            <p>SkillVersion 是不可变内容快照；运行环境标签记录在每次 EvalRun 上。</p>
          </div>
        </header>
        <div className="version-toolbar">
          <div className="filter-tabs">
            <button className="filter-button active" type="button">
              全部
              <span>{skill.versions.length}</span>
            </button>
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
          <div className="version-grid">
            {skill.versions.map((version) => (
              <VersionCard
                key={version.id}
                version={version}
                currentVersionId={skill.skill.current_version_id}
                evalSetName={evalSetName}
                latestRun={latestRunForVersion(version, skill.latest_eval_runs)}
                active={selected?.id === version.id}
                onClick={() => onNavigate({ selectedVersionId: version.id })}
              />
            ))}
          </div>
        ) : (
          <div className="version-list-view">
            {skill.versions.map((version) => (
              <VersionListRow
                key={version.id}
                version={version}
                currentVersionId={skill.skill.current_version_id}
                evalSetName={evalSetName}
                latestRun={latestRunForVersion(version, skill.latest_eval_runs)}
                active={selected?.id === version.id}
                onClick={() => onNavigate({ selectedVersionId: version.id })}
              />
            ))}
          </div>
        )}
      </section>
      {uploadOpen ? (
        <aside className="version-upload-panel" aria-label="上传新版本">
          <div className="version-upload-head">
            <div>
              <h2>上传新版本</h2>
              <p>上传标准 Skill bundle 后会追加一个不可变 SkillVersion。</p>
            </div>
            <button className="icon-button" type="button" aria-label="关闭上传面板" onClick={onUploadClose}>
              <X size={18} />
            </button>
          </div>
          <VersionUploadForm
            skill={skill}
            actionsClassName="version-upload-actions"
            onCancel={onUploadClose}
            onUploaded={onUploaded}
          />
        </aside>
      ) : null}
      <aside className="version-detail-panel">
        {selected ? (
          <VersionInspector
            skill={skill}
            version={selected}
            evalSetName={evalSetName}
            latestRun={latestRunForVersion(selected, skill.latest_eval_runs)}
          />
        ) : (
          <div className="quiet-panel">还没有版本。</div>
        )}
      </aside>
    </div>
  );
}

function VersionCard({
  version,
  currentVersionId,
  evalSetName,
  latestRun,
  active,
  onClick,
}: {
  version: SkillVersion;
  currentVersionId: string | null;
  evalSetName: string;
  latestRun: EvalRunRecord | null;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={clsx("version-card", active && "active")} type="button" onClick={onClick}>
      <div className="version-card-head">
        <h3>{versionName(version)}</h3>
        {version.id === currentVersionId ? <CheckCircle2 size={23} /> : null}
      </div>
      <span className="version-pill">{version.id === currentVersionId ? "当前版本" : "历史版本"}</span>
      <div className="version-card-metrics">
        <span>
          <small>最新得分</small>
          <strong className={scoreKind(latestRun)}>{scoreLabel(latestRun)}</strong>
        </span>
        <span>
          <small>绑定测评集</small>
          <strong>{evalSetName}</strong>
        </span>
      </div>
      <p>{version.change_summary}</p>
    </button>
  );
}

function VersionListRow({
  version,
  currentVersionId,
  evalSetName,
  latestRun,
  active,
  onClick,
}: {
  version: SkillVersion;
  currentVersionId: string | null;
  evalSetName: string;
  latestRun: EvalRunRecord | null;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={clsx("version-list-row", active && "active")} type="button" onClick={onClick}>
      <strong>{versionName(version)}</strong>
      <span className="version-pill">{version.id === currentVersionId ? "当前" : "历史"}</span>
      <span className={scoreKind(latestRun)}>{scoreLabel(latestRun)}</span>
      <span>{evalSetName}</span>
      <small>{version.change_summary}</small>
    </button>
  );
}

function latestRunForVersion(version: SkillVersion, runs: EvalRunRecord[]): EvalRunRecord | null {
  return [...runs]
    .filter((run) => run.skill_version_id === version.id)
    .sort((left, right) => Date.parse(right.created_at ?? "") - Date.parse(left.created_at ?? ""))[0] ?? null;
}
