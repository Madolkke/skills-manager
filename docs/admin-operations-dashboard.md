# 后台运营看板

后台管理 → 运营看板提供 Skill 总量、首次新增、详情页 PV/UV、日/月趋势及热门 Top 10。默认展示近 12 个自然月，包含本月，日期范围最长 24 个月。图表按需加载，点击月份可下钻日趋势，数据表可查看精确数值。

## 统计口径

- 当前总量包含现存归档 Skill；新增量按首次创建统计，普通创建、Workflow 创建、外部同步首次创建均计入。更新版本、保存或覆盖导入不重复计数。
- PV 在成功打开 Skill 详情后上报；内部标签切换、数据刷新、工作流编辑器及普通 GET 请求不计数。离开后重进或浏览器刷新计新 PV。
- UV 由服务端按 actor 在查询范围内去重，各日/月独立去重；月 UV 不是日 UV 之和。默认 actor 与其他 actor 遵循相同规则。
- 统一按北京时间切分日期，数据库存储 UTC。截止日包含当天，不接受未来日期；本月截至查询时刻。
- 创建事实和访问事件不随 Skill 永久删除清理。热门榜保留已删除 Skill 的名称、负责人快照，并禁用链接。
- 上线时从现存 Skill 回填历史创建日期，无法恢复此前已永久删除的 Skill。访问数据从正式采集起点开始记录，未覆盖时期显示“未采集”，部分覆盖明确标注。

## HTTP 契约

`POST /api/skills/{skill_id}/visits` 使用现有 actor 会话/请求头，沿用 Skill 详情开放读取规则并检查 Skill 存在。请求严格为 `{ "event_id": "UUID" }`；身份、事件时间不能由 body 指定。成功返回 `{ "ok": true }`。同一 UUID、Skill、actor 的重试幂等；同一 UUID 用于其他身份或 Skill 返回 `409`。无效 UUID/额外字段返回 `422`，不存在的 Skill 返回 `404`。前端失败时以原 UUID 重试一次，不影响浏览。

`GET /api/admin/analytics/overview?start_date=2026-01-01&end_date=2026-09-13&granularity=month` 使用 `X-SkillHub-Admin-Key`。`start_date`、`end_date` 必填，`granularity` 为 `day|month`，默认 `month`。无效日期范围返回 `400`，非法查询格式或粒度返回 `422`，错误密钥返回 `403`。

响应包含 `start_date/end_date/granularity/timezone/generated_at`、`visits_started_at/demo_started_at/includes_demo/creation_history_note/coverage`、`metrics`、`trend`、`popular`。`coverage` 为 `none|partial|complete`；未采集时 PV/UV 返回 `null`，已覆盖的零访问桶返回 `0`。`metrics` 包含 `total_skills/new_skills/pv/uv`；趋势桶包含 `date/new_skills/pv/uv/coverage`；热门榜包含 `skill_id/name/owner_ref/pv/uv/deleted`。排名依次按 PV 降序、UV 降序、Skill ID 升序取前 10。服务端直接聚合，不返回原始 actor 列表。

## 本地演示

仓库根目录执行：

```powershell
uv --directory apps/backend run --env-file ../../.env python -m skillhub.models.schema.cli upgrade
uv --directory apps/backend run --env-file ../../.env python ../../scripts/seed-analytics-mocks.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-local-services.ps1 -SkipWorker
```

脚本生成 60 个有效示例 Skill、30 个模拟访客、12,000 条访问事件，覆盖最近 12 个月。名称带“演示”，ID 使用 `analytics-demo-` 前缀。固定随机种子可通过 `--seed` 指定；相同当前时间与种子生成相同内容，重复执行更新演示实体并替换模拟事件，保留其他业务数据及真实浏览事件。数据包含增长、周末低谷、长尾访问及零访问日期；不会写入未来或早于 Skill 创建的访问。

看板注明“包含模拟数据”，并分别展示正式采集与模拟数据的起点。实际手动浏览会在模拟数据基础上增加真实 PV/UV。后台入口为本地 Web 地址的 `/skills/admin`，使用已有后台密钥进入。

## 验证限制

本次 PostgreSQL 全量测试发现两项主分支已有的 `test_skill_list_statuses.py` 失败，已在独立 `main` 检出复现。实际应用测试库还包含工作流助手分支遗留的四张 `workflow_agent_*` 表，全库 Alembic drift 会报告这些额外表；本次迁移的干净数据库测试及统计表元数据检查通过。

## 本地验收记录（2026-09-13）

- 功能分支：`codex/admin-operations-dashboard`，从包含非互斥执行标记的本地 `main` 创建。
- 页面：`http://127.0.0.1:3030/skills/admin` → 运营看板；API：`http://127.0.0.1:8003`。
- 本地库已升级至 `0008_operations_analytics`，包含原有 15 个 Skill 和新增 60 个演示 Skill；12,000 条模拟访问、30 个模拟 actor。浏览器验收后累计 12,002 PV、31 UV，与 SQL 聚合一致。
- 后端完整 pytest 强制启用 PostgreSQL：686 passed、2 failed、1 skipped、2 subtests passed。两项失败为前述主分支问题；跳过项为 Windows 无符号链接创建权限。compile、ruff、CI 范围的 mypy 均通过。
- 前端完整测试 47 个文件、287 项通过；lint、类型检查及构建通过。构建仍提示部分按需加载资源超过 500 kB。
- Alembic revision 与干净库 drift 检查通过；本地库 drift 仅有前述四张额外表及其索引。EXPLAIN 确认窄时间范围查询使用时间索引、单 Skill 查询使用 Skill/时间联合索引，统计接口无逐 Skill 查询。
- 浏览器已验证桌面和 390 px 窄屏、悬浮提示、月份下钻、本月与自定义日期、未采集空状态、精确数据表、榜单详情入口及访问计数。窄屏页面无横向溢出；内部标签切换不增加 PV，刷新增加 PV 且相同 actor 的 UV 不增加。失败重试和过期响应由单元测试覆盖，未进行浏览器断网注入测试。
