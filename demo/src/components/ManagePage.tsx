import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import { aggregateScore, currentVersionForVariant, percent, tagsForVariant } from "../domain/scoring";
import type { AppState } from "../domain/types";
import { createBackendSkill, createBackendVariant, updateBackendSkill, updateBackendVariant } from "../store/backendState";
import { TagPill } from "./ui";

export function ManagePage({
  state,
  setState,
}: {
  state: AppState;
  setState: Dispatch<SetStateAction<AppState>>;
}) {
  const { data } = state;
  const skill = data.skills.find((item) => item.id === state.selectedSkillRef);
  const versions = data.evalSetVersions.filter((version) => {
    const corpus = data.evalCorpora.find((item) => item.id === version.corpusRef);
    return corpus?.skillRef === state.selectedSkillRef;
  });
  const version = data.evalSetVersions.find((item) => item.id === state.evalSetVersionRef) ?? versions[0];
  const variants = data.variants.filter((item) => item.skillRef === state.selectedSkillRef);
  const variantIds = variants.map((variant) => variant.id).join("|");
  const defaultVariant = skill ? variants.find((item) => item.id === skill.defaultVariantRef) ?? variants[0] : variants[0];
  const [backendError, setBackendError] = useState("");
  const [summary, setSummary] = useState(defaultVariant?.summary ?? "");
  const [skillForm, setSkillForm] = useState({
    slug: skill?.slug ?? "",
    ownerRef: skill?.ownerRef ?? "",
    defaultVariantRef: skill?.defaultVariantRef ?? "",
  });
  const [newSkillForm, setNewSkillForm] = useState({
    slug: "api-reviewer",
    ownerRef: "skillhub-lab",
    variantName: "Variant A",
    variantLabel: "API baseline",
    variantSummary: "审查 API 兼容性、鉴权边界和错误响应泄露。",
    tags: "codex",
    changeNote: "初始 API review 版本。",
  });
  const [variantForm, setVariantForm] = useState({
    name: "Variant D",
    label: "Response-leak aware",
    summary: "在默认审查中加强 token、secret、credential 出现在日志或响应体中的检查。",
    tags: "codex",
    changeNote: "针对新增测评用例强化敏感信息泄露检查，目标是提升 critical case 通过率。",
  });

  useEffect(() => {
    if (!skill) return;
    setSkillForm({
      slug: skill.slug,
      ownerRef: skill.ownerRef,
      defaultVariantRef: skill.defaultVariantRef,
    });
    setSummary(defaultVariant?.summary ?? "");
  }, [skill?.id, skill?.slug, skill?.ownerRef, skill?.defaultVariantRef, defaultVariant?.summary, variantIds]);

  if (!skill || !version) return null;

  const runApiAction = (action: Promise<AppState>) => {
    setBackendError("");
    action.then(setState).catch((error) => {
      setBackendError(error instanceof Error ? error.message : "后端写入失败");
    });
  };

  return (
    <div className="workbench">
      {backendError && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>后端写入失败</h2>
              <p>{backendError}</p>
            </div>
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Skill 入口</h2>
            <p>这里只管理分发入口和默认 Variant；版本实验放到 Experiment 页面。</p>
          </div>
          <div className="topbar-actions">
            <button
              className="ghost-button"
              type="button"
              onClick={() =>
                runApiAction(
                  updateBackendSkill({
                    skillId: skill.id,
                    slug: skillForm.slug,
                    ownerRef: skillForm.ownerRef,
                    defaultVariantRef: skillForm.defaultVariantRef,
                    view: "manage",
                  }),
                )
              }
            >
              保存入口
            </button>
            <button
              className="primary-button"
              type="button"
              onClick={() =>
                defaultVariant &&
                runApiAction(
                  updateBackendVariant({
                    variantId: defaultVariant.id,
                    summary,
                    view: "manage",
                  }),
                )
              }
            >
              保存说明
            </button>
          </div>
        </div>
        <div className="form-grid">
          <label className="field-block">
            <span>Skill slug</span>
            <input value={skillForm.slug} onChange={(event) => setSkillForm({ ...skillForm, slug: event.target.value })} />
          </label>
          <label className="field-block">
            <span>Owner</span>
            <input value={skillForm.ownerRef} onChange={(event) => setSkillForm({ ...skillForm, ownerRef: event.target.value })} />
          </label>
          <label className="field-block">
            <span>默认 Variant</span>
            <select
              value={skillForm.defaultVariantRef}
              onChange={(event) => setSkillForm({ ...skillForm, defaultVariantRef: event.target.value })}
            >
              {variants.map((variant) => (
                <option value={variant.id} key={variant.id}>
                  {variant.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field-block wide">
            <span>默认变体简介</span>
            <textarea value={summary} onChange={(event) => setSummary(event.target.value)} />
          </label>
          <div className="workbench-variants">
            {variants.map((variant) => (
              <div className="variant-mini-card" key={variant.id}>
                <strong>{variant.name}</strong>
                <span>{variant.label}</span>
                <div>
                  {tagsForVariant(data, variant).map((tag) => (
                    <TagPill key={tag} tag={tag} />
                  ))}
                </div>
                <b>{percent(aggregateScore(data, currentVersionForVariant(data, variant)?.id ?? "", version.id))}</b>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>新建 Skill</h2>
            <p>创建 Skill 时会同时创建默认 Variant、初始 VariantVersion 和空 EvalSetVersion。</p>
          </div>
          <button
            className="primary-button"
            type="button"
            onClick={() =>
              runApiAction(
                createBackendSkill({
                  ...newSkillForm,
                  tags: newSkillForm.tags.split(",").map((item) => item.trim()),
                  view: "manage",
                }),
              )
            }
          >
            创建 Skill
          </button>
        </div>
        <div className="form-grid">
          <label className="field-block">
            <span>Skill slug</span>
            <input value={newSkillForm.slug} onChange={(event) => setNewSkillForm({ ...newSkillForm, slug: event.target.value })} />
          </label>
          <label className="field-block">
            <span>Owner</span>
            <input value={newSkillForm.ownerRef} onChange={(event) => setNewSkillForm({ ...newSkillForm, ownerRef: event.target.value })} />
          </label>
          <label className="field-block">
            <span>默认 Variant 名称</span>
            <input
              value={newSkillForm.variantName}
              onChange={(event) => setNewSkillForm({ ...newSkillForm, variantName: event.target.value })}
            />
          </label>
          <label className="field-block">
            <span>默认 Variant label</span>
            <input
              value={newSkillForm.variantLabel}
              onChange={(event) => setNewSkillForm({ ...newSkillForm, variantLabel: event.target.value })}
            />
          </label>
          <label className="field-block">
            <span>Tags，用逗号分隔</span>
            <input value={newSkillForm.tags} onChange={(event) => setNewSkillForm({ ...newSkillForm, tags: event.target.value })} />
          </label>
          <label className="field-block wide">
            <span>默认 Variant 说明</span>
            <textarea
              value={newSkillForm.variantSummary}
              onChange={(event) => setNewSkillForm({ ...newSkillForm, variantSummary: event.target.value })}
            />
          </label>
          <label className="field-block wide">
            <span>初始版本说明</span>
            <input
              value={newSkillForm.changeNote}
              onChange={(event) => setNewSkillForm({ ...newSkillForm, changeNote: event.target.value })}
            />
          </label>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>新建约束变体</h2>
            <p>只有当你要维护另一组 tags 下的最优解时，才创建新 Variant。</p>
          </div>
          <button
            className="primary-button"
            type="button"
            onClick={() =>
              runApiAction(
                createBackendVariant({
                  skillId: state.selectedSkillRef,
                  ...variantForm,
                  tags: variantForm.tags.split(",").map((item) => item.trim()),
                  view: "manage",
                }),
              )
            }
          >
            创建 Variant
          </button>
        </div>
        <div className="form-grid">
          <label className="field-block">
            <span>名称</span>
            <input value={variantForm.name} onChange={(event) => setVariantForm({ ...variantForm, name: event.target.value })} />
          </label>
          <label className="field-block">
            <span>Label</span>
            <input value={variantForm.label} onChange={(event) => setVariantForm({ ...variantForm, label: event.target.value })} />
          </label>
          <label className="field-block">
            <span>Tags，用逗号分隔</span>
            <input value={variantForm.tags} onChange={(event) => setVariantForm({ ...variantForm, tags: event.target.value })} />
          </label>
          <label className="field-block wide">
            <span>变体说明</span>
            <textarea value={variantForm.summary} onChange={(event) => setVariantForm({ ...variantForm, summary: event.target.value })} />
          </label>
          <label className="field-block wide">
            <span>变更来源说明，可选</span>
            <input
              value={variantForm.changeNote}
              onChange={(event) => setVariantForm({ ...variantForm, changeNote: event.target.value })}
            />
          </label>
        </div>
      </section>
    </div>
  );
}
