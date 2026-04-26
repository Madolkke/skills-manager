# SkillHub React Demo

运行：

```bash
npm install
npm run dev
```

建议验证路径：

1. 在 Hub 页点击 `code-reviewer`。
2. 在 Skill Detail 页查看默认 skill 介绍、默认变体和以 tag set 为入口的 Variant Map。
3. 进入 Workbench，修改 skill 简介、添加一个 input/output 测评用例。
4. 在 Workbench 里选择一个变体，手工勾选每条用例是否通过并保存 EvalRun。
5. 在 Workbench 里创建一个升级变体。
6. 回到 Skill Detail 或 Eval Corpus，查看变体地图和测评矩阵如何变化。

这个 demo 只验证产品闭环和信息架构。`ContentRef` 使用本地 mock，`EvalRun` 和 `CaseResult` 可以通过 Workbench 写入 localStorage。
