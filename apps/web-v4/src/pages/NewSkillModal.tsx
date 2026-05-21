import { useState } from "react";
import { BundlePicker } from "../components/BundlePicker";
import { Modal } from "../components/Modal";
import { TagInput } from "../components/TagInput";
import { api, ApiError } from "../lib/api";
import { sourceFromFiles } from "../lib/bundle";

type NewSkillModalProps = {
  actor: string;
  knownTags: string[];
  onClose: () => void;
  onCreated: (skillId: string) => Promise<void>;
};

export function NewSkillModal({ actor, knownTags, onClose, onCreated }: NewSkillModalProps) {
  const [tags, setTags] = useState<string[]>([]);
  const [folderFiles, setFolderFiles] = useState<File[]>([]);
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const source = await sourceFromFiles(folderFiles, zipFile);
      const created = await api.importSkill({ owner_ref: actor, tags, source });
      await onCreated(created.skill_id);
    } catch (caught) {
      setError(caught instanceof ApiError || caught instanceof Error ? caught.message : "创建失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="新建 Skill" description="上传标准 Skill bundle，名称和说明会从 SKILL.md frontmatter 读取。" onClose={onClose}>
      <div className="form-stack">
        {error ? <div className="form-error">{error}</div> : null}
        <label className="field-label">
          约束 tag
          <TagInput value={tags} suggestions={knownTags} onChange={setTags} placeholder="例如 codex，按 Enter 添加" />
        </label>
        <BundlePicker
          onFiles={(nextFolderFiles, nextZipFile) => {
            setFolderFiles(nextFolderFiles);
            setZipFile(nextZipFile);
          }}
        />
        <div className="modal-actions">
          <button className="secondary-button" type="button" onClick={onClose}>
            取消
          </button>
          <button className="primary-button" type="button" disabled={busy || tags.length === 0 || (!zipFile && folderFiles.length === 0)} onClick={submit}>
            {busy ? "创建中..." : "创建 Skill"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
