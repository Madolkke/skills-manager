# 基于测评集的 SkillHub MVP 设计稿

## 1. 概要

这个项目不是普通的 SkillHub，也不是 GitHub for skills。它的定位是：

> 一个以测评集为核心资产、以变体为分发单位、通过策略层持续评估和升级 skill 的平台。

分发只是用户最容易看到的表层。真正的产品价值在下面：

- 每个 skill 有持续增长的测评资产池。
- 每个可安装对象都是一个 `Variant`。
- 每个 `Variant` 维护自己的线性 `VariantVersion` 历史。
- 失败反馈可以作为 `EvalCase` 的来源，但不是 v1 的独立主模块。
- 每次比较都绑定明确的 `EvalSetVersion`。
- 测评、排序、升级、门禁都通过可替换策略完成。
- 内容存储层负责保存 skill 内容和 diff；平台负责保存引用、证据和关系。Git 是可选实现之一，但不是唯一实现。

MVP 要证明的核心闭环是：

```text
Skill -> Variant -> VariantVersion -> EvalSetVersion -> EvalRun -> CaseResult -> 发布新 VariantVersion
```

核心模型必须保持小而稳定。tag 匹配、测评方式、排序规则、自动升级、发布建议都属于策略层，不应该写死进主对象字段。

## 2. 产品原则

- `Skill` 是稳定入口，本质上指向默认 `Variant`。
- `Variant` 是分发单位，表示一组 tags 约束下的当前最优解。
- 同一 `Variant` 的内容迭代通过 `VariantVersion` 表达，不通过父子 variant 表达。
- v1 的 tags 只用简单字符串，例如 `codex`、`gpt5.4`、`opencode`、`minimax2.7`。
- tags 表示某个 variant 被优化或测评过的运行约束，不表示继承、权限或固定分类体系。
- 测评集必须版本化。所谓“当前最优”，必须说明它在哪个 `EvalSetVersion` 上被验证过。
- bad case 只作为来源说明或变更说明出现。只有转化成 eval case 并进入测评集版本后，才产生长期价值。
- 内容存储层保存 skill 内容和 diff；平台存引用、证据和可查询关系。Git 可以作为一种实现，但核心模型不依赖 Git。
- `verified`、`recommended` 这类标签不是 v1 的核心状态，可以后续由测评结果派生。
- 策略必须可替换。平台应能编排 SkillGrade、Skill Bench、自定义脚本、LLM rubric、未来的自动升级器等外部能力。

## 3. MVP 非目标

- 不做完整 GitHub 替代品。
- 不做完整 marketplace 排名系统。
- 不提前设计复杂 typed tag ontology。
- 不把自动 skill evolution 作为第一产品面。
- 不要求一个 skill 只有一个官方版本。
- 不在业务数据库里存完整 skill 内容。
- 不把 LLM judge 作为唯一事实来源。

## 3.1 原型策略：先做纯前端

第一版可以先做纯前端原型，后台数据全部模拟。目标不是验证存储和分布式执行，而是验证产品闭环是否顺手：

```text
查看 skill -> 查看默认 variant -> 查看变体地图 -> 查看版本历史 -> 查看 eval set version -> 手工记录 eval results -> 发布新 variant version
```

纯前端原型中的简化：

- `ContentRef` 使用 `inline_bundle` 或 mock artifact，不接真实 Git。
- `EvalRun` 直接使用预置结果，不启动真实 runner。
- `CaseResult` 使用 mock 数据，但必须按真实 schema 组织。
- 来源反馈可以作为 `EvalCase.source_type` 或版本变更说明出现，不单独做主流程。
- 排序和推荐先不作为主体验，重点验证对象关系和结果解释是否清楚。
- 所有数据放在本地 TypeScript fixtures 或 JSON fixtures 中。

验收标准：

- 用户能理解 variant 是分发单位。
- 用户能看懂为什么某个 variant 在某个 eval set version 下表现更好。
- 用户能看到新增 case 或发布新版本后，结果如何变化。
- 用户不需要理解底层策略，也能完成“查看结果、比较、升级”的主流程。

这一步跑通后，再决定真实后端、内容存储、runner 和外部 adapter 的实现方式。

## 4. 核心对象

稳定模型是一张由轻量节点和引用组成的图。主对象只保存身份、引用和少量可查询字段；大内容进入 artifact。

### Skill

`Skill` 是命名空间，不是最终分发物。

```text
Skill(
  id,
  slug,
  owner_ref,
  default_variant_ref,
  created_at
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 平台内部主键。建议使用 UUID/ULID，不承载业务语义。 |
| `slug` | 是 | 面向 URL、CLI、安装命令的稳定标识，例如 `code-reviewer`。同一 owner 下唯一。 |
| `owner_ref` | 是 | 指向用户、组织或命名空间。用于权限、归属和展示。 |
| `default_variant_ref` | 是 | 指向默认 `Variant.id`。Hub 首页和安装按钮默认使用这个引用。 |
| `created_at` | 是 | skill 创建时间。 |

规则：

- 一个 skill 可以有多个 variants，但必须有一个默认 variant。
- MVP 中一个 skill 对应一个 eval corpus。
- skill 是稳定入口；面向用户的说明、tags 和内容引用主要在 variant/version 上。

### Variant

`Variant` 是可安装、可比较、可展示的对象。

```text
Variant(
  id,
  skill_ref,
  name,
  label,
  summary,
  tag_set_ref,
  current_version_ref,
  created_at
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 平台内部主键。variant 是用户可安装和可比较的最小单位。 |
| `skill_ref` | 是 | 指向所属 `Skill.id`。用于查询某个 skill 下的所有 variants。 |
| `name` | 是 | 面向作者和用户展示的短名称，例如 `Variant A`。 |
| `label` | 是 | 更可读的变体标题，例如 `Codex baseline`。 |
| `summary` | 是 | 说明该变体适用的运行约束和设计意图。 |
| `tag_set_ref` | 是 | 指向 `TagSet.id`。表示该 variant 声称适用、并应参与比较的运行约束集合。 |
| `current_version_ref` | 是 | 指向当前分发的 `VariantVersion.id`。更新同一变体时只移动这个指针。 |
| `created_at` | 是 | variant 注册时间，不一定等于底层内容创建时间。 |

规则：

- variant 不直接保存内容，只保存当前版本指针。
- 更新同一约束下的最优解时，创建新的 `VariantVersion`，再更新 `current_version_ref`。
- 多个 variants 可以拥有相同 tag set。
- variant 之间不表达 parent/child lineage。fork、PR、来源追踪属于后续协作层。
- 只有注册到平台的 variants 对用户可见；内容存储层里可以存在未注册实验内容。

### VariantVersion

`VariantVersion` 是某个 variant 在某一时间点的不可变内容快照。

```text
VariantVersion(
  id,
  variant_ref,
  version,
  content_ref,
  change_ref?,
  change_note?,
  created_at
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 平台内部主键。 |
| `variant_ref` | 是 | 指向所属 `Variant.id`。 |
| `version` | 是 | 在该 variant 内部递增的版本号，例如 `v1`、`v2`。 |
| `content_ref` | 是 | 指向不可变 skill 内容。可以是 Git commit、对象存储 artifact、外部 repo digest 或 mock bundle。 |
| `change_ref` | 否 | 指向更结构化的变更记录。v1 可以只用 `change_note`。 |
| `change_note` | 否 | 类似 commit message，说明这次版本为什么发布。 |
| `created_at` | 是 | 版本创建时间。 |

规则：

- `VariantVersion` append-only，不原地修改。
- `EvalRun` 必须指向 `VariantVersion`，否则历史结果会随着当前指针移动而失真。
- 历史版本可以继续展示、复测和比较。

### TagSet

`TagSet` 是规范化后的字符串集合。

```text
TagSet(
  id,
  tags_hash,
  tags
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 平台内部主键。 |
| `tags_hash` | 是 | 规范化后 tags 的哈希，用于唯一约束和快速查找。 |
| `tags` | 是 | 排序、去重后的字符串数组，例如 `["codex", "gpt5.4"]`。 |

规则：

- `["codex", "gpt5.4"]` 和 `["gpt5.4", "codex"]` 是同一个 tag set。
- v1 不区分 tag 类型。
- tag 匹配规则属于后续 selection strategy，不属于数据模型。

### ContentRef

`ContentRef` 标识某个 variant version 对应的不可变 skill 内容。

```text
ContentRef(
  kind,
  locator,
  digest,
  path?,
  meta_artifact_ref?
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `kind` | 是 | 内容存储类型，例如 `git`、`artifact`、`external_repo`、`inline_bundle`。 |
| `locator` | 是 | 内容定位符。`git` 可为 repo + commit，`artifact` 可为 artifact id，`external_repo` 可为 URL + revision。 |
| `digest` | 是 | 内容摘要，用于不可变校验、去重和复现。 |
| `path` | 否 | 内容包内的 skill 路径。Git monorepo 或 bundle 中多 skill 时需要。 |
| `meta_artifact_ref` | 否 | 指向更完整的内容元数据，例如 Git provider 信息、bundle manifest、外部 repo 权限信息。 |

规则：

- 可以作为结构化字段内嵌在 `VariantVersion` 中。
- `digest` 必须不可变，是内容复现的核心。
- Git 是推荐实现之一，因为它天然支持 diff、回滚、分支和 PR。
- 平台核心模型不能依赖 Git 语义。eval、来源转化等流程只依赖 `content_ref`。
- v1 纯前端原型可以使用 `artifact` 或 `inline_bundle` 模拟内容，不需要真实 Git 后端。

### EvalCorpus

`EvalCorpus` 是某个 skill 的测评资产池。

```text
EvalCorpus(
  id,
  skill_ref,
  created_at
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 平台内部主键。 |
| `skill_ref` | 是 | 指向所属 `Skill.id`。MVP 中一个 skill 一个 corpus。 |
| `created_at` | 是 | corpus 创建时间。 |

规则：

- corpus 是资产池，不是一次固定运行的列表。
- `EvalSetVersion` 是从 corpus 中选出的不可变快照。

### EvalCase / EvalCaseVersion

`EvalCase` 是可复用的测评场景入口。`EvalCaseVersion` 是不可变测试内容快照。

```text
EvalCase(
  id,
  corpus_ref,
  title,
  source_type,
  current_version_ref,
  origin_ref?,
  created_at
)

EvalCaseVersion(
  id,
  case_ref,
  version,
  input_artifact_ref,
  expectation_artifact_ref,
  grader_ref,
  created_at
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 平台内部主键。 |
| `corpus_ref` | 是 | 指向所属 `EvalCorpus.id`。 |
| `title` | 是 | 场景标题。 |
| `source_type` | 是 | case 来源：`manual`、`bad_case`、`imported`、`generated`。 |
| `current_version_ref` | 是 | 指向当前维护的 `EvalCaseVersion.id`。 |
| `origin_ref` | 否 | 指向来源对象，例如 `BadCase.id`、外部 benchmark case、导入批次或生成任务。 |
| `created_at` | 是 | case 创建时间。 |
| `EvalCaseVersion.id` | 是 | 平台内部主键。 |
| `case_ref` | 是 | 指向所属 `EvalCase.id`。 |
| `version` | 是 | case 内递增版本号。 |
| `input_artifact_ref` | 是 | 指向输入内容 artifact，例如 prompt、文件集合、代码 diff、网页快照或多源材料。 |
| `expectation_artifact_ref` | 是 | 指向期望行为 artifact。可以是精确答案、验收条件、rubric 描述或禁止行为列表。 |
| `grader_ref` | 是 | 指向 `Grader.id`，定义如何判分。 |

规则：

- `source_type` 可取 `manual`、`bad_case`、`imported`、`generated`。
- `origin_ref` 可以指向 bad case、外部 benchmark、导入批次或生成任务。
- case 内容不可变。如需修正，创建新 `EvalCaseVersion`，并纳入新的 eval set version。
- MVP 中只记录 pass/fail。权重、严重度、rubric 细分都留给后续策略层。

### Grader

`Grader` 定义某个 case 如何被判分。

```text
Grader(
  id,
  kind,
  config_artifact_ref,
  version,
  created_at
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 平台内部主键。 |
| `kind` | 是 | 判分器类型，例如 `manual`、`deterministic`、`script`、`llm_rubric`。 |
| `config_artifact_ref` | 是 | 指向 grader 配置 artifact，例如脚本路径、rubric、阈值、judge prompt、解析规则。 |
| `version` | 是 | grader 配置版本。grader 变化必须产生新版本，避免历史结果不可解释。 |
| `created_at` | 是 | grader 创建时间。 |

MVP 推荐支持：

- `manual`
- `deterministic`
- `script`
- `llm_rubric`

规则：

- grader 配置必须版本化。
- grader 变化时创建新版本。
- eval set version 应通过 case 间接引用精确的 grader 版本，保证可复现。

### EvalSetVersion

`EvalSetVersion` 是可运行的不可变测评快照。

```text
EvalSetVersion(
  id,
  corpus_ref,
  version,
  case_index_artifact_ref,
  created_at
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 平台内部主键。 |
| `corpus_ref` | 是 | 指向所属 `EvalCorpus.id`。 |
| `version` | 是 | corpus 内递增版本号，例如 `1`、`2`，或语义化版本。 |
| `case_index_artifact_ref` | 是 | 指向 case index artifact。内容是确定顺序的 eval case version refs 列表。 |
| `created_at` | 是 | 该快照创建时间。 |

规则：

- case index 是确定顺序的 eval case version ref 列表。
- 旧版本必须保留，方便复现历史排名。
- bad-case-derived eval case 加入后，创建新的 eval set version。
- variant 的测评结果必须明确绑定 eval set version。

### EvalRun

`EvalRun` 记录某个策略对某个 variant version 和某个 eval set version 的一次执行。

```text
EvalRun(
  id,
  variant_version_ref,
  eval_set_version_ref,
  strategy_ref,
  run_config_hash,
  status,
  result_artifact_ref?,
  started_at,
  finished_at?
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 平台内部主键。 |
| `variant_version_ref` | 是 | 指向被测 `VariantVersion.id`。 |
| `eval_set_version_ref` | 是 | 指向使用的 `EvalSetVersion.id`。没有这个字段，结果不可比较。 |
| `strategy_ref` | 是 | 指向具体 eval strategy 实现和版本。 |
| `run_config_hash` | 是 | 策略配置、运行环境、工具版本、模型配置等规范化后的哈希。 |
| `status` | 是 | 最小状态：`queued`、`running`、`finished`、`failed`。 |
| `result_artifact_ref` | 否 | 指向完整 run 报告 artifact，例如日志、HTML 报告、外部工具输出。 |
| `started_at` | 是 | run 开始时间。 |
| `finished_at` | 否 | run 结束时间。未结束时为空。 |

规则：

- `status` 保持最小集合：`queued`、`running`、`finished`、`failed`。
- run 不指向 mutable variant current 指针，必须固定到某个 variant version。
- `run_config_hash` 捕获策略配置、运行配置、工具版本和相关环境信息。
- 同一输入允许重复运行，因为 LLM 和 agent 行为可能有随机性。
- 聚合分数可以缓存，但事实来源是 case results 和 artifacts。

### CaseResult

`CaseResult` 记录一次 run 中某个 case 的规范化结果。

```text
CaseResult(
  run_ref,
  case_ref,
  passed,
  score,
  evidence_artifact_ref?,
  error_artifact_ref?
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `run_ref` | 是 | 指向所属 `EvalRun.id`。 |
| `case_ref` | 是 | 指向被判分的 `EvalCase.id`。 |
| `passed` | 是 | 该 case 是否通过。用于快速查询和对比。 |
| `score` | 是 | 归一化分数，范围 `0.0..1.0`。 |
| `evidence_artifact_ref` | 否 | 指向判分证据，例如引用片段、脚本输出、judge 解释。 |
| `error_artifact_ref` | 否 | 指向错误信息，例如运行超时、脚本异常、解析失败。 |

规则：

- `score` 归一化到 `0.0..1.0`。
- `passed` 可以由 score 和 grader 阈值推导，但存下来能简化查询。
- evidence 要足够解释判分原因。

### BadCase

`BadCase` 是原始失败反馈。

```text
BadCase(
  id,
  skill_ref,
  variant_ref?,
  tag_set_ref?,
  raw_input_artifact_ref,
  raw_output_artifact_ref?,
  failure_note_artifact_ref?,
  reporter_ref?,
  created_at
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 平台内部主键。 |
| `skill_ref` | 是 | 指向相关 `Skill.id`。 |
| `variant_ref` | 否 | 指向触发失败的 variant。用户只知道 skill、不知道 variant 时可为空。 |
| `tag_set_ref` | 否 | 记录失败发生时的运行约束。用于后续分析和转化。 |
| `raw_input_artifact_ref` | 是 | 指向原始输入 artifact。 |
| `raw_output_artifact_ref` | 否 | 指向原始输出 artifact。没有输出、执行中断或用户只提交描述时可为空。 |
| `failure_note_artifact_ref` | 否 | 指向用户或 reviewer 对失败的说明。 |
| `reporter_ref` | 否 | 指向提交者。匿名反馈可为空或指向匿名主体。 |
| `created_at` | 是 | bad case 提交时间。 |

规则：

- bad case 不直接影响排名。
- 原始输入、输出和说明必须保留，方便审计和重新解释。
- 去重和清洗应发生在转成 eval case 之前或过程中。

### Change

`Change` 解释某个 variant 为什么存在。

```text
Change(
  id,
  skill_ref,
  source_type,
  source_ref?,
  note_artifact_ref?,
  actor_ref?,
  created_at
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 平台内部主键。 |
| `skill_ref` | 是 | 指向相关 `Skill.id`。 |
| `source_type` | 是 | 变更来源类型，例如 `manual`、`bad_case_fix`、`generated_upgrade`。 |
| `source_ref` | 否 | 指向来源对象，例如 `BadCase.id`、`EvalRun.id`、外部导入记录。 |
| `note_artifact_ref` | 否 | 指向变更说明 artifact。 |
| `actor_ref` | 否 | 指向创建变更的人、agent 或系统任务。 |
| `created_at` | 是 | change 创建时间。 |

推荐 `source_type`：

- `manual`
- `bad_case_fix`
- `eval_regression_repair`
- `context_adaptation`
- `generated_upgrade`
- `imported`

规则：

- `Change` 在 MVP 中可以轻量存在，但对 lineage 很有价值。
- variant 可以指向产生它的 change。

### Artifact

`Artifact` 保存大内容或非结构化内容。

```text
Artifact(
  id,
  kind,
  storage_uri,
  content_hash,
  media_type,
  created_at
)
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 平台内部主键。 |
| `kind` | 是 | artifact 类型，例如 `eval_input`、`expectation`、`rubric_config`、`run_log`、`raw_output`。 |
| `storage_uri` | 是 | 实际存储位置，可以是对象存储 key、本地路径或外部报告 URL。 |
| `content_hash` | 是 | 内容 hash，用于去重、完整性校验和复现。 |
| `media_type` | 是 | MIME 类型或平台内部类型，例如 `application/json`、`text/markdown`。 |
| `created_at` | 是 | artifact 创建时间。 |

示例：

- skill manifest 快照
- 原始用户 prompt
- 原始 agent 输出
- eval 输入
- 期望行为
- rubric 配置
- 脚本文件
- run 日志
- 生成报告
- 判分证据

规则：

- 主对象只保存 artifact ref，不保存大 blob。
- artifacts 应按内容 hash，便于复现和去重。

## 5. 派生视图

下面这些不要作为主模型字段：

- verified status
- aggregate score
- repaired bad case count
- regression delta
- compatibility summary
- recommended variant
- ordering view

它们应由以下事实计算得出：

```text
Variant + VariantVersion + TagSet + EvalSetVersion + EvalRun + CaseResult
```

MVP 不需要推荐系统。首页显示默认 variant；详情页展示所有可见 variants、版本历史和测评证据。

## 6. 策略接口

策略是稳定模型背后的可替换插件。

### EvalStrategy

用途：让某个 variant 在某个 eval set version 上运行测评。

输入：

```text
variant_version_ref
eval_set_version_ref
strategy_config
runtime_config
```

输出：

```text
EvalRun
CaseResult[]
Artifact[]
```

MVP 实现：

- `manual-eval`：用户手动输入 pass/fail/score。
- `script-eval`：运行本地脚本，并把输出映射成 case results。
- `llm-rubric-eval`：用 judge model 根据 rubric 判分。

未来适配器：

- SkillGrade
- Skill Bench
- skills-check
- custom CI runner
- benchmark imports

### SelectionStrategy

用途：后续如果需要自动选择默认变体、推荐变体或按请求约束排序，可以作为策略层加入。MVP 不实现，避免把平台做成推荐系统。

输入：

```text
skill_ref
requested_tags
eval_set_version_ref
candidate_variant_refs
selection_config
```

输出：

```text
selected_variant_ref?
ordered_variant_refs?
reason_artifact_ref?
```

规则：

- tag 匹配策略在这里。
- score 权重策略在这里。
- 高严重安全失败等硬门禁可以在这里调用，也可以委托给 `GateStrategy`。

### UpgradeStrategy

用途：基于证据创建新的内容快照，并发布到某个 variant。

输入：

```text
variant_ref
bad_case_refs?
eval_case_version_refs?
eval_run_refs?
upgrade_config
```

输出：

```text
content_ref
change_ref
variant_version_ref
```

MVP 实现：

- `manual-upgrade`：作者修改内容并生成新的 `content_ref`，然后发布新的 `VariantVersion`。内容可以来自前端模拟 bundle、对象存储或 Git commit。

未来实现：

- prompt mutation
- trace-driven synthesis
- Hermes-style self-evolution
- EvoSkill-style candidate search

### GateStrategy

用途：判断某个 run 或候选排名是否存在硬性阻断风险。

输入：

```text
eval_run_ref
gate_config
```

输出：

```text
pass/fail
blockers[]
```

示例：

- 任意高严重安全 case 失败。
- 回归通过率低于阈值。
- 必要静态检查失败。
- run artifact 显示超时或工具错误。

## 7. MVP 工作流

### 工作流 A：创建 Skill 和首个 Variant

1. 用户创建 `Skill`。
2. 用户上传或导入 skill 内容，平台生成 `content_ref`。纯前端原型可直接用模拟 bundle。
3. 平台记录 `Variant`，绑定 `content_ref` 和 `tag_set_ref`。
4. 平台创建 `EvalCorpus`。
5. 用户添加初始 eval cases。
6. 平台创建 `EvalSetVersion v1`。
7. 用户对 variant 运行 eval。
8. Skill 页面展示 variant 和测评证据。

验收：

- 用户可以安装或获取已注册 variant。
- variant 能追踪到精确不可变内容。
- variant 至少有一次绑定不可变 eval set version 的 eval run。

### 工作流 B：查看变体测评矩阵

1. 用户注册 Variant A，tags 为 `[codex]`。
2. 用户注册 Variant B，tags 为 `[codex, gpt5.4]`。
3. 两个 variants 都在同一个 eval set version 上运行。
4. 平台展示每个 case 对每个 variant current version 的 pass/fail。
5. 用户点进某个 variant 查看版本历史和该版本的 case-level 结果。

验收：

- UI 能展示每条 case 在各 variant 上是否通过。
- 矩阵必须明确使用的 eval set version。
- 结果必须能从已保存 run 中重新计算。

### 工作流 C：Bad Case 转 Eval Case

1. 用户为某个 skill 或 variant 提交 bad case。
2. 平台把原始输入、输出、说明保存为 artifacts。
3. curator 或作者把 bad case 转成 eval case。
4. 平台创建新的 eval set version。
5. 相关 variants 重新运行测评。
6. 对比页展示该 bad case 是否已被修复，或是否仍然失败。

验收：

- bad case 不直接改变排名。
- 新 eval set version 引用了新增 eval case。
- 旧 eval set versions 仍然存在，能解释历史排名。

### 工作流 D：Variant 版本升级

1. 某个 variant 在 case 上失败。
2. 作者或升级策略创建新的内容快照，并生成新的 `content_ref`。
3. 平台创建新的 `VariantVersion`，并把 `Variant.current_version_ref` 指向它。
4. 新 version 在当前 eval set version 上运行。
5. 页面展示新旧 version 的测评结果和 case-level 变化。

验收：

- 旧 version 仍然可见，旧 eval run 仍然指向旧 version。
- 新 version 能与旧 version 做 diff。若底层是 Git，则使用 Git diff；若是模拟 bundle，则使用内容 diff。
- 新 version 的变更说明可以指向来源反馈、eval case 或 change。

## 8. API 草案

这些是产品级 API，不是最终实现细节。

```text
POST /skills
GET  /skills/:skill_id

POST /skills/:skill_id/variants
GET  /skills/:skill_id/variants
GET  /variants/:variant_id
POST /variants/:variant_id/versions
GET  /variants/:variant_id/versions

POST /skills/:skill_id/eval-cases
GET  /skills/:skill_id/eval-cases

POST /skills/:skill_id/eval-set-versions
GET  /eval-set-versions/:version_id

POST /eval-runs
GET  /eval-runs/:run_id
GET  /eval-runs/:run_id/case-results

POST /source-events
GET  /source-events/:source_event_id
```

重要规则：

- create endpoints 默认返回 refs，不默认展开整个对象图。
- 涉及真实 agent 或外部工具的 eval runs 应异步执行。

## 9. UI 页面

### Skill 页面

用途：浏览默认可安装 variant、其它约束变体和它们的证据。

必须展示：

- skill 名称
- 默认 variant
- 变体地图，按 tag set 展示
- 当前 eval set version
- 测评集摘要
- 当前测评结果摘要
- 历史版本入口
- eval corpus 摘要

### Variant 页面

用途：检查某个可安装 variant。

必须展示：

- tags
- 当前 version 和 content ref
- 历史 versions
- eval runs
- case-level results
- 与上一 version 的 diff 链接
- change note，如果存在

### Eval Corpus 页面

用途：管理平台最重要的测评资产。

必须展示：

- eval cases
- case 来源
- input / expected output
- eval set versions
- 每个 variant version 在当前 eval set version 上的 case-level 结果

### Eval Case 来源详情

用途：在 Eval Corpus 内查看某条 eval case 的来源。bad case 不作为独立主页面，而是作为 `EvalCase.source_type = bad_case` 和 `origin_ref` 展示。

必须展示：

- raw input/output
- reporter note
- related variant version
- 转化关系：尚未转化，或已关联 eval case

## 10. 存储架构

MVP 推荐：

- 关系型数据库保存 refs 和可查询 metadata。
- 对象存储或本地 artifact store 保存 artifacts。
- 内容存储保存 skill 内容。v1 纯前端原型可使用 mock content store；后续可接 Git repository 或对象存储。
- background job runner 执行 eval runs。

最佳实践：

- core rows 保持小。
- 大内容进入 artifacts。
- eval set versions 不可变。
- variant version 内容通过 `content_ref` 和 digest 引用，保持不可变。
- 记录 strategy config hash，便于复现。
- runs 和 results 尽量 append-only。

## 11. 安全与可靠性

最低要求：

- 脚本和 agent eval 必须在 sandbox 中运行。
- 所有 eval runs 必须有 timeout。
- 尽可能从 artifacts 中脱敏 secrets。
- 上传的 skill 内容和 eval scripts 都按不可信处理。
- 原始 bad cases 需要访问控制。
- 外部 adapter 输出必须规范化后才能进入 evidence model。
- 外部工具失败不能破坏核心 metadata。

## 12. MVP 验收标准

MVP 完成的标准是下面这个场景能端到端跑通：

1. 创建 `code-reviewer`。
2. 注册 Variant A，tags 为 `[codex]`。
3. 注册 Variant B，tags 为 `[codex, gpt5.4]`。
4. 添加至少 5 个 eval cases。
5. 创建 `EvalSetVersion v1`。
6. A v1 和 B v1 都在 `EvalSetVersion v1` 上运行。
7. 按 case 对比 A 和 B 的结果。
8. 添加一个新的 eval case，并创建 `EvalSetVersion v2`。
9. A 当前 version 和 B 当前 version 在 `v2` 上重新运行。
10. 针对 A 发布 `VariantVersion v2`。
11. A v2 在 `EvalSetVersion v2` 上运行。
12. Variant 页面能看到 A v1 / A v2 的历史，以及每条 case 的通过情况。

这证明核心闭环成立：

```text
分发 -> 测评 -> 测评集增长 -> 重新测评 -> 版本改进
```

## 13. 推荐实现顺序

阶段 0：纯前端原型

1. 定义 TypeScript 数据类型和 mock fixtures。
2. 实现 Hub 首页、Skill Detail 页面和 Eval Corpus 页面。
3. 实现 variant map、variant version history 和 eval result detail。
4. 实现手工添加 eval case、手工 pass/fail 记录和发布新 version。
5. 保留策略接口位置，但不把推荐和比较做成主流程。
6. 用 `code-reviewer` seed data 跑通完整体验。

阶段 1：真实核心后端

1. 定义 schema 和 artifact store。
2. 实现 skill 和 variant 注册。
3. 实现 eval case 创建。
4. 实现 eval set version 快照。
5. 实现 manual eval strategy。
6. 实现 eval run 和 case results。
7. 实现 variant version 发布。
8. 实现 version history 和内容 diff 链接；Git diff 是其中一种实现。
9. 实现 source event 到 eval case 的转化。
10. 实现 script eval strategy。
11. 增加外部 adapter 边界。

不要从自动升级开始。第一个里程碑应该证明：测评证据能支撑 variant/version 的可靠迭代，并且 eval corpus 能持续增厚。
