# CVE REST API

所有 CVE 接口都位于 `/api/v1/vulnerabilities`，并要求 Bearer Token。交互式文档可在 `http://localhost:8000/docs` 查看。

## 权限

| 操作 | 登录用户 | 超级管理员 |
| --- | --- | --- |
| 列表、筛选、详情 | 允许 | 允许 |
| 新增 | 禁止（403） | 允许（扩展功能） |
| 修改 | 禁止（403） | 允许 |
| 删除 | 禁止（403） | 允许 |

## 新增（扩展功能）

`POST /api/v1/vulnerabilities/`

作业基础要求不包含 CVE 新增，本接口作为管理员扩展能力提供。`cve_id` 必须符合 `CVE-YYYY-NNNN` 格式且全局唯一；重复编号返回 409。创建成功返回 201，并记录 CREATE 审计日志。教师批量数据仍应使用幂等导入程序维护。

## 列表和筛选

`GET /api/v1/vulnerabilities/`

| 参数 | 说明 |
| --- | --- |
| `skip` | 跳过数量，默认 0 |
| `limit` | 每页数量，默认 50，范围 1–200 |
| `search` | 在 CVE ID、标题和描述中模糊检索 |
| `severity` | `CRITICAL/HIGH/MEDIUM/LOW/UNKNOWN` |
| `source_name` | 来源名称，不区分大小写 |
| `min_cvss` / `max_cvss` | 有效 CVSS 范围，优先使用 v4、其次 v3、最后 v2 |
| `published_from` / `published_to` | ISO 8601 发布时间范围 |

响应包含 `data` 和筛选后的 `count`。默认按发布时间倒序、CVE ID 倒序排列。最小值大于最大值时返回 422。

## 详情

`GET /api/v1/vulnerabilities/{uuid}`

返回完整 CVE 字段；记录不存在时返回 404。

## 修改

`PATCH /api/v1/vulnerabilities/{uuid}`

- 只传需要修改的字段。
- `cve_id` 不允许修改。
- CVSS 必须在 0–10。
- 严重等级必须使用约定枚举且不能置空。
- 实际发生变化时更新 `updated_at`，并写入包含 before/after 的审计日志。
- 空请求或内容未变化时不写入无意义审计日志。

示例：

```json
{
  "severity": "CRITICAL",
  "cvss_score_v3": 9.8,
  "title": "更新后的标题"
}
```

## 删除

`DELETE /api/v1/vulnerabilities/{uuid}`

- 删除漏洞及其组件关联和处置记录。
- 保留一条不依赖漏洞外键的删除审计日志。
- 前端仍须在调用接口前进行二次确认。

## 状态码

| 状态码 | 含义 |
| ---: | --- |
| 200 | 查询、修改或删除成功 |
| 201 | CVE 创建成功 |
| 401 | 未提供登录令牌 |
| 403 | 登录用户权限不足或令牌无效 |
| 404 | CVE 不存在 |
| 409 | CVE 编号已存在 |
| 422 | 参数、枚举、范围或请求体校验失败 |
