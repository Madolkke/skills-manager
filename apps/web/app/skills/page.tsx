import { PageHeader } from "@/components/chrome";
import { SkillHubList } from "@/components/skill-views";
import { listSkills } from "@/lib/api";

export default async function SkillsPage() {
  const skills = await listSkills();

  return (
    <>
      <PageHeader
        eyebrow="Hub"
        title="Skills"
        description="像普通 SkillHub 一样查找 skill；每条记录背后都能继续下钻到 variant、版本、测评集和测评结果。"
        actions={
          <>
            <button className="actionButton">Import</button>
            <button className="actionButton actionButtonPrimary">New Skill</button>
          </>
        }
      />
      <div className="hubTools">
        <input className="searchBox" placeholder="Search skills, tags, owners..." />
        <span className="filterChip">Owner</span>
        <span className="filterChip">Tags</span>
        <span className="filterChip">Verified</span>
      </div>
      <SkillHubList skills={skills} />
    </>
  );
}
