import { PageHeader } from "@/components/chrome";
import { VariantPageView } from "@/components/skill-views";
import { getSkillDetail } from "@/lib/api";

export default async function SkillPage({ params }: { params: Promise<{ skillId: string }> }) {
  const { skillId } = await params;
  const skill = await getSkillDetail(skillId);
  const variant = skill.summary.default_variant ?? skill.variants[0];

  return (
    <>
      <PageHeader
        eyebrow="Skill / Default Variant"
        title={skill.skill.slug}
        description="Skill 页面默认展示 default variant；点击其他 variant 或历史版本时仍然使用同一套页面模板。"
      />
      <VariantPageView skill={skill} variant={variant} />
    </>
  );
}
