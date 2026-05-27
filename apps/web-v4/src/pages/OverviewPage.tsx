import { ArrowRight, CheckCircle2, ExternalLink, GitCompareArrows } from "lucide-react";
import { BundleBrowser } from "../components/BundleBrowser";
import { compactText, evalSetVersionName, humanDate, scoreKind, scoreLabel, slugTitle, versionName } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import type { SkillDetail } from "../types";

type OverviewPageProps = {
  skill: SkillDetail;
  onNavigate: (next: Partial<RouteState>) => void;
};

export function OverviewPage({ skill, onNavigate }: OverviewPageProps) {
  const version = skill.summary.current_version;
  const evalSet = skill.summary.primary_eval_set;
  const run = skill.summary.latest_accepted_eval_run;
  const files = version?.bundle_files ?? [];
  const evalSetVersion = evalSetVersionName(evalSet?.current_version);
  const lifecycleLabel = skillLifecycleLabel(skill.skill.lifecycle_status);

  return (
    <div className="overview-grid">
      <section className="skill-summary-panel">
        <div className="skill-title-block">
          <dl className="skill-identity-card" aria-label="Skill 身份信息">
            <div>
              <dt>根目录</dt>
              <dd>{skill.skill.slug}/</dd>
            </div>
            <div>
              <dt>维护者</dt>
              <dd>{skill.skill.owner_ref}</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd>{lifecycleLabel}</dd>
            </div>
          </dl>
          <div className="skill-title-copy">
            <h1>{slugTitle(skill.skill.slug)}</h1>
            <p>{compactText(version?.change_summary, "这个 Skill 还没有说明。")}</p>
          </div>
        </div>
        <Metric label="当前版本" value={versionName(version)} hint={version?.created_at ? `更新于 ${humanDate(version.created_at)}` : undefined} />
        <Metric label="验证分数" value={scoreLabel(run)} tone={scoreKind(run)} hint={run?.summary?.total ? `${run.summary.passed ?? 0}/${run.summary.total} 通过` : "尚无测评"} />
        <Metric label="测评集" value={evalSet?.name ?? "未创建"} hint={evalSet?.current_version ? `当前 ${evalSetVersionName(evalSet.current_version)}` : "无版本"} />
      </section>

      <section className="primary-panel bundle-panel">
        <div className="panel-title-row">
          <h2>Skill bundle</h2>
          <div className="button-row">
            <button className="secondary-button" type="button" onClick={() => onNavigate({ tab: "versions" })}>
              版本管理
              <GitCompareArrows size={16} />
            </button>
            <button className="secondary-button" type="button" onClick={() => onNavigate({ tab: "history" })}>
              打开历史
              <ExternalLink size={16} />
            </button>
          </div>
        </div>
        <BundleBrowser files={files} rootLabel={skill.skill.slug} />
      </section>

      <aside className="reliability-panel">
        <h2>可靠性</h2>
        <div className="score-large">
          <strong className={scoreKind(run)}>{scoreLabel(run)}</strong>
          {scoreKind(run) !== "empty" ? (
            <span>
              <CheckCircle2 size={16} />
              已验证
            </span>
          ) : (
            <span>未测</span>
          )}
        </div>
        <dl>
          <div>
            <dt>测评集</dt>
            <dd>{evalSet ? `${evalSet.name} ${evalSetVersion}`.trim() : "-"}</dd>
          </div>
          <div>
            <dt>版本</dt>
            <dd>{versionName(version)}</dd>
          </div>
          <div>
            <dt>运行时间</dt>
            <dd>{humanDate(run?.created_at)}</dd>
          </div>
          <div>
            <dt>运行结果</dt>
            <dd>{run?.summary?.total ? `${run.summary.passed ?? 0}/${run.summary.total} 通过` : "-"}</dd>
          </div>
        </dl>
        <button className="secondary-button full-width" type="button" onClick={() => onNavigate(run ? { tab: "history", selectedRunId: run.id } : { tab: "evaluate" })}>
          {run ? "查看运行详情" : "进入测评"}
          <ArrowRight size={16} />
        </button>
      </aside>
    </div>
  );
}

function skillLifecycleLabel(status: string): string {
  if (status === "active") return "活跃";
  if (status === "archived") return "归档";
  return status;
}

function Metric({ label, value, hint, tone, compact }: { label: string; value: string; hint?: string; tone?: string; compact?: boolean }) {
  const valueClass = [tone, compact ? "summary-value-chip" : ""].filter(Boolean).join(" ") || undefined;
  return (
    <div className="summary-metric">
      <span>{label}</span>
      <strong className={valueClass}>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}
