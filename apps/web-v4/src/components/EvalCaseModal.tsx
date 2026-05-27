import { useState } from "react";
import { Modal } from "./Modal";
import type { EvalSetCase } from "../types";

export type EvalCaseFormData = {
  title: string;
  input_text: string;
  expected_output: string;
  notes: string;
  eval_set_version_display_name: string;
};

type EvalCaseModalProps = {
  caseItem?: EvalSetCase | null;
  busy: boolean;
  onClose: () => void;
  onSubmit: (data: EvalCaseFormData) => Promise<void>;
};

export function EvalCaseModal({ caseItem, busy, onClose, onSubmit }: EvalCaseModalProps) {
  const [form, setForm] = useState<EvalCaseFormData>(() => ({
    title: caseItem?.case.title ?? "",
    input_text: caseItem?.case_version.input_artifact.content_text ?? "",
    expected_output: caseItem?.case_version.expected_output_artifact.content_text ?? "",
    notes: caseItem?.case_version.notes ?? "",
    eval_set_version_display_name: "",
  }));
  const editing = Boolean(caseItem);

  return (
    <Modal title={editing ? "编辑 case" : "添加 case"} description="保存后会形成 case version；已有运行记录的测评集会保留历史快照。" onClose={onClose}>
      <form
        className="form-stack"
        onSubmit={(event) => {
          event.preventDefault();
          void onSubmit(form);
        }}
      >
        <label className="field-label">
          标题
          <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="PR: missing owner filter" required />
        </label>
        <label className="field-label">
          Input
          <textarea value={form.input_text} onChange={(event) => setForm({ ...form, input_text: event.target.value })} placeholder="代码 diff、用户请求、上下文" required />
        </label>
        <label className="field-label">
          Expected output
          <textarea value={form.expected_output} onChange={(event) => setForm({ ...form, expected_output: event.target.value })} placeholder="应该指出什么" required />
        </label>
        <label className="field-label">
          Notes
          <input value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} placeholder="来源或维护说明，可选" />
        </label>
        <label className="field-label">
          测评集版本名称（可选）
          <input
            value={form.eval_set_version_display_name}
            maxLength={80}
            onChange={(event) => setForm({ ...form, eval_set_version_display_name: event.target.value })}
            placeholder={editing ? "例如 tightened expected output" : "例如 first regression cases"}
          />
        </label>
        <div className="modal-actions">
          <button className="secondary-button" type="button" onClick={onClose}>
            取消
          </button>
          <button className="primary-button" type="submit" disabled={busy}>
            {busy ? "保存中..." : editing ? "保存 case version" : "添加 case"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
