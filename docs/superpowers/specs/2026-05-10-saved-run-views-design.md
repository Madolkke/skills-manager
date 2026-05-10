# 测评历史保存视图设计

## 背景

当前历史页已经能按 `VariantVersion`、`EvalSetVersion`、`strategy`、`status` 筛选，并且同一组筛选会驱动 run 列表和 case x run 矩阵。问题是用户一旦积累多个变体、多个评测集版本和大量实验 run，每次重新组合筛选会很慢，也不利于团队形成稳定的验证入口。

本轮只做一个可落库的 `run_history` 保存视图，把当前筛选条件保存为命名视图。它不是复杂 BI，也不引入权限、排序、列配置和跨 skill 查询，先把“保存常用实验视角，一键恢复并继续验证”的闭环做扎实。

## 市场借鉴

Linear 的 saved views / filters 适合高频工作流：保存的是可复用查询意图，而不是复制数据。Airtable 的 view 证明同一份数据可以有多个视图入口。LangSmith experiment comparison 和 W&B Tables 都强调实验结果需要可筛选、可复现、可对比。

适配到 SkillHub：保存视图只保存筛选配置，列表、矩阵、详情仍实时读取后端 run 数据。这样不会制造第二份实验结果，也能为后续多维表格、共享视图、权限视图留接口。

## 用户体验

用户在历史页顶部看到一个“保存视图”区域：

- 选择框：`临时视图`、以及已经保存的视图名。
- 输入框：输入“候选 v2 / Primary v3”之类的视图名。
- 按钮：保存当前视图。
- 删除按钮：删除当前选中的保存视图。

选择某个保存视图后，页面立即把历史筛选恢复到该视图保存的条件；run 列表和矩阵自动刷新。用户仍然可以临时修改筛选，修改后不会自动覆盖已保存视图，必须再次保存为新名字。

## 数据模型

新增 `saved_views`：

- `id`：保存视图 ID。
- `skill_id`：所属 skill。
- `name`：用户可见名称，同一个 skill + view type 下唯一。
- `view_type`：当前只允许 `run_history`。
- `config`：JSON，只允许保存 `variant_version_id`、`eval_set_version_id`、`strategy`、`status`。值为 `all` 或空字符串时不入库。
- `created_at`：创建时间。
- `created_by`：创建人。

## API

- `GET /api/skills/{skill_id}/saved-views?view_type=run_history`：列出当前 skill 的保存视图。
- `POST /api/saved-views`：创建保存视图。
- `DELETE /api/saved-views/{saved_view_id}`：删除保存视图。

重复名称返回 `400`，未知 skill 返回 `404`，非法 `view_type` 返回 `400`。

## 测试

- Repository 测试：创建、列出、删除保存视图，并验证配置会规范化。
- API 测试：端点能完成保存视图 round trip。
- E2E 测试：用户在历史页保存一个筛选视图，切回临时筛选后再应用保存视图，run 列表和矩阵都恢复到保存条件。

