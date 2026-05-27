import { Pencil, Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import { evalSetVersionName } from "../lib/format";

type EvalSetVersionNameEditorProps = {
  version?: { version_number: number; display_name?: string | null } | null;
  evalSetName: string;
  onSave: (displayName: string | null) => Promise<void>;
};

export function EvalSetVersionNameEditor({ version, evalSetName, onSave }: EvalSetVersionNameEditorProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(version?.display_name ?? "");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setDraft(version?.display_name ?? "");
  }, [version?.display_name, version?.version_number]);

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
      <div className="evalset-name-editor">
        <input value={draft} maxLength={80} placeholder={version ? `v${version.version_number}` : "版本名称"} onChange={(event) => setDraft(event.target.value)} />
        <button className="icon-button" type="button" disabled={busy} aria-label="保存测评集版本名称" onClick={save}>
          <Save size={16} />
        </button>
        <button className="icon-button" type="button" aria-label="取消命名" onClick={() => setEditing(false)}>
          <X size={16} />
        </button>
      </div>
    );
  }

  return (
    <div className="evalset-name-row">
      <h1>{evalSetName} {evalSetVersionName(version)}</h1>
      <button className="icon-button mini" type="button" aria-label="命名测评集版本" onClick={() => setEditing(true)}>
        <Pencil size={15} />
      </button>
    </div>
  );
}

function cleanName(value: string): string | null {
  const clean = value.trim();
  return clean || null;
}
