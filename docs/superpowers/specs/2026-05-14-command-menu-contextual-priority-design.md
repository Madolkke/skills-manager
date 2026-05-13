# Command menu 上下文化排序设计

## 背景

当前 `Cmd/Ctrl+K` 命令菜单已经可以搜索、方向键选择、执行导入、创建、测评、历史和差异等动作，但默认列表仍是静态顺序：先导航，再创建，再测评。这样在用户已经进入 `测评` 页时，第一屏仍然先看到“打开概览/打开变体”；在 `变体` 页时，追加版本和新建 variant 也不够靠前。

本轮只做排序策略，不改命令菜单弹层结构、搜索算法、快捷键系统或视觉风格。

## 外部实践

- [Linear concepts](https://linear.app/docs/conceptual-model) 强调同一动作可以通过按钮、快捷键、上下文菜单或 command menu 触发，并且 command menu 会优先显示和当前 view/selection 相关的命令。
- [GitHub Command Palette](https://docs.github.com/en/get-started/accessibility/github-command-palette) 会根据当前 UI 位置确定 scope，并在 repository、organization、file、issue、pull request 等不同上下文里提供不同建议。
- [GitKraken Command Palette](https://help.gitkraken.com/gitkraken-desktop/command-palette/) 把 command palette 定义为键盘优先的工作流入口，并明确 command availability 会依赖当前 repository state、open repo context 和 configured integrations。

对 SkillHub 的适配结论：命令菜单不应该只是一张全局命令清单，而应该是“当前工作台 mode 的动作加速器”。禁用命令仍保留，让用户知道能力存在；但可用且与当前 mode 最相关的命令应该进入第一屏。

## 产品设计

新增 `currentMode` 输入给 `useWorkbenchCommands` / `buildWorkbenchCommands`。

排序策略：

- 空 skill 状态：优先 `导入标准 Skill bundle`、`新建 skill`，避免用户打开菜单后第一项是无意义的“打开概览”。
- `overview`：优先 skill 身份设置、导入/新建和常用导航，保持 overview 作为起点。
- `variants`：优先 `新建 variant`、`追加版本`、`比较版本`，因为用户此时最可能在维护约束组合和版本。
- `evals`：优先 `记录本次测评`、`添加 case`、`批量添加 case`，然后是历史证据。
- `history`：优先历史相关导航、run comparison/accepted verification 的证据入口和重新测评。
- `diff` / `promotion`：优先版本比较、追加版本、打开变体和打开测评。
- `audit`：优先审计视图，其次是 skill 设置和历史。

实现上不新增复杂 scoring 系统，只维护一个 mode -> command id priority list。基础命令数组仍保留原定义顺序；排序函数先按 priority list 提前相关命令，再稳定保留其他命令顺序。`CommandMenu` 里已有 disabled 命令下沉逻辑，本轮不重复处理。

## 范围

本轮修改：

- `apps/web/components/command-menu/workbench-command-config.ts`
- `apps/web/components/command-menu/use-workbench-commands.ts`
- `apps/web/components/decision-workbench.tsx`
- `apps/web/components/command-menu/workbench-command-config.test.ts`
- `apps/web/e2e/skills-workbench.spec.ts`

本轮不做：

- 最近使用命令、个性化学习排序。
- 分组视觉重排、命令 preview、右侧详情面板。
- 命令模式前缀，例如 GitHub 的 `>` / `#` / `/`。

## 验收标准

- Vitest 红绿覆盖：`evals` mode 首屏优先测评命令；`variants` mode 首屏优先 variant/version 命令；空 skill 状态优先导入/新建。
- E2E 覆盖：用户在 `测评` 页打开 command menu 时，不输入搜索也能看到 `记录本次测评` 作为第一条可执行命令。
- 现有 command menu ARIA、Tab trap、搜索执行和完整 SkillHub E2E 不回归。
- README、产品体验评审、摩擦审计、完成度审计和任务日志同步更新。
