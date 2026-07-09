# SkillHub 部署指南

本文档说明如何把 SkillHub 部署到一台或多台服务器上。当前项目不保留 compose 部署方式，推荐由运维系统分别管理 PostgreSQL、后端 API、前端静态站点、Worker、Opencode 和可选的 Laminar。

## 1. 部署组件

SkillHub 由以下组件组成：

| 组件 | 目录或服务 | 必需 | 说明 |
| --- | --- | --- | --- |
| 后端 API | `apps/backend` | 是 | FastAPI 服务，启动入口为 `skillhub.bootstrap.app:create_app`。 |
| 前端 | `apps/frontend` | 是 | Vue + Vite 构建出的静态站点。 |
| PostgreSQL | 外部数据库 | 是 | Skill、版本、测评、评审、发布、权限和 artifact 元数据的事实源。 |
| Worker | `apps/backend/skillhub_worker` | 测评需要 | 消费测评任务，调用 Opencode 执行测试例。 |
| Opencode | 外部服务 | 测评需要 | SkillHub 不管理 provider key，只读取其 provider/model 配置并调用运行接口。 |
| Laminar | 外部服务 | 可选 | 用于记录测评 trace。未配置时不阻断测评。 |

## 2. 前置要求

建议生产或准生产环境使用：

- Python `3.12+`
- `uv`
- Node.js `24+`
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

部署用户需要对 `/var/lib/skillhub/eval-runs` 有读写权限。

## 4. 环境变量

### 必填配置

| 变量 | 作用 | 示例 |
| --- | --- | --- |
| `SKILLHUB_DATABASE_URL` | PostgreSQL 连接串 | `postgresql+psycopg://skillhub:***@db:5432/skillhub` |
| `SKILLHUB_SESSION_SECRET` | 签名本地 actor cookie | 使用 32 字节以上随机值 |
| `SKILLHUB_ADMIN_CONSOLE_KEY` | `/skills/admin` 和 `/api/admin/*` 后台密钥 | 使用高强度随机值 |

### 常用配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SKILLHUB_LOCAL_SESSION_CODE` | `skillhub-dev` | 前端切换本地身份时使用的访问码，生产环境必须修改。 |
| `SKILLHUB_SESSION_COOKIE_SECURE` | 未启用 | HTTPS 部署时设为 `1`。 |
| `SKILLHUB_CORS_ALLOW_ORIGINS` | 空 | 明确允许的前端 Origin，多个值用逗号分隔。 |
| `SKILLHUB_CORS_ALLOW_ORIGIN_REGEX` | 允许 localhost、IP 和常见主机名 | 自定义跨域匹配规则。 |
| `SKILLHUB_LOG_LEVEL` | `INFO` | 后端 API 和 Worker 日志级别；排查问题时可临时设为 `DEBUG`。 |
| `OPENCODE_BASE_URL` | 后端默认 `http://127.0.0.1:4096`，Worker 默认 `http://opencode:4096` | Opencode 服务地址。 |
| `EVAL_WORKDIR_HOST` | Worker 默认 `/var/lib/skillhub/eval-runs` | Worker 在宿主机上的测评工作目录。 |
| `EVAL_WORKDIR_CONTAINER` | `/workspace/eval-runs` | 传给容器化 Opencode 时使用的容器内路径。 |
| `EVAL_RUNNER_POLL_SECONDS` | `2` | Worker 轮询任务间隔。 |
| `EVAL_RUNNER_TIMEOUT_SECONDS` | `300` | Worker 默认运行超时。 |
| `EVAL_RUNNER_MAX_ATTEMPTS` | `2` | 测评任务最大尝试次数。 |
| `EVAL_RUNNER_WORKER_ID` | `opencode-worker` | Worker 实例标识；多实例部署时必须为每个 Worker 设置不同值，后台 Worker 状态页依赖该值聚合心跳。 |
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
| `VITE_WORKFLOW_APP_URL` | 可选的外部 Workflow 页面地址。 |

生产建议优先配置 `VITE_SKILLHUB_API_URL`，避免前端在反向代理或多域名场景下拼错 API 地址。

## 5. 数据库准备

创建数据库和用户：

```sql
CREATE USER skillhub WITH PASSWORD 'change-me';
CREATE DATABASE skillhub OWNER skillhub;
GRANT ALL PRIVILEGES ON DATABASE skillhub TO skillhub;
```

SkillHub 启动时会通过 schema sync 创建和调整当前表结构。当前项目仍处于开发阶段，没有独立 Alembic migration 流程；升级前必须先备份数据库。

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

健康检查可以使用：

```bash
curl -f http://127.0.0.1:8000/api/skills
```

该接口公开可读，正常情况下应返回 JSON 数组。

## 7. Worker 部署

Worker 与 API 使用同一个后端代码目录和同一个数据库连接串。

```bash
cd /opt/skillhub/repo/apps/backend

export SKILLHUB_DATABASE_URL='postgresql+psycopg://skillhub:change-me@127.0.0.1:5432/skillhub'
export OPENCODE_BASE_URL='http://127.0.0.1:4096'
export EVAL_WORKDIR_HOST='/var/lib/skillhub/eval-runs'
export EVAL_WORKDIR_CONTAINER='/workspace/eval-runs'
export EVAL_RUNNER_WORKER_ID='skillhub-worker-1'

uv run python -m skillhub_worker.main
```

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

Worker 服务：

```ini
[Unit]
Description=SkillHub Worker
After=network.target skillhub-api.service

[Service]
User=skillhub
WorkingDirectory=/opt/skillhub/repo/apps/backend
EnvironmentFile=/opt/skillhub/env/skillhub.env
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
sudo systemctl enable --now skillhub-worker
```

查看日志：

```bash
journalctl -u skillhub-api -f
journalctl -u skillhub-worker -f
```

API 每个响应都会带 `X-Request-ID`，日志中也会输出同名 `request_id`。临时排查时可在 `skillhub.env` 中设置 `SKILLHUB_LOG_LEVEL=DEBUG`，重启 API 和 Worker 后查看更详细的外部调用、任务认领和执行阶段日志。

后台管理的 “Worker 状态” 页读取 Worker 心跳：Worker 每轮轮询会写入空闲心跳，认领测评或 AI 创建任务后写入运行中心跳。最近 30 秒内有心跳的实例显示为在线，最近 24 小时内活跃但超过 30 秒无心跳的实例显示为离线。

## 11. Docker 镜像部署

项目保留单服务 Dockerfile，但不提供 compose 编排。

构建后端镜像：

```bash
docker build -t skillhub-backend:latest apps/backend
```

运行 API：

```bash
docker run --rm \
  -p 8000:8000 \
  -e SKILLHUB_DATABASE_URL='postgresql+psycopg://skillhub:change-me@db:5432/skillhub' \
  -e SKILLHUB_SESSION_SECRET='replace-with-random-secret' \
  -e SKILLHUB_ADMIN_CONSOLE_KEY='replace-with-random-admin-key' \
  -e SKILLHUB_LOCAL_SESSION_CODE='replace-with-random-session-code' \
  -e OPENCODE_BASE_URL='http://opencode:4096' \
  skillhub-backend:latest
```

运行 Worker 可复用同一个镜像并覆盖命令：

```bash
docker run --rm \
  -e SKILLHUB_DATABASE_URL='postgresql+psycopg://skillhub:change-me@db:5432/skillhub' \
  -e OPENCODE_BASE_URL='http://opencode:4096' \
  -e EVAL_WORKDIR_HOST='/var/lib/skillhub/eval-runs' \
  -v /var/lib/skillhub/eval-runs:/var/lib/skillhub/eval-runs \
  skillhub-backend:latest \
  python -m skillhub_worker.main
```

构建前端镜像：

```bash
docker build -t skillhub-frontend:latest apps/frontend
```

前端 Dockerfile 当前在镜像构建阶段执行 `npm run build`。如果需要注入生产 API 地址，应在构建环境中传入 Vite 变量，或改造 Dockerfile 支持 `ARG VITE_SKILLHUB_API_URL` 后再构建。

## 12. 发布和升级流程

推荐升级步骤：

1. 记录当前 Git commit。
2. 停止 Worker，避免升级过程中继续消费测评任务。
3. 备份 PostgreSQL。
4. 拉取新代码并安装依赖。
5. 构建前端。
6. 重启 API，等待 schema sync 完成。
7. 验证核心 API。
8. 重启 Worker。
9. 打开前端做一次冒烟检查。

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
curl -f https://skillhub.example.com/api/skills
curl -f https://skillhub.example.com/api/tag-groups
```

前端检查：

- 打开 `/skills`，确认 Skill 列表能加载。
- 进入 `/skills/admin`，输入 `SKILLHUB_ADMIN_CONSOLE_KEY`，确认后台可访问。
- 创建或导入一个 Skill，确认数据库写入正常。
- 如果启用测评，创建测试例并运行一次，确认 Worker 和 Opencode 能完成任务。
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
journalctl -u skillhub-worker -f
```

并确认 `SKILLHUB_DATABASE_URL` 与 API 使用同一个数据库。

### 测评长时间处于 running

通常是 Worker 等待 Opencode 返回。检查：

- `OPENCODE_BASE_URL` 是否可从 Worker 访问。
- Opencode provider/model 是否已在 Opencode 侧配置。
- `EVAL_WORKDIR_HOST` 是否可写。
- Opencode 是否能访问 Worker 物化出的测试工作目录。

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
- 数据库用户是否有建表和更新 schema 权限。
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
bash scripts/worker.sh
```

这些脚本面向本地联调，不替代生产进程管理。生产部署应使用 systemd、容器平台或其他运维系统托管进程。
