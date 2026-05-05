import { PageHeader } from "@/components/chrome";
import { VariantPageView } from "@/components/skill-views";
import { getVariantVersionDetail } from "@/lib/api";

export default async function VariantVersionPage({
  params,
}: {
  params: Promise<{ variantId: string; versionId: string }>;
}) {
  const { variantId, versionId } = await params;
  const { skill, variant, selectedVersionId } = await getVariantVersionDetail(variantId, versionId);

  return (
    <>
      <PageHeader
        eyebrow="Variant Version"
        title={`${variant.label} history`}
        description="历史版本也是同一个 variant 页面，只是选中某个不可变 VariantVersion。"
      />
      <VariantPageView skill={skill} variant={variant} selectedVersionId={selectedVersionId} />
    </>
  );
}
