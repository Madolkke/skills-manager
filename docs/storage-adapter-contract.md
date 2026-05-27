# Storage Adapter Contract

本文档定义 SkillHub 内容存储边界。数据库保存事实关系，Artifact adapter 保存不可变内容。当前实现仍可使用数据库内 artifact 记录，后续可以替换为文件系统、对象存储或 Git adapter。

## 存储对象

Artifact adapter 负责：

- 标准 Skill bundle 文件树。
- Eval case input。
- Expected output。
- Actual output。
- 外部 runner 原始报告、日志和 transcript。

数据库只保存：

- `artifact_id`
- `kind`
- `locator`
- `digest`
- `media_type`
- `size`
- `created_at`
- `created_by`

## 最小接口

```python
class ArtifactStore(Protocol):
    def put_blob(self, namespace: str, content: bytes, media_type: str) -> ArtifactRef:
        ...

    def put_tree(self, namespace: str, files: list[BundleFileInput]) -> ArtifactRef:
        ...

    def read_blob(self, ref: ArtifactRef) -> bytes:
        ...

    def read_tree(self, ref: ArtifactRef) -> list[BundleFile]:
        ...
```

要求：

- 写入必须返回不可变 locator。
- digest 在写入前或写入时计算，并在读取时可校验。
- 路径必须标准化，拒绝 path traversal。
- 同一内容重复写入应该是幂等的。
- adapter 不保存 Skill、EvalRun 或权限关系。

## 文件和对象存储

本地文件系统和 S3-compatible object storage 都应满足同一 locator 语义：

```text
file:<absolute-or-data-root-relative-path>#sha256:<digest>
object:<bucket>/<key>#sha256:<digest>
```

生产部署优先使用对象存储；本地开发可以继续使用 `.data` 下的文件型实现。

## Git Adapter

Git adapter 只能作为内容 adapter：

- locator 必须指向 commit SHA 和路径。
- 不允许使用 branch name 作为不可变内容引用。
- fork、PR、review 是协作层概念，不进入核心 `SkillVersion` 模型。

示例：

```text
git:ssh://git.example/skills.git#abc1234:bundles/code-reviewer/
```

## 当前约束

- `SkillVersion.content_ref` 指向不可变 Skill bundle。
- Bundle diff 只比较同一 Skill 的两个 `SkillVersion`。
- actual output 必须作为 run 证据保存，不能只存在浏览器状态。
