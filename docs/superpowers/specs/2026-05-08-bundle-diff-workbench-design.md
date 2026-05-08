# SkillHub Bundle Diff Workbench 设计规格

日期：2026-05-08

状态：待用户确认后进入实现计划

## 1. 背景

当前正式版已经跑通这些闭环：

- 标准 skill folder / zip 导入。
- skill、variant、variant version、eval case、eval run 的基础 CRUD 和手工 pass/fail。
- `/skills` 三栏工作台和视觉回归。
- `skill_bundle` 文件树和 `SKILL.md` 内容预览。

但产品文档已经明确要求：`skill_bundle` 版本需要支持任意两个历史版本的文件 diff。现在 README 也写了“viewed or diffed by version”，实际 UI 还没有一等 diff 工作流，这是产品承诺和实现之间的缺口。

## 2. 外部实践调研

### GitHub Pull Request Files changed

GitHub 的 PR diff 不是把 commit 自身当主角，而是把“合并后文件会怎么变”作为 review 对象。官方文档强调 Files changed 展示 proposed changes，并提供 unified、split、rich/source diff、忽略空白和按文件过滤等能力。

适配 SkillHub：

- 版本 diff 应该围绕 `left VariantVersion` 和 `right VariantVersion` 的 bundle 文件树，而不是围绕数据库字段。
- 默认先做 split/unified 中的一种即可，但必须保留后续切换空间。
- 文件过滤和 changed/added/removed 分组要比“展示所有文件”更重要。
- 对 skill 来说，默认比较 current version 和上一版；用户后续可切换任意两个版本。

参考：https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-comparing-branches-in-pull-requests

### VS Code Source Control Diff Editor

VS Code 把 Source Control view 作为变化文件入口，点击文件后打开 side-by-side diff editor。它的优势是“文件列表”和“差异内容”保持在同一工作流里，不需要用户跳转到另一套页面模型。

适配 SkillHub：

- VariantVersion 页面和 `/skills` 工作台都可以有 diff 入口，但主 diff 体验应该是：左侧 changed files，右侧 selected file diff。
- 文件级 diff 是第一版重点；目录级统计只作为摘要。
- 对二进制/大文件，显示 added/removed/changed 和 hash，不强行展示内容 diff。

参考：https://code.visualstudio.com/docs/sourcecontrol/overview

### Linear Filters / Views

Linear 的过滤系统强调几乎所有 view 都能按属性过滤，并能把过滤后的视图保存成 custom view。SkillHub 后续的 run history / eval matrix 也需要这个方向，但 diff 的第一步不应过早做完整 query builder。

适配 SkillHub：

- Diff 工作台第一版只提供轻量过滤：all / changed / added / removed / deleted / text / binary。
- 多维表格和自定义 view 放到 run history / matrix 阶段，不塞进 diff 第一版。

参考：https://linear.app/docs/filters

## 3. 目标

Bundle Diff Workbench 要让维护者回答三个问题：

1. 这个 variant 的新版本相对上一版改了什么？
2. 改动是否集中在 `SKILL.md`、references、scripts、assets 等关键文件？
3. 这次改动对应的 eval 结果是否值得把新版本设为 current / 继续保留？

第一版不做 PR 评论、权限、merge、三方 Git adapter，也不做语义级 prompt diff。它只做稳定、可验证、可扩展的文件树 diff。

## 4. 推荐方案

### 方案 A：前端从两个 bundle snapshot 直接计算 diff

做法：

- API 继续返回 variant versions 的 `bundle_files`。
- 前端比较两个 `bundle_files`，生成 file-level diff summary。
- 文本文件用前端 LCS 或简单 line diff 渲染。

优点：

- 最快，不需要新增后端 endpoint。
- demo 立刻可用。

缺点：

- diff 逻辑会落在浏览器，后续 Git/Object Store adapter 接入时要搬迁。
- 大文件或大量文件时性能和传输都不理想。
- API 契约不够正式，难以给外部集成复用。

### 方案 B：后端新增 artifact diff read model，前端只渲染

做法：

- 新增 `GET /api/artifacts/diff?left_variant_version_id=&right_variant_version_id=`。
- 后端从两个不可变 bundle artifact 读取规范化 file tree。
- 返回 file summary、selected text diff、binary marker、left/right digest。
- 前端负责展示和筛选，不负责事实计算。

优点：

- 符合“平台保存事实引用，内容层负责文件树/diff”的架构。
- 后续可以无缝替换成本地 artifact、Git adapter、对象存储 adapter。
- Diff 结果可以被 API、测试、未来 PR/review 页面复用。

缺点：

- 需要新增后端 read model、测试和前端 API 类型。

### 方案 C：直接引入 Git adapter，并用 Git diff 作为唯一实现

做法：

- 每个 bundle 导入都写入 Git repository。
- VariantVersion 指向 commit/tree。
- Diff 全部走 Git。

优点：

- 长远协作能力最强。
- 天然获得成熟 diff、历史、commit、branch 基础。

缺点：

- 现在过早。当前正式版还在单用户和本地 SQLite 阶段，直接接 Git 会把存储选型复杂度引进主线。
- 用户真正要验证的是 skill 管理和 eval 闭环，不是 Git 托管平台。

### 推荐

采用方案 B。

第一版实现“后端 artifact diff read model + 前端 diff workbench”。Git 仍然作为后续 adapter，不进入主业务模型。这样既能兑现产品承诺，也不会把正式版绑死在 Git 实现上。

## 5. 数据契约

新增 endpoint：

```text
GET /api/artifacts/diff?left_variant_version_id={id}&right_variant_version_id={id}
```

约束：

- left/right 必须属于同一个 skill。
- left/right 必须是 `skill_bundle` 或可解析为 bundle manifest 的 artifact。
- 如果 version 没有 bundle artifact，返回 422，说明该版本没有可 diff 的文件树。
- 不比较可变状态，只比较两个 immutable bundle snapshots。

返回结构：

```json
{
  "left": {
    "variant_version_id": "varver_a_v1",
    "version_number": 1,
    "content_digest": "sha256:..."
  },
  "right": {
    "variant_version_id": "varver_a_v2",
    "version_number": 2,
    "content_digest": "sha256:..."
  },
  "summary": {
    "added": 1,
    "removed": 0,
    "changed": 2,
    "unchanged": 5,
    "binary": 1
  },
  "files": [
    {
      "path": "SKILL.md",
      "status": "changed",
      "binary": false,
      "left_digest": "sha256:...",
      "right_digest": "sha256:...",
      "left_size_bytes": 812,
      "right_size_bytes": 926,
      "hunks": [
        {
          "old_start": 4,
          "old_lines": 3,
          "new_start": 4,
          "new_lines": 5,
          "lines": [
            { "kind": "context", "old_line": 4, "new_line": 4, "text": "# Code Reviewer" },
            { "kind": "removed", "old_line": 5, "new_line": null, "text": "Flag null checks." },
            { "kind": "added", "old_line": null, "new_line": 5, "text": "Prioritize auth regressions." }
          ]
        }
      ]
    }
  ]
}
```

字段说明：

- `status`: `added | removed | changed | unchanged`。
- `binary`: true 时不返回 `hunks`。
- `hunks`: 第一版可以用 Python 标准库 `difflib.unified_diff` 或 `SequenceMatcher` 生成，后续 adapter 可替换。
- `files` 默认包含 changed/added/removed；是否包含 unchanged 由后续 query 参数控制。第一版可以返回 unchanged summary，但不返回 unchanged 文件详情。

## 6. UI 设计

### 入口

在两个位置放入口：

- `/skills` 工作台的 Skill bundle 区域：当当前 variant 有至少两个版本时，显示 `比较版本`。
- Variant detail / version page：History timeline 每条历史版本旁边显示 `Compare to previous`。

第一版可以优先实现 `/skills` 工作台入口，详情页入口只保留链接或按钮。

### Diff Workbench 布局

桌面：

```text
Header
  v1 -> v2
  change summary
  eval summary if available

Toolbar
  left version select
  right version select
  file status filters

Main
  Left rail: changed file list
    SKILL.md changed
    references/checklist.md added
    assets/logo.png binary changed

  Right panel: selected file diff
    metadata row: status, size, digest
    diff hunks
```

移动端：

```text
Version selector
Status segmented control
Changed file list
Selected file diff below list
```

视觉要求：

- 不使用卡片套卡片。
- 文件列表和 diff 内容是一个工具，不是多个孤立模块。
- Added 用绿色、removed 用红色、changed 用蓝/灰，保持低饱和。
- Digest 和 version id 默认短码，hover/title 或复制按钮再看全量。
- 对文本 diff 使用 monospace；外层仍保持当前工作台字体。

## 7. 交互规则

- 默认比较当前 variant 的上一版本和 current version。
- 如果只有一个版本，显示空状态：`还没有可比较的历史版本`，并提供 `追加版本` 入口。
- 点击文件列表项切换右侧 diff。
- 状态过滤不能改变 selected version，只过滤文件列表。
- 版本选择变化后重新请求 diff read model。
- 若 diff 请求失败，保留当前页面并在 diff 区域显示错误，不影响 skill 工作台其它操作。

## 8. 测试策略

后端：

- 两个 bundle 版本中同一文本文件变化，返回 `changed` 和 hunk。
- 新增文件返回 `added`。
- 删除文件返回 `removed`。
- 二进制文件只返回 binary marker 和 digest，不返回 hunks。
- left/right 不同 skill 返回 400/422。
- 没有 bundle artifact 的 version 返回 422。

前端：

- E2E 创建或导入 skill 后追加版本，再打开 diff。
- 能看到 changed file list。
- 能切换文件并看到对应 diff。
- 只有一个版本时显示明确空状态。
- 视觉回归增加 imported skill diff workbench 状态。

## 9. 不做什么

- 不做 PR review comments。
- 不做 branch/fork。
- 不做 semantic prompt diff。
- 不做 merge conflict 或三路 diff。
- 不做完整 Git adapter。
- 不做 run history / matrix query builder。

这些都重要，但不是第一版 diff 的核心。

## 10. 验收标准

实现完成后必须满足：

1. 用户能在 `/skills` 工作台从当前 skill 打开版本 diff。
2. 用户能比较同一 variant 的两个历史版本。
3. 用户能看到文件级 added/removed/changed summary。
4. 用户能选择某个文本文件并看到 line-level diff。
5. 二进制或不可展示文件不会破坏页面。
6. diff 绑定 exact `VariantVersion`，不会按当前指针推断历史。
7. API 和 UI 都有回归测试。
8. `uv run pytest`、`npm run typecheck`、`npm run build`、`npm run e2e` 通过。

## 11. Spec 自审

占位符检查：

- 没有 TBD/TODO。

一致性检查：

- 方案 B 与现有 `ArtifactStore` 和 `VariantVersion.content_ref` 模型一致。
- Git 仍是 adapter 选项，不进入主模型。

范围检查：

- 该 spec 只覆盖 bundle diff，不包含 run history、matrix query、PR 协作。

歧义检查：

- 第一版 diff 明确为 immutable bundle snapshot diff，不是 current variant 状态 diff。
