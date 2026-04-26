import type { AppData } from "../domain/types";
import { aggregateScore, currentVersionForVariant, latestVersionForSkill } from "../domain/scoring";
import { TagPill } from "./ui";

export function HubPage({
  data,
  onOpenSkill,
}: {
  data: AppData;
  onOpenSkill: (skillRef: string) => void;
}) {
  return (
    <section className="panel hub-panel">
      <div className="panel-header">
        <div>
          <h2>SkillHub</h2>
          <p>主页保持传统 SkillHub 的浏览体验，测评证据作为摘要露出。点击进入后再展开变体图和测评矩阵。</p>
        </div>
        <input className="search-input" value="code review" aria-label="搜索 skills" readOnly />
      </div>
      <div className="hub-grid">
        {data.skills.map((skill) => {
          const variants = data.variants.filter((item) => item.skillRef === skill.id);
          const defaultVariant = data.variants.find((item) => item.id === skill.defaultVariantRef) ?? variants[0];
          const version = latestVersionForSkill(data, skill.id);
          const defaultVersion = defaultVariant ? currentVersionForVariant(data, defaultVariant) : undefined;
          const defaultScore = version && defaultVersion ? aggregateScore(data, defaultVersion.id, version.id) : null;
          const tags = Array.from(
            new Set(
              variants.flatMap((variant) => data.tagSets.find((tagSet) => tagSet.id === variant.tagSetRef)?.tags ?? []),
            ),
          );
          const cases = version?.caseRefs.length ?? 0;
          return (
            <article className="skill-card" key={skill.id} onClick={() => onOpenSkill(skill.id)}>
              <div className="skill-card-head">
                <div>
                  <h2>{skill.slug}</h2>
                  <p>{defaultVariant?.summary ?? "这个 skill 还没有注册默认变体。"}</p>
                </div>
                <button className="primary-button" type="button">
                  查看
                </button>
              </div>
              <div className="skill-card-tags">
                {(tags.length ? tags : ["pending"]).map((tag) => (
                  <TagPill key={tag} tag={tag} />
                ))}
              </div>
              <div className="skill-card-metrics">
                <div>
                  <strong>{variants.length}</strong>
                  <span>variants</span>
                </div>
                <div>
                  <strong>{cases}</strong>
                  <span>eval cases</span>
                </div>
                <div>
                  <strong>{defaultScore === null || defaultScore === undefined ? "未运行" : `${Math.round(defaultScore * 100)}%`}</strong>
                  <span>default pass</span>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
