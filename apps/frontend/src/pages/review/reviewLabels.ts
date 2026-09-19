import { reviewerSourceText } from "../../lib/reviewerSelection";
import type { ReviewSummary } from "../../lib/api/paginationApi";
import type { ReviewRequest, ReviewerCandidateOverview } from "../../types";

/** 显示已回复与参与评审的人数。 */
export function responseCount(review: ReviewRequest): string {
  return `${review.responses.length} / ${review.reviewers.length}`;
}

/** 汇总通过评审后的发布目标。 */
export function autoTargetText(review: ReviewRequest): string {
  const names = review.publish_targets.filter((item) => item.auto_submit_on_pass).map((item) => `${item.name}${item.auto_publish_enabled ? "（自动发布）" : "（后台确认）"}`);
  return names.length ? names.join("、") : "未设置";
}

/** 显示评审参与者及其来源。 */
export function reviewerText(review: ReviewRequest, candidates: ReviewerCandidateOverview | null): string {
  return review.reviewers.map((item) => reviewerSourceText(item, candidates)).join("、") || "无";
}

/** 将评审状态转换为中文标签。 */
export function reviewStatusText(review: ReviewSummary): string {
  if (review.status === "open") return "进行中";
  if (review.status === "closed") return "已关闭";
  return "已取消";
}

/** 显示投票结果标签。 */
export function scoreLabel(score: -1 | 0 | 1): string {
  if (score === 1) return "+1 通过";
  if (score === 0) return "0 保留";
  return "-1 不通过";
}

/** 映射投票结果的呈现级别。 */
export function scoreTone(score: -1 | 0 | 1): string {
  if (score === 1) return "positive";
  if (score === 0) return "neutral";
  return "negative";
}
