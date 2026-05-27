import { Modal } from "../components/Modal";
import type { SkillDetail } from "../types";
import { VersionUploadForm } from "./VersionUploadForm";

type UploadVersionModalProps = {
  skill: SkillDetail;
  onClose: () => void;
  onUploaded: () => Promise<void>;
};

export function UploadVersionModal({ skill, onClose, onUploaded }: UploadVersionModalProps) {
  return (
    <Modal title="上传版本" description="上传标准 Skill bundle 并追加一个不可变 SkillVersion。" onClose={onClose}>
      <VersionUploadForm skill={skill} onCancel={onClose} onUploaded={onUploaded} />
    </Modal>
  );
}
