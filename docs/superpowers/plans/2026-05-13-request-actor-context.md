# 请求级 ActorContext 实施计划

> **给执行代理的说明：** 按任务逐项执行，步骤用 checkbox（`- [ ]`）追踪。

**目标：** 让后端 mutation 命令从请求级 `ActorContext` 获取 actor，不再信任 JSON body 中的 `actor` 字段。

**架构：** 新增 FastAPI dependency `actor_dependency`，集中读取 `X-SkillHub-Actor` 开发 header。API route 负责把 `ActorContext.id` 传给 repository；repository 权限判断和审计写入保持不变。前端的 `apiSend` 统一附加 header，并删除 mutation body 中的 actor。

**技术栈：** FastAPI dependency、Pydantic payload、Next.js client component fetch、Playwright E2E、pytest。

---

### Task 1: 红色 API 测试

**涉及文件：**
- 修改：`apps/api/tests/test_api_commands.py`

- [x] **步骤 1：让 TestClient 默认携带 actor header**

`setUp` 中把测试客户端改为：

```python
self.client = TestClient(create_app(create_local_sqlite_engine()), headers={"X-SkillHub-Actor": "tester"})
```

- [x] **步骤 2：新增 header actor 覆盖 body actor 的测试**

新增测试：用 `headers={"X-SkillHub-Actor": "header-owner"}` 创建 skill，同时 JSON body 传 `"actor": "body-attacker"`；断言 role assignment 的 owner 是 `header-owner`，不是 `body-attacker`。

- [x] **步骤 3：更新受保护动作测试**

viewer promotion、viewer accepted verification 用 per-request `headers={"X-SkillHub-Actor": "readonly-user"}`；maintainer accepted verification 用 `headers={"X-SkillHub-Actor": "release-manager"}`。body 里故意保留或传入伪造 actor，确认不会绕过 header 身份。

- [x] **步骤 4：验证红灯**

运行：

```bash
cd apps/api && uv run pytest tests/test_api_commands.py -k "actor or permission" -q
```

预期：至少 header 覆盖 body actor 的测试失败，因为 route 仍使用 payload actor。

### Task 2: 后端 ActorContext

**涉及文件：**
- 新增：`apps/api/skillhub/api/auth.py`
- 修改：`apps/api/skillhub/api/main.py`

- [x] **步骤 1：新增 auth dependency**

创建 `auth.py`，定义：

```python
from dataclasses import dataclass

from fastapi import Header

from skillhub.domain.errors import InvariantError

ACTOR_HEADER = "X-SkillHub-Actor"
DEFAULT_LOCAL_ACTOR = "product-operator"


@dataclass(frozen=True)
class ActorContext:
    id: str
    subject_type: str = "user"


def actor_dependency(x_skillhub_actor: str | None = Header(default=None, alias=ACTOR_HEADER)) -> ActorContext:
    actor = (x_skillhub_actor or DEFAULT_LOCAL_ACTOR).strip()
    if not actor:
        raise InvariantError("Actor identity cannot be blank.")
    return ActorContext(id=actor)
```

- [x] **步骤 2：API route 使用 ActorContext**

在所有 mutation route 上增加 `actor: ActorContext = Depends(actor_dependency)`，包括 skill、skill import、variant、variant version、promotion、role assignment、eval case、eval case batch、eval case version、case restore、case archive、eval run、accepted verification、saved view。

- [x] **步骤 3：删除 payload actor 字段**

从 mutation payload model 中删除 `actor: str = "system"`。旧客户端如果传 actor，Pydantic 忽略；后端只使用 `actor.id`。

- [x] **步骤 4：验证绿色 API**

运行：

```bash
cd apps/api && uv run pytest tests/test_api_commands.py -k "actor or permission" -q
```

预期：通过。

### Task 3: 前端请求收敛

**涉及文件：**
- 修改：`apps/web/components/decision-workbench.tsx`
- 修改：`apps/web/components/skills/skill-access-panel.tsx`

- [x] **步骤 1：apiSend 统一设置 header**

`apiSend` 的 headers 增加：

```ts
"X-SkillHub-Actor": ACTOR,
```

- [x] **步骤 2：删除 mutation body 中的 actor**

删除所有 `actor: ACTOR` 字段，删除 role revoke URL 的 `?actor=...` query。

- [x] **步骤 3：调整访问控制文案**

把 `SkillAccessPanel` 中“本地模式先用 actor”文案改为“本地开发身份来自请求 header，正式版会替换为 session/token”。

- [x] **步骤 4：验证前端局部路径**

运行：

```bash
cd apps/web && npm run typecheck
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "access roles"
```

预期：通过。

### Task 4: 文档、审计和完整验证

**涉及文件：**
- 修改：`README.md`
- 修改：`docs/api-contract.md`
- 修改：`docs/product-ux-review.md`
- 修改：`docs/product-completion-audit-2026-05-08.md`
- 修改：`.agent/logs/LOG.md`
- 修改：`.agent/tasks.json`
- 新增：`.agent/tasks/TASK-021.json`

- [x] **步骤 1：更新中文文档**

说明本地开发 actor 来自 `X-SkillHub-Actor`，body actor 已废弃；真实认证仍是后续任务。

- [x] **步骤 2：完整验证**

运行：

```bash
cd apps/api && uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e
git diff --check
```

预期：全部通过。

- [x] **步骤 3：提交**

设置 TASK-021 complete / passes true，提交：

```bash
git commit -m "feat: add request actor context"
```
