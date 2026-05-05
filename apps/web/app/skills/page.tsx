import { Metric, PageHeader } from "@/components/chrome";
import { SkillHubList } from "@/components/skill-views";
import { listSkills, passRate } from "@/lib/api";
import { percent } from "@/lib/format";

export default async function SkillsPage() {
  const skills = await listSkills();
  const verified = skills.filter((skill) => skill.latest_accepted_eval_run).length;
  const defaultRun = skills[0]?.latest_accepted_eval_run;
  const defaultRate = defaultRun ? passRate(defaultRun) : null;

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
      <section className="hubOverview">
        <div>
          <p className="eyebrow">Distribution surface</p>
          <h2>Find the skill first. Drill into evidence only when needed.</h2>
          <p>
            The hub stays familiar: a searchable skill catalog. The difference is that every usable skill can show
            the exact variant, content version, eval set snapshot, and latest accepted result behind it.
          </p>
        </div>
        <div className="metricGrid metricGridWide">
          <Metric label="Skills" value={String(skills.length)} hint="active catalog entries" tone="blue" />
          <Metric label="Verified" value={String(verified)} hint="with accepted eval run" tone={verified ? "good" : "neutral"} />
          <Metric label="Default score" value={percent(defaultRate)} hint={defaultRun?.strategy ?? "no run"} tone={defaultRate === 100 ? "good" : "bad"} />
        </div>
      </section>
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
