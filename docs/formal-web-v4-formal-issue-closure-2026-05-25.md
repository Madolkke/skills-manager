# SkillHub 正式版问题收口审计

日期：2026-05-25

## 结论

本轮收口针对正式版验收前暴露的 4 类问题：Windows 默认启动误用内存库、历史记录和 Bundle diff 入口没有真实数据链路、手工 eval 缺少本次实际输出、小浏览器窗口布局溢出。修复后的目标状态是：默认启动即文件型 SQLite，刷新或重启后 Skill、变体、eval run、history 仍在；历史页能看到 actual output 与 expected output；变体页 Bundle diff 使用后端 API；320px 到桌面宽度不出现关键组件穿出或遮挡。

## 外部 UI 参考

本轮没有引入新的 UI 框架，而是把成熟项目的布局原则落回现有 Web V4 组件和 CSS：

- MDN CSS Grid `repeat(auto-fit, minmax(...))`：用于选择器、进度面板和对比面板的自动折列，避免固定列宽把内容推出视口。参考：<https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/repeat>
- Radix Dialog 可滚动 overlay 模式：表单和长内容应允许容器滚动，不应依赖固定视口高度。参考：<https://www.radix-ui.com/primitives/docs/components/dialog>
- shadcn/ui Data Table 指南：复杂数据视图应按本项目数据源定制列和密度，重复后再抽可复用组件，不直接套一个万能表格。参考：<https://ui.shadcn.com/docs/components/data-table>
- shadcn/ui Sidebar 指南：应用级导航和移动端 offcanvas 是布局 primitive，不应把窄屏内容塞进桌面宽度假设。参考：<https://ui.shadcn.com/docs/components/radix/sidebar>

## 修复项

### 1. Windows / 默认 SQLite 持久化

- `create_app()` 不再在缺少显式 `SKILLHUB_DATABASE_URL` 时回退到 `sqlite:///:memory:`。
- 新增默认数据库解析：优先 `SKILLHUB_DATABASE_URL`，其次 `SKILLHUB_DATA_DIR`，否则使用仓库 `.data/skillhub.sqlite3`。
- SQLite 文件型 URL 在 Python 侧生成，避免 Windows Git Bash 下 `$PWD` 拼成不兼容的 `sqlite:///C:/...` 变体。
- `scripts/dev-v4.sh` 默认传 `SKILLHUB_DATA_DIR`，Git Bash 有 `cygpath` 时转换为 Windows 路径；只有用户显式设置 `SKILLHUB_DATABASE_URL` 时才透传连接串。
- API 回归覆盖 `create_app()` 默认文件库创建，确保干净 clone 不需要预置 sqlite 文件。

### 2. History 和 Bundle diff 真实实现

- 历史页不再静默吞掉加载错误；失败会进入 toast。
- `record_eval_run` 写入 case result 时，把 actual output 存成 `kind=actual_output` 的 artifact，并把 id 挂到 `case_results.result_artifact_id`。
- `eval_run_detail` read model 返回 `result_artifact`，历史页按 case 展示 expected output 和 actual output。
- 变体 inspector 的 `Bundle diff` 入口改为请求 `GET /api/artifacts/diff?left_variant_version_id=&right_variant_version_id=`，展示后端返回的 summary、文件状态和 hunk 预览。
- E2E 在追加新版 bundle 后等待 `/api/artifacts/diff` 响应，防止 UI 只是本地假摘要。

### 3. Run eval actual output

- 手工测评 case 详情中新增“本次运行结果”输入区。
- 每条 case 同屏展示 expected output 和 actual output，用户判断后再标记通过或不通过。
- `POST /api/eval-runs` 兼容旧的布尔结果，也支持 `{ passed, actual_output }` 新结构。
- 记录成功后自动刷新并跳到历史页选中刚创建的 run，便于立刻核对证据链。

### 4. 小窗口响应式修复

- 全局输入、按钮、选择器和长文本统一加 `min-width: 0` / `max-width: 100%` / wrap 保护。
- 固定双列区域改为 `auto-fit` / `minmax(min(..., 100%), 1fr)` 或小屏单列。
- Hub hero、toolbar、variant toolbar、case row、diff row、actual/expected 对比和 history evidence 在 560px 以下改为纵向排列。
- 新增 `responsive-smoke.spec.ts`，用 `320x820` viewport 逐页检查 Hub、概览、测评集、测评、历史、变体没有横向溢出。

## 验收覆盖

- API：默认文件 SQLite、actual output artifact、eval run detail read model。
- Web unit：manual eval helper、diff helper、数据格式兼容。
- Playwright E2E：正式 happy path、后端 Bundle diff、actual output 记录和 history 证据链、320px 小窗口无关键横向溢出。
- Visual smoke：5 张正式页面基线更新，覆盖手工测评 actual output 对比和变体 diff 入口。
- 手工/agent-browser：启动真实 `scripts/dev.sh` 后在浏览器访问 Web V4，验证页面、响应式入口和数据链路可用。

## 剩余非本轮范围

- CI 必须以 GitHub main 分支结果为准；本地验证只能证明代码在本机环境通过。
- 复杂 run-to-run matrix、promotion review 和认证体系仍不属于 Web V4 主流程，本轮不重新开放旧工作台。
