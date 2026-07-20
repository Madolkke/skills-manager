# SkillHub 部署指南

本文档说明如何把 SkillHub 部署到一台或多台服务器上。当前项目不保留 compose 部署方式，推荐由运维系统分别管理 PostgreSQL、后端 API、前端静态站点、Worker、Opencode 和可选的 Laminar。

后端最小上线顺序为：准备 PostgreSQL 和环境变量、安装锁定依赖、执行一次数据库 migration、启动 API、检查 `/health`、使用唯一 ID 启动 Worker、完成数据库读写和异步任务冒烟测试。数据库 migration 成功前不得启动 API 或 Worker。

## 1. 部署组件

SkillHub 由以下组件组成：

| 组件 | 目录或服务 | 必需 | 说明 |
| --- | --- | --- | --- |
| 后端 API | `apps/backend` | 是 | FastAPI 服务，启动入口为 `skillhub.bootstrap.app:create_app`。 |
| 前端 | `apps/frontend` | 是 | Vue + Vite 构建出的静态站点。 |
| PostgreSQL | 外部数据库 | 是 | Skill、版本、测评、评审、发布、权限和 artifact 元数据的事实源。 |
| Worker | `apps/backend/skillhub_worker` | 异步任务需要 | 消费测评、AI 创建和发布任务；确认发布接口本身只负责入队。 |
| Opencode | 外部服务 | 测评和 AI 创建需要 | SkillHub 不管理 provider key，只读取其 provider/model 配置并调用运行接口。 |
| Laminar | 外部服务 | 可选 | 用于记录测评 trace。未配置时不阻断测评。 |

## 2. 前置要求

建议生产或准生产环境使用：

- Python `3.12+`
- `uv`
- Node.js `24+`，仅构建前端时需要
- PostgreSQL `14+`
- 一个进程管理器，例如 `systemd`、Supervisor、PM2 或平台自带服务管理
- 一个反向代理，例如 Nginx、Caddy、Traefik 或云负载均衡
- 可写的数据目录，用于 Worker 测评工作区，例如 `/var/lib/skillhub/eval-runs`

数据库连接串必须使用 PostgreSQL 协议：

```bash
postgresql+psycopg://skillhub:change-me@127.0.0.1:5432/skillhub
```

## 3. 目录规划

示例目录：

```text
/opt/skillhub/
  repo/              # Git checkout
  env/
    skillhub.env     # API、前端构建和 Worker 共用配置
/var/lib/skillhub/
  eval-runs/         # Worker 隔离工作区
/var/log/skillhub/
  api.log
  worker.log
```

部署用户需要对 `/var/lib/skillhub/eval-runs` 有读写权限。API 与 Worker 可以使用不同系统用户，但必须读取同一份非公开环境配置，并连接同一个 PostgreSQL 数据库。

## 4. 环境变量

### 必填配置

| 变量 | 作用 | 示例 |
| --- | --- | --- |
| `SKILLHUB_DATABASE_URL` | PostgreSQL 连接串 | `postgresql+psycopg://skillhub:***@db:5432/skillhub` |
| `SKILLHUB_SESSION_SECRET` | 签名本地 actor cookie | 使用 32 字节以上随机值 |
| `SKILLHUB_ADMIN_CONSOLE_KEY` | `/skills/admin` 和 `/api/admin/*` 后台密钥 | 使用高强度随机值 |
| `SKILLHUB_LOCAL_SESSION_CODE` | 前端切换本地身份时使用的访问码 | 生产环境必须显式设置，禁止使用默认值 |

### 常用配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SKILLHUB_SESSION_COOKIE_SECURE` | 未启用 | HTTPS 部署时设为 `1`。 |
| `SKILLHUB_CORS_ALLOW_ORIGINS` | 空 | 明确允许的前端 Origin，多个值用逗号分隔。 |
| `SKILLHUB_CORS_ALLOW_ORIGIN_REGEX` | 允许 localhost、IP 和常见主机名 | 自定义跨域匹配规则。 |
| `SKILLHUB_LOG_LEVEL` | `INFO` | 后端 API 和 Worker 日志级别；排查问题时可临时设为 `DEBUG`。 |
| `SKILLHUB_DATABASE_CONNECT_TIMEOUT_SECONDS` | `10` | API、Worker 和 migration 建立 PostgreSQL 连接的最长等待秒数。 |
| `SKILLHUB_DATABASE_STATEMENT_TIMEOUT_MS` | `30000` | PostgreSQL 单条语句最长执行时间，单位毫秒。 |
| `SKILLHUB_DATABASE_LOCK_TIMEOUT_MS` | `5000` | PostgreSQL 锁等待上限，单位毫秒。 |
| `OPENCODE_BASE_URL` | 后端默认 `http://127.0.0.1:4096`，Worker 默认 `http://opencode:4096` | Opencode 服务地址。 |
| `EVAL_WORKDIR_HOST` | Worker 默认 `/var/lib/skillhub/eval-runs` | Worker 在宿主机上的测评工作目录。 |
| `EVAL_WORKDIR_CONTAINER` | `/workspace/eval-runs` | 传给容器化 Opencode 时使用的容器内路径。 |
| `EVAL_RUNNER_POLL_SECONDS` | `2` | Worker 轮询任务间隔。 |
| `EVAL_RUNNER_TIMEOUT_SECONDS` | `300` | Worker 默认运行超时。 |
| `EVAL_RUNNER_MAX_ATTEMPTS` | `2` | 测评任务最大尝试次数。 |
| `EVAL_RUNNER_WORKER_ID` | `opencode-worker` | Worker 实例标识；多实例部署时必须为每个 Worker 设置不同值，后台 Worker 状态页依赖该值聚合心跳。 |
| `WORKER_JOB_STALE_AFTER_SECONDS` | `max(EVAL_RUNNER_TIMEOUT_SECONDS + 60, 360)` | Eval 和 Publish Job 的租约过期阈值。Worker 重启后会立即回收过期任务。 |
| `PUBLISH_RELEASE_TIMEOUT_SECONDS` | `120` | 发布适配器执行外部 release 的截止时间；适配器必须把该值传递给实际 I/O。 |
| `SKILL_BUILDER_STALE_AFTER_SECONDS` | `600` | AI 创建 Skill 会话超过该秒数无进展时，后端会自动释放为可恢复失败态，避免一直占用新会话入口。 |
| `LMNR_PROJECT_API_KEY` | 空 | 配置后启用 Laminar trace。 |
| `LMNR_BASE_URL` | `https://api.lmnr.ai` | Laminar API 地址。 |
| `LMNR_HTTP_PORT` | 空 | Laminar 本地 HTTP 端口，可选。 |
| `OPENCODE_LMNR_BASE_URL` | 同 `LMNR_BASE_URL` | 传给 Opencode Laminar 插件的 Laminar 地址；容器访问本机 Laminar 时通常设为 `http://host.docker.internal`。 |
| `OPENCODE_LMNR_GRPC_PORT` | 空 | 传给 Opencode Laminar 插件的 gRPC 端口；本地 Laminar 通常为 `8001`。 |

### 前端构建配置

| 变量 | 作用 |
| --- | --- |
| `VITE_SKILLHUB_API_URL` | 前端显式 API 地址，例如 `https://skillhub.example.com`。 |
| `VITE_SKILLHUB_API_PORT` | 未配置 API URL 时，按当前浏览器 hostname 拼接该端口。 |
| `VITE_OPENCODE_RUN_POLL_INTERVAL_MS` | 前端测评运行轮询间隔，默认由脚本设为 `5000`。 |

生产建议优先配置 `VITE_SKILLHUB_API_URL`，避免前端在反向代理或多域名场景下拼错 API 地址。

Workflow 编辑器已内置在 SkillHub 前端，不需要单独的服务地址或 iframe 配置。Workflow 文档、Collection Catalog 和同步源快照均使用现有 PostgreSQL 与 artifact 存储。

## 5. 数据库准备

创建数据库和用户：

```sql
CREATE USER skillhub WITH PASSWORD 'change-me';
CREATE DATABASE skillhub OWNER skillhub;
GRANT ALL PRIVILEGES ON DATABASE skillhub TO skillhub;
```

首次部署前先执行数据库初始化和结构检查。迁移命令必须作为独立的一次性任务运行，不能由每个 API 或 Worker 副本并发执行：

```bash
cd /opt/skillhub/repo/apps/backend
export SKILLHUB_DATABASE_URL='postgresql+psycopg://skillhub:change-me@127.0.0.1:5432/skillhub'
uv run python -m skillhub.models.schema.cli upgrade
uv run python -m skillhub.models.schema.cli check
uv run alembic check
```

当前仓库只保留 `0001_initial_schema`，它是首个正式数据库版本，不包含任何正式版之前的迁移链。空数据库会直接创建当前完整结构并写入固定发布目标。已有但未纳入 Alembic 的数据库只有在结构与当前 ORM metadata 完全一致时才会自动 stamp；存在差异时命令会中止且不会删除数据。

正式版之前的 revision 不再受支持。仍带有旧 revision 标记的环境应先备份，通过 SQLAlchemy metadata reflection 确认结构完全一致，再执行 `alembic stamp --purge head`；无法确认一致时应使用空库重新初始化，禁止直接伪造 revision。`stamp` 只改 revision 标记，不会补建表、约束或索引。

## 6. 后端 API 部署

安装依赖：

```bash
cd /opt/skillhub/repo/apps/backend
uv sync --frozen --no-dev
```

启动 API：

```bash
export SKILLHUB_DATABASE_URL='postgresql+psycopg://skillhub:change-me@127.0.0.1:5432/skillhub'
export SKILLHUB_SESSION_SECRET='replace-with-random-secret'
export SKILLHUB_ADMIN_CONSOLE_KEY='replace-with-random-admin-key'
export SKILLHUB_LOCAL_SESSION_CODE='replace-with-random-session-code'
export SKILLHUB_SESSION_COOKIE_SECURE=1
export SKILLHUB_CORS_ALLOW_ORIGINS='https://skillhub.example.com'

uv run uvicorn skillhub.bootstrap.app:create_app \
  --factory \
  --host 127.0.0.1 \
  --port 8000
```

进程健康检查使用专用接口：

```bash
curl -f http://127.0.0.1:8000/health
```

正常响应为 `{"ok":true}`。API 在开始监听端口前会校验数据库 revision；revision 不是 Alembic head 时进程会直接启动失败。部署后的数据库读路径可再使用 `GET /api/skills` 验证。

## 7. Worker 部署

Worker 与 API 使用同一个后端代码目录和同一个数据库连接串。每个 Worker 必须设置唯一且稳定的 `EVAL_RUNNER_WORKER_ID`，禁止多个进程复用同一个 ID。

```bash
cd /opt/skillhub/repo/apps/backend

export SKILLHUB_DATABASE_URL='postgresql+psycopg://skillhub:change-me@127.0.0.1:5432/skillhub'
export OPENCODE_BASE_URL='http://127.0.0.1:4096'
export EVAL_WORKDIR_HOST='/var/lib/skillhub/eval-runs'
export EVAL_WORKDIR_CONTAINER='/workspace/eval-runs'
export EVAL_RUNNER_WORKER_ID='skillhub-worker-1'
export WORKER_JOB_STALE_AFTER_SECONDS=360
export PUBLISH_RELEASE_TIMEOUT_SECONDS=120

uv run python -m skillhub_worker.main
```

需要多个 Worker 时，复制同一服务配置并分别使用 `skillhub-worker-1`、`skillhub-worker-2` 等 ID。Worker 应由进程管理器自动重启；进程异常退出后，重启实例会回收超过租约的 Eval/Publish Job。

当前 `skillhub.services.publish_release.perform_publish_release()` 已为固定目标 `target_key="yunxi"` 提供文件系统发布适配器。Skill 当前标签中存在精确、区分大小写的 `group_id="A"`、`value="a"` 时，Worker 会把完整 Bundle 写入：

```text
/var/lib/skillhub/publish/yunxi/{skill_slug}
```

部署时需要修改发布目录时，只修改 `apps/backend/skillhub/services/publish_release.py` 中这一行：

```python
root = Path("/var/lib/skillhub/publish/yunxi")
```

云析发布会先在相邻的 `.yunxi-control/staging` 中落盘并校验，再整体替换目标 Skill 目录；锁和幂等状态分别保存在 `.yunxi-control/locks` 与 `.yunxi-control/state`。因此 Worker 服务账号必须对以下两个位置具备创建、写入、替换和删除权限：

- `/var/lib/skillhub/publish/yunxi`
- `/var/lib/skillhub/publish/.yunxi-control`

缺少 `A=a` 标签时不会创建目录，适配器返回 `mode="skipped"`，现有状态机会将 PublishRecord 标记为 `released`，并在 release metadata 中记录 `reason="required_tag_missing"`。`path_valid=false` 不影响底层标签匹配。除 `yunxi` 外的发布目标仍使用 noop 行为。

扩展或替换发布适配器时必须：

- 实现新的 `perform_publish_release(payload, artifact, *, timeout_seconds)` 签名；`artifact` 是脱离数据库 Session 的不可变 `PublishArtifact` DTO，不得在适配器中持有或查询 ORM 实体。
- 从 `artifact.files` 读取已按路径排序的 Bundle 文件；文本文件使用 `content_text`，二进制文件使用 `content_base64`。`artifact.content_text` 保留原始 Bundle manifest，供需要原始表示的适配器使用。
- 使用 payload 中稳定的 `idempotency_key=publish_release:{record_id}` 去重。
- 将 `PUBLISH_RELEASE_TIMEOUT_SECONDS` 传递给所有外部 I/O。
- 发生结果不确定时抛出错误，让记录进入 `failed`，由管理员核对外部状态后人工重试。
- 不在 API 确认请求内执行外部发布；所有副作用只允许在 Worker 中发生。

适配器入口示例：

```python
from skillhub.services.publish_release import (
    PublishArtifact,
    PublishReleasePayload,
    PublishReleaseResult,
)


def perform_publish_release(
    payload: PublishReleasePayload,
    artifact: PublishArtifact,
    *,
    timeout_seconds: float = 120,
) -> PublishReleaseResult:
    files = {file.path: file for file in artifact.files}
    skill_markdown = files["SKILL.md"].content_text
    if skill_markdown is None:
        raise RuntimeError("SKILL.md is not a text file.")

    external_id = release_to_target(
        target=payload["publish_target_key"],
        slug=payload["skill_slug"],
        version=payload["version"],
        files=artifact.files,
        idempotency_key=payload["idempotency_key"],
        timeout_seconds=timeout_seconds,
    )
    return {"mode": "released", "external_id": external_id}
```

Worker 在调用适配器前会校验 SkillVersion 的 Artifact 引用、类型、digest 和 Bundle manifest。缺失、损坏或不匹配时不会调用外部适配器，PublishRecord 会进入 `failed` 并记录 `metadata.release_error`。历史 `memory`、`git` 或 `external_repo` ContentRef 不提供回退发布能力。

如果 Opencode 和 Worker 分别运行在不同容器或不同机器上，需要确保：

- `OPENCODE_BASE_URL` 对 Worker 可达。
- `EVAL_WORKDIR_HOST` 对 Worker 可写。
- Opencode 能访问测试运行目录。容器场景下通常需要把宿主机 `EVAL_WORKDIR_HOST` 挂载到 Opencode 容器的 `EVAL_WORKDIR_CONTAINER`。

## 8. Opencode 部署要求

SkillHub 不保存、不配置 provider API key。Opencode 侧需要自行完成 provider/model 配置。

SkillHub 依赖 Opencode 的能力包括：

- 读取 provider/model 列表：`GET {OPENCODE_BASE_URL}/config/providers`
- 创建 session 和发送消息，用于测评运行
- 在测试工作目录中发现项目级 Skill：`workdir/.opencode/skills/<skill_slug>/SKILL.md`

测评运行时，Worker 会把被测 SkillVersion 安装到本次隔离工作区的 `.opencode/skills` 目录中，并只向 Opencode 发送测试例步骤的 `input`。

如果希望在 Laminar 中看到每次 Opencode 会话的 trace，需要在 Opencode 侧启用 Laminar 插件。仅配置 SkillHub Worker 的 `LMNR_PROJECT_API_KEY` 只能写入 Laminar Evaluate 结果，不能自动捕获 Opencode 内部 LLM/tool trace。

Opencode 配置目录中需要安装并启用插件：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": [
    "@lmnr-ai/opencode-plugin"
  ]
}
```

启动 Opencode 的进程还需要具备以下环境变量：

```bash
export LMNR_PROJECT_API_KEY='replace-with-laminar-project-key'
export LMNR_BASE_URL='https://api.lmnr.ai'
# 自托管 Laminar 通常需要显式设置 gRPC 端口，例如 8001。
export LMNR_GRPC_PORT='8443'
```

本地 Docker 运行 Opencode 时，可以使用仓库脚本：

```powershell
.\scripts\start-local-opencode.ps1
```

该脚本会使用 `.data/opencode/config` 作为 Opencode 配置目录，自动注册 `@lmnr-ai/opencode-plugin`，并把 `.env` 中的 `LMNR_PROJECT_API_KEY`、`OPENCODE_LMNR_BASE_URL`、`OPENCODE_LMNR_GRPC_PORT` 传给容器。

## 9. 前端部署

安装依赖并构建：

```bash
cd /opt/skillhub/repo/apps/frontend
npm ci
VITE_SKILLHUB_API_URL='https://skillhub.example.com' npm run build
```

构建产物位于：

```text
apps/frontend/dist/
```

可以用任意静态文件服务托管，例如 Nginx：

```nginx
server {
  listen 443 ssl http2;
  server_name skillhub.example.com;

  root /opt/skillhub/repo/apps/frontend/dist;
  index index.html;

  location / {
    try_files $uri $uri/ /index.html;
  }

  location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }

  location = /health {
    proxy_pass http://127.0.0.1:8000/health;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

如果前端和 API 使用不同域名，需要：

- 前端构建时设置 `VITE_SKILLHUB_API_URL=https://api.example.com`。
- API 设置 `SKILLHUB_CORS_ALLOW_ORIGINS=https://skillhub.example.com`。
- HTTPS 下设置 `SKILLHUB_SESSION_COOKIE_SECURE=1`。

## 10. systemd 示例

API 服务：

```ini
[Unit]
Description=SkillHub API
After=network.target postgresql.service

[Service]
User=skillhub
WorkingDirectory=/opt/skillhub/repo/apps/backend
EnvironmentFile=/opt/skillhub/env/skillhub.env
ExecStart=/usr/bin/env uv run uvicorn skillhub.bootstrap.app:create_app --factory --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Worker 使用 systemd 模板服务，实例名直接作为唯一 Worker ID。文件保存为 `/etc/systemd/system/skillhub-worker@.service`：

```ini
[Unit]
Description=SkillHub Worker
After=network.target skillhub-api.service

[Service]
User=skillhub
WorkingDirectory=/opt/skillhub/repo/apps/backend
EnvironmentFile=/opt/skillhub/env/skillhub.env
Environment=EVAL_RUNNER_WORKER_ID=%i
ExecStart=/usr/bin/env uv run python -m skillhub_worker.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now skillhub-api
sudo systemctl enable --now skillhub-worker@skillhub-worker-1
sudo systemctl enable --now skillhub-worker@skillhub-worker-2
```

查看日志：

```bash
journalctl -u skillhub-api -f
journalctl -u skillhub-worker@skillhub-worker-1 -f
```

API 每个响应都会带 `X-Request-ID`，日志中也会输出同名 `request_id`。临时排查时可在 `skillhub.env` 中设置 `SKILLHUB_LOG_LEVEL=DEBUG`，重启 API 和 Worker 后查看更详细的外部调用、任务认领和执行阶段日志。

后台管理的 “Worker 状态” 页读取 Worker 心跳和 Job 租约：Worker 每轮轮询会写入空闲心跳，认领任务后写入运行中心跳。最近 30 秒内有心跳的实例显示为在线，最近 24 小时内活跃但超过 30 秒无心跳的实例显示为离线。运行中 Job 超过租约阈值未续租时显示为“已阻塞”，管理员应重启对应 Worker；新进程启动后会立即回收过期任务。

Eval Job 过期后会在最大尝试次数内重新排队，达到上限后失败。Publish Job 过期后不会自动重试，发布记录会进入失败态并标记 `external_state=unknown`；管理员必须先核对外部发布目标，再在发布确认页执行“核对后重试”。确认发布接口只负责事务内入队，真实 release 始终由 Worker 执行。

后台的 “Tag Group” 页支持枚举组和自由组。自由组允许用户输入新值，新值会在 Skill 保存事务中写入全局候选；枚举组只接受后台已经维护的值。“Tag 级联” 页可把无父级 Group 挂到某个枚举值下，并显示因重配产生的路径失效或条件必填缺失。相关结构变更由 Alembic revision 应用，已有 Group 保持为非自由顶层组。

级联重配不会批量改写历史 Skill。路径失效的 Tag 仍会显示并参与全文搜索，但不会参与结构化 Tag 筛选或 `skill_tag` 授权；管理员应通过诊断数量跳转到 “Skill Tags” 页逐项修复。仍被 Skill、授权或级联引用的 Group/Tag 值不能删除。

## 11. Docker 镜像部署

项目保留单服务 Dockerfile，但不提供 compose 编排。

构建后端镜像：

```bash
docker build -t skillhub-backend:latest apps/backend
```

先用同一镜像执行一次数据库初始化；多个 API/Worker 容器不得各自执行 migration：

```bash
docker run --rm \
  --env-file /opt/skillhub/env/skillhub.env \
  skillhub-backend:latest \
  python -m skillhub.models.schema.cli upgrade

docker run --rm \
  --env-file /opt/skillhub/env/skillhub.env \
  skillhub-backend:latest \
  python -m skillhub.models.schema.cli check
```

运行 API：

```bash
docker run -d \
  --name skillhub-api \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file /opt/skillhub/env/skillhub.env \
  skillhub-backend:latest
```

运行 Worker 可复用同一个镜像并覆盖命令：

```bash
docker run -d \
  --name skillhub-worker-1 \
  --restart unless-stopped \
  --env-file /opt/skillhub/env/skillhub.env \
  -e EVAL_RUNNER_WORKER_ID='skillhub-worker-1' \
  -e EVAL_WORKDIR_HOST='/var/lib/skillhub/eval-runs' \
  -v /var/lib/skillhub/eval-runs:/var/lib/skillhub/eval-runs \
  skillhub-backend:latest \
  python -m skillhub_worker.main
```

增加 Worker 时复制该容器并修改容器名与 `EVAL_RUNNER_WORKER_ID`。如果 `OPENCODE_BASE_URL` 使用 `http://opencode:4096`，API、Worker 和 Opencode 必须加入同一个 Docker network；执行测评时 Opencode 容器还必须以一致路径挂载 Worker 工作目录。

构建前端镜像：

```bash
docker build -t skillhub-frontend:latest apps/frontend
```

前端 Dockerfile 当前在镜像构建阶段执行 `npm run build`。如果需要注入生产 API 地址，应在构建环境中传入 Vite 变量，或改造 Dockerfile 支持 `ARG VITE_SKILLHUB_API_URL` 后再构建。

## 12. 发布和升级流程

API、Worker 和 Web 必须协调发布，不支持新旧版本混跑。推荐升级步骤：

1. 记录当前 Git commit。
2. 从负载均衡摘除并停止所有旧 API，停止全部 Worker，避免升级时继续写入或消费任务。
3. 备份 PostgreSQL，并验证备份文件可读取。
4. 拉取同一个 Git commit 的代码或镜像，安装后端依赖并构建前端。
5. 只运行一次 `uv run python -m skillhub.models.schema.cli upgrade`。
6. 执行 `uv run python -m skillhub.models.schema.cli check` 和 `uv run alembic check`。
7. 启动新版 API，确认 `/health` 和 `/api/skills` 正常后再恢复流量。
8. 启动所有新版 Worker，在后台确认每个唯一 Worker ID 在线。
9. 部署前端，执行 Skill 创建、测评入队和后台查询冒烟检查。

备份示例：

```bash
pg_dump --format=custom --file=skillhub-$(date +%Y%m%d%H%M%S).dump skillhub
```

恢复示例：

```bash
createdb skillhub_restore
pg_restore --dbname=skillhub_restore skillhub-20260101010101.dump
```

## 13. 部署后验证

基础检查：

```bash
curl -f https://skillhub.example.com/health
curl -f https://skillhub.example.com/api/skills
curl -f https://skillhub.example.com/api/tag-groups
cd /opt/skillhub/repo/apps/backend
uv run python -m skillhub.models.schema.cli check
```

前端检查：

- 打开 `/skills`，确认 Skill 列表能加载。
- 进入 `/skills/admin`，输入 `SKILLHUB_ADMIN_CONSOLE_KEY`，确认后台可访问。
- 在后台 Worker 状态页确认所有预期实例在线、ID 不重复且没有 `stalled` 告警。
- 创建或导入一个 Skill，确认数据库写入正常。
- 如果启用测评，创建测试例并运行一次，确认 Worker 和 Opencode 能完成任务。
- 确认发布后应先看到 `queued/releasing`，再由 Worker 进入 `released/failed`；HTTP 请求本身不执行外部发布。
- 如果配置 Laminar，检查运行详情中是否出现 trace 信息。

## 14. 安全建议

- 生产环境必须修改 `SKILLHUB_SESSION_SECRET`、`SKILLHUB_ADMIN_CONSOLE_KEY` 和 `SKILLHUB_LOCAL_SESSION_CODE`。
- 只通过 HTTPS 暴露前端和 API。
- HTTPS 下设置 `SKILLHUB_SESSION_COOKIE_SECURE=1`。
- 不要把 `.env`、`skillhub.env`、数据库 dump 或 Opencode provider key 提交到 Git。
- 后台密钥只用于 `/skills/admin` 和 `/api/admin/*`，不等同于普通 user/group 角色。
- PostgreSQL 账号只授予 SkillHub 所需数据库权限。
- Worker 工作目录应限制在专用目录，不要与系统敏感目录共用。

## 15. 常见问题

### 前端提示 CORS 错误

检查：

- `VITE_SKILLHUB_API_URL` 是否指向真实 API 地址。
- API 的 `SKILLHUB_CORS_ALLOW_ORIGINS` 是否包含前端 Origin。
- 反向代理是否正确转发 `/api/`。

### `/skills/admin` 显示无权限或后台接口 403

检查：

- API 是否设置了 `SKILLHUB_ADMIN_CONSOLE_KEY`。
- 前端输入的后台密钥是否与环境变量完全一致。
- 浏览器 sessionStorage 中的 `skillhub.admin.key` 是否是旧值。

### 测评长时间处于 queued

通常是 Worker 未运行或无法连接数据库。检查：

```bash
journalctl -u skillhub-worker@skillhub-worker-1 -f
```

并确认 `SKILLHUB_DATABASE_URL` 与 API 使用同一个数据库。

### 测评长时间处于 running

通常是 Worker 等待 Opencode 返回。检查：

- `OPENCODE_BASE_URL` 是否可从 Worker 访问。
- Opencode provider/model 是否已在 Opencode 侧配置。
- `EVAL_WORKDIR_HOST` 是否可写。
- Opencode 是否能访问 Worker 物化出的测试工作目录。

如果后台 Worker 状态页显示 `stalled`，记录 `worker_id`、Job ID、attempt 和租约年龄后重启对应 Worker。新进程会在启动时回收过期 Eval Job；不要直接在数据库中手工修改 Job 状态。

### 发布长时间处于 queued 或 releasing

- `queued` 通常表示没有可用 Worker，检查所有 Worker 是否在线以及 ID 是否重复。
- `releasing` 且 Worker 显示 `stalled` 时，重启对应 Worker 触发租约回收。
- Publish 租约过期会进入 `failed` 并标记 `external_state=unknown`，系统不会自动重试。
- 管理员必须先核对外部发布目标，再使用“核对后重试”；不要在外部状态未知时连续点击重试。

### AI 创建 Skill 长时间处于 running

Skill Builder 会话超过 `SKILL_BUILDER_STALE_AFTER_SECONDS` 无进展后，后端会在下次读取或操作该会话时自动标记为失败态。失败态会保留当前对话和工作区，用户可以继续发送消息、取消本次运行或新建会话。若频繁触发，请检查 Worker 日志、`OPENCODE_BASE_URL`、Opencode provider/model 配置和 `EVAL_RUNNER_TIMEOUT_SECONDS`。

### 运行详情没有 Laminar trace

Laminar 是可选能力。检查：

- 是否设置 `LMNR_PROJECT_API_KEY`。
- 如果只看到 Laminar Evaluate 结果、看不到每次 Opencode 运行的 trace，说明 SkillHub Worker 已写入测评结果，但 Opencode 侧 trace 插件没有生效。
- Opencode 配置中是否安装并启用了 `@lmnr-ai/opencode-plugin`。
- 启动 Opencode 的进程是否带有 `LMNR_PROJECT_API_KEY`、`LMNR_BASE_URL` 和自托管所需的 `LMNR_GRPC_PORT`。
- 容器化 Opencode 访问本机 Laminar 时，`LMNR_BASE_URL` 通常不能写 `localhost`，应使用 `host.docker.internal` 或可路由地址。
- Worker 日志中是否有 Laminar Evaluate 创建/更新错误。
- Opencode 日志中是否出现 `Laminar tracing initialized`。

### API 启动时报数据库错误

检查：

- `SKILLHUB_DATABASE_URL` 是否以 `postgresql://` 或 `postgresql+psycopg://` 开头。
- 是否已经执行 `uv run python -m skillhub.models.schema.cli upgrade`。
- `alembic_version` 是否处于当前 head。
- 执行 migration 的数据库用户是否有建表和修改约束权限。
- PostgreSQL 网络和防火墙是否允许 API 访问。

## 16. 本地联调脚本

本地开发或单机联调可使用脚本启动：

Windows PowerShell：

```powershell
.\scripts\start-local-services.ps1
.\scripts\start-local-opencode.ps1
```

Linux 或 macOS：

```bash
bash scripts/dev.sh
bash scripts/worker.sh local-worker-1
```

使用 `just` 时必须显式传入 Worker ID：`just worker local-worker-1`。

这些脚本面向本地联调，不替代生产进程管理。生产部署应使用 systemd、容器平台或其他运维系统托管进程。
