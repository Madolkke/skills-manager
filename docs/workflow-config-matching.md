# Workflow 配置匹配 Collection

配置匹配 Collection 描述如何从执行器提供的完整设备配置文本中定位配置块。SkillHub 只保存语法、命令树和捕获字段 Schema，不读取设备文本，也不在本地执行匹配。

## 契约

```json
{
  "collectionType": "config",
  "config": {
    "commands": [
      {
        "name": "interface",
        "unique": false,
        "pattern": "interface <name>",
        "captures": {
          "name": { "type": "string", "title": "接口名称", "description": "" }
        },
        "children": [
          {
            "name": "ip_address",
            "unique": true,
            "pattern": "ip address <address:\\S+> <mask:\\S+>",
            "captures": {
              "address": { "type": "string", "title": "", "description": "" },
              "mask": { "type": "string", "title": "", "description": "" }
            },
            "children": []
          }
        ]
      }
    ]
  }
}
```

`name` 和捕获名必须是合法 Python 标识符，不能以 `_` 开头、不能是关键字或字典方法名。`unique` 默认是 `true`；设置为 `false` 后结果始终是数组。`captures` 必须与模式中的捕获名称完全一致，字段类型仅支持 `string`、`integer`、`number`、`boolean`。

## 模式语法

尖括号外是字面量，连续空白按一个空白区间匹配。`<name>` 等价于 `<name:\S+>`；`<name:regex>` 将整个尖括号作为一个捕获字段。`\\<`、`\\>`、`\\\\` 表示字面字符，整行隐含起止边界。正则内部额外的捕获组不会暴露给工作流。模式必须是单行，执行器负责大小写和配置块边界。

## 结果与表达式

运行结果始终位于 `config` 根。唯一命令无匹配为 `null`，无捕获但匹配成功为 `{}`；非唯一命令无匹配为 `[]`。子命令成为父对象属性，数组只能使用整数下标：

```text
config.interface[0].name
config.interface[0].ip_address.address
```

不支持 `config["interface"]`。每台设备拥有独立上下文；同一上下文合并多个 Config 调用时根命令名不能冲突。Config Collection 的普通 inputs/outputs 仍按原有绑定语义保存，捕获结果不并入普通 outputs。

## 运行边界

Config 调用的 `sampleCount` 固定为 `1`，可以按设备角色形成独立上下文。原始配置文本、块匹配、唯一性判断和捕获类型转换由执行器负责。当前 `/workflow/executor` 尚不接受 Config Collection，会返回 `executor_workflow.unsupported_collection_type`；执行器契约演进后再单独扩展。
