import { useState } from "react";
import { BundleEditor } from "../components/BundleEditor";
import { api, ApiError } from "../lib/api";
import type { BundleFile, BundleSource, SkillDetail, SkillVersion } from "../types";

type SkillEditFormProps = {
  skill: SkillDetail;
  version: SkillVersion;
  actionsClassName?: string;
  onCancel: () => void;
  onSaved: () => Promise<void>;
};

const ENTRY_PATH = "SKILL.md";

export function SkillEditForm({ skill, version, actionsClassName = "modal-actions", onCancel, onSaved }: SkillEditFormProps) {
  const files = version.bundle_files ?? [];
  const entryFile = version.bundle_files?.find((file) => file.path === ENTRY_PATH) ?? null;
  const [drafts, setDrafts] = useState(() => textDrafts(files));
  const [displayName, setDisplayName] = useState("");
  const [changeSummary, setChangeSummary] = useState(`基于 ${versionLabel(version)} 编辑 Skill 内容。`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const missingBinaryContent = files.some((file) => file.binary && !file.content_base64);
  const canSubmit = !busy && files.length > 0 && Boolean(entryFile && !entryFile.binary && drafts[ENTRY_PATH]?.trim() && changeSummary.trim() && !missingBinaryContent);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.createSkillVersion({
        skill_id: skill.skill.id,
        source: sourceFromBundle(files, drafts, skill.skill.slug),
        make_current: true,
        display_name: cleanOptional(displayName),
        change_summary: changeSummary.trim(),
      });
      await onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError || caught instanceof Error ? caught.message : "保存失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="form-stack skill-edit-form">
      {error ? <div className="form-error">{error}</div> : null}
      <div className="hint-strip">保存后会追加新的 SkillVersion，并设置为当前版本。</div>
      {!entryFile ? <div className="form-error">当前 bundle 找不到根目录 SKILL.md，无法使用页面编辑。</div> : null}
      {entryFile?.binary ? <div className="form-error">SKILL.md 不是可编辑文本文件。</div> : null}
      {missingBinaryContent ? <div className="form-error">当前 bundle 有缺少内容的二进制文件，无法从页面编辑保存。</div> : null}
      <label className="field-label">
        <span>版本名称</span>
        <input value={displayName} maxLength={80} placeholder={`例如 ${skill.skill.slug} edited`} onChange={(event) => setDisplayName(event.target.value)} />
      </label>
      <label className="field-label">
        <span>版本说明</span>
        <input value={changeSummary} maxLength={500} onChange={(event) => setChangeSummary(event.target.value)} />
      </label>
      <BundleEditor files={files} drafts={drafts} rootLabel={skill.skill.slug} onDraftChange={(path, content) => setDrafts((current) => ({ ...current, [path]: content }))} />
      <div className={actionsClassName}>
        <button className="secondary-button" type="button" onClick={onCancel}>
          取消
        </button>
        <button className="primary-button" type="button" disabled={!canSubmit} onClick={submit}>
          {busy ? "保存中..." : "保存为新版本"}
        </button>
      </div>
    </div>
  );
}

function sourceFromBundle(files: BundleFile[], drafts: Record<string, string>, slug: string): BundleSource {
  return {
    kind: "files",
    name: slug,
    files: files.map((file) => filePayload(file, drafts)),
  };
}

function filePayload(file: BundleFile, drafts: Record<string, string>): { path: string; content_text?: string; content_base64?: string } {
  if (!file.binary) return { path: file.path, content_text: drafts[file.path] ?? file.content_text ?? "" };
  if (file.content_base64) return { path: file.path, content_base64: file.content_base64 };
  throw new Error(`当前 bundle 的二进制文件 ${file.path} 缺少内容，无法从页面编辑保存。`);
}

function textDrafts(files: BundleFile[]): Record<string, string> {
  return Object.fromEntries(files.filter((file) => !file.binary).map((file) => [file.path, file.content_text ?? ""]));
}

function cleanOptional(value: string): string | undefined {
  const clean = value.trim();
  return clean || undefined;
}

function versionLabel(version: SkillVersion): string {
  return version.display_name?.trim() || `v${version.version_number}`;
}
