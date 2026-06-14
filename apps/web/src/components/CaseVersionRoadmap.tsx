import clsx from "clsx";
import { GitBranch, Plus } from "lucide-react";
import { humanDate } from "../lib/format";
import type { EvalCaseHistory } from "../types";

type CaseVersionRoadmapProps = {
  history: EvalCaseHistory | null;
  currentVersionId: string;
};

export function CaseVersionRoadmap({ history, currentVersionId }: CaseVersionRoadmapProps) {
  const versions = orderedCaseVersions(history?.versions ?? []);
  const nextVersionNumber = versions.length > 0 ? versions.at(-1)!.case_version.version_number + 1 : null;

  return (
    <section className="case-version-history">
      <h2>Case 版本记录</h2>
      <ol className="case-version-track" aria-label="Case version history">
        {versions.map((item) => {
          const current = item.case_version.id === currentVersionId;
          return (
            <li
              className={clsx("case-version-step", current && "current")}
              key={item.case_version.id}
              aria-current={current ? "step" : undefined}
            >
              <span className="case-version-marker" aria-hidden="true">
                <GitBranch size={14} />
              </span>
              <article className="case-version-card">
                <strong>
                  v{item.case_version.version_number}
                  {current ? "（当前）" : ""}
                </strong>
                <span>{humanDate(item.case_version.created_at)}</span>
                <p>{item.case_version.notes ?? "无说明"}</p>
                <small>case v{item.case_version.version_number}</small>
              </article>
            </li>
          );
        })}
        {nextVersionNumber ? (
          <li className="case-version-step pending" aria-label={`case v${nextVersionNumber} 待创建`}>
            <span className="case-version-marker" aria-hidden="true">
              <Plus size={14} />
            </span>
            <article className="case-version-card">
              <strong>v{nextVersionNumber}</strong>
              <span>待创建</span>
              <p>编辑当前 case 后会生成新的 case version，并更新测评集。</p>
              <small>case v{nextVersionNumber}</small>
            </article>
          </li>
        ) : null}
      </ol>
    </section>
  );
}

function orderedCaseVersions(versions: EvalCaseHistory["versions"]): EvalCaseHistory["versions"] {
  return [...versions].sort((left, right) => left.case_version.version_number - right.case_version.version_number);
}
