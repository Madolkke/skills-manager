import { X } from "lucide-react";
import { useMemo, useState } from "react";

type TagInputProps = {
  value: string[];
  suggestions?: string[];
  placeholder?: string;
  onChange: (tags: string[]) => void;
};

export function TagInput({ value, suggestions = [], placeholder = "输入 tag 后按 Enter", onChange }: TagInputProps) {
  const [draft, setDraft] = useState("");
  const available = useMemo(
    () => suggestions.filter((tag) => !value.includes(tag) && tag.toLowerCase().includes(draft.toLowerCase())).slice(0, 6),
    [draft, suggestions, value],
  );

  function addTag(raw: string) {
    const tag = raw.trim();
    if (!tag || value.includes(tag)) return;
    onChange([...value, tag]);
    setDraft("");
  }

  return (
    <div className="tag-input">
      <div className="tag-box">
        {value.map((tag) => (
          <span className="tag-chip editable" key={tag}>
            {tag}
            <button type="button" onClick={() => onChange(value.filter((item) => item !== tag))} aria-label={`移除 ${tag}`}>
              <X size={13} />
            </button>
          </span>
        ))}
        <input
          value={draft}
          placeholder={value.length === 0 ? placeholder : ""}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === ",") {
              event.preventDefault();
              addTag(draft);
            }
            if (event.key === "Backspace" && !draft && value.length > 0) onChange(value.slice(0, -1));
          }}
          onBlur={() => addTag(draft)}
        />
      </div>
      {available.length > 0 ? (
        <div className="tag-suggestions">
          {available.map((tag) => (
            <button type="button" key={tag} onMouseDown={(event) => event.preventDefault()} onClick={() => addTag(tag)}>
              {tag}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
