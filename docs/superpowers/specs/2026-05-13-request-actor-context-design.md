# 请求级 ActorContext 设计

日期：2026-05-13

## 背景

SkillHub 已经有 skill 作用域 `owner` / `maintainer` / `evaluator` / `viewer` 和受保护动作门禁，但当前 mutation payload 里仍有 `actor` 字段。这样会让权限判断和审计来源混在业务输入里：前端可以把任意 actor 放进 body，后端如果直接信任，就无法证明“谁在执行动作”。

本轮不接入 OAuth、OIDC 或真实登录，只做一个可替换的请求级身份边界：后端从统一请求上下文读取 actor，mutation body 不再承载 actor。正式认证接入时，只需要替换这个 dependency，而不是逐个改业务命令。

## 外部实践

- OWASP REST Security 要求非公开 REST endpoint 在每次请求里做 access control，并建议 user authentication 集中在身份提供方、endpoint 本地做授权判断。适配到 SkillHub：权限判断应依赖 request context 中的 actor，而不是业务 payload。来源：<https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html>
- OWASP Authorization Cheat Sheet 强调 deny by default 和 every-request permission validation。适配到 SkillHub：受保护命令必须从统一 actor context 取身份，并继续在 repository 里按 skill scope 检查角色。来源：<https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html>
- GitHub REST API 把认证信息放在 HTTP `Authorization` header，而不是每个 JSON body。适配到 SkillHub：本地开发先用 `X-SkillHub-Actor` header 模拟用户身份，后续可替换为 Bearer token/session。来源：<https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api>
- Next.js Authentication 文档提醒 authorization checks 不能只靠客户端 UI，server actions / mutation 也必须自己检查。适配到 SkillHub：前端只负责发送当前本地身份 header，后端仍然做角色检查。来源：<https://nextjs.org/docs/app/guides/authentication>

## 方案比较

### 方案 A：保留 body actor，只补文档说明

改动最小，但权限模型没有实质进步。用户、E2E 或第三方 runner 仍然可以在 body 中伪造 actor。淘汰。

### 方案 B：引入 `X-SkillHub-Actor` 开发 header

后端新增 `ActorContext` dependency，从 `X-SkillHub-Actor` 读取当前 actor；如果缺失，使用本地默认 actor `product-operator`，方便一键启动和老脚本。所有 mutation endpoint 忽略 body 中的 actor。正式登录接入时替换 dependency 即可。推荐。

### 方案 C：一步到位接 OAuth/OIDC

方向正确，但超出当前单任务范围，会牵涉用户表、session/cookie、登录页、token rotation、退出登录和部署密钥。先不做。

## 本轮设计

采用方案 B。

新增 `apps/api/skillhub/api/auth.py`：

- `ActorContext`：包含 `id` 和 `subject_type`。
- `actor_dependency`：读取 `X-SkillHub-Actor`，去空格，空字符串报错；缺失时回退到 `product-operator`。
- `ACTOR_HEADER` 和 `DEFAULT_LOCAL_ACTOR` 常量，便于测试和文档引用。

API 层变化：

- 所有会写入 `created_by`、`actor_ref` 或触发权限检查的 mutation endpoint 都通过 `Depends(actor_dependency)` 获取 actor。
- Payload schema 保留业务字段，但不再定义 `actor`。如果旧调用继续传 `actor`，Pydantic 会忽略，后端以 header 为准。
- `DELETE /api/role-assignments/{id}` 不再通过 query string 传 actor。

前端变化：

- `apiSend` 统一加入 `X-SkillHub-Actor: product-operator`。
- 所有 mutation body 删除 `actor: ACTOR`，避免继续暗示 body actor 是可信输入。
- `SkillAccessPanel` 仍显示当前本地 actor，但文案改成“本地开发身份”。

测试策略：

- API 红绿测试证明：header actor 创建 skill 后成为 owner，即使 body 里伪造 actor 也无效。
- API 红绿测试证明：受保护动作只看 header actor；body 里伪造 owner 不会绕过 viewer 权限。
- 更新已有权限测试：viewer/maintainer 操作通过 per-request header 表达身份。
- E2E 继续覆盖工作台创建/导入/角色管理；前端请求 body 不再包含 actor。

## 非目标

- 不做登录页、cookie session、JWT 校验、OAuth/OIDC、SSO。
- 不新增 user/org 表。
- 不在本轮把所有写操作都加角色门禁；本轮只把 actor 来源收敛。
- 不改 repository 方法签名，repository 仍接收显式 actor，便于单元测试和未来 worker 调用。
