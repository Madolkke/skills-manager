# 产品操作摩擦审计计划

## 输入收集

1. 读取最新 Vercel Web Interface Guidelines。
2. 读取 NN/g heuristics、Linear command menu、GitHub PR review、Microsoft menu guidelines 的相关实践。
3. 查看当前视觉回归截图。
4. 检查 `product-ux-review.md` 和完成度审计。
5. 搜索关键 CSS/组件，定位空间、表单、focus、URL state 和审计视图证据。

## 实施步骤

1. 新增 `docs/product-ux-friction-audit-2026-05-14.md`。
2. 更新 `docs/product-ux-review.md` 中的剩余摩擦和下一轮优化队列。
3. 新增 TASK-039 任务记录和规格/计划文档。
4. 写入 `.agent/logs/LOG.md`。

## 验证步骤

1. `cd apps/web && npm run test:unit`
2. `cd apps/web && npm run typecheck`
3. `cd apps/web && npm run build`
4. `cd apps/web && npm audit --omit=dev`
5. `cd apps/api && uv run pytest`
6. `cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e`
7. `git diff --check`

## 回滚策略

如果审计结论和证据不一致，删除本轮新增审计文档，恢复 `product-ux-review.md` 的上一版队列。由于本任务不改代码，回滚不会影响产品运行。
