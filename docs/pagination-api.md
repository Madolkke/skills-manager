# 前端分页接口与按需加载

本次提供独立查询接口，保留旧接口的响应和行为。数据库先执行筛选、计数和 `LIMIT/OFFSET`，再批量装配当前页关联摘要；不通过读取全库后切片实现分页。

## 公共约定

- 页码 `page` 从 1 开始，默认 1；`page_size` 默认 20，范围 1–100。页面提供 20、50、100。
- 响应为 `{ "items": [], "total": 0, "page": 1, "page_size": 20 }`。`total` 是完整筛选结果数。
- 非法页码、页大小、枚举和额外查询字段返回 422。越界页返回空 `items` 和真实总数，前端自动回到最后有效页。
- 所有排序增加稳定 ID 次序；更新数据后记录可以自然移动，不保证分页快照。
- 普通查询沿用 REST actor，后台接口要求 `X-SkillHub-Admin-Key`。查询不记录详情访问，页面成功进入详情仍独立上报 visits。
- JSON 中日期采用 ISO 8601；JSON 对象中的业务摘要保留原有字段。

## 接口目录

| 方法与路径 | 查询及用途 |
| --- | --- |
| `POST /api/skills/query` | JSON 分页、广场筛选与分面计数 |
| `POST /api/admin/skills/query` | 同上，后台鉴权；不计算广场分面 |
| `GET /api/admin/overview` | 活跃 Skill、用户组、Tag Group、授权计数；最近 5 个 Tag Group 和 8 条授权 |
| `GET /api/admin/role-assignments/page` | `page`、`page_size`、`subject`、`resource`、`resource_type`、`role` |
| `GET /api/skills/{skill_id}/core` | 基础详情、`version_count`、`highest_version`；不含 `versions` 或版本文件 |
| `GET /api/skills/{skill_id}/versions/page` | 版本摘要，支持 `query` 搜索版本号、显示名称、变更说明 |
| `GET /api/skill-versions/{version_id}/detail` | `{version, previous}`；`include_files=false` 用于远程选择器 |
| `GET /api/skills/{skill_id}/guidance` | 概览最近 4 个版本，以及这些版本和当前版本的评审、发布状态及各自最新测评运行摘要 |
| `GET /api/skills/{skill_id}/reviews/page` | `status` 为 `open`、`closed`、`cancelled` 或空；额外返回完整 `counts` |
| `GET /api/reviews/{review_id}` | 直接读取选中评审详情，含参与者和回复 |
| `GET /api/skills/{skill_id}/eval-runs/page` | `eval_set_id`、`skill_version_id`、`status`；不含测试例结果 |
| `GET /api/publish-targets/enabled` | 发起评审所需启用目标目录，不读取发布历史 |

版本页按创建版本序号倒序展示；`previous` 和 `highest_version` 在完整版本集合中按 SemVer 确定，包括预发布版本。`previous` 不依赖当前页的相邻元素。最高版本摘要用于上传、编辑和 Workflow 同步的版本建议。

运行历史的“第几次”由 `total - (page - 1) * page_size - index` 确定；只有第一页面首行显示“最新”。评审和运行直达 ID 独立于当前列表页。

## 广场请求

```json
{
  "page": 1,
  "page_size": 20,
  "query": "网络",
  "category": "workflow",
  "sort": "updated",
  "tags": [{ "group_id": "domain", "value": "network" }],
  "evaluations_visible": true
}
```

- `category`：`all`、`workflow`、`verified`、`untested`、`mine`；我的分类依据当前 actor 与 owner。
- `sort`：`updated`、`score`、`name`；name 按 slug 排序。
- 搜索范围保持名称、slug、负责人、当前版本变更说明、内容摘要和 Tag 文本，按字面子串匹配。
- Tag 同组 OR、跨组 AND；失效级联路径不作为有效 Tag 命中。
- `counts` 的分类计数不受搜索、Tag 筛选和分页影响。
- `tag_counts` 键为 `group_id + "\u0000" + value`，数值表示在当前搜索、分类和 Tag 筛选基础上加入候选后的匹配数量。
- 后台支持 `diagnostic_group` 与 `diagnostic_kind=orphaned|missing_required`，从完整活跃 Skill 集合筛选诊断目标后分页。
- 授权页返回 `resource_label` 与 `resource_missing`，缺失资源使用 ID 显示，不下载全部 Skill 解析名称。

## 前端状态与兼容边界

公共 `usePagedQuery` 负责取消请求、忽略过期响应、防抖、错误重试及越界回退；`PaginationBar` 负责导航。列表用命名空间路由参数保存页码、每页数量和筛选，例如 `hub_page`、`hub_size`、`hub_filters`。后台用 `admin_tab` 保留标签页。

后台仅加载活动标签页及其依赖。Skill Tags 草稿以 Skill ID 保存在后台页面状态中，翻页、搜索和切换标签页不丢失；保存成功更新基线，取消或丢弃清理草稿。退出后台、身份变化或整页刷新不保留未保存草稿，不写浏览器持久存储。

后台发布确认仍使用原接口最近 200 条、前端分组分页和选择行为。单 Skill 发布概览、任务中心仍可请求完整历史；目录类模块保持原数据范围，仅改为按需加载。不能据此宣称整个应用已消除全部历史读取。

本次没有数据库迁移或 Workflow schema version 变更。对大量历史数据仍需关注深 OFFSET、模糊搜索及 Tag 候选聚合成本；结合实际查询计划再评估 trigram、Skill 时间排序和历史复合索引。

## 调用示例

```bash
curl -X POST http://127.0.0.1:8003/api/skills/query \
  -H 'Content-Type: application/json' \
  -H 'X-SkillHub-Actor: product-operator' \
  -d '{"page":2,"page_size":20,"category":"all","sort":"updated"}'

curl 'http://127.0.0.1:8003/api/skills/SKILL_ID/versions/page?page=2&page_size=20'
```
