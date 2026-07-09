import type { ReviewerCandidateOverview, ReviewReviewer, ReviewSubject } from "../types";

export function reviewerUserIds(input: string): string[] {
  return uniqueTokens(input.split(/[\s,，;；]+/));
}

export function buildReviewerSources(groupIds: string[], userInput: string): ReviewSubject[] {
  const groups = uniqueTokens(groupIds);
  const users = reviewerUserIds(userInput);
  return [
    ...groups.map((subject_id) => ({ subject_type: "group" as const, subject_id })),
    ...users.map((subject_id) => ({ subject_type: "user" as const, subject_id })),
  ];
}

export function reviewerSourceText(reviewer: ReviewReviewer, candidates: ReviewerCandidateOverview | null): string {
  if (reviewer.source_subject_type !== "group") return reviewer.reviewer_actor;
  const group = candidates?.groups.find((item) => item.id === reviewer.source_subject_id);
  return `${reviewer.reviewer_actor}（${group?.name ?? reviewer.source_subject_id}）`;
}

export function selectedReviewerCount(groupIds: string[], userInput: string, candidates: ReviewerCandidateOverview | null): number {
  const reviewers = new Set(reviewerUserIds(userInput));
  const groups = new Set(groupIds);
  for (const group of candidates?.groups ?? []) {
    if (!groups.has(group.id)) continue;
    for (const member of group.members) reviewers.add(member.subject_id);
  }
  return reviewers.size;
}

function uniqueTokens(values: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const token = value.trim();
    if (!token || seen.has(token)) continue;
    seen.add(token);
    result.push(token);
  }
  return result;
}
