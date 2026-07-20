set dotenv-load
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

host := env_var_or_default("SKILLHUB_HOST", "127.0.0.1")
api_port := env_var_or_default("SKILLHUB_API_PORT", "8000")
web_port := env_var_or_default("SKILLHUB_WEB_PORT", "3030")

export VITE_SKILLHUB_API_PORT := env_var_or_default("VITE_SKILLHUB_API_PORT", api_port)
export VITE_OPENCODE_RUN_POLL_INTERVAL_MS := env_var_or_default("VITE_OPENCODE_RUN_POLL_INTERVAL_MS", "5000")
export SKILLHUB_REQUIRE_POSTGRES_TESTS := env_var_or_default("SKILLHUB_REQUIRE_POSTGRES_TESTS", "1")

dev_command := if os() == "windows" { "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-local-services.ps1" } else { "bash scripts/dev.sh" }
dev_no_worker_command := if os() == "windows" { "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/start-local-services.ps1 -SkipWorker" } else { "bash scripts/dev.sh" }
worker_command := if os() == "windows" { "powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/worker.ps1 -WorkerId" } else { "bash scripts/worker.sh" }

# 列出所有可用命令
default:
    @just --list

# 安装后端和前端依赖
setup: backend-install frontend-install

# 按锁文件安装后端开发依赖
backend-install:
    uv --directory apps/backend sync --locked --all-groups

# 按锁文件安装前端依赖
frontend-install:
    npm --prefix apps/frontend ci

# 启动本地 API、Web 和 Worker；Unix 下需另行运行 just worker
dev:
    {{ dev_command }}

# 启动本地 API 和 Web，不启动 Worker
dev-no-worker:
    {{ dev_no_worker_command }}

# 在前台启动 API
api:
    uv --directory apps/backend run uvicorn skillhub.bootstrap.app:create_app --factory --host {{ host }} --port {{ api_port }}

# 在前台启动 Web
web:
    npm --prefix apps/frontend run dev -- --host {{ host }} --port {{ web_port }}

# 在前台启动指定 ID 的 Worker
worker worker_id:
    {{ worker_command }} {{ if os() == "windows" { "'" + replace(worker_id, "'", "''") + "'" } else { quote(worker_id) } }}

# 升级 .env 指向的数据库到 Alembic head
db-upgrade:
    uv --directory apps/backend run python -m skillhub.models.schema.cli upgrade

# 检查数据库 revision 是否为 Alembic head
db-revision-check:
    uv --directory apps/backend run python -m skillhub.models.schema.cli check

# 检查 ORM metadata 与 Alembic migration 是否存在漂移
db-drift-check:
    uv --directory apps/backend run alembic check

# 执行全部数据库结构检查
db-check: db-revision-check db-drift-check

# 编译检查后端 Python 模块
backend-compile:
    uv --directory apps/backend run python -m compileall -q skillhub skillhub_worker

# 检查后端代码风格
backend-lint:
    uv --directory apps/backend run ruff check skillhub skillhub_worker tests

# 检查 ORM schema 类型
backend-typecheck:
    uv --directory apps/backend run mypy skillhub/models/schema

# 运行后端测试；PostgreSQL 不可用时失败
backend-test:
    uv --directory apps/backend run pytest

# 检查前端代码风格
frontend-lint:
    npm --prefix apps/frontend run lint

# 运行前端测试
frontend-test:
    npm --prefix apps/frontend run test

# 检查类型并构建前端
frontend-build:
    npm --prefix apps/frontend run build

# 执行前后端代码风格检查
lint: backend-lint frontend-lint

# 执行前后端测试
test: backend-test frontend-test

# 执行后端编译检查和前端构建
build: backend-compile frontend-build

# 执行全部本地质量门禁
check: backend-compile backend-lint backend-typecheck backend-test frontend-lint frontend-test frontend-build

# 升级数据库并执行与 CI 等价的全部检查
ci: db-upgrade db-check check
