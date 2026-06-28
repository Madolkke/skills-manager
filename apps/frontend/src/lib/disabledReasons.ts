export type DisabledReason = {
  disabled: boolean;
  reason: string;
};

export function disabledReason(disabled: boolean, reason: string): DisabledReason {
  return { disabled, reason: disabled ? reason : "" };
}

export function firstDisabledReason(...items: DisabledReason[]): string {
  return items.find((item) => item.disabled)?.reason ?? "";
}

export function evalManageReason(canManage: boolean): string {
  return canManage ? "" : "当前身份没有管理测评集和测试例的权限，需要 maintainer、owner 或 admin 角色。";
}

export function evalRunReason(input: { canRun: boolean; busy?: boolean; caseCount?: number }): string {
  return firstDisabledReason(
    disabledReason(!input.canRun, "当前身份没有运行测评权限，需要 evaluator、maintainer、owner 或 admin 角色。"),
    disabledReason(Boolean(input.busy), "已有测评任务正在入队或运行，请等待当前操作完成。"),
    disabledReason((input.caseCount ?? 0) <= 0, "当前测评集还没有测试例，请先创建或添加测试例。"),
  );
}

export function formalEvalReason(input: { canRun: boolean; canRunFormal: boolean; busy?: boolean; caseCount?: number }): string {
  const baseReason = evalRunReason({ canRun: input.canRun, busy: input.busy, caseCount: input.caseCount });
  if (baseReason) return baseReason;
  return firstDisabledReason(
    disabledReason(!input.canRunFormal, "需要所有测试例都有可聚合的运行结果后，才能发起正式测评。"),
  );
}

export function reviewManageReason(canManage: boolean): string {
  return canManage ? "" : "当前身份需要 maintainer、owner 或 admin 才能发起或结束评审。";
}

export function publishRequestReason(input: { canRequest: boolean; reviewClosed?: boolean; gatePassed?: boolean; duplicate?: boolean }): string {
  return firstDisabledReason(
    disabledReason(!input.canRequest, "当前身份需要 maintainer、owner 或 admin 才能提交发布确认单。"),
    disabledReason(input.reviewClosed === false, "评审关闭后才能提交发布确认单。"),
    disabledReason(input.gatePassed === false, "发布门禁未通过，不能提交发布确认单。"),
    disabledReason(Boolean(input.duplicate), "这个版本已经存在对应发布记录。"),
  );
}
