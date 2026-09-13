# 表达式函数库合并验收

验收日期：2026-09-14。本地 API：`http://127.0.0.1:8003`；Web：`http://127.0.0.1:3030/skills/admin`。

## 集成范围

从 `main` 建立 `codex/integrate-expression-function-library`，完整合并 `codex/expression-function-library`，保留源提交历史。集成提交为 `b57da6e`，合入本地 main 的合并提交为 `413339e`。功能分支保留。

保留运营看板、非互斥标记、自定义函数 Collection、表达式输入绑定、主分支类型推断和中文诊断位置修复。函数体仅保存文本，不增加执行能力。空目录不回退旧内置列表，参数顺序以 `x-parameter-order` 持久化。公开表达式契约维持版本 1，不公开函数体。

## 迁移与初始化

在仓库根目录执行：

```powershell
uv --directory apps/backend run --env-file ../../.env python -m skillhub.models.schema.cli upgrade
uv --directory apps/backend run --env-file ../../.env python scripts/seed_expression_functions.py
```

唯一 head 为 `0010_expression_analytics_merge`，父迁移为 `0008_operations_analytics`、`0009_expression_functions`。空库及两侧版本升级测试通过。本地数据库已实际升级；seed 首次创建 14 条，重复执行结果为 `created=0 skipped=14 updated=0`，未使用 `--force`。

本地 drift 仅包括已有的 `workflow_agent_events`、`workflow_agent_proposals`、`workflow_agent_sessions`、`workflow_agent_runs` 四张遗留表及其索引，均保留。干净测试数据库的 revision/drift 检查通过。访问统计查询确认使用时间索引及 Skill/时间联合索引。

## 自动化结果

| 检查 | 最终结果 |
| --- | --- |
| 完整 PostgreSQL pytest，`SKILLHUB_REQUIRE_POSTGRES_TESTS=1` | 698 passed，1 skipped，2 subtests passed |
| Python compile、ruff | 通过 |
| CI 范围 mypy：`skillhub/models/schema` | 20 个文件通过 |
| 完整前端测试 | 49 个文件，298 项通过 |
| 前端 lint、vue-tsc、Vite build | 通过 |
| OpenAPI | 114 条路径，契约快照通过 |
| 迁移、seed 幂等、数据保留 | 通过 |

原先记录的两项 main 状态测试在本次完整测试中通过，不将其宣称为本次修复。Windows 符号链接相关测试仍跳过。构建仍提示部分 chunk 超过 500 kB，不影响构建成功。

## 内置浏览器逐项验收

以下操作均在合入后的本地 main 上实际进行；数据持久化另以 API 或数据库核对。

| 项目 | 操作与预期 | 实际结果 |
| --- | --- | --- |
| 函数列表、搜索、切换 | 初始化内置函数，搜索 round，切换记录 | 14 条内置记录；round 搜索唯一命中，参数 value/ndigits 与选中记录一致 |
| 创建、编辑、保存 | 新建 qa_merge_probe，修改说明、语言、参数及返回 Schema、函数体，刷新 | 全部保留；语言 python-text、说明“已更新说明”、函数体抛异常文本均原样保存，未执行 |
| 表单校验 | 非法名称 class、重名 len、非 object 参数根 Schema、空函数体 | 非法输入禁用保存或确认；重名显示错误且保留草稿；空函数体禁用保存 |
| Schema 双向编辑 | JSON 输入嵌套 object/array，视觉必填切换后查看 JSON | 层级、类型和 required 一致；zvalue/amount 的参数顺序经保存刷新仍一致 |
| 撤销 | 修改说明、必填状态、函数体后撤销 | 恢复已保存内容，撤销状态重置 |
| 停用 | 停用专用函数，重新打开 Workflow | 调用原文保留，字段及全局校验显示未注册，禁止同步 |
| 删除 | 取消删除再确认删除，重新进入编辑器 | 取消保留记录；确认删除后列表更新；qa_merge_probe 无补全且旧调用报未注册 |
| 表达式补全 | 条件表达式输入 qa_、Ctrl+Space | 提示 qa_merge_probe、参数 zvalue/amount、返回 object 和说明 |
| 模板补全 | 条件说明中输入 `结果 {{ qa_` | 同样提供函数签名；不完整模板显示结束标记诊断 |
| 参数检查 | 交换 string/integer 实参，再改为正确关键字调用 | 分别标出 zvalue/amount 类型不兼容；正确调用无该诊断 |
| Workflow 往返 | 保存条件、模板及 integer 输入绑定，下载 Bundle 后通过浏览器回导、刷新 | revision 3 保存、revision 4 回导；表达式原文、非互斥 true 和函数 Collection source 完整保留 |
| Tag 展示 | 验收按值保留复选；验收按选中改为多选下拉 | 前台两类控件均可选中，结果为对应专用 Skill；清除恢复未选择状态 |
| 指定父值级联 | A 下挂载验收按值，选择 A 后切换 B | A 时出现；B 时隐藏并清理其子值，结果切换到 B 专用 Skill |
| 任意父值级联 | 父组选中时挂载验收按选中 | A/B 均激活；A 切 B 保留已选子项；取消最后父项清理全部子项 |
| 看板回归 | 刷新近 12 个月指标，与数据库比对 | 清理后总量/新增均 75，PV 12,002，UV 31；工作流编辑期间未新增访问 |
| 窄屏 | 390×844 检查筛选、后台导航、函数管理、JSON 弹窗并保存 | 均可操作；DOM clientWidth/scrollWidth 均 375（含滚动条），无横向溢出；最终恢复桌面视口 |

验收中的独立 Workflow、标签组/级联、函数及导入 Collection 已清理，保留审计记录。看板演示数据和其他业务内容未清理。未额外执行全局函数体；这属于明确不支持的能力，不作为执行成功验收。

## 浏览器发现并修复

1. Schema 必填控件错误读取父级状态：改为读取对应属性的 required，向嵌套数组传播编辑选项，增加组件回归测试。
2. 表达式绑定导出带 `value: null` 导致回导拒绝：序列化时省略表达式的 value，保留 literal null，新增往返测试。
3. 字段诊断正确但全局校验显示零错误：将函数未注册及参数诊断纳入全局错误列表，新增批量诊断回归测试。
4. 原生删除确认框阻塞内置浏览器：复用项目 Modal，验证取消及确认路径并补充测试。

## 本地证据

截图和日志仅保存在本地 `.tmp/`，不提交仓库：

- `function-catalog.png`：最终函数库。
- `function-schema-mobile.png`：窄屏嵌套 Schema 编辑。
- `function-tags.png`、`function-tags-mobile.png`：两类标签展示及级联筛选。
- `function-disabled.png`：停用后的全局未注册诊断。
- `function-workflow.png`：回导后 Workflow。
- `function-analytics.png`：看板回归。
- `function-backend-final.log`、`function-frontend-final.log`、`function-build-final.log`、`function-drift-final.log`：检查输出。
