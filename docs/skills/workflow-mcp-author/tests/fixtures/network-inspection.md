# 网络设备接口、路由与 Fabric 健康巡检

这是合成测试流程，不代表真实设备厂商支持这些命令，也不包含生产数据。请创建在线 CLI 工作流，供人工审阅，不运行命令。

## 标识与输入

工作流名称前缀 qa_mcp_skill_网络巡检，编码 QA_MCP_NETWORK；slug 使用 qa-mcp-skill-network 加本轮唯一后缀。已有同名目标先检查，不覆盖其他测试数据。
标签选“演示：技能场景”的“数据中心”；若目标目录没有此标签，先询问替代，不随机选择。可选级联标签不选。
全局输入 interface（string，接口名称）、vrf（string，路由实例）、index（integer，观察接口的下标）均必填。
设备角色 key=device，名称“巡检设备”，具有必填 string 字段 address（管理地址），禁止额外字段。所有采集使用该设备角色。输入和嵌套字段均需中文名称、说明。

## 第一步：接口与路由概况

唯一起始步骤，互斥分支。按顺序采集：

1. 调用 Key interfaces，具体命令 `show interfaces <interface>`，interface 绑定全局同名输入，采集一次。
2. 调用 Key routes，具体命令 `show routes <vrf>`，vrf 绑定全局同名输入，采集一次。

分支必须先判断数据是否存在：
- 接口列表为空或路由列表为空，转“数据不足”结论；说明展示接口和路由的数量，不索引空数组。
- 两者非空且第一个接口 up 为 false，转“接口异常”；说明展示第一个接口名及 counters.errors。
- 两者非空且第一个接口 up 为 true，进入第二步；说明展示设备管理地址、第一个接口名以及路由数量。

## 第二步：邻居与 Fabric 检查

互斥分支，按顺序采集：

1. bgp：`show bgp peers <vrf>`，参数使用第一步 routes 结果第一条路由的 vrf，不再绑定全局 vrf，采集一次。
2. fabric：固定命令 `show fabric health`，没有输入，采集三次。
3. peer_check：合成命令 `show qa-mcp-check <peer_count> compare <peer_count>`，采集一次。重复占位符只对应一个必填 integer 参数，绑定本步骤前序 bgp 邻居数组的长度。系统库无兼容规则时创建自定义 CLI，输出契约在下方。

分支规则：
- 第一轮 fabric 的 matrix 没有行或第一行没有单元，转“数据不足”，说明“不完整的 Fabric 矩阵”。检查时不得在空列表上索引。
- 第一轮 matrix 有第一个单元且该单元 healthy 为 true，转“健康”；说明展示该单元 healthy 及最后一轮 labels 数量。
- 同一单元存在且 healthy 为 false，转“Fabric 异常”；说明展示该单元 healthy 及 peer_check 的 matched 值。

BGP 邻居和 labels 可以为空，不依赖其第一个元素。Fabric.value 是可选字段，不用于必达路径或必填结论。业务数组没有固定长度保证，index 为用户输入，不能假定它有效；本流程仅声明该输入供后续人工拓展，不强行引用。

## 四个结论

- 数据不足：只陈述“采集结果不足，请核对命令与设备回显”，建议人工补齐；不引用只有第二步才有的输出。
- 接口异常：显示第一接口名和错误计数，建议检查链路；不要下发修复命令。
- 健康：显示第一步路由数量、BGP 邻居数量、第一轮 Fabric 第一个单元 healthy、最后一轮 labels 数量；建议保留巡检记录。
- Fabric 异常：显示第一轮 Fabric 第一个单元 healthy 和 peer_check.matched，建议人工核对 Fabric 状态。

## 明确输出契约

下面 JSON 是每种命令的完整根输出 Schema，不是工作流 JSON。业务层级不包含三次采集的额外外层。系统来源必须兼容下述契约，不根据回显示例推断或修改类型。所有示例均为合成展示，不要求 TTP 解析。

### interfaces

```json
{"type": "object", "title": "接口输出", "required": ["interfaces"], "properties": {"interfaces": {"type": "array", "items": {"type": "object", "title": "接口信息", "required": ["name", "up", "counters", "addresses"], "properties": {"up": {"type": "boolean", "title": "链路状态", "description": "是否已连接"}, "name": {"type": "string", "title": "接口名称", "description": "接口标识"}, "counters": {"type": "object", "title": "计数器", "required": ["rx", "tx", "errors"], "properties": {"rx": {"type": "integer", "title": "接收数", "description": "接收包数"}, "tx": {"type": "integer", "title": "发送数", "description": "发送包数"}, "errors": {"type": "integer", "title": "错误数", "description": "错误包数"}}, "description": "计数器结构", "additionalProperties": false}, "addresses": {"type": "array", "items": {"type": "object", "title": "地址信息", "required": ["address", "prefix_length"], "properties": {"address": {"type": "string", "title": "地址", "description": "IP 地址"}, "prefix_length": {"type": "integer", "title": "前缀长度", "description": "网络前缀长度"}}, "description": "地址信息结构", "additionalProperties": false}, "title": "地址", "description": "地址列表"}}, "description": "接口信息结构", "additionalProperties": false}, "title": "接口", "description": "接口列表"}}, "description": "接口输出结构", "additionalProperties": false}
```

### routes

```json
{"type": "object", "title": "路由输出", "required": ["routes", "summary"], "properties": {"routes": {"type": "array", "items": {"type": "object", "title": "路由信息", "required": ["prefix", "vrf", "next_hops"], "properties": {"vrf": {"type": "string", "title": "路由实例", "description": "所属 VRF"}, "prefix": {"type": "string", "title": "目标前缀", "description": "路由目标地址"}, "next_hops": {"type": "array", "items": {"type": "object", "title": "下一跳信息", "required": ["address", "metric"], "properties": {"metric": {"type": "number", "title": "度量", "description": "路由度量值"}, "address": {"type": "string", "title": "地址", "description": "下一跳 IP 地址"}}, "description": "下一跳信息结构", "additionalProperties": false}, "title": "下一跳", "description": "下一跳列表"}}, "description": "路由信息结构", "additionalProperties": false}, "title": "路由", "description": "路由列表"}, "summary": {"type": "object", "title": "汇总", "required": ["total"], "properties": {"total": {"type": "integer", "title": "路由总数", "description": "路由记录数量"}}, "description": "汇总结构", "additionalProperties": false}}, "description": "路由输出结构", "additionalProperties": false}
```

### bgp

```json
{"type": "object", "title": "BGP 输出", "required": ["peers"], "properties": {"peers": {"type": "array", "items": {"type": "object", "title": "邻居信息", "required": ["address", "state", "families"], "properties": {"state": {"type": "string", "title": "会话状态", "description": "BGP 会话状态"}, "address": {"type": "string", "title": "地址", "description": "邻居 IP 地址"}, "families": {"type": "array", "items": {"type": "object", "title": "地址族信息", "required": ["name", "prefixes"], "properties": {"name": {"type": "string", "title": "地址族名称", "description": "IPv4 或 IPv6"}, "prefixes": {"type": "object", "title": "前缀统计", "required": ["received", "accepted"], "properties": {"accepted": {"type": "integer", "title": "接受数", "description": "接受的前缀数量"}, "received": {"type": "integer", "title": "接收数", "description": "收到的前缀数量"}}, "description": "前缀统计结构", "additionalProperties": false}}, "description": "地址族信息结构", "additionalProperties": false}, "title": "地址族", "description": "地址族列表"}}, "description": "邻居信息结构", "additionalProperties": false}, "title": "邻居", "description": "邻居列表"}}, "description": "BGP 输出结构", "additionalProperties": false}
```

### fabric

```json
{"type": "object", "title": "Fabric 输出", "required": ["matrix", "labels"], "properties": {"labels": {"type": "array", "items": {"type": "string", "title": "标签名称", "description": "节点名称"}, "title": "标签", "description": "标签列表"}, "matrix": {"type": "array", "items": {"type": "array", "items": {"type": "object", "title": "矩阵单元", "required": ["healthy"], "properties": {"value": {"type": "number", "title": "健康评分", "description": "单元健康评分"}, "healthy": {"type": "boolean", "title": "健康状态", "description": "单元是否健康"}}, "description": "矩阵单元结构", "additionalProperties": false}, "title": "矩阵行", "description": "矩阵行列表"}, "title": "健康矩阵", "description": "健康矩阵列表"}}, "description": "Fabric 输出结构", "additionalProperties": false}
```

### peer_check

```json
{"type": "object", "title": "邻居复核输出", "description": "合成计数复核结果", "properties": {"matched": {"type": "boolean", "title": "计数匹配", "description": "两个传入计数是否一致"}, "checked": {"type": "integer", "title": "复核数量", "description": "参与复核的邻居数量"}}, "required": ["matched", "checked"], "additionalProperties": false}
```

## 合成回显示例

```text
Interface eth0 is up; rx=10 tx=12 errors=0
Route 10.0.0.0/24 vrf=default via=192.0.2.1 metric=10
Peer 192.0.2.2 state=Established
Fabric cell healthy=true value=99.5 labels=leaf-a
Peer check matched=true checked=1
```
