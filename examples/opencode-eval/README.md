# Opencode Eval 手动测试素材

这个目录提供一套可直接用于手动测试 Opencode Runner 的素材。

## 1. 导入测试 Skill

在页面点击“新建 Skill”，选择上传文件夹：

```text
examples/opencode-eval/skill-bundle
```

这个文件夹根目录包含 `SKILL.md`，可被系统作为标准 Skill bundle 导入。

## 2. 创建 Eval case

建议创建一个 case：

- 标题：`发现缺少 ownerId 过滤`
- Prompt 模板：`工作目录文件任务`
- Provider：`DeepSeek`
- Model：`deepseek-v4-flash`
- Input：

```text
请审查工作目录中的代码，找出最关键的数据隔离问题。
输出必须包含：
1. 风险等级
2. 具体文件和函数
3. 为什么会泄露跨租户数据
4. 建议修复方式
```

- Expected output：

```text
应指出 src/repositories/orders.ts 的 listOrders 函数只按 status 查询订单，缺少 ownerId 或 tenant/user 维度过滤，可能返回其他用户的订单。建议把 ownerId 作为必填参数并加入 where 条件，同时补充回归测试。
```

## 3. 准备附件 zip

把下面这个目录压缩为 zip 后上传到 case 附件：

```text
examples/opencode-eval/case-attachment
```

PowerShell 示例：

```powershell
Compress-Archive -Path examples/opencode-eval/case-attachment/* -DestinationPath examples/opencode-eval/case-attachment.zip -Force
```

运行 Opencode Runner 时，zip 内文件会被解压复制到工作目录，测试 Skill 应该读取这些文件后给出审查结果。

