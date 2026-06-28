import type { EvalRunRecord, PublishRecord, ReviewRequest, SkillDetail, SkillVersion } from "../types";
import type { SkillTab } from "./navigation";

export type VersionFlowStage = {
  id: "version" | "evaluation" | "review" | "publish";
  label: string;
  status: "done" | "active" | "pending" | "blocked";
  description: string;
  tab: SkillTab;
};

export type VersionFlowItem = {
  versionId: string;
  version: string;
  isCurrent: boolean;
  stages: VersionFlowStage[];
};

export type SkillSuggestion = {
  id: string;
  title: string;
  description: string;
  actionLabel: string;
  tab: SkillTab;
};

export function buildVersionFlowItems(input: {
  skill: SkillDetail;
  reviews?: ReviewRequest[];
  publishRecords?: PublishRecord[];
}): VersionFlowItem[] {
  return input.skill.versions.map((version) => {
    const review = input.reviews?.find((item) => item.skill_version_id === version.id) ?? null;
    const publishRecords = (input.publishRecords ?? []).filter((item) => item.skill_version_id === version.id);
    const evalRun = latestRunForVersion(input.skill.latest_eval_runs, version.id);
    return {
      versionId: version.id,
      version: version.version,
      isCurrent: input.skill.skill.current_version_id === version.id,
      stages: [
        versionStage(version),
        evaluationStage(evalRun),
        reviewStage(review),
        publishStage(publishRecords),
      ],
    };
  });
}

export function buildSkillSuggestions(input: {
  skill: SkillDetail;
  reviews?: ReviewRequest[];
  publishRecords?: PublishRecord[];
}): SkillSuggestion[] {
  const suggestions: SkillSuggestion[] = [];
  const currentVersionId = input.skill.skill.current_version_id;
  const currentReview = currentVersionId ? input.reviews?.find((item) => item.skill_version_id === currentVersionId) : null;
  const currentPublish = currentVersionId ? input.publishRecords?.filter((item) => item.skill_version_id === currentVersionId) ?? [] : [];
  if (!input.skill.versions.length) {
    suggestions.push({
      id: "upload-version",
      title: "上传第一个版本",
      description: "当前 Skill 还没有可测评和发布的版本。",
      actionLabel: "去版本管理",
      tab: "versions",
    });
  }
  if (!input.skill.eval_sets.length) {
    suggestions.push({
      id: "create-eval-set",
      title: "创建测评集",
      description: "添加测评集和测试例后，才能验证 Skill 是否完成任务。",
      actionLabel: "去测评集",
      tab: "evalsets",
    });
  }
  if (input.skill.versions.length && !input.skill.latest_eval_runs.length) {
    suggestions.push({
      id: "run-evaluation",
      title: "运行一次测评",
      description: "还没有可用于评审和发布判断的测评记录。",
      actionLabel: "去测评",
      tab: "evaluate",
    });
  }
  if (currentVersionId && !currentReview) {
    suggestions.push({
      id: "start-review",
      title: "发起版本评审",
      description: "当前版本还没有评审记录，发布前建议先收集评审意见。",
      actionLabel: "去评审",
      tab: "reviews",
    });
  }
  if (currentReview?.status === "closed" && !currentPublish.length) {
    suggestions.push({
      id: "request-publish",
      title: "提交发布确认单",
      description: "评审已关闭，但当前版本还没有发布记录。",
      actionLabel: "去发布",
      tab: "publish",
    });
  }
  return suggestions.slice(0, 3);
}

function versionStage(version: SkillVersion): VersionFlowStage {
  return {
    id: "version",
    label: "版本",
    status: "done",
    description: version.display_name || version.change_summary || "版本已创建。",
    tab: "versions",
  };
}

function evaluationStage(run: EvalRunRecord | null): VersionFlowStage {
  if (!run) return { id: "evaluation", label: "测评", status: "pending", description: "暂无测评记录。", tab: "evaluate" };
  const total = run.summary.total ?? 0;
  const passed = run.summary.passed ?? 0;
  return {
    id: "evaluation",
    label: "测评",
    status: total > 0 ? "done" : "active",
    description: total > 0 ? `${passed}/${total} 通过` : "测评记录暂无聚合结果。",
    tab: "history",
  };
}

function reviewStage(review: ReviewRequest | null): VersionFlowStage {
  if (!review) return { id: "review", label: "评审", status: "pending", description: "未发起评审。", tab: "reviews" };
  if (review.status === "closed") return { id: "review", label: "评审", status: "done", description: `已关闭，${review.responses.length}/${review.reviewers.length} 已回复。`, tab: "reviews" };
  if (review.status === "open") return { id: "review", label: "评审", status: "active", description: `进行中，${review.responses.length}/${review.reviewers.length} 已回复。`, tab: "reviews" };
  return { id: "review", label: "评审", status: "blocked", description: "评审已取消。", tab: "reviews" };
}

function publishStage(records: PublishRecord[]): VersionFlowStage {
  if (!records.length) return { id: "publish", label: "发布", status: "pending", description: "暂无发布记录。", tab: "publish" };
  if (records.some((record) => record.status === "pending_confirmation")) {
    return { id: "publish", label: "发布", status: "active", description: "存在待后台确认发布单。", tab: "publish" };
  }
  if (records.some((record) => record.status === "released")) {
    return { id: "publish", label: "发布", status: "done", description: `${records.filter((record) => record.status === "released").length} 条已发布。`, tab: "publish" };
  }
  return { id: "publish", label: "发布", status: "blocked", description: "发布记录未完成。", tab: "publish" };
}

function latestRunForVersion(runs: EvalRunRecord[], versionId: string): EvalRunRecord | null {
  return [...runs]
    .filter((run) => run.skill_version_id === versionId)
    .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))[0] ?? null;
}
