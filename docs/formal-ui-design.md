# SkillHub 正式版 UI 设计规格

本文档定义当前 Web V4 的页面契约。UI 围绕 `SkillVersion + EvalSetVersion + run_context` 证据链组织，不再使用 Variant、promotion 或 tags-as-version 的概念。

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
| 测评集 | 管理 case 和 EvalSetVersion | case version、expected output、当前测评集快照。 |
| 测评 | 记录一次 exact run | SkillVersion、EvalSetVersion、环境标签、actual output、actual vs expected。 |
| 历史 | 查看证据链 | EvalRun、case result、run context、artifact digest、actual output。 |

## 布局原则

- 页面首屏展示可操作产品，不做营销式落地页。
- 表格和列表用于可比较信息，单个对象摘要才使用 card。
- 不做卡片套卡片；页面 section 保持全宽布局。
- 小窗口从 `320px` 开始不能出现关键内容穿出、遮挡或不可操作。
- 长文本默认换行或在容器内滚动，按钮和 tab 不允许因文本撑破布局。
- 版本、case、run 这类固定格式对象要有稳定尺寸，避免 hover、loading 或动态标签造成布局跳动。

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
- 当前版本卡：version number、digest、created_by、change summary。
- Bundle browser：目录树、文件内容、digest。
- 最近测评：run context、pass/fail、actual output 摘要。

### 版本

版本页负责不可变内容线：

- 版本线必须清楚标出 current version。
- `Bundle diff` 使用后端 `GET /api/artifacts/diff` 的真实数据。
- 上传版本只创建新的 `SkillVersion`，是否设为 current 由显式选项控制。
- 不展示 Variant、promotion 或默认 Variant。

### 测评集

测评集页负责测试数据版本：

- case 列表显示 position、title、case version、状态。
- 新增、编辑、恢复和归档 case 都必须生成或保留可追溯版本。
- expected output 是一等字段，不能藏在备注里。

### 测评

测评页负责记录当前运行结果：

- 用户必须选择 exact `SkillVersion + EvalSetVersion`。
- 运行环境标签、OS、runner、model 记录到本次 `EvalRun`。
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
| `SkillVersionTrack` | 版本线和 current pointer。 |
| `VersionInspector` | 版本详情和真实 diff。 |
| `CaseVersionRoadmap` | case version 可追溯视图。 |
| `EvaluationContextCard` | 本次 run 的环境和绑定信息。 |
| `ManualEvaluationPanels` | actual output、pass/fail 和对比状态。 |

## 验收口径

- `npm run e2e` 通过正式流程冒烟。
- `npm run e2e:visual` 通过 5 个页面视觉基线。
- `responsive-smoke.spec.ts` 覆盖 `320px` 小窗口。
- README 的核心验收清单全部可手工复现。
