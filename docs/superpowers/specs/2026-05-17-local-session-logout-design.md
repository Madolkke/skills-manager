# 本地 Session 退出控制设计

日期：2026-05-17

## 背景

SkillHub 当前已经把本地 actor 从自由切换升级为需要本地登录码的 HttpOnly cookie session。后端也已经提供 `DELETE /api/session` 清除 `skillhub_actor` cookie。但前端 `Local login` 面板只有“登录 actor”，没有“退出/清除当前 session”的入口。

这会造成两个成熟度问题：

1. 用户可以进入某个维护者身份，却没有明显方式回到默认身份。
2. 权限调试时，用户容易误以为已经回到默认 actor，实际 cookie 仍然生效。

本轮只补本地 session 的退出控制；不引入真实 OAuth/OIDC，不移除 `X-SkillHub-Actor` 自动化 fallback。

## 借鉴实践

- OWASP Session Management 建议服务端提供可终止 session 的机制，清除 session 后不应继续使用旧身份。
- GitHub / GitLab / Linear 这类协作产品都会把账号切换和退出作为 session 级动作，而不是隐藏在业务表单里。

SkillHub 的适配：

- `Local login` 面板显示当前 actor，并提供 `退出登录` 按钮。
- 点击后调用已有 `DELETE /api/session`，后端清除 cookie，响应默认 actor `product-operator`。
- 前端收到响应后刷新 actor、skill 列表和当前 skill capabilities，避免受保护动作状态滞后。

## 方案

### API

复用现有接口：

```http
DELETE /api/session
```

响应：

```json
{
  "actor": "product-operator",
  "subject_type": "user"
}
```

### 前端

- `LocalSessionPanel` 新增 `onClearSession` prop。
- 登录表单下方按钮区改为两个按钮：
  - 主按钮：`登录 actor`
  - 次按钮：`退出登录`
- 当前 actor 已经是 `product-operator` 时，`退出登录` disabled，并给出 title：`当前已经是默认 actor。`
- `DecisionWorkbench.clearSession` 调用 `DELETE /api/session`，设置返回的 actor，并复用 `runCommand` 的 `loadSkills` 刷新 capabilities。

## 成功标准

1. E2E 中先登录 `release-manager`，面板显示 `release-manager`。
2. 点击 `退出登录` 后，面板回到 `product-operator`。
3. 退出后再导入 skill，新 skill 的 owner 是 `product-operator`。
4. 默认 actor 状态下，`退出登录` 按钮 disabled。
5. Local session 视觉基线更新为包含双按钮的状态。
6. 全量 API、Web unit、typecheck、build、audit、E2E、diff check 和任务 JSON 检查通过。

## 非目标

- 不做真实认证。
- 不做 token rotation。
- 不移除直接 API 的 `X-SkillHub-Actor` fallback。
- 不新增用户目录、组织级 identity store 或邀请流程。
