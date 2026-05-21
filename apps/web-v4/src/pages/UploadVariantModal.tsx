import { Modal } from "../components/Modal";
import type { SkillDetail } from "../types";
import { VariantUploadForm } from "./VariantUploadForm";

type UploadVariantModalProps = {
  skill: SkillDetail;
  knownTags: string[];
  onClose: () => void;
  onUploaded: () => Promise<void>;
};

export function UploadVariantModal({ skill, knownTags, onClose, onUploaded }: UploadVariantModalProps) {
  return (
    <Modal title="上传版本" description="同一组 tag 会追加历史版本；新的 tag 组合会创建新变体。" onClose={onClose}>
      <VariantUploadForm skill={skill} knownTags={knownTags} onCancel={onClose} onUploaded={onUploaded} />
    </Modal>
  );
}
