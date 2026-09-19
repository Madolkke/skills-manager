# 网络巡检 CLI 流程说明

这是可复现的离线作者验收场景，命令和输出类型在本文明确规定；不声称某一真实设备厂商支持这些命令，也没有生产回显。

## 目标与输入

名称为“网络巡检 CLI 离线示例”，编码 OFFLINE_CLI_CHECK。先采集接口和路由，再检查 Fabric 健康，最后汇总路由数量供人工查看，不自动执行修复。

全局输入 interface（接口名称 string）、vrf（路由实例 string）、index（查询下标 integer）均必填。设备角色 key=device，名称“巡检设备”，具有必填 string 字段 address（管理地址）；所有采集均使用该角色。

## 步骤一：采集接口与路由

这是唯一的起始步骤，按顺序采集 interfaces、routes、bgp：

1. `show interfaces <interface>`，参数来自全局 interface。
2. `show routes vrf <vrf>`，参数来自全局 vrf。
3. `show bgp peers <vrf>`，参数取前一个 routes 调用返回的第一条路由的 vrf；不要再次绑定全局 vrf。

本步骤按“执行所有满足条件的分支”记录分支模式。接口数组非空时转步骤二；数组为空时直接转汇总结论。前一个条件说明展示设备管理地址和第一个接口名，后一个说明“接口为空时直接生成结论”。这两条条件本身互斥，模式仍按作者要求保留。

## 步骤二：重复采集健康信息

普通互斥分支模式。按顺序执行：

1. fabric 调用：固定命令 `show fabric health`，不需要输入，采集三次。
2. routes_repeat 调用：复用 routes 定义，vrf 引用步骤一 routes 输出第一条路由的 vrf。这是跨步骤输入绑定。

第一轮采集 matrix 的第 0 行第 0 列 healthy 为真时转汇总结论。路径说明包含该单元格的 value，以及最后一轮采集的 labels 数量。为假时本文没有指定后续处置，应列入人工审阅事项，不编造第二个业务结论。

## 结论

名称“汇总巡检结果”。根因栏仅陈述“已采集 N 条路由”，N 来自步骤一 routes 数组长度，不据此认定设备存在故障。建议“依据采集结果人工判断；本文不执行命令或修复操作。”

## 明确的输出契约

以下为每条命令的输出字段及 Schema。所有输出均 required=true；嵌套 required 和 additionalProperties 均按下列契约保留。items 是业务数组结构，不包含 fabric 的三次采集外层数组。

### interfaces

```json
{
  "interfaces": {
    "type": "array",
    "title": "接口列表",
    "description": "接口列表，由本示例契约明确声明。",
    "items": {
      "type": "object",
      "title": "接口",
      "description": "接口，由本示例契约明确声明。",
      "properties": {
        "name": {"type": "string", "title": "接口名称", "description": "接口名称，由本示例契约明确声明。"},
        "up": {"type": "boolean", "title": "链路状态", "description": "链路状态，由本示例契约明确声明。"},
        "counters": {
          "type": "object",
          "title": "报文统计",
          "description": "报文统计，由本示例契约明确声明。",
          "properties": {"rx": {"type": "integer", "title": "接收数", "description": "接收数，由本示例契约明确声明。"}, "tx": {"type": "integer", "title": "发送数", "description": "发送数，由本示例契约明确声明。"}},
          "required": ["rx", "tx"],
          "additionalProperties": false
        },
        "addresses": {
          "type": "array",
          "title": "地址列表",
          "description": "地址列表，由本示例契约明确声明。",
          "items": {
            "type": "object",
            "title": "地址",
            "description": "地址，由本示例契约明确声明。",
            "properties": {
              "address": {"type": "string", "title": "IP 地址", "description": "IP 地址，由本示例契约明确声明。"},
              "prefix_length": {"type": "integer", "title": "掩码位数", "description": "掩码位数，由本示例契约明确声明。"}
            },
            "required": ["address", "prefix_length"],
            "additionalProperties": false
          }
        }
      },
      "required": ["name", "up", "counters", "addresses"],
      "additionalProperties": false
    }
  }
}
```

### routes

```json
{
  "routes": {
    "type": "array",
    "title": "路由列表",
    "description": "路由列表，由本示例契约明确声明。",
    "items": {
      "type": "object",
      "title": "路由",
      "description": "路由，由本示例契约明确声明。",
      "properties": {
        "prefix": {"type": "string", "title": "目的前缀", "description": "目的前缀，由本示例契约明确声明。"},
        "vrf": {"type": "string", "title": "路由实例", "description": "路由实例，由本示例契约明确声明。"},
        "next_hops": {
          "type": "array",
          "title": "下一跳列表",
          "description": "下一跳列表，由本示例契约明确声明。",
          "items": {
            "type": "object",
            "title": "下一跳",
            "description": "下一跳，由本示例契约明确声明。",
            "properties": {
              "address": {"type": "string", "title": "下一跳地址", "description": "下一跳地址，由本示例契约明确声明。"},
              "weight": {"type": "number", "title": "权重", "description": "权重，由本示例契约明确声明。"}
            },
            "required": ["address", "weight"],
            "additionalProperties": false
          }
        }
      },
      "required": ["prefix", "vrf", "next_hops"],
      "additionalProperties": false
    }
  }
}
```

### bgp

```json
{
  "peers": {
    "type": "array",
    "title": "邻居列表",
    "description": "邻居列表，由本示例契约明确声明。",
    "items": {
      "type": "object",
      "title": "邻居",
      "description": "邻居，由本示例契约明确声明。",
      "properties": {
        "address": {"type": "string", "title": "邻居地址", "description": "邻居地址，由本示例契约明确声明。"},
        "state": {"type": "string", "title": "会话状态", "description": "会话状态，由本示例契约明确声明。"},
        "families": {
          "type": "array",
          "title": "地址族列表",
          "description": "地址族列表，由本示例契约明确声明。",
          "items": {
            "type": "object",
            "title": "地址族",
            "description": "地址族，由本示例契约明确声明。",
            "properties": {
              "name": {"type": "string", "title": "地址族名称", "description": "地址族名称，由本示例契约明确声明。"},
              "prefixes": {
                "type": "object",
                "title": "前缀统计",
                "description": "前缀统计，由本示例契约明确声明。",
                "properties": {"received": {"type": "integer", "title": "接收前缀数", "description": "接收前缀数，由本示例契约明确声明。"}},
                "required": ["received"],
                "additionalProperties": false
              }
            },
            "required": ["name", "prefixes"],
            "additionalProperties": false
          }
        }
      },
      "required": ["address", "state", "families"],
      "additionalProperties": false
    }
  }
}
```

### fabric

```json
{
  "matrix": {
    "type": "array",
    "title": "健康矩阵",
    "description": "健康矩阵，由本示例契约明确声明。",
    "items": {
      "type": "array",
      "title": "矩阵行",
      "description": "矩阵行，由本示例契约明确声明。",
      "items": {
        "type": "object",
        "title": "单元格",
        "description": "单元格，由本示例契约明确声明。",
        "properties": {
          "value": {"type": "number", "title": "测量值", "description": "测量值，由本示例契约明确声明。"},
          "healthy": {"type": "boolean", "title": "是否健康", "description": "是否健康，由本示例契约明确声明。"}
        },
        "required": ["value", "healthy"],
        "additionalProperties": false
      }
    }
  },
  "labels": {"type": "array", "title": "标签列表", "description": "标签列表，由本示例契约明确声明。", "items": {"type": "string", "title": "标签", "description": "标签，由本示例契约明确声明。"}}
}
```
