# 服务端批量 case 字段错误契约 Implementation Plan

**Goal:** 让直接调用 `POST /api/eval-cases/batch` 的客户端在批量 case 缺字段或空字段时获得带行号的 `field_errors`。

## Steps

- [x] **Step 1: 任务登记和红测**
  - 新增 `.agent/tasks/TASK-055.json` 并登记到 `.agent/tasks.json`。
  - API 测试覆盖第 1 行标题为空和第 2 行缺少 `expected_output`。
  - 红灯先失败于旧字段名 `cases.title` / `cases.expected_output` 和泛化文案。

- [x] **Step 2: 字段路径映射**
  - `request_body_field` 保留 `cases[n]` 索引。
  - 非 `cases` 数组仍忽略 item 索引，保持 `tags[0] -> tags`。

- [x] **Step 3: 行级中文文案**
  - 新增批量 case 字段 label 映射。
  - `missing` 和 `string_too_short` 返回 `第 n 行填写字段。`
  - 中文 label 不加多余空格，英文 label 保留自然空格。

- [x] **Step 4: 文档与验证**
  - 更新 API contract、README、产品体验评审、完成度审计、摩擦审计、任务日志和本任务规格。
  - 运行后端、前端、E2E、diff check 和 JSON 校验。

## Rollback

如果未来表格型客户端需要完整 JSON Pointer，可以在 `field_errors` 中追加 `pointer` 字段；不能移除现有 `field = cases[n].field`，否则会破坏当前表单和自动化脚本的字段回填契约。
