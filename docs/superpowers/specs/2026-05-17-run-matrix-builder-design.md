# Run Matrix Builder 设计

## 背景

Run matrix 是后续多维表格、自定义指标列和实验分析的核心读模型。目前 `SqlSkillRepository.eval_run_matrix_for_skill` 同时负责 SQL 查询和矩阵 cases/cells 组装。随着 Summary、Impact、CSV、saved view 继续增长，把产品语义留在 repository 里会让后续扩展变脆。

## 目标

- 新增应用层纯函数 builder，负责把 skill、run context、每个 run 的 eval set cases 和 case results 组装成矩阵 read model。
- repository 继续负责 SQL 查询、权限/存在性检查和 row_dict 转换。
- 保持 API 返回结构完全不变：`skill`、`runs`、`cases`、`cells`。
- 给 builder 补直接单元测试，覆盖跨 run 合并同一个 case、多 case version 去重、缺失 result 不生成 cell。

## 非目标

- 不改变 Run matrix 前端。
- 不新增自定义指标列。
- 不改数据库 schema。
- 不重写 `_filtered_eval_run_rows` 或 `_eval_set_cases`。
- 不更新 README，因为没有用户可见行为变化。

## 设计

新增 `apps/api/skillhub/application/run_matrix.py`：

- `build_eval_run_matrix(skill, runs, eval_set_cases_by_run, results_by_run) -> dict[str, Any]`

输入是 repository 已经查好的 dict/list 数据。builder 不知道 SQLAlchemy、不访问数据库，只维护矩阵结构规则。后续新增指标列或多维聚合时，可以优先在这个模块加纯函数测试。

## 验收

- 新 builder 单元测试先红后绿。
- `tests/test_sql_repository.py -k eval_run_matrix` 和 `tests/test_api_commands.py -k eval_run_matrix` 通过。
- 完整 API、Web unit、build、typecheck、audit、E2E、diff check 和任务 JSON 检查通过。
