"use client";

import Link from "next/link";
import { FormEvent } from "react";

import { Badge } from "@/components/chrome";
import { VerificationStartPanel } from "@/components/eval-cases/verification-start-panel";
import type { InspectorActionMode, InspectorImportPreview } from "@/components/inspector/workbench-inspector";
import { SkillAccessPanel } from "@/components/skills/skill-access-panel";
import { SkillGovernancePanel } from "@/components/skills/skill-governance-panel";
import { SkillLaunchpad } from "@/components/skills/skill-launchpad";
import { SkillSettingsPanel } from "@/components/skills/skill-settings-panel";
import { Metric } from "@/components/workbench-metric";
import { formatBytes, percent } from "@/lib/format";
import type { BundleFile, EvalRunRecord, SkillDetail, VariantDetail } from "@/lib/types";

type WorkbenchOverviewPaneProps = {
  actor: string;
  assignSkillRole: (event: FormEvent<HTMLFormElement>) => void;
  busy: boolean;
  caseCount: number;
  createSkill: (event: FormEvent<HTMLFormElement>) => void;
  defaultVariant: VariantDetail | null;
  hasPersistedSkill: boolean;
  importPreview: InspectorImportPreview;
  importSkill: (event: FormEvent<HTMLFormElement>) => void;
  latestRun: EvalRunRecord | null;
  onAction: (mode: InspectorActionMode) => void;
  onArchiveSkill: () => void;
  onDiff: () => void;
  onOpenAudit: () => void;
  onOpenEvals: () => void;
  onOpenHistory: () => void;
  primaryEvalSetVersion?: number;
  refreshImportPreview: (event: FormEvent<HTMLFormElement>) => void;
  revokeSkillRole: (roleAssignmentId: string) => void;
  score: number | null;
  selectedDetail: SkillDetail;
  updateSkill: (event: FormEvent<HTMLFormElement>) => void;
};

export function WorkbenchOverviewPane({
  actor,
  assignSkillRole,
  busy,
  caseCount,
  createSkill,
  defaultVariant,
  hasPersistedSkill,
  importPreview,
  importSkill,
  latestRun,
  onAction,
  onArchiveSkill,
  onDiff,
  onOpenEvals,
  onOpenHistory,
  onOpenAudit,
  primaryEvalSetVersion,
  refreshImportPreview,
  revokeSkillRole,
  score,
  selectedDetail,
  updateSkill,
}: WorkbenchOverviewPaneProps) {
  const currentVersion = defaultVariant?.current_version ?? null;
  const bundleFiles = bundleFilesFromVariant(defaultVariant);
  const skillMd = fileContent(bundleFiles, "SKILL.md") ?? formatBundlePreview(defaultVariant);
  const tags = defaultVariant?.tags ?? [];

  if (!hasPersistedSkill) {
    return (
      <div className="linearPane overviewPane">
        <SkillLaunchpad
          busy={busy}
          importPreview={importPreview}
          onCreateSkill={createSkill}
          onImportSkill={importSkill}
          onRefreshImportPreview={refreshImportPreview}
        />
      </div>
    );
  }

  return (
    <div className="linearPane overviewPane">
      <section className="productHero">
        <div className="productHeroCopy">
          <span>Default distribution</span>
          <h2>{defaultVariant?.label ?? "暂无默认 variant"}</h2>
          <p>{defaultVariant?.summary ?? "这个 skill 还没有默认 variant。先创建或导入一个标准 Skill bundle。"}</p>
          <div className="tagLine">
            {tags.length > 0 ? tags.map((tag) => <Badge key={tag} tone="blue">{tag}</Badge>) : <Badge>draft</Badge>}
          </div>
        </div>
        <div className="heroScore">
          <span>Verified score</span>
          <strong>{latestRun ? percent(score) : "未测"}</strong>
          <small>{latestRun ? `${latestRun.summary.passed ?? 0}/${latestRun.summary.total ?? 0} cases passed` : "等待第一次手工测评"}</small>
        </div>
      </section>

      <div className="linearMetrics">
        <Metric label="变体数" value={String(selectedDetail.variants.length)} />
        <Metric label="当前版本" value={currentVersion ? `v${currentVersion.version_number}` : "暂无"} />
        <Metric label="测评集版本" value={primaryEvalSetVersion ? `v${primaryEvalSetVersion}` : "暂无"} />
        <Metric label="最近分数" tone={latestRun ? (score === 100 ? "good" : "bad") : "neutral"} value={latestRun ? percent(score) : "未测"} />
      </div>

      <SkillSettingsPanel
        busy={busy}
        defaultVariant={defaultVariant}
        latestRun={latestRun}
        onUpdateSkill={updateSkill}
        score={score}
        selectedDetail={selectedDetail}
      />
      <SkillAccessPanel
        actor={actor}
        busy={busy}
        onAssignRole={assignSkillRole}
        onRevokeRole={revokeSkillRole}
        roleAssignments={selectedDetail.role_assignments}
      />
      <SkillGovernancePanel
        busy={busy}
        onArchiveSkill={onArchiveSkill}
        onOpenAudit={onOpenAudit}
        selectedDetail={selectedDetail}
      />

      <VerificationStartPanel
        bundleFileCount={bundleFiles.length}
        caseCount={caseCount}
        currentVersionNumber={currentVersion?.version_number}
        latestRun={latestRun}
        onAddCase={() => onAction("new-case")}
        onOpenEvals={onOpenEvals}
        onOpenHistory={onOpenHistory}
      />

      <section className="linearSection bundleSection">
        <div className="linearSectionHeader">
          <div>
            <h3>Skill bundle</h3>
            <p>{bundleFiles.length > 0 ? `${bundleFiles.length} files · ${currentVersion?.content_digest ?? ""}` : currentVersion?.content_ref.locator}</p>
          </div>
          <div className="sectionActions">
            <button onClick={() => onAction("new-version")} type="button">追加版本</button>
            <button disabled={!defaultVariant || defaultVariant.versions.length < 2} onClick={onDiff} type="button">比较版本</button>
            <Link href={defaultVariant ? `/variants/${defaultVariant.id}` : "#"}>打开详情</Link>
          </div>
        </div>
        <div className="linearBundle">
          <div className="bundleFileList">
            {bundleFiles.length > 0 ? (
              bundleFiles.map((file) => (
                <span className={file.path === "SKILL.md" ? "bundleFileActive" : ""} key={file.path}>
                  {file.path}
                  {typeof file.size_bytes === "number" ? <small>{formatBytes(file.size_bytes)}</small> : null}
                </span>
              ))
            ) : (
              <span className="bundleFileActive">content_ref</span>
            )}
          </div>
          <pre>{skillMd}</pre>
        </div>
      </section>
    </div>
  );
}

function formatBundlePreview(variant: VariantDetail | null): string {
  if (!variant?.current_version) return "还没有 current version。";
  const files = bundleFilesFromVariant(variant);
  const importedSkill = fileContent(files, "SKILL.md") ?? skillMdFromBundleArtifact(variant.current_version.bundle_artifact?.content_text);
  if (importedSkill) return importedSkill;
  return [
    `name: ${variant.label}`,
    `tags: ${variant.tags.join(", ")}`,
    `version: v${variant.current_version.version_number}`,
    `locator: ${variant.current_version.content_ref.locator}`,
    `digest: ${variant.current_version.content_digest}`,
    "",
    variant.current_version.change_summary,
  ].join("\n");
}

function bundleFilesFromVariant(variant: VariantDetail | null): BundleFile[] {
  const version = variant?.current_version;
  if (!version) return [];
  if (version.bundle_files?.length) return version.bundle_files;
  return bundleFilesFromArtifact(version.bundle_artifact?.content_text);
}

function bundleFilesFromArtifact(contentText?: string | null): BundleFile[] {
  if (!contentText) return [];
  try {
    const manifest = JSON.parse(contentText) as {
      files?: BundleFile[];
    };
    return (manifest.files ?? []).filter((file) => typeof file.path === "string").sort((a, b) => a.path.localeCompare(b.path));
  } catch {
    return [];
  }
}

function fileContent(files: BundleFile[], path: string): string | null {
  return files.find((file) => file.path === path)?.content_text ?? null;
}

function skillMdFromBundleArtifact(contentText?: string | null): string | null {
  if (!contentText) return null;
  try {
    const manifest = JSON.parse(contentText) as {
      files?: Array<{ path?: string; content_text?: string }>;
    };
    return manifest.files?.find((file) => file.path === "SKILL.md")?.content_text ?? null;
  } catch {
    return null;
  }
}
