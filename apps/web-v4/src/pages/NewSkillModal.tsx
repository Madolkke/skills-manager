import { useState } from "react";
import { BundlePicker } from "../components/BundlePicker";
import { Modal } from "../components/Modal";
import { api, ApiError } from "../lib/api";
import { sourceFromFiles } from "../lib/bundle";

type NewSkillModalProps = {
  actor: string;
  onClose: () => void;
  onCreated: (skillId: string) => Promise<void>;
};

export function NewSkillModal({ actor, onClose, onCreated }: NewSkillModalProps) {
  const [folderFiles, setFolderFiles] = useState<File[]>([]);
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const source = await sourceFromFiles(folderFiles, zipFile);
      const created = await api.importSkill({ owner_ref: actor, source });
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
          <button className="primary-button" type="button" disabled={busy || (!zipFile && folderFiles.length === 0)} onClick={submit}>
            {busy ? "创建中..." : "创建 Skill"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
