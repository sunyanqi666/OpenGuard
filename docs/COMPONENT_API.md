# 组件 REST API

所有组件接口位于 `/api/v1/components`，并要求 Bearer Token。Swagger 地址为 `http://localhost:8000/docs`。

## 权限

| 操作 | 登录用户 | 超级管理员 |
| --- | --- | --- |
| 列表、筛选、详情 | 允许 | 允许 |
| 新增、修改、删除 | 禁止（403） | 允许 |

## 列表和筛选

`GET /api/v1/components/`

| 参数 | 说明 |
| --- | --- |
| `skip` | 跳过数量，默认 0 |
| `limit` | 每页数量，默认 50，范围 1–200 |
| `search` | 在 PURL、名称、厂商和描述中模糊检索 |
| `ecosystem` | 生态类型，不区分大小写，如 `maven`、`npm` |
| `language` | 编程语言，不区分大小写 |
| `vendor` | 厂商，不区分大小写 |

响应包含 `data` 和筛选后的 `count`，默认按名称、PURL 升序排列。

## 详情

`GET /api/v1/components/{uuid}`

返回完整组件字段；记录不存在时返回 404。

## 新增

`POST /api/v1/components/`

- `purl` 和 `name` 必填。
- PURL 必须以 `pkg:` 开头并包含包路径。
- 名称不能只包含空格，保存前会去除首尾空格。
- 仓库地址如果提供，必须是 HTTP 或 HTTPS URL。
- `version` 允许为空，以兼容教师原始数据。
- 创建成功返回 201 并写入审计日志。
- PURL 已存在时返回 409。

示例：

```json
{
  "purl": "pkg:maven/org.example/demo@1.0.0",
  "ecosystem": "maven",
  "vendor": "org.example",
  "name": "demo",
  "version": "1.0.0",
  "language": "java",
  "repository": "https://github.com/example/demo"
}
```

## 修改

`PATCH /api/v1/components/{uuid}`

- 只传需要修改的字段。
- PURL 可以修改，但不能与其他组件重复。
- PURL 和名称不能置为 NULL。
- 实际变化会更新 `updated_at` 并记录 before/after 审计信息。
- 空请求或内容未变化时不生成审计日志。

## 删除

`DELETE /api/v1/components/{uuid}`

- 删除组件及其漏洞关联和处置记录。
- 删除审计日志会继续保留。
- 前端调用前必须提供二次确认。

## 状态码

| 状态码 | 含义 |
| ---: | --- |
| 200 | 查询、修改或删除成功 |
| 201 | 创建成功 |
| 401 | 未提供登录令牌 |
| 403 | 权限不足或令牌无效 |
| 404 | 组件不存在 |
| 409 | PURL 与已有组件冲突 |
| 422 | 请求参数或字段校验失败 |
