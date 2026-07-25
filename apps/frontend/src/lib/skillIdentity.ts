import type { SkillRecord } from "../types";

type SkillIdentity = Pick<SkillRecord, "slug" | "display_name">;

export function skillSecondaryName(skill: SkillIdentity): string | null {
  const displayName = skill.display_name?.trim();
  return displayName && displayName !== skill.slug ? displayName : null;
}

export function skillOptionLabel(skill: SkillIdentity): string {
  const displayName = skillSecondaryName(skill);
  return displayName ? `${skill.slug}（${displayName}）` : skill.slug;
}
