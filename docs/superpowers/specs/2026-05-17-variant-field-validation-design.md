# Variant 写入字段校验设计

日期：2026-05-17

## 背景

`EvalCase`、保存视图、accepted verification note 和 promotion decision note 已经有字段长度上限、后端 `field_errors` 和前端错误摘要。但 variant 创建、候选版本追加和初始 skill 创建里的变体说明仍然只靠 `required`，长文本会直接入库，主工作区的 `VariantCreationComposer` / `WorkspaceVersionComposer` 也还没有接入共享字段基础件。

这会让用户在高频路径里得到不一致体验：有的表单会把错误聚焦到字段，有的表单只会显示全局 notice，甚至保存过长说明。

## 外部实践

- GOV.UK Error summary 要求有验证错误时显示错误摘要、把焦点移到摘要、摘要链接回具体字段，并且摘要里的错误文案要和字段旁一致。来源：<https://design-system.service.gov.uk/components/error-summary/>
- GOV.UK Error message 要求字段旁也显示错误，而不是只有页面顶部提示。来源：<https://design-system.service.gov.uk/components/error-message/>
- Atlassian Forms pattern 把错误放在字段附近，让用户能就地修复配置类表单。来源：<https://atlassian.design/patterns/forms>
- Material Design Text fields 强调错误文本应在输入控件附近，并给出如何修复的说明；也建议字段可表达字符限制。来源：<https://m1.material.io/components/text-fields.html>

适配到 SkillHub：继续沿用现有 `ValidatedForm + WorkbenchField`，不新增第二套表单系统。后端仍是权威校验，前端只负责把 `field_errors` 映射到相同字段。

## 本轮范围

新增以下上限：

| 字段 | 上限 | 适用 payload |
| --- | --- | --- |
| `variant_name` / `variant_label` / `label` | 80 字符 | 初始 skill、导入 skill、自建 variant |
| `variant_summary` / `summary` | 1000 字符 | 初始 skill、自建 variant |
| `change_summary` | 1000 字符 | 初始 skill、创建 variant、追加 variant version |

前端范围：

- `VariantCreationComposer` 改用 `ValidatedForm`、`TextField`、`TextAreaField` 和 `CheckboxField`。
- `WorkspaceVersionComposer` 改用 `ValidatedForm`、`SelectField`、`FileField`、`TextAreaField` 和 `CheckboxField`。
- `createVariant` 和 `createVariantVersion` 对 API 字段错误重新抛出，让表单显示错误摘要和字段错误。

## 不做

- 不引入字符计数器。
- 不做 owner_ref、role subject_id、strategy_ref 等其他字段上限。
- 不改变数据库 schema；当前 SQLite 文本列可承载这些限制，限制放在 API contract。
- 不做真实认证；这仍然是后续独立任务。

## 成功标准

1. API 对过长 variant label / summary / change summary 返回 `422` 和对应 `field_errors`。
2. 主工作区创建 variant 时，过长 summary 会显示错误摘要，摘要链接能回到 `summary` textarea，字段有 `aria-invalid="true"`。
3. 主工作区追加候选版本时，过长 change summary 会显示同样的表单错误体验。
4. 现有完整测试、构建、E2E 通过。
