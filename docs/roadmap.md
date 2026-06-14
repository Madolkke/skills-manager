# SkillHub Roadmap

本文档只记录当前正式版之后的产品方向，不再保留 demo 或 Variant 时代计划。

## 已收口

- 标准 Skill bundle 导入。
- 不可变 `SkillVersion`。
- case 和 `EvalSetVersion` 版本化。
- 手工 `EvalRun`，包含运行环境标签和 actual output。
- 历史页、run 详情、case result 和 actual vs expected。
- 后端真实 bundle diff。
- PostgreSQL-only 持久化，数据源通过配置注入。
- Web 正式工作台。

## 下一阶段

1. **Repository 拆分**

   `apps/api/skillhub/infrastructure/db/repositories.py` 仍然过大。下一轮应按写入命令、读模型、权限、diff/artifact 拆成多个协作模块，同时保持现有 API contract 不变。

2. **外部 Eval Runner**

   定义 `EvalStrategy` registry，让外部命令或脚本能生成标准 `{ passed, actual_output }` case result，再通过现有 `POST /api/eval-runs` 写入。

3. **Artifact Adapter**

   把当前数据库内 artifact 记录抽象成 file/object storage adapter，保留 digest、media type、size 和 immutable locator 语义。

4. **密集历史视图**

   历史和 run matrix 可以引入表格组件，支持更强的列配置、排序和导出。

5. **权限和团队化**

   当前本地 actor 机制足够单机使用。团队化前需要补组织、成员、OIDC 和 audit export。

## 明确不做

- 不恢复 Variant。
- 不恢复旧 demo/prototype runtime。
- 不恢复历史任务体系到主分支。
- 不把运行环境标签放进内容版本。
- 不把 Git branch 当作 `SkillVersion` locator。
