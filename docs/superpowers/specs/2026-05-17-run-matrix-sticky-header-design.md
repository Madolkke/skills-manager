# Run matrix sticky header 设计

## 背景

Run matrix 已经把 case 首列做成 sticky，横向滚动时用户不会丢失行上下文。但当 case 数量继续增加、矩阵纵向滚动时，run header 会离开视口，用户看单元格时仍然需要回到顶部确认列含义。

## 目标

让 Run matrix 的表头在矩阵内部纵向滚动时保持可见。它应该和现有 sticky case 首列配合：左上角 `Case` header 同时保持横向和纵向上下文。

## 范围

- Run matrix `thead th` 使用 sticky header。
- 左上角 case header 保持更高层级，避免和 run header / case title 交叠。
- 新增 E2E 检查 sticky header CSS 语义。
- 更新 run comparison 视觉基线。

## 非范围

- 不引入第三方 data grid。
- 不改 Run matrix 数据模型。
- 不新增列配置或指标列。
- 不改 CSV 导出。

## 验收

- `.runMatrixRunHeader` 的 computed `position` 为 `sticky`。
- `.runMatrixRunHeader` 的 computed `top` 为 `0px`。
- `.runMatrixCaseHeader` 继续保持 sticky left。
- 完整回归通过。
