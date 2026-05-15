# 服务端批量 case 字段错误契约设计

## 背景

TASK-054 已经让前端批量粘贴 case 在提交前显示行级错误，但直连 `POST /api/eval-cases/batch` 的脚本、自动化导入器或未来表格型客户端仍只能拿到泛化字段名。旧响应会把 `cases[1].expected_output` 折叠成 `cases.expected_output`，用户无法知道应该修正第几行。

## 外部依据

- JSON:API error object：错误对象应该同时有人读 `detail` 和机器可读定位，客户端不应解析普通文案。
- RFC 9457 problem details：错误响应要保留稳定机器字段，便于不同客户端做一致回填。
- GOV.UK Error Summary：错误摘要应该能带用户回到需要修正的位置；批量录入时位置至少要精确到行。

## 方案

继续沿用 SkillHub 已有的 `detail + field_errors` 兼容契约，不引入第二套 JSON Pointer 字段。对请求体验证错误做最小差异：

- 普通数组 item 错误继续折叠到顶层字段，例如 `tags[0]` 映射为 `tags`。
- `cases[]` 是批量 case 的核心业务集合，保留索引为 `cases[n].field`。
- 文案使用 1-based 行号，例如 `第 2 行填写 Expected output。`
- `code` 保留 Pydantic/FastAPI 错误类型前缀，例如 `request.missing`、`request.string_too_short`。

## 范围

本阶段覆盖：

- `POST /api/eval-cases/batch` 中 `title`、`input_text`、`expected_output` 的缺失或空字符串。
- 继续保持 `tags[0] -> tags` 的旧字段映射。
- API 红绿测试覆盖 missing 和 empty string 两类错误。

暂不覆盖：

- 服务端解析 raw pasted text。
- CSV 引号、换行和转义。
- 批量 case 去重。
- 完整 RFC 9457 媒体类型和 `application/problem+json`。

## 验收

- 红灯 API 测试先失败于字段名缺少行号、文案无法定位行。
- 绿色后同一测试返回 `cases[0].title` 和 `cases[1].expected_output`。
- 旧请求体字段错误测试继续通过，证明 `tags[0] -> tags` 没被破坏。
