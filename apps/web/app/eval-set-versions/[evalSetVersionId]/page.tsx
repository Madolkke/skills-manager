import { PageHeader } from "@/components/chrome";
import { EvalSetVersionView } from "@/components/skill-views";
import { getEvalSetVersionDetail } from "@/lib/api";

export default async function EvalSetVersionPage({ params }: { params: Promise<{ evalSetVersionId: string }> }) {
  const { evalSetVersionId } = await params;
  const detail = await getEvalSetVersionDetail(evalSetVersionId);

  return (
    <>
      <PageHeader
        eyebrow="Eval Set Version"
        title={`${detail.eval_set.name} v${detail.eval_set_version.version_number}`}
        description="测评集版本是不可变 case version 快照，因此页面必须显示具体 case 内容和 artifact 引用。"
      />
      <EvalSetVersionView detail={detail} />
    </>
  );
}
