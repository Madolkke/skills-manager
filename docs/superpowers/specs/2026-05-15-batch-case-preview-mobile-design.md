# 批量 case 预览移动端护栏设计

## 背景

TASK-057 给批量粘贴 case 增加了逐行预览表，但移动端仍沿用桌面两栏网格：textarea 和统计卡会并排挤压，用户在 390px 宽度下很难先编辑输入、再确认预览。这个问题不影响接口闭环，但会让手机或窄窗口上的高频“补 case”动作变钝。

## 方案

本阶段只做响应式护栏，不重做测评页信息架构：

- 批量模式在 `max-width: 640px` 下改为单列。
- textarea、统计卡、预览表、错误列表和提交按钮纵向排布。
- 页面整体不能产生文档级横向滚动。
- 预览表保留内部横向滚动，因为列内容本身是数据表，不应强行压缩成难读的卡片。
- 同一媒体查询顺手覆盖单条 quick case 表单，避免标题/Input/Expected output 在窄屏挤成多列。

## 验收

- E2E 先在未修复样式下失败：统计卡仍位于 textarea 同行。
- 修复后移动端测试通过：
  - 统计卡在 textarea 下方。
  - `document.documentElement.scrollWidth <= viewport width`。
  - `.quickCaseBatchTableFrame` 内部 `scrollWidth > clientWidth`，说明表格横向滚动被限制在容器内。

## 非目标

- 不做新的移动端测评页导航。
- 不做表格内联编辑。
- 不做 CSV 高级解析。
