import clsx from "clsx";
import { FileText, Pencil, Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import { BundleBrowser } from "../components/BundleBrowser";
import { BundleDiffPanel } from "../components/BundleDiffPanel";
import { api, ApiError } from "../lib/api";
import { compactText, humanDate, scoreKind, scoreLabel, versionName } from "../lib/format";
import { compactDigest } from "../lib/history";
import type { RouteState } from "../lib/navigation";
import type { EvalRunRecord, SkillDetail, SkillVersion, ToastState } from "../types";
import { VersionUploadForm } from "./VersionUploadForm";

type VersionsPageProps = {
  skill: SkillDetail;
  selectedVersionId: string | null;
  uploadOpen: boolean;
  onNavigate: (next: Partial<RouteState>) => void;
  onUploadClose: () => void;
  onUploaded: () => Promise<void>;
  onRefresh: () => Promise<void>;
  onToast: (toast: ToastState) => void;
};

export function VersionsPage({ skill, selectedVersionId, uploadOpen, onNavigate, onUploadClose, onUploaded, onRefresh, onToast }: VersionsPageProps) {
  const selected = skill.versions.find((version) => version.id === selectedVersionId) ?? skill.summary.current_version ?? skill.versions[0] ?? null;
  const previous = selected ? previousSkillVersion(skill.versions, selected) : null;
  const evalSetName = skill.summary.primary_eval_set?.name ?? "未绑定";
  const latestRun = selected ? latestRunForVersion(selected, skill.latest_eval_runs) : null;
  const files = selected?.bundle_files ?? [];

  async function renameSelected(displayName: string | null) {
    if (!selected) return;
    try {
      await api.updateSkillVersionName(selected.id, displayName);
      onToast({ tone: "success", message: "Skill 版本名称已更新。" });
      await onRefresh();
    } catch (caught) {
      onToast({ tone: "danger", message: errorMessage(caught) });
    }
  }

  if (!selected) return <div className="quiet-panel">还没有版本。</div>;

  return (
    <div className={clsx("versions-workspace", uploadOpen && "with-upload-panel")}>
      <section className="skill-summary-panel version-summary-panel">
        <div className="skill-title-block">
          <dl className="skill-identity-card" aria-label="版本身份信息">
            <div>
              <dt>Skill</dt>
              <dd>{skill.skill.slug}/</dd>
            </div>
            <div>
              <dt>内容 digest</dt>
              <dd>{compactDigest(selected.content_digest)}</dd>
            </div>
            <div>
              <dt>创建者</dt>
              <dd>{selected.created_by}</dd>
            </div>
          </dl>
          <div className="skill-title-copy">
            <VersionNameEditor version={selected} onSave={renameSelected} />
            <p>{compactText(selected.change_summary, "这个版本还没有说明。")}</p>
          </div>
        </div>
        <Metric label="节点" value={versionName(selected)} hint={selected.id === skill.skill.current_version_id ? "当前版本" : "历史版本"} />
        <Metric label="最新得分" value={scoreLabel(latestRun)} tone={scoreKind(latestRun)} hint={latestRun?.summary?.total ? `${latestRun.summary.passed ?? 0}/${latestRun.summary.total} 通过` : "尚无测评"} />
        <Metric label="测评集" value={evalSetName} hint="运行环境保存在 EvalRun" compact />
      </section>

      <section className="version-node-strip" aria-label="Skill 版本节点">
        {skill.versions.map((version) => (
          <button
            className={clsx("version-node", selected.id === version.id && "active")}
            type="button"
            key={version.id}
            onClick={() => onNavigate({ selectedVersionId: version.id })}
          >
            <span>{versionName(version)}</span>
            <small>{version.id === skill.skill.current_version_id ? "当前" : humanDate(version.created_at)}</small>
          </button>
        ))}
      </section>

      {uploadOpen ? (
        <section className="version-upload-panel" aria-label="上传新版本">
          <div className="version-upload-head">
            <div>
              <h2>上传新版本</h2>
              <p>上传标准 Skill bundle 后会追加一个不可变 SkillVersion。</p>
            </div>
            <button className="icon-button" type="button" aria-label="关闭上传面板" onClick={onUploadClose}>
              <X size={18} />
            </button>
          </div>
          <VersionUploadForm skill={skill} actionsClassName="version-upload-actions" onCancel={onUploadClose} onUploaded={onUploaded} />
        </section>
      ) : null}

      <section className="version-files-panel">
        <div className="panel-title-row">
          <h2>Bundle 内容</h2>
          <span className="version-meta-line">
            <FileText size={16} />
            {files.length} 个文件 · {humanDate(selected.created_at)}
          </span>
        </div>
        <BundleBrowser files={files} rootLabel={skill.skill.slug} />
      </section>

      <BundleDiffPanel current={selected} previous={previous} />
    </div>
  );
}

function VersionNameEditor({ version, onSave }: { version: SkillVersion; onSave: (displayName: string | null) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(version.display_name ?? "");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setDraft(version.display_name ?? "");
    setEditing(false);
  }, [version.id, version.display_name]);

  async function save() {
    setBusy(true);
    try {
      await onSave(cleanName(draft));
      setEditing(false);
    } finally {
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <div className="version-name-editor">
        <input value={draft} maxLength={80} placeholder={`v${version.version_number}`} onChange={(event) => setDraft(event.target.value)} />
        <button className="icon-button" type="button" aria-label="保存版本名称" disabled={busy} onClick={save}>
          <Save size={17} />
        </button>
        <button className="icon-button" type="button" aria-label="取消命名" onClick={() => setEditing(false)}>
          <X size={17} />
        </button>
      </div>
    );
  }

  return (
    <div className="version-title-row">
      <h1>{versionName(version)}</h1>
      {version.display_name ? <span className="version-number-badge">v{version.version_number}</span> : null}
      <button className="icon-button" type="button" aria-label="命名 Skill 版本" onClick={() => setEditing(true)}>
        <Pencil size={17} />
      </button>
    </div>
  );
}

function Metric({ label, value, hint, tone, compact }: { label: string; value: string; hint?: string; tone?: string; compact?: boolean }) {
  const valueClass = [tone, compact ? "summary-value-chip" : ""].filter(Boolean).join(" ") || undefined;
  return (
    <div className="summary-metric">
      <span>{label}</span>
      <strong className={valueClass}>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}

function previousSkillVersion(versions: SkillVersion[], current: SkillVersion): SkillVersion | null {
  return [...versions]
    .filter((version) => version.version_number < current.version_number)
    .sort((left, right) => right.version_number - left.version_number)[0] ?? null;
}

function latestRunForVersion(version: SkillVersion, runs: EvalRunRecord[]): EvalRunRecord | null {
  return [...runs]
    .filter((run) => run.skill_version_id === version.id)
    .sort((left, right) => Date.parse(right.created_at ?? "") - Date.parse(left.created_at ?? ""))[0] ?? null;
}

function cleanName(value: string): string | null {
  const clean = value.trim();
  return clean || null;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "操作失败。";
}
