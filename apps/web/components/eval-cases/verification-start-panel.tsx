"use client";

import { passRate } from "@/lib/api";
import { percent } from "@/lib/format";
import type { EvalRunRecord } from "@/lib/types";
import { Badge } from "@/components/chrome";

type VerificationStartPanelProps = {
  bundleFileCount: number;
  caseCount: number;
  currentVersionNumber?: number;
  latestRun: EvalRunRecord | null;
  onAddCase: () => void;
  onOpenEvals: () => void;
  onOpenHistory: () => void;
};

export function VerificationStartPanel({
  bundleFileCount,
  caseCount,
  currentVersionNumber,
  latestRun,
  onAddCase,
  onOpenEvals,
  onOpenHistory,
}: VerificationStartPanelProps) {
  const hasCases = caseCount > 0;
  const hasRun = Boolean(latestRun);
  const primaryAction = !hasCases
    ? { label: "添加首批 case", onClick: onAddCase }
    : hasRun
      ? { label: "查看证据历史", onClick: onOpenHistory }
      : { label: "打开手工测评", onClick: onOpenEvals };

  return (
    <section className="verificationStartPanel">
      <div className="verificationGuideCopy">
        <span>验证清单</span>
        <strong>把导入 bundle 变成有证据的 skill</strong>
        <p>先沉淀测试用例，再记录 exact eval run。分发页面显示默认版本，但可信度来自这条证据链。</p>
      </div>

      <div className="verificationSteps" aria-label="导入后验证清单">
        <VerificationStep
          detail={`${bundleFileCount} files${currentVersionNumber ? ` · current v${currentVersionNumber}` : ""}`}
          done={Boolean(currentVersionNumber)}
          label="Bundle 已接入"
          status="已完成"
        />
        <VerificationStep
          detail={hasCases ? `${caseCount} cases in current EvalSetVersion` : "先添加能代表真实代码场景的 input / expected output"}
          done={hasCases}
          label="补齐评测集"
          status={hasCases ? "已完成" : "待处理"}
        />
        <VerificationStep
          detail={latestRun ? `${latestRun.summary.passed ?? 0}/${latestRun.summary.total ?? 0} passed · ${percent(passRate(latestRun))}` : "每条 case 只需要确认通过或不通过"}
          done={hasRun}
          label="记录首轮测评"
          status={hasRun ? "首轮测评完成" : "等待测评"}
        />
        <VerificationStep
          detail={hasRun ? "可进入历史页查看 run、case result 和 accepted verification" : "记录 run 后会形成可追溯证据"}
          done={hasRun}
          label="证据沉淀"
          status={hasRun ? "可查看" : "等待 run"}
        />
      </div>

      <div className="verificationGuideActions">
        <button onClick={primaryAction.onClick} type="button">{primaryAction.label}</button>
        {!hasRun ? <button onClick={onOpenEvals} type="button">批量粘贴 case</button> : null}
      </div>
    </section>
  );
}

function VerificationStep({
  detail,
  done,
  label,
  status,
}: {
  detail: string;
  done: boolean;
  label: string;
  status: string;
}) {
  return (
    <article className={`verificationStep ${done ? "verificationStepDone" : ""}`}>
      <div>
        <span>{label}</span>
        <strong>{status}</strong>
      </div>
      <p>{detail}</p>
      <Badge tone={done ? "good" : "neutral"}>{done ? "Done" : "Next"}</Badge>
    </article>
  );
}
