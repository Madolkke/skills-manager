import Link from "next/link";

import { passRate, verificationLabel } from "@/lib/api";
import { formatDate, percent, shortId } from "@/lib/format";
import type { EvalRunDetail, EvalSetVersionDetail, SkillDetail, SkillSummary, VariantDetail } from "@/lib/types";
import { Badge, Metric, Section } from "./chrome";

export function SkillHubList({ skills }: { skills: SkillSummary[] }) {
  return (
    <div className="hubList" role="list">
      <div className="hubListHeader">
        <span>Skill</span>
        <span>Default variant</span>
        <span>Verification</span>
      </div>
      {skills.map((summary) => {
        const variant = summary.default_variant;
        const run = summary.latest_accepted_eval_run;
        const rate = run ? passRate(run) : null;
        return (
          <Link className="hubRow" href={`/skills/${summary.skill.id}`} key={summary.skill.id} role="listitem">
            <div className="skillCell">
              <div className="rowTitle">
                <strong>{summary.skill.slug}</strong>
                <Badge tone={run ? (rate === 100 ? "good" : "bad") : "neutral"}>
                  {summary.skill.lifecycle_status}
                </Badge>
              </div>
              <p>{variant?.summary ?? "No default variant configured."}</p>
            </div>
            <div className="variantCell">
              <strong>{variant?.label ?? "No variant"}</strong>
              <span>{variant?.tags.join(" + ") ?? "no tags"}</span>
              <small>{variant?.current_version ? `current v${variant.current_version.version_number}` : "no version"}</small>
            </div>
            <div className="scoreCell">
              <span className={`scoreRing ${run ? "scoreRingOn" : ""}`}>{run ? percent(rate) : "-"}</span>
              <div>
                <strong>{verificationLabel(summary)}</strong>
                <small>{run?.strategy ?? "no eval run"}</small>
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}

export function VariantPageView({
  skill,
  variant,
  selectedVersionId,
}: {
  skill: SkillDetail;
  variant: VariantDetail;
  selectedVersionId?: string;
}) {
  const selectedVersion =
    variant.versions.find((version) => version.id === selectedVersionId) ?? variant.current_version ?? variant.versions[0];
  const evalSet = skill.eval_sets[0];
  const latestRun = skill.latest_eval_runs.find((run) => run.variant_version_id === selectedVersion?.id) ?? skill.latest_eval_runs[0];
  const rate = latestRun ? passRate(latestRun) : null;

  return (
    <div className="stack">
      <section className="heroPanel">
        <div>
          <p className="eyebrow">{skill.skill.slug}</p>
          <h1>{variant.label}</h1>
          <p>{variant.summary}</p>
          <div className="tagLine">
            {variant.tags.map((tag) => (
              <Badge key={tag} tone="blue">{tag}</Badge>
            ))}
          </div>
        </div>
        <div className="metricGrid">
          <Metric label="Selected version" value={`v${selectedVersion?.version_number ?? "-"}`} hint={shortId(selectedVersion?.id)} tone="blue" />
          <Metric label="Verification" value={percent(rate)} hint={latestRun?.strategy ?? "Unverified"} tone={rate === 100 ? "good" : "bad"} />
          <Metric label="Eval set" value={evalSet?.current_version ? `v${evalSet.current_version.version_number}` : "N/A"} hint={evalSet?.name} />
        </div>
      </section>

      <div className="workbenchGrid">
        <Section title="Skill Bundle" description="当前版本的不可变内容引用。正式版会接 artifact file tree 和 diff。">
          <div className="splitPanel">
            <div className="fileTree">
              <strong>SKILL.md</strong>
              <span>examples/review-input.md</span>
              <span>tests/manual-pass-fail.json</span>
            </div>
            <pre className="codePane">{`content_ref.kind: ${selectedVersion?.content_ref.kind}
locator: ${selectedVersion?.content_ref.locator}
digest: ${selectedVersion?.content_digest}

${selectedVersion?.change_summary}`}</pre>
          </div>
        </Section>

        <Section title="Evidence" description="测评结果必须绑定 exact VariantVersion + EvalSetVersion。">
          <div className="evidenceGrid">
            <Link className="evidenceCard" href={`/eval-set-versions/${evalSet?.current_version?.id}`}>
              <strong>Eval Set</strong>
              <span>{evalSet?.name ?? "No eval set"}</span>
              <small>{evalSet?.current_version ? `version ${evalSet.current_version.version_number}` : "no snapshot"}</small>
            </Link>
            <Link className="evidenceCard evidenceCardStrong" href={`/eval-runs/${latestRun?.id ?? "evalrun-code-v2-primary"}`}>
              <strong>Latest Eval Run</strong>
              <span>{latestRun ? percent(rate) : "Unverified"}</span>
              <small>{latestRun ? `${latestRun.summary.passed}/${latestRun.summary.total} passed` : "no run"}</small>
            </Link>
          </div>
        </Section>
      </div>

      <Section title="Variant Space" description="这里表达 tags 约束空间，不表达 parent/child 血缘。">
        <div className="variantMap">
          {skill.variants.map((item) => (
            <Link
              key={item.id}
              className={`variantNode ${item.id === variant.id ? "variantNodeActive" : ""}`}
              href={`/variants/${item.id}`}
            >
              <strong>{item.label}</strong>
              <span>{item.tags.join(" + ")}</span>
              <small>{item.current_version ? `current v${item.current_version.version_number}` : "no current"}</small>
            </Link>
          ))}
        </div>
      </Section>

      <Section title="History" description="Variant 只维护自己的版本历史；候选版本也是普通不可变版本。">
        <div className="timeline">
          {variant.versions.map((version) => (
            <Link
              href={`/variants/${variant.id}/versions/${version.id}`}
              className={`timelineItem ${version.id === selectedVersion?.id ? "timelineItemActive" : ""}`}
              key={version.id}
            >
              <strong>v{version.version_number}</strong>
              <span>{version.change_summary}</span>
              <small>{formatDate(version.created_at)} · {version.created_by} · {shortId(version.content_digest)}</small>
            </Link>
          ))}
        </div>
      </Section>
    </div>
  );
}

export function EvalSetVersionView({ detail }: { detail: EvalSetVersionDetail }) {
  return (
    <div className="stack">
      <div className="metricGrid metricGridWide">
        <Metric label="Version" value={`v${detail.eval_set_version.version_number}`} hint={shortId(detail.eval_set_version.id)} />
        <Metric label="Cases" value={String(detail.cases.length)} hint="exact case versions" />
        <Metric label="Created by" value={detail.eval_set_version.created_by} hint={formatDate(detail.eval_set_version.created_at)} />
      </div>
      <Section title="Cases" description="展示具体 case version，不只展示数量。">
        <div className="table">
          <div className="tableHeader gridCases">
            <span>#</span>
            <span>Case</span>
            <span>Version</span>
            <span>Input</span>
            <span>Expected</span>
          </div>
          {detail.cases.map((item) => (
            <div className="tableRow gridCases" key={item.case_version.id}>
              <span>{item.position + 1}</span>
              <strong>{item.case.title}</strong>
              <span>v{item.case_version.version_number}</span>
              <span>{shortId(item.case_version.input_artifact.digest)}</span>
              <span>{shortId(item.case_version.expected_output_artifact.digest)}</span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

export function EvalRunView({ detail }: { detail: EvalRunDetail }) {
  const rate = passRate(detail.eval_run);
  return (
    <div className="stack">
      <div className="metricGrid metricGridWide">
        <Metric label="Pass rate" value={percent(rate)} hint={`${detail.eval_run.summary.passed}/${detail.eval_run.summary.total} passed`} />
        <Metric label="Strategy" value={detail.eval_run.strategy} hint={detail.eval_run.status} />
        <Metric label="Binding" value="Exact versions" hint={`${shortId(detail.variant_version.id)} + ${shortId(detail.eval_set_version.id)}`} />
      </div>
      <Section title="Case Results" description="MVP 只有一层 pass/fail，没有额外 checklist 层级。">
        <div className="table">
          <div className="tableHeader gridResults">
            <span>Result</span>
            <span>Case</span>
            <span>Case version</span>
            <span>Score</span>
          </div>
          {detail.case_results.map((item) => (
            <div className="tableRow gridResults" key={item.result.case_version_id}>
              <Badge tone={item.result.passed ? "good" : "bad"}>{item.result.passed ? "Passed" : "Failed"}</Badge>
              <strong>{item.case.title}</strong>
              <span>v{item.case_version.version_number}</span>
              <span>{item.result.score}</span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
