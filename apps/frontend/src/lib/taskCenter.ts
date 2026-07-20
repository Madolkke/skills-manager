import type { NotificationItem, PublishRecord, ReviewRequest, SkillDetail, SkillPublishOverview } from "../types";

export type TaskCenterItem = {
  id: string;
  title: string;
  description: string;
  tone: "info" | "warning" | "danger";
  actionLabel: string;
  target: "reviews" | "notifications" | "evaluate" | "publish";
  createdAt?: string;
};

export type TaskCenterGroup = {
  id: string;
  label: string;
  items: TaskCenterItem[];
};

export function buildTaskCenterGroups(input: {
  reviews: ReviewRequest[];
  notifications: NotificationItem[];
  skill: SkillDetail | null;
  publishOverview: SkillPublishOverview | null;
}): TaskCenterGroup[] {
  const reviewItems = input.reviews.filter((review) => review.status === "open").map(reviewTask);
  const notificationItems = input.notifications.filter((item) => !item.read_at).map(notificationTask);
  const contextItems = buildSkillContextTasks(input.skill, input.publishOverview);
  return [
    { id: "reviews", label: "我的评审", items: reviewItems },
    { id: "notifications", label: "通知", items: notificationItems },
    { id: "skill", label: "当前 Skill", items: contextItems },
  ].filter((group) => group.items.length > 0);
}

export function taskCenterBadgeCount(groups: TaskCenterGroup[]): number {
  return groups.reduce((total, group) => total + group.items.length, 0);
}

function reviewTask(review: ReviewRequest): TaskCenterItem {
  return {
    id: `review:${review.id}`,
    title: review.skill.slug,
    description: `版本 ${review.skill_version.version} 等待你的评审意见。`,
    tone: "warning",
    actionLabel: "去评审",
    target: "reviews",
    createdAt: review.created_at,
  };
}

function notificationTask(item: NotificationItem): TaskCenterItem {
  return {
    id: `notification:${item.id}`,
    title: item.title,
    description: item.body || "有一条未读通知。",
    tone: "info",
    actionLabel: "查看通知",
    target: "notifications",
    createdAt: item.created_at,
  };
}

function buildSkillContextTasks(skill: SkillDetail | null, publishOverview: SkillPublishOverview | null): TaskCenterItem[] {
  if (!skill) return [];
  const runningRuns = skill.latest_eval_runs.filter((run) => ["queued", "running"].includes(run.status));
  const pendingPublish = (publishOverview?.publish_records ?? []).filter((record) =>
    ["pending_confirmation", "queued", "releasing"].includes(record.status),
  );
  const items: TaskCenterItem[] = [];
  if (runningRuns.length) {
    items.push({
      id: `skill-runs:${skill.skill.id}`,
      title: "测评正在运行",
      description: `${runningRuns.length} 个最近测评任务还没有完成。`,
      tone: "warning",
      actionLabel: "查看测评",
      target: "evaluate",
      createdAt: runningRuns[0]?.created_at,
    });
  }
  if (pendingPublish.length) {
    items.push({
      id: `skill-publish:${skill.skill.id}`,
      title: "发布记录处理中",
      description: `${pendingPublish.length} 条发布记录正在确认或执行。`,
      tone: "info",
      actionLabel: "查看发布",
      target: "publish",
      createdAt: newestCreatedAt(pendingPublish),
    });
  }
  return items;
}

function newestCreatedAt(records: PublishRecord[]): string | undefined {
  return records.map((record) => record.created_at).filter(Boolean).sort().at(-1);
}
