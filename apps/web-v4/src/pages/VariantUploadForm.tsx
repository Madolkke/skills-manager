import { useMemo, useState } from "react";
import { BundlePicker } from "../components/BundlePicker";
import { TagInput } from "../components/TagInput";
import { api, ApiError } from "../lib/api";
import { sourceFromFiles } from "../lib/bundle";
import { sameTags, variantName } from "../lib/format";
import type { SkillDetail } from "../types";

type VariantUploadFormProps = {
  skill: SkillDetail;
  knownTags: string[];
  initialTags?: string[];
  actionsClassName?: string;
  onCancel: () => void;
  onUploaded: () => Promise<void>;
};

export function VariantUploadForm({ skill, knownTags, initialTags, actionsClassName = "modal-actions", onCancel, onUploaded }: VariantUploadFormProps) {
  const [tags, setTags] = useState<string[]>(initialTags ?? skill.summary.default_variant?.tags ?? []);
  const [folderFiles, setFolderFiles] = useState<File[]>([]);
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const matchedVariant = useMemo(() => skill.variants.find((variant) => sameTags(variant.tags, tags)), [skill.variants, tags]);
  const canSubmit = !busy && tags.length > 0 && Boolean(zipFile || folderFiles.length);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const source = await sourceFromFiles(folderFiles, zipFile);
      if (matchedVariant) await api.createVariantVersion({ variant_id: matchedVariant.id, source, make_current: true });
      else await api.createVariant({ skill_id: skill.skill.id, tags, source, make_default: false });
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
      <label className="field-label">
        tag 约束
        <TagInput value={tags} suggestions={knownTags} onChange={setTags} />
      </label>
      <div className="hint-strip">{matchedVariant ? `将更新变体：${variantName(matchedVariant)}` : "将创建新的变体。"}</div>
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
