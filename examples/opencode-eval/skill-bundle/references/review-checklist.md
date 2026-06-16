# Review Checklist

- 查询列表接口是否绑定当前用户或租户。
- Repository 方法是否接受并使用 owner/tenant 参数。
- Service 是否从认证上下文中读取 owner/tenant 并向下传递。
- 测试是否覆盖“不能读取他人数据”的负向用例。

