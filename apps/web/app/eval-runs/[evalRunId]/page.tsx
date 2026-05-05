import { PageHeader } from "@/components/chrome";
import { EvalRunView } from "@/components/skill-views";
import { getEvalRunDetail } from "@/lib/api";

export default async function EvalRunPage({ params }: { params: Promise<{ evalRunId: string }> }) {
  const { evalRunId } = await params;
  const detail = await getEvalRunDetail(evalRunId);

  return (
    <>
      <PageHeader
        eyebrow="Eval Run"
        title={detail.eval_run.id}
        description="一次测评结果绑定 exact VariantVersion + EvalSetVersion，并展示每个 case 的 pass/fail。"
      />
      <EvalRunView detail={detail} />
    </>
  );
}
