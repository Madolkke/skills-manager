import type { EvalSetVersion } from "../domain/types";

const tagOptions = ["codex", "gpt5.4", "opencode", "minimax2.7"];

export function Controls({
  requestedTags,
  versions,
  evalSetVersionRef,
  onToggleTag,
  onSetVersion,
}: {
  requestedTags: string[];
  versions: EvalSetVersion[];
  evalSetVersionRef: string;
  onToggleTag: (tag: string) => void;
  onSetVersion: (versionRef: string) => void;
}) {
  return (
    <section className="control-strip" aria-label="筛选条件">
      <div className="control-group">
        <div className="control-label">请求 tags</div>
        <div className="tag-toggle-row">
          {tagOptions.map((tag) => (
            <button
              className={`chip ${requestedTags.includes(tag) ? "is-active" : ""}`}
              key={tag}
              type="button"
              onClick={() => onToggleTag(tag)}
            >
              {tag}
            </button>
          ))}
        </div>
      </div>
      <div className="control-group">
        <div className="control-label">测评集版本</div>
        <div className="segmented">
          {versions.map((version) => (
            <button
              className={evalSetVersionRef === version.id ? "is-active" : ""}
              key={version.id}
              type="button"
              onClick={() => onSetVersion(version.id)}
            >
              {version.version}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
