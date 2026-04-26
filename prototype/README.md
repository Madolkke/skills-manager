# SkillHub 纯前端原型

打开 `index.html` 即可运行，不需要后端或依赖安装。

建议验证路径：

1. 在 Hub 页点击 `code-reviewer`。
2. 在 Skill Detail 页查看以 tag set 为入口的 Variant Map。
3. 切换请求 tags 和测评集版本，观察 ranking 是否符合直觉。
4. 进入 Eval Corpus 页，点击“将来源转为 EvalCase”。
5. 点击“注册 Variant C”，再点击“运行 C on v2”。
6. 回到 Skill Detail 页查看 Variant C 的排名、历史和 case-level 对比。

这个原型只验证产品闭环和信息架构。`ContentRef`、`EvalRun`、`CaseResult` 和 `RankingStrategy` 都使用本地 mock 数据。
