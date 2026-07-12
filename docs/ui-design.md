# SkillHub 正式版 UI 设计规格

本文档定义当前 Web 的页面契约。UI 围绕 `SkillVersion + EvalSetVersion + run_context` 证据链组织，不再使用 Variant、promotion 或 tags-as-version 的概念。

## 信息架构

```text
/skills
  Hub 首页：搜索、筛选、最近测评、当前验证状态。

/skills/:skillId
  Skill 工作台：概览、版本、测评集、测评、历史。
```

页面内 tab 是正式产品结构：

| Tab | 目标 | 必须展示的证据 |
| --- | --- | --- |
| 概览 | 解释 Skill 身份和当前状态 | owner、当前版本、主测评集、最近 run、bundle 文件树。 |
| 版本 | 管理不可变 SkillVersion | 版本号、digest、bundle 文件、真实 diff、当前版本指针。 |
| 测评集 | 管理 case 和 EvalSetVersion | case version、expected output、当前测评集工作版和已运行快照。 |
| 测评 | 记录一次 exact run | SkillVersion、EvalSetVersion、环境标签、actual output、actual vs expected。 |
| 历史 | 查看证据链 | EvalRun、case result、run context、artifact digest、actual output。 |

## 布局原则

- 页面首屏展示可操作产品，不做营销式落地页。
- 表格和列表用于可比较信息，单个对象摘要才使用 card。
- 不做卡片套卡片；页面 section 保持全宽布局。
- 小窗口从 `320px` 开始不能出现关键内容穿出、遮挡或不可操作。
- 长文本默认换行或在容器内滚动，按钮和 tab 不允许因文本撑破布局。
- 版本、case、run 这类固定格式对象要有稳定尺寸，避免 hover、loading 或动态标签造成布局跳动。

## 按钮与动效

Workflow 编辑器先行采用共享 `UiButton`、`UiIconButton` 和 `UiTooltip` 原语，其他页面继续使用现有按钮样式，后续按功能域迁移。

- 按钮层级使用 `primary / secondary / ghost / danger / text`；一个操作区只保留一个主按钮。
- 尺寸使用 `sm 30px / md 36px / lg 40px`。纯图标按钮保持正方形，并必须提供可读的 `aria-label`。
- 异步按钮使用受控的 `idle / loading / success` 状态。正常、处理中和成功内容在同一网格轨道内叠放，切换状态不得改变按钮宽度。
- 保存操作可在服务端确认后短暂展示成功态；会关闭弹窗、导航或改变上下文的操作继续使用 Toast 或页面结果确认。
- 不熟悉的图标按钮在 hover 或键盘 focus 后展示 Tooltip；禁用状态仍需能够通过 Tooltip 解释原因。

动效时长统一为：

| 级别 | 时长 | 用途 |
| --- | --- | --- |
| fast | `120ms` | hover、active、图标和徽标反馈。 |
| base | `180ms` | Popover、内容切换、展开收起。 |
| emphasis | `260ms` | 面板折叠、Modal、流程图重排。 |

- 动效只用于解释状态和空间关系，不响应普通文本输入，不添加 Ripple 或装饰性循环动画。
- 优先动画化 `transform` 和 `opacity`；拖动调宽时必须关闭过渡，保证指针与面板同步。
- Workflow 图谱重排时节点坐标和连线必须同帧更新，不能只对节点 DOM 添加 CSS 位移。
- `prefers-reduced-motion: reduce` 下取消位移、缩放、图谱插值和循环边动画，状态颜色和文字仍需即时更新。

## 页面契约

### Hub

Hub 必须能让用户快速找到 Skill，并看到是否已有可信验证：

- 搜索和 owner/status 筛选。
- 每个 Skill 展示 slug、description、owner、current version、primary eval set、latest accepted run。
- 最近测评默认显示有限条数，并可展开查看全部。
- 空状态优先提供 `新建 Skill`，不显示无用说明。

### 概览

概览负责回答“这个 Skill 是什么，当前可用证据是什么”：

- 身份卡：slug、owner、lifecycle、root path。
- 当前版本卡：SemVer version、digest、created_by、change summary。
- Bundle browser：目录树、文件内容、digest。
- 最近测评：run context、pass/fail、actual output 摘要。

### 版本

版本页负责不可变内容线：

- 版本线必须清楚标出 current version。
- 新建 Skill 可填写初始 SemVer，默认 `0.0.1`。
- 上传和编辑新版本时提供重大、功能、修订三类更新选择，并自动填入对应 SemVer；用户仍可手动微调版本号。
- `Bundle diff` 使用后端 `GET /api/artifacts/diff` 的真实数据。
- 上传版本只创建新的 `SkillVersion`，是否设为 current 由显式选项控制。
- 不展示 Variant、promotion 或默认 Variant。

### 测评集

测评集页负责测试数据版本：

- case 列表显示 position、title、case version、状态。
- 新增、编辑、恢复和归档 case 都必须保留 case version；当前 EvalSetVersion 没有运行记录时作为工作版更新，已有运行记录时创建新快照。
- expected output 是一等字段，不能藏在备注里。

### 测评

测评页负责记录当前运行结果：

- 用户必须选择 exact `SkillVersion + EvalSetVersion`。
- 运行环境标签记录到本次 `EvalRun`。
- 每个 case 都可以输入 actual output，并在界面中对比 expected output。
- 未完成所有 case 的 pass/fail 标记前不能提交 run。

### 历史

历史页负责事后审计：

- run 列表可按 SkillVersion、EvalSetVersion、strategy、status 过滤。
- run 详情展示 run context、summary、case result 和 artifact digest。
- actual output 与 expected output 必须同屏可比。
- 刷新或重启后同一历史数据仍可见。

## 组件边界

| 组件 | 责任 |
| --- | --- |
| `BrandRail` / `TopBar` | 全局导航、搜索和主动作入口。 |
| `BundleBrowser` | bundle 文件树和文件预览。 |
| `BundleDiffPanel` | 版本间真实 diff。 |
| `EvalSetVersionNameEditor` | 测评集版本命名。 |
| `CaseVersionRoadmap` | case version 可追溯视图。 |
| `EvaluationContextCard` | 本次 run 的环境和绑定信息。 |
| `ManualEvaluationPanels` | actual output、pass/fail 和对比状态。 |

## 验收口径

- README 的核心验收清单全部可手工复现。
- `npm run test`、`npm run lint` 和 `npm run build` 通过。
