import { PageHeader } from "@/components/chrome";
import { VariantPageView } from "@/components/skill-views";
import { getVariantDetail } from "@/lib/api";

export default async function VariantPage({ params }: { params: Promise<{ variantId: string }> }) {
  const { variantId } = await params;
  const { skill, variant } = await getVariantDetail(variantId);

  return (
    <>
      <PageHeader
        eyebrow="Variant"
        title={variant.label}
        description="Variant 是一组 tags 约束下维护者认可的当前解；这里展示它自己的版本历史和测评证据。"
      />
      <VariantPageView skill={skill} variant={variant} />
    </>
  );
}
