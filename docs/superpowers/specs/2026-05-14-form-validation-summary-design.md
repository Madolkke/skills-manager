# 表单验证错误摘要设计

## 背景

SkillHub 的主要写入表单已经接入 `WorkbenchField` 字段基础件，字段级 `error`、`aria-invalid` 和 `aria-describedby` 接口也已经预留。但当前必填字段主要依赖浏览器原生 required 校验：不同浏览器文案不一致、样式不可控、错误不会形成可扫读摘要，也不能稳定链接回字段。

本轮目标是做一个可复用的表单验证基础件，让用户提交缺字段的表单时能立刻知道哪里需要修正，并能用键盘或读屏顺利恢复。范围先限定为客户端必填字段验证，不改 API 错误结构。

## 外部实践

- [GOV.UK Error Summary](https://design-system.service.gov.uk/components/error-summary/) 要求有验证错误时同时展示 error summary 和字段旁 error message，并把错误摘要放在页面顶部。
- [GOV.UK Error Message](https://design-system.service.gov.uk/components/error-message/) 强调错误文案要直接包含字段 label、清晰简短、避免“invalid/required”这类泛化词，并且摘要和字段旁文案保持一致。
- [Vercel Web Interface Guidelines](https://vercel.com/design/guidelines) 建议不要预先禁用提交，允许提交不完整表单以展示验证反馈；错误放在字段旁，提交时聚焦第一个错误。
- [MDN aria-invalid](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-invalid) 说明自定义验证需要给错误字段设置 `aria-invalid`，并提供消息帮助用户理解如何修复。
- [MOJ Form Validator](https://design-patterns.service.justice.gov.uk/archive/form-validator/) 建议提交时验证，不在输入或 blur 时打扰用户；有错误时焦点移到 error summary。

## 产品设计

新增 `ValidatedForm`：

- 默认 `noValidate`，避免浏览器原生气泡抢走焦点和文案。
- submit 时扫描当前 form 中的 `required` 控件。
- 如果有缺失字段，不调用业务提交函数，而是展示 `formErrorSummary`。
- 错误摘要使用 `role="alert"`、`tabIndex=-1`，出现后自动聚焦。
- 每条摘要错误链接到对应字段；点击链接后焦点进入字段。
- 同一条文案同时显示在摘要和字段旁。
- 字段错误通过现有 `WorkbenchField` error API 渲染，字段自动获得 `aria-invalid="true"`。

默认 copy：

- 文本/textarea/select：`填写 {字段 label}`。
- 文件输入：`选择 {字段 label}`。
- checkbox/radio：`确认 {字段 label}`。

本轮先接入高频写入路径：

- `SkillLaunchpad` 的导入/新建表单。
- `WorkbenchInspector` 的 skill、new-skill、import-skill、new-variant、new-version、new-case、edit-case 表单。
- `QuickAddCases` 的单条快速添加表单。

## 范围

本轮修改：

- `apps/web/components/forms/form-validation.tsx`
- `apps/web/components/forms/form-validation.test.ts`
- `apps/web/components/forms/workbench-field.tsx`
- `apps/web/components/skills/skill-launchpad.tsx`
- `apps/web/components/inspector/workbench-inspector.tsx`
- `apps/web/components/eval-cases/quick-add-cases.tsx`
- `apps/web/app/globals.css`
- `apps/web/e2e/accessibility-workbench.spec.ts`

本轮不做：

- 后端字段级错误 contract。
- API `detail` 到具体字段的映射。
- 长度、格式、唯一性等复杂校验。
- 批量 case 行级错误摘要。
- 表单视觉大改版。

## 验收标准

- Vitest 覆盖默认 required 文案：文本、文件、checkbox 三类 label 生成。
- E2E 覆盖 Launchpad 新建 skill 空提交：显示 error summary、焦点移到 summary、摘要链接可聚焦 `Skill ID` 字段、字段旁显示同一错误文案、字段有 `aria-invalid="true"`。
- E2E 覆盖测评页快速添加空提交：显示 error summary、焦点移到 summary，并至少包含 `标题 / Input / Expected output` 三个错误。
- 现有 autocomplete、focus handoff、command menu、完整 SkillHub E2E 不回归。
- README、产品体验评审、摩擦审计、完成度审计和任务日志同步更新，明确后端字段错误映射仍是下一步。
