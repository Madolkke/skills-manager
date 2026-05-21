# Web V4 正式流程 E2E

这条 Playwright smoke 固化 SkillHub Web V4 的核心闭环，作为正式版每轮推送前的真实操作验证。

## 运行方式

```bash
cd apps/web-v4
npm run e2e
```

Playwright 会自动启动两个本地服务：

- API: `http://127.0.0.1:18110`
- Web V4: `http://127.0.0.1:13110/skills`

测试使用临时 SQLite 数据库，不写入 `.data/skillhub.sqlite3`。失败时 Playwright 会把 trace 和错误上下文写入 `apps/web-v4/test-results/`；该目录已加入 `.gitignore`，不应提交。

## 覆盖范围

1. 从 Hub 首页新建 Skill，并上传标准 Skill 文件夹。
2. 在 Skill 变体页打开页面内上传面板，用同一组 tags 上传新版 bundle，追加 `VariantVersion`。
3. 在测评集页新增 case，再编辑为新的 case version，并确认版本历史以连接式 roadmap 展示。
4. 在独立测评页选择 exact 版本组合，手动标记通过并记录结果。
5. 在历史页确认 `VariantVersion`、`EvalSetVersion`、case result 和 digest 证据链可见。

## 边界

它刻意只保留一条稳定 happy path，用来证明核心业务闭环可跑。更细的 helper 逻辑继续放在 Vitest；视觉布局回归由 [Web V4 视觉 Smoke](visual-smoke.md) 覆盖。
