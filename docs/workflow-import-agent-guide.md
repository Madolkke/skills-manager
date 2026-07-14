# Workflow 转换与导入 Agent 指南

本文面向负责迁移旧 Workflow 的 Agent。输入是用户提供的旧 Workflow 文件和目标 Workflow Skill ID；输出是符合本指南的 `WorkflowImportBundle`，并通过 SkillHub API 原子导入。

持久化 Workflow 的完整字段语义见 [workflow-schema.md](workflow-schema.md)。本指南只描述 schema v3 的转换和导入专用格式；v2 的步骤输入、`step_input` Binding 和 Collection 输出 `name` 均不能导入。

## 1. 导入接口

```http
POST /api/skills/{skill_id}/workflow/import
Content-Type: application/json
X-SkillHub-Actor: <actor>
```

请求体直接是 `WorkflowImportBundle`，不要包装为 `document`，也不要提交 `collection_changes`。

接口具有以下语义：

- 覆盖目标 Skill 当前绑定的 Workflow，并创建下一 Workflow revision。
- 不修改 Skill slug、owner、Tags、权限或已有 SkillVersion。
- 每个导入 Collection 都获得新的永久 ID，revision 固定为 1。
- 每次请求都会创建新 Collection，接口不幂等，禁止无条件自动重试。
- 结构和引用错误会回滚全部写入；领域 error/warning 可以作为草稿导入。

## 2. Import Bundle 字段

### 顶层

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `documentType` | `"workflow_import_bundle"` | 是 | 导入文档类型常量。 |
| `workflow` | `ImportWorkflow` | 是 | 不含持久化 ID/revision 的 Workflow 内容。 |
| `collections` | `ImportCollectionDefinition[]` | 否，默认 `[]` | 本次导入的 Collection 定义；无论是否被调用都会进入 Catalog。 |

### ImportWorkflow

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `metadata` | `WorkflowMetadata` | 是 | 名称、编码、说明、问题现象、产业、设备和适用版本。 |
| `inputs` | `Parameter[]` | 否 | Workflow 全局输入。 |
| `deviceRoles` | `DeviceRole[]` | 否 | 逻辑设备角色。 |
| `nodes` | `(ImportExpressionStep \| ImportScriptStep \| Conclusion)[]` | 否 | 步骤和结论节点。 |

不要填写 `workflow.id` 或 `workflow.revision`。后端使用目标 Workflow 的永久 ID 并分配下一 revision。

### ImportCollectionDefinition

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `localId` | `string` | 是 | 仅在本次请求内有效的唯一引用标识。 |
| `key` | `string` | 是 | Collection 可读 Key。 |
| `metadata` | `CollectionMetadata` | 是 | 名称、说明、适用范围和 Tags。 |
| `spec` | `CliCollectionSpec` | 是 | CLI 命令模板和回显示例。 |
| `inputs` | `Parameter[]` | 否 | 命令模板输入参数。 |
| `outputs` | `CollectionOutput[]` | 否 | 采集输出字段。 |

不要填写持久化 `id`、`revision` 或 `forkedFrom`。

### Import Collection Call

Import Step 的 `collectionCalls` 与标准 Call 基本一致，但使用 `definitionLocalId`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `id` | `string` | 是 | Call 身份，Binding 可通过它引用输出。 |
| `key` | `string` | 是 | 可选输出命名空间，允许空字符串。 |
| `name` | `string` | 是 | 可选展示名称，允许空字符串。 |
| `definitionLocalId` | `string` | 是 | 指向 `collections[].localId`。 |
| `deviceRoleId` | `string` | 否 | 使用的设备角色 ID。 |
| `sampleCount` | `integer` | 否，默认 `1` | 采集次数。 |
| `inputBindings` | `Record<inputId, Binding>` | 否 | Collection 输入参数的来源。 |

不要提交标准持久化字段 `definition: { id, revision }`。

### 复用的标准结构

以下对象与 [Workflow 文档 Schema](workflow-schema.md) 完全相同：

- `WorkflowMetadata`
- `Parameter` 和 `Binding`
- `DeviceRole`
- Step 的 `id/name/description/isStart/collectionCalls/topology/stepType/script`
- `Transition`、`NodeRef` 和 `Conclusion`
- `CollectionMetadata`、`CliCollectionSpec`、`CollectionOutput` 和回显示例

## 3. 转换算法

Agent 必须按以下顺序转换：

1. 读取旧文件并列出元信息、参数、设备、步骤、命令、路径和结论。
2. 记录无法映射或主动丢弃的旧字段，不要静默遗漏。
3. 为节点、参数、Call、Output 和 Transition 生成请求内唯一且稳定的 ID。
4. 将可复用的命令采集能力抽取到 `collections`，为每个定义分配唯一 `localId`。
5. 将步骤调用改为 `definitionLocalId`，不要生成 Catalog ID 或 revision。
6. 重建 Collection 输入 Binding、Transition target 和脚本返回的 Transition ID。
7. 运行本地结构检查，输出 JSON 文件供人工检查。
8. 只有操作者显式要求时才调用导入接口。
9. 保存响应中的 Collection ID 映射，并再次 GET Workflow 核对 revision 和文档。

### ID 规则

- 节点名称只用于展示，Transition 必须通过节点 ID 指向目标。
- `localId` 只关联导入定义与 Call，不能在导入后当作永久 ID 使用。
- 脚本如果返回 Transition ID，源码中的字符串必须与对应 `topology[].id` 完全一致。
- 不要重新生成脚本已经引用的 Transition ID，除非同步改写脚本源码。

### 数据与安全规则

- 输入参数使用现有 `Parameter`，Collection 输出使用 `id/key/dataType/description`，不要添加输出 `name` 或发明脚本专属输入格式。
- 原始命令回显只可作为必要的作者示例；默认不迁移生产回显、账号、Cookie、Token、私钥或设备敏感信息。
- 不把 Skill owner、平台 Tags、权限和版本历史写入 Import Bundle。
- 未被 Call 引用的 `collections` 仍会入库；Agent 必须在报告中列出这些定义。

## 4. 完整 Import Bundle 示例

<!-- workflow-import-example:start -->
```json
{
  "documentType": "workflow_import_bundle",
  "workflow": {
    "metadata": {
      "name": "接口状态检查",
      "code": "INTERFACE_CHECK",
      "description": "采集并分析接口状态。",
      "symptom": "接口出现频繁闪断。",
      "industry": "网络",
      "device": "交换机",
      "versions": []
    },
    "inputs": [],
    "deviceRoles": [],
    "nodes": [
      {
        "id": "step-analyze",
        "name": "分析接口状态",
        "description": "根据命令回显选择路径。",
        "isStart": true,
        "collectionCalls": [
          {
            "id": "call-interface",
            "key": "interface",
            "name": "接口状态",
            "definitionLocalId": "interface-status",
            "sampleCount": 1,
            "inputBindings": {}
          }
        ],
        "topology": [
          {
            "id": "transition-fault",
            "target": { "id": "conclusion-fault" },
            "conditionText": "检测到接口故障",
            "conditionExpression": ""
          }
        ],
        "stepType": "script",
        "script": {
          "language": "python",
          "source": "def main(context):\n    return 'transition-fault'",
          "options": {}
        }
      },
      {
        "id": "conclusion-fault",
        "name": "接口故障",
        "rootCause": "接口状态异常。",
        "repairRecommendation": "检查接口配置和物理连接。",
        "nodeType": "conclusion"
      }
    ]
  },
  "collections": [
    {
      "localId": "interface-status",
      "key": "interface_status",
      "metadata": {
        "name": "接口状态采集",
        "description": "采集接口运行状态。",
        "industry": "网络",
        "device": "交换机",
        "versions": [],
        "tags": []
      },
      "spec": {
        "collectionType": "cli",
        "commandTemplate": "display interface",
        "outputSamples": []
      },
      "inputs": [],
      "outputs": [
        {
          "id": "output-cli-text",
          "key": "cli_text",
          "description": "原始 CLI 输出。",
          "dataType": "string"
        }
      ]
    }
  ]
}
```
<!-- workflow-import-example:end -->

## 5. Python 转换脚本骨架

下面的脚本默认只生成 JSON。只有传入 `--apply` 才调用 API；Agent 必须实现 `convert_old_workflow()` 中针对旧格式的映射。

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib import error, request


def convert_old_workflow(old: dict) -> dict:
    """将用户提供的旧结构转换为 WorkflowImportBundle。"""
    raise NotImplementedError("根据旧 Workflow 格式实现字段映射")


def validate_import_bundle(bundle: dict) -> None:
    if bundle.get("documentType") != "workflow_import_bundle":
        raise ValueError("documentType 必须为 workflow_import_bundle")
    workflow = bundle.get("workflow")
    if not isinstance(workflow, dict) or not isinstance(bundle.get("collections", []), list):
        raise ValueError("workflow 或 collections 格式不正确")
    for field in ("metadata", "inputs", "deviceRoles", "nodes"):
        if field not in workflow:
            raise ValueError(f"workflow 缺少必填字段: {field}")

    local_ids = [item.get("localId", "").strip() for item in bundle["collections"]]
    if any(not item for item in local_ids) or len(local_ids) != len(set(local_ids)):
        raise ValueError("Collection localId 必须非空且唯一")
    known_local_ids = set(local_ids)
    definitions = {item["localId"]: item for item in bundle["collections"]}
    all_ids: list[str] = []
    for definition in bundle["collections"]:
        for field in ("key", "metadata", "spec", "inputs", "outputs"):
            if field not in definition:
                raise ValueError(f"Collection {definition['localId']} 缺少字段: {field}")
        all_ids.extend(item.get("id", "") for item in definition["inputs"])
        all_ids.extend(item.get("id", "") for item in definition["outputs"])
        all_ids.extend(item.get("id", "") for item in definition["spec"].get("outputSamples", []))
    all_ids.extend(item.get("id", "") for item in workflow["inputs"])
    all_ids.extend(item.get("id", "") for item in workflow["deviceRoles"])
    nodes = workflow.get("nodes", [])
    node_ids = [item.get("id") for item in nodes]
    if any(not item for item in node_ids) or len(node_ids) != len(set(node_ids)):
        raise ValueError("节点 ID 必须非空且唯一")
    known_nodes = set(node_ids)
    all_ids.extend(node_ids)
    workflow_input_ids = {item["id"] for item in workflow["inputs"]}
    for node in nodes:
        if "stepType" not in node:
            continue
        calls = {item["id"]: item for item in node.get("collectionCalls", [])}
        all_ids.extend(calls)
        for call in node.get("collectionCalls", []):
            if call.get("definitionLocalId") not in known_local_ids:
                raise ValueError(f"Call 引用了不存在的 localId: {call.get('definitionLocalId')}")
            definition = definitions[call["definitionLocalId"]]
            known_inputs = {item["id"] for item in definition["inputs"]}
            if not set(call.get("inputBindings", {})) <= known_inputs:
                raise ValueError(f"Call {call['id']} 包含不存在的 Collection 输入绑定")
        for transition in node.get("topology", []):
            if transition.get("target", {}).get("id") not in known_nodes:
                raise ValueError(f"Transition 目标不存在: {transition.get('id')}")
            all_ids.append(transition.get("id", ""))
        for call in node.get("collectionCalls", []):
            for binding in call.get("inputBindings", {}).values():
                validate_binding(binding, workflow_input_ids, calls, definitions)
    if any(not item for item in all_ids) or len(all_ids) != len(set(all_ids)):
        raise ValueError("节点、参数、角色、Call、Output、Sample 和 Transition ID 必须非空且全局唯一")


def validate_binding(binding: dict, workflow_inputs: set[str], calls: dict, definitions: dict) -> None:
    kind = binding.get("kind")
    reference = binding.get("reference", {})
    if kind == "literal":
        return
    if kind == "workflow_input" and reference.get("input_id") in workflow_inputs:
        return
    if kind == "collection_output":
        call = calls.get(reference.get("call_id"))
        definition = definitions.get(call.get("definitionLocalId")) if call else None
        if definition and any(item["id"] == reference.get("output_id") for item in definition["outputs"]):
            return
    raise ValueError(f"Binding 引用无效: {kind}")


def post_bundle(api_base: str, skill_id: str, actor: str, bundle: dict) -> dict:
    url = f"{api_base.rstrip('/')}/api/skills/{skill_id}/workflow/import"
    payload = json.dumps(bundle, ensure_ascii=False).encode("utf-8")
    call = request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "X-SkillHub-Actor": actor},
    )
    try:
        with request.urlopen(call, timeout=60) as response:
            return json.load(response)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Workflow 导入失败: HTTP {exc.code}: {detail}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("old_file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--api-base")
    parser.add_argument("--skill-id")
    parser.add_argument("--actor")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    old = json.loads(args.old_file.read_text(encoding="utf-8"))
    bundle = convert_old_workflow(old)
    validate_import_bundle(bundle)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not args.apply:
        print(f"已生成待检查文件: {args.output}")
        return
    if not all((args.api_base, args.skill_id, args.actor)):
        parser.error("--apply 需要 --api-base、--skill-id 和 --actor")
    result = post_bundle(args.api_base, args.skill_id, args.actor, bundle)
    mapping_file = args.output.with_suffix(".mapping.json")
    mapping_file.write_text(
        json.dumps(result["import_result"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"导入完成，Workflow revision={result['revision']}，映射文件={mapping_file}")


if __name__ == "__main__":
    main()
```

## 6. 导入后核对

成功响应包含规范化 `document` 和映射：

```json
{
  "revision": 2,
  "import_result": {
    "collection_mappings": [
      {
        "local_id": "interface-status",
        "definition_id": "collection_generated",
        "revision": 1
      }
    ]
  }
}
```

导入后执行：

```http
GET /api/skills/{skill_id}/workflow
```

核对以下内容：

- 返回 revision 与导入响应一致。
- `document.workflow.id` 是目标 Workflow ID。
- 所有 Call 已转换为 `definition: { id, revision: 1 }`。
- 被调用的定义出现在 `document.collectionSnapshots`。
- `validation.errors/warnings` 已记录在转换报告中。

## 7. 错误处理

| 状态 | 含义 | Agent 行为 |
| --- | --- | --- |
| `400` | Import Bundle 结构、localId 或引用错误 | 修正转换结果，不重试原请求。 |
| `403` | actor 缺少 `skill.edit` | 停止并要求提供有权限的 actor。 |
| `404` | Skill 不存在或未绑定 Workflow | 停止并核对目标 Skill。 |
| 网络超时 | 结果未知 | 禁止自动重试；先 GET Workflow 比较 revision/updated_at，再由操作者决定。 |

## 8. Agent 完成报告

Agent 完成转换后必须报告：

- 旧 Workflow 来源文件和识别出的格式。
- 转换后的步骤、结论、Transition、Collection 和参数数量。
- 未映射、推断或丢弃的旧字段。
- 脚本引用的 Transition ID 核对结果。
- 未被任何 Call 引用但仍导入的 Collection。
- Import Bundle 输出路径和是否实际调用 API。
- 导入后的 Workflow revision、Collection ID 映射和 validation errors/warnings。
