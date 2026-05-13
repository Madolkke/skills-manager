# 产品操作摩擦审计规格

## 背景

当前 SkillHub 已经跑通标准 Skill 导入、variant/version 管理、eval case 管理、手工测评、candidate promotion、run history、run matrix、audit explorer 和 command menu。下一步继续堆功能之前，需要重新审视“是否顺手”，并把下一轮优化排成证据充分的任务队列。

本任务只做审计和文档收束，不直接修改 UI。

## 审计方法

- 对照当前视觉回归截图，检查 first-run、overview、manual eval、variants、promotion、run comparison、audit explorer、mobile。
- 对照 E2E 覆盖，区分“已闭环路径”和“仍然摩擦”。
- 对照源码行号，确保每个摩擦不是主观感受，而能定位到具体布局/组件/状态边界。
- 对照外部实践：Vercel Web Interface Guidelines、NN/g heuristics、Linear command menu、GitHub PR review、Microsoft menu guidelines。

## 产物

- 新增 `docs/product-ux-friction-audit-2026-05-14.md`。
- 更新 `docs/product-ux-review.md` 的剩余摩擦和下一轮优化队列。
- 更新 `.agent/tasks.json`、`TASK-039.json` 和执行日志。

## 非目标

- 不改 CSS 和组件实现。
- 不更新视觉快照。
- 不调整 API 或数据库。
- 不把总目标标记为完成。

## 验收标准

- 审计文档列出外部参考、当前优势、P1/P2/P3 摩擦、证据和下一轮任务排序。
- 每个高优先级摩擦都绑定视觉截图或源码文件/行号。
- `product-ux-review.md` 的优化队列与新审计一致。
- 全量验证命令通过后提交。
