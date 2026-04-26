import { useEffect, useState } from "react";
import type { AppState, EvalSetVersion } from "../domain/types";
import { aggregateScore, casesForVersion, percent, resultCounts, runFor, summarizeVariants, tagsForVariant } from "../domain/scoring";
import { loadBackendSkillBundle, type SkillBundleSnapshot } from "../store/backendState";
import { VariantMap } from "./VariantMap";
import { Controls } from "./Controls";
import { StatePill, TagPill } from "./ui";

export function SkillPage({
  state,
  versions,
  onToggleTag,
  onSetVersion,
  onSelectVariant,
  onSelectVersion,
  onOpenEvalSet,
  onOpenResult,
  onOpenWorkbench,
}: {
  state: AppState;
  versions: EvalSetVersion[];
  onToggleTag: (tag: string) => void;
  onSetVersion: (versionRef: string) => void;
  onSelectVariant: (variantRef: string) => void;
  onSelectVersion: (versionRef: string) => void;
  onOpenEvalSet: () => void;
  onOpenResult: () => void;
  onOpenWorkbench: () => void;
}) {
  const [diffBaseVersionRef, setDiffBaseVersionRef] = useState("");
  const [diffTargetVersionRef, setDiffTargetVersionRef] = useState("");
  const [bundleCache, setBundleCache] = useState<Record<string, SkillBundleSnapshot>>({});
  const [bundleError, setBundleError] = useState("");
  const { data } = state;
  const skill = data.skills.find((item) => item.id === state.selectedSkillRef);
  const version = data.evalSetVersions.find((item) => item.id === state.evalSetVersionRef);
  const summaries = version
    ? summarizeVariants(data, state.selectedSkillRef, state.requestedTags, version.id)
    : [];
  const selected = data.variants.find((item) => item.id === state.selectedVariantRef) ?? summaries[0]?.variant;
  const selectedVersion =
    data.variantVersions.find((item) => item.id === state.selectedVersionRef && item.variantRef === selected?.id) ??
    data.variantVersions.find((item) => item.id === selected?.currentVersionRef);
  const variantVersions = data.variantVersions
    .filter((item) => item.variantRef === selected?.id)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  const variantVersionRefs = variantVersions.map((item) => item.id).join("|");
  const selectedVersionIndex = selectedVersion ? variantVersions.findIndex((item) => item.id === selectedVersion.id) : -1;
  const previousVersion = selectedVersionIndex >= 0 ? variantVersions[selectedVersionIndex + 1] : undefined;
  const diffBaseVersion = variantVersions.find((item) => item.id === diffBaseVersionRef) ?? previousVersion;
  const diffTargetVersion = variantVersions.find((item) => item.id === diffTargetVersionRef) ?? selectedVersion;
  const bundleRefs = uniqueBundleRefs([
    selectedVersion?.contentRef.kind === "skill_bundle" ? selectedVersion.contentRef.locator : undefined,
    diffBaseVersion?.contentRef.kind === "skill_bundle" ? diffBaseVersion.contentRef.locator : undefined,
    diffTargetVersion?.contentRef.kind === "skill_bundle" ? diffTargetVersion.contentRef.locator : undefined,
  ]);
  const bundleRefKey = bundleRefs.join("|");

  useEffect(() => {
    if (!selectedVersion) return;
    const fallbackBase = previousVersion?.id ?? variantVersions.find((item) => item.id !== selectedVersion.id)?.id ?? selectedVersion.id;
    setDiffBaseVersionRef(fallbackBase);
    setDiffTargetVersionRef(selectedVersion.id);
  }, [selected?.id, selectedVersion?.id, previousVersion?.id, variantVersionRefs]);

  useEffect(() => {
    const missingRefs = bundleRefs.filter((ref) => !bundleCache[ref]);
    if (missingRefs.length === 0) return;

    let cancelled = false;
    setBundleError("");
    Promise.all(missingRefs.map((ref) => loadBackendSkillBundle(ref)))
      .then((bundles) => {
        if (cancelled) return;
        setBundleCache((prev) => {
          const next = { ...prev };
          bundles.forEach((bundle, index) => {
            next[missingRefs[index]] = bundle;
          });
          return next;
        });
      })
      .catch((error) => {
        if (!cancelled) setBundleError(error instanceof Error ? error.message : "Skill bundle 读取失败");
      });

    return () => {
      cancelled = true;
    };
  }, [bundleRefKey]);

  if (!version || !selected) return null;
  const selectedTags = tagsForVariant(data, selected);
  const selectedScore = selectedVersion ? aggregateScore(data, selectedVersion.id, version.id) : null;
  const counts = selectedVersion ? resultCounts(data, selectedVersion.id, version.id) : { passed: 0, failed: 0, missing: 0, total: 0 };
  const selectedRun = selectedVersion ? runFor(data, selectedVersion.id, version.id) : undefined;
  const verification = verificationState(Boolean(selectedRun), counts);
  const cases = casesForVersion(data, version);
  const contentRef = selectedVersion
    ? `${selectedVersion.contentRef.kind}:${selectedVersion.contentRef.locator}@${selectedVersion.contentRef.digest}`
    : "no version";
  const selectedBundleRef = selectedVersion?.contentRef.kind === "skill_bundle" ? selectedVersion.contentRef.locator : "";
  const bundle = selectedBundleRef ? bundleCache[selectedBundleRef] ?? null : null;
  const diffBaseBundle =
    diffBaseVersion?.contentRef.kind === "skill_bundle" ? bundleCache[diffBaseVersion.contentRef.locator] ?? null : null;
  const diffTargetBundle =
    diffTargetVersion?.contentRef.kind === "skill_bundle" ? bundleCache[diffTargetVersion.contentRef.locator] ?? null : null;
  const bundleDiff = diffBaseBundle && diffTargetBundle ? diffBundles(diffBaseBundle, diffTargetBundle) : null;
  const changedFiles = bundleDiff?.files.filter((file) => file.status !== "unchanged") ?? [];
  const verificationRows = selectedVersion
    ? [...versions]
        .sort((a, b) => b.version.localeCompare(a.version, undefined, { numeric: true }))
        .map((evalSetVersion) => ({
          evalSetVersion,
          run: runFor(data, selectedVersion.id, evalSetVersion.id),
          score: aggregateScore(data, selectedVersion.id, evalSetVersion.id),
          counts: resultCounts(data, selectedVersion.id, evalSetVersion.id),
        }))
    : [];

  return (
    <>
      <section className="variant-page panel">
        <div className="variant-page-hero">
          <div>
            <div className="eyebrow">{skill?.slug ?? "Skill"} / Variant</div>
            <div className="variant-titleline">
              <h2>{selected.name}</h2>
              {selectedTags.map((tag) => (
                <TagPill key={tag} tag={tag} />
              ))}
              <StatePill tone={selected.id === skill?.defaultVariantRef ? "pass" : "warn"}>
                {selected.id === skill?.defaultVariantRef ? "默认入口" : "约束变体"}
              </StatePill>
              <StatePill tone={verification.tone}>{verification.label}</StatePill>
            </div>
            <p>
              {selected.label}。{selected.summary}
            </p>
          </div>
          <div className="variant-score-card">
            <div className="fact-label">当前查看版本</div>
            <div className="default-title">{selectedVersion?.version ?? "无"}</div>
            <div className="default-score">{percent(selectedScore)}</div>
            <div className="metric-note">
              {counts.passed} 通过 / {counts.failed} 不通过 / {counts.missing} 未测
            </div>
          </div>
        </div>
        <div className="drawer-facts">
          <Fact label="content_ref" value={contentRef} />
          <Fact label="变更说明" value={selectedVersion?.changeNote ?? "无"} />
        </div>
      </section>

      {verification.needsRun && (
        <section className="panel verification-callout">
          <div>
            <h2>{verification.label}</h2>
            <p>
              {selectedVersion?.version ?? "当前版本"} 还没有在 {version.version} 上形成完整 EvalRun。发布内容包以后需要重新测评，证据才不会停留在旧版本。
            </p>
          </div>
          <button className="primary-button" type="button" onClick={onOpenWorkbench}>
            去手工测评
          </button>
        </section>
      )}

      {selectedBundleRef && !bundle && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Skill Bundle</h2>
              <p>{bundleError || "正在从 /api/skill-bundle 读取标准 skill 文件夹快照。"}</p>
            </div>
          </div>
        </section>
      )}

      {bundle && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Skill Bundle</h2>
              <p>{bundle.metadata.description}</p>
            </div>
          </div>
          <div className="summary-row">
            <Metric label="标准名称" value={bundle.metadata.name} />
            <Metric label="文件数" value={String(bundle.files.length)} />
          </div>
          <div className="bundle-file-grid">
            {bundle.files.map((file) => (
              <article className="bundle-file-card" key={file.path}>
                <strong>{file.path}</strong>
                <pre>{file.content}</pre>
              </article>
            ))}
          </div>
        </section>
      )}

      {bundle && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Bundle Diff</h2>
              <p>
                选择任意两个历史版本比较。MVP 从完整快照计算 diff，不把差异文件作为事实源存储。
              </p>
            </div>
          </div>
          <div className="diff-selector-row">
            <label className="field-block compact">
              <span>比较起点</span>
              <select value={diffBaseVersion?.id ?? ""} onChange={(event) => setDiffBaseVersionRef(event.target.value)}>
                {variantVersions.map((item) => (
                  <option value={item.id} key={item.id}>
                    {versionOptionLabel(item, selected.currentVersionRef)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-block compact">
              <span>比较终点</span>
              <select value={diffTargetVersion?.id ?? ""} onChange={(event) => setDiffTargetVersionRef(event.target.value)}>
                {variantVersions.map((item) => (
                  <option value={item.id} key={item.id}>
                    {versionOptionLabel(item, selected.currentVersionRef)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {!diffBaseVersion || !diffTargetVersion ? <p className="empty-note">请选择两个版本。</p> : null}
          {diffBaseVersion?.contentRef.kind === "skill_bundle" && !diffBaseBundle && <p className="empty-note">正在读取比较起点 bundle。</p>}
          {diffTargetVersion?.contentRef.kind === "skill_bundle" && !diffTargetBundle && <p className="empty-note">正在读取比较终点 bundle。</p>}
          {diffBaseVersion && diffBaseVersion.contentRef.kind !== "skill_bundle" && (
            <p className="empty-note">比较起点不是 skill_bundle，无法做文件级 diff。</p>
          )}
          {diffTargetVersion && diffTargetVersion.contentRef.kind !== "skill_bundle" && (
            <p className="empty-note">比较终点不是 skill_bundle，无法做文件级 diff。</p>
          )}
          {bundleDiff && (
            <>
              <div className="summary-row diff-summary">
                <Metric label="新增" value={String(bundleDiff.added)} />
                <Metric label="修改" value={String(bundleDiff.modified)} />
                <Metric label="删除" value={String(bundleDiff.deleted)} />
                <Metric label="未变" value={String(bundleDiff.unchanged)} />
              </div>
              <div className="diff-file-list">
                {changedFiles.length === 0 && <p className="empty-note">文件内容没有变化。</p>}
                {changedFiles.map((file) => (
                  <article className={`diff-file-card ${file.status}`} key={file.path}>
                    <div className="diff-file-title">
                      <strong>{file.path}</strong>
                      <span>{diffStatusLabel(file.status)}</span>
                    </div>
                    <pre className="diff-lines">
                      {file.lines.map((line, index) => (
                        <span className={`diff-line ${line.kind}`} key={`${file.path}-${index}`}>
                          <span className="diff-prefix">{linePrefix(line.kind)}</span>
                          {line.text || " "}
                        </span>
                      ))}
                    </pre>
                  </article>
                ))}
              </div>
            </>
          )}
        </section>
      )}

      <Controls
        requestedTags={state.requestedTags}
        versions={versions}
        evalSetVersionRef={version.id}
        onToggleTag={onToggleTag}
        onSetVersion={onSetVersion}
      />

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>版本验证记录</h2>
            <p>当前查看的 VariantVersion 在各个 EvalSetVersion 上的运行状态；内容版本和测评集版本必须一起看。</p>
          </div>
        </div>
        <div className="version-timeline">
          {verificationRows.map((row) => (
            <button
              className={`history-row verification-row ${row.evalSetVersion.id === version.id ? "is-active" : ""}`}
              key={row.evalSetVersion.id}
              type="button"
              onClick={() => {
                onSetVersion(row.evalSetVersion.id);
                onOpenResult();
              }}
            >
              <span>
                <strong>{row.evalSetVersion.version}</strong>
                <em>{row.evalSetVersion.caseRefs.length} 个 cases · {row.run ? `EvalRun ${row.run.id}` : "未运行"}</em>
              </span>
              <span className="verification-metrics">
                <strong>{percent(row.score)}</strong>
                <em>
                  {row.counts.passed} 通过 / {row.counts.failed} 不通过 / {row.counts.missing} 未测
                </em>
              </span>
            </button>
          ))}
        </div>
      </section>

      <div className="variant-overview-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>测评集总览</h2>
              <p>{version.version} 包含 {cases.length} 个完整测试用例，每个 case 是 input + expected。</p>
            </div>
            <button className="ghost-button" type="button" onClick={onOpenEvalSet}>
              查看详情
            </button>
          </div>
          <div className="summary-row">
            <Metric label="EvalSetVersion" value={version.version} />
            <Metric label="Cases" value={String(cases.length)} />
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>当前测评结果</h2>
              <p>当前查看版本在当前测评集上的最终结论，只记录通过或不通过。</p>
            </div>
            <button className="ghost-button" type="button" onClick={onOpenResult}>
              查看详情
            </button>
          </div>
          <div className="summary-row">
            <Metric label="得分" value={percent(selectedScore)} />
            <Metric label="通过 / 不通过" value={`${counts.passed} / ${counts.failed}`} />
          </div>
        </section>
      </div>

      <div className="variant-overview-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>变体地图</h2>
              <p>点击节点会切换到同一个 variant 页面模板，不打开单独抽屉。</p>
            </div>
          </div>
          <VariantMap
            data={data}
            summaries={summaries}
            evalSetVersionRef={version.id}
            selectedVariantRef={selected.id}
            onSelectVariant={onSelectVariant}
          />
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>历史版本</h2>
              <p>历史版本也是同一个页面模板，只是切换当前查看的 VariantVersion。</p>
            </div>
          </div>
          <div className="version-timeline">
            {variantVersions.map((item) => (
              <button
                className={`history-row ${selectedVersion?.id === item.id ? "is-active" : ""}`}
                key={item.id}
                type="button"
                onClick={() => onSelectVersion(item.id)}
              >
                <span>
                  <strong>{item.version}</strong>
                  <em>{item.changeNote ?? "无变更说明"}</em>
                </span>
                <span>{item.id === selected.currentVersionRef ? "current" : "history"}</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact-row">
      <div className="fact-label">{label}</div>
      <div className="fact-value">{value}</div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric compact-metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}

function verificationState(
  hasRun: boolean,
  counts: { passed: number; failed: number; missing: number; total: number },
): { label: string; tone: "pass" | "fail" | "warn"; needsRun: boolean } {
  if (counts.total === 0) return { label: "空测评集", tone: "warn", needsRun: true };
  if (!hasRun) return { label: "需要测评", tone: "warn", needsRun: true };
  if (counts.missing > 0) return { label: "部分测评", tone: "warn", needsRun: true };
  if (counts.failed > 0) return { label: "有失败", tone: "fail", needsRun: false };
  return { label: "已验证", tone: "pass", needsRun: false };
}

function versionOptionLabel(version: { id: string; version: string; contentRef: { kind: string } }, currentVersionRef: string) {
  const markers = [];
  if (version.id === currentVersionRef) markers.push("current");
  if (version.contentRef.kind !== "skill_bundle") markers.push(version.contentRef.kind);
  return markers.length ? `${version.version} · ${markers.join(" · ")}` : version.version;
}

type DiffLine = { kind: "same" | "add" | "delete"; text: string };
type FileDiff = {
  path: string;
  status: "added" | "deleted" | "modified" | "unchanged";
  lines: DiffLine[];
};

function diffBundles(before: SkillBundleSnapshot, after: SkillBundleSnapshot) {
  const paths = Array.from(new Set([...Object.keys(before.fileMap), ...Object.keys(after.fileMap)])).sort();
  const files = paths.map((path) => {
    const beforeContent = before.fileMap[path];
    const afterContent = after.fileMap[path];
    if (beforeContent === undefined) {
      return { path, status: "added" as const, lines: afterContent.split("\n").map((text) => ({ kind: "add" as const, text })) };
    }
    if (afterContent === undefined) {
      return { path, status: "deleted" as const, lines: beforeContent.split("\n").map((text) => ({ kind: "delete" as const, text })) };
    }
    if (beforeContent === afterContent) {
      return { path, status: "unchanged" as const, lines: [] };
    }
    return { path, status: "modified" as const, lines: lineDiff(beforeContent, afterContent) };
  });

  return {
    files,
    added: files.filter((file) => file.status === "added").length,
    deleted: files.filter((file) => file.status === "deleted").length,
    modified: files.filter((file) => file.status === "modified").length,
    unchanged: files.filter((file) => file.status === "unchanged").length,
  };
}

function lineDiff(before: string, after: string): DiffLine[] {
  const a = before.split("\n");
  const b = after.split("\n");
  const dp = Array.from({ length: a.length + 1 }, () => Array(b.length + 1).fill(0));

  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const lines: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      lines.push({ kind: "same", text: a[i] });
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      lines.push({ kind: "delete", text: a[i] });
      i += 1;
    } else {
      lines.push({ kind: "add", text: b[j] });
      j += 1;
    }
  }
  while (i < a.length) {
    lines.push({ kind: "delete", text: a[i] });
    i += 1;
  }
  while (j < b.length) {
    lines.push({ kind: "add", text: b[j] });
    j += 1;
  }
  return lines;
}

function diffStatusLabel(status: FileDiff["status"]) {
  return {
    added: "新增",
    deleted: "删除",
    modified: "修改",
    unchanged: "未变",
  }[status];
}

function linePrefix(kind: DiffLine["kind"]) {
  if (kind === "add") return "+";
  if (kind === "delete") return "-";
  return " ";
}

function uniqueBundleRefs(refs: Array<string | undefined>) {
  return Array.from(new Set(refs.filter((ref): ref is string => Boolean(ref))));
}
