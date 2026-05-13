"use client";

import type { FormEvent } from "react";
import { useState } from "react";

type ImportPreview = {
  tone: "good" | "bad" | "neutral";
  title: string;
  detail: string;
} | null;

type SkillLaunchpadProps = {
  busy: boolean;
  importPreview: ImportPreview;
  onCreateSkill: (event: FormEvent<HTMLFormElement>) => void;
  onImportSkill: (event: FormEvent<HTMLFormElement>) => void;
  onRefreshImportPreview: (event: FormEvent<HTMLFormElement>) => void;
};

const launchpadFolderInputProps = {
  directory: "",
  multiple: true,
  name: "folder_files",
  type: "file",
  webkitdirectory: "",
} as const;

export function SkillLaunchpad({
  busy,
  importPreview,
  onCreateSkill,
  onImportSkill,
  onRefreshImportPreview,
}: SkillLaunchpadProps) {
  const [mode, setMode] = useState<"import" | "create">("import");

  return (
    <section className="skillLaunchpad">
      <div className="skillLaunchpadIntro">
        <span>首次接入</span>
        <h2>把第一个 Skill 接进来</h2>
        <p>导入标准 Skill bundle 是最可信的起点；也可以先创建草稿 skill，再补 bundle、case 和测评证据。</p>
        <div className="skillLaunchpadSegments" aria-label="Skill 接入方式">
          <button className={mode === "import" ? "skillLaunchpadSegmentActive" : ""} onClick={() => setMode("import")} type="button">
            导入 bundle
          </button>
          <button className={mode === "create" ? "skillLaunchpadSegmentActive" : ""} onClick={() => setMode("create")} type="button">
            新建 skill
          </button>
        </div>
      </div>

      {mode === "import" ? (
        <form className="skillLaunchpadForm" onChange={onRefreshImportPreview} onSubmit={onImportSkill}>
          <label>
            <span>归属</span>
            <input name="owner_ref" placeholder="skillhub-lab" required />
          </label>
          <label>
            <span>约束标签</span>
            <input name="tags" placeholder="codex, gpt5.4" required />
          </label>
          <label>
            <span>变体名称</span>
            <input defaultValue="Imported" name="variant_label" placeholder="Imported" />
          </label>
          <label className="skillLaunchpadDrop">
            <span>Skill 文件夹</span>
            <input {...launchpadFolderInputProps} />
          </label>
          <label className="skillLaunchpadDrop">
            <span>或 zip</span>
            <input accept=".zip,application/zip" name="zip_file" type="file" />
          </label>
          {importPreview ? (
            <div className={`importPreview importPreview-${importPreview.tone}`}>
              <strong>{importPreview.title}</strong>
              <span>{importPreview.detail}</span>
            </div>
          ) : null}
          <button disabled={busy || importPreview?.tone === "bad"} type="submit">
            导入并创建 skill
          </button>
        </form>
      ) : (
        <form className="skillLaunchpadForm" onSubmit={onCreateSkill}>
          <label>
            <span>Skill ID</span>
            <input name="slug" placeholder="security-reviewer" required />
          </label>
          <label>
            <span>归属</span>
            <input name="owner_ref" placeholder="skillhub-lab" required />
          </label>
          <label>
            <span>初始变体</span>
            <input name="variant_label" placeholder="Baseline" required />
          </label>
          <label>
            <span>约束标签</span>
            <input name="tags" placeholder="codex, gpt5.4" required />
          </label>
          <label className="skillLaunchpadFull">
            <span>简介</span>
            <textarea name="summary" placeholder="这个 skill 解决什么问题" required />
          </label>
          <label className="skillLaunchpadFull">
            <span>初始版本说明</span>
            <textarea name="change_summary" placeholder="初始版本说明" required />
          </label>
          <button disabled={busy} type="submit">
            创建 skill
          </button>
        </form>
      )}

      <div className="skillLaunchpadChecklist">
        <strong>证据闭环</strong>
        <span>1. 导入 bundle 或创建草稿 skill</span>
        <span>2. 补充可复用 eval cases</span>
        <span>3. 记录首轮 pass / fail run</span>
        <span>4. 接受一次 exact verification</span>
      </div>
    </section>
  );
}
