import { useState } from "react";
import { BundlePicker } from "../components/BundlePicker";
import { api, ApiError } from "../lib/api";
import { sourceFromFiles } from "../lib/bundle";
import type { SkillDetail } from "../types";

type VersionUploadFormProps = {
  skill: SkillDetail;
  actionsClassName?: string;
  onCancel: () => void;
  onUploaded: () => Promise<void>;
};

export function VersionUploadForm({ skill, actionsClassName = "modal-actions", onCancel, onUploaded }: VersionUploadFormProps) {
  const [folderFiles, setFolderFiles] = useState<File[]>([]);
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canSubmit = !busy && Boolean(zipFile || folderFiles.length);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const source = await sourceFromFiles(folderFiles, zipFile);
      await api.createSkillVersion({ skill_id: skill.skill.id, source, make_current: true, display_name: cleanName(displayName) });
      await onUploaded();
    } catch (caught) {
      setError(caught instanceof ApiError || caught instanceof Error ? caught.message : "上传失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="form-stack">
      {error ? <div className="form-error">{error}</div> : null}
      <div className="hint-strip">将追加新的 SkillVersion，并设置为当前版本。</div>
      <label className="field-label">
        <span>版本名称</span>
        <input value={displayName} maxLength={80} placeholder={`例如 ${skill.skill.slug} stable`} onChange={(event) => setDisplayName(event.target.value)} />
      </label>
      <BundlePicker
        onFiles={(nextFolderFiles, nextZipFile) => {
          setFolderFiles(nextFolderFiles);
          setZipFile(nextZipFile);
        }}
      />
      <div className={actionsClassName}>
        <button className="secondary-button" type="button" onClick={onCancel}>
          取消
        </button>
        <button className="primary-button" type="button" disabled={!canSubmit} onClick={submit}>
          {busy ? "上传中..." : "确认上传"}
        </button>
      </div>
    </div>
  );
}

function cleanName(value: string): string | undefined {
  const clean = value.trim();
  return clean || undefined;
}
