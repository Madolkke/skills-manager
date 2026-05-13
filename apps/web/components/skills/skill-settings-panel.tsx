"use client";

import type { FormEvent } from "react";

import { passRate } from "@/lib/api";
import type { EvalRunRecord, SkillDetail, VariantDetail } from "@/lib/types";

type SkillSettingsPanelProps = {
  busy: boolean;
  defaultVariant: VariantDetail | null;
  latestRun: EvalRunRecord | null;
  onUpdateSkill: (event: FormEvent<HTMLFormElement>) => void;
  score: number | null;
  selectedDetail: SkillDetail;
};

export function SkillSettingsPanel({
  busy,
  defaultVariant,
  latestRun,
  onUpdateSkill,
  score,
  selectedDetail,
}: SkillSettingsPanelProps) {
  const verifiedScore = latestRun ? `${score ?? passRate(latestRun) ?? 0}%` : "未测";

  return (
    <section className="skillSettingsPanel">
      <div className="skillSettingsHeader">
        <div>
          <span>Skill settings</span>
          <h3>身份与默认分发</h3>
        </div>
        <p>这里编辑 SkillHub 入口本身；bundle 内容和评测证据仍由 variant version 与 eval run 维护。</p>
      </div>

      <form className="skillSettingsForm" key={selectedDetail.skill.id} onSubmit={onUpdateSkill}>
        <label>
          <span>Skill ID</span>
          <input name="slug" defaultValue={selectedDetail.skill.slug} required />
        </label>
        <label>
          <span>归属</span>
          <input name="owner_ref" defaultValue={selectedDetail.skill.owner_ref} required />
        </label>
        <label className="skillSettingsWide">
          <span>默认分发 variant</span>
          <select name="default_variant_id" defaultValue={defaultVariant?.id ?? ""}>
            {selectedDetail.variants.map((variant) => (
              <option key={variant.id} value={variant.id}>
                {variant.label} · {variant.tags.join(" + ") || "draft"}
              </option>
            ))}
          </select>
        </label>
        <button disabled={busy} type="submit">保存 skill 设置</button>
      </form>

      <div className="skillSettingsDistribution">
        <span>当前默认</span>
        <strong>{defaultVariant?.label ?? "暂无默认 variant"}</strong>
        <p>{defaultVariant?.summary ?? "先创建或导入一个 variant，再选择默认分发。"}</p>
        <div>
          <small>Version {defaultVariant?.current_version ? `v${defaultVariant.current_version.version_number}` : "-"}</small>
          <small>{defaultVariant?.tags.join(" + ") ?? "draft"}</small>
          <small>{verifiedScore}</small>
        </div>
      </div>
    </section>
  );
}
