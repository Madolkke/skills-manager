# Run matrix sticky header 计划

## 目标

补齐 Run matrix 的纵向扫读上下文，让表头在矩阵滚动时保持可见。

## 步骤

1. 写红灯 E2E
   - 在 Run matrix 用例中断言 run header 是 sticky。
   - 保留 case header sticky left 断言。

2. 实现 CSS
   - 给 `thead th` 添加 sticky top。
   - 调整 `Case` header 的 z-index，避免左上角交叠。

3. 视觉验证
   - 更新 run comparison snapshot。

4. 文档和任务记录
   - 更新产品体验审计和任务记录。

5. 完整验证
   - API、Web unit、build、typecheck、audit、E2E、diff check、任务 JSON。
