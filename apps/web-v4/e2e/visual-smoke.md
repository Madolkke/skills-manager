# Web V4 视觉 Smoke

这组 Playwright 截图基线覆盖 `docs/product-ui-reference/` 对应的 5 个正式版页面：

1. Hub 首页
2. Skill 概览
3. 测评集管理
4. 手动测评
5. 版本管理（打开页面内上传面板）

## 运行方式

```bash
cd apps/web-v4
npm run e2e:visual
```

测试会启动独立的临时 SQLite 数据库，用固定 seed 创建 Skill、多个 `SkillVersion`、case、EvalRun，并用 `1586x992` viewport 截图。该尺寸与参考图尺寸一致或接近。Hub 首页会断言最近测评默认显示 6 条，并且 `查看全部` / `收起` 能在同一真实列表内切换 6/7 条记录；Skill 概览页会断言 summary 身份卡显示真实根目录和维护者，也会断言 bundle 文件树存在根目录、子目录和叶子文件节点，避免退回轻量标题区或平铺分组列表；测评集页会断言 case 行包含序号、case version、当前状态和生命周期状态；手动测评页会断言进度区包含聚合摘要、总 case 数、结果分布条、actual output 输入区和 actual vs expected 对照；版本页会断言 inspector 使用水平版本线、当前版本摘要、`Bundle diff` 和 `查看该版本详情`，并等待后端 `/api/artifacts/diff` 返回真实 diff，避免退回纵向版本卡片或无真实行为的底部按钮。

如果需要接受新的视觉基线：

```bash
cd apps/web-v4
npm run e2e:visual -- --update-snapshots
```

在受限 Codex 沙箱里，如果新的 npm script 前缀没有网络绑定权限，可以使用已授权的等价形式：

```bash
cd apps/web-v4
npm run e2e -- --config playwright.visual.config.ts
```

## 边界

这些截图是当前 Web V4 的回归基线，用来防止布局、层级、主要控件和页面密度意外倒退。它们不是“逐像素复刻参考图”的证明；正式验收口径见 [Web V4 视觉参考验收记录](../../../docs/formal-web-v4-visual-reference-acceptance-2026-05-22.md)。
