# 漏洞与组件关联 API

阶段 6 提供 `/api/v1/associations` 接口，用于维护 CVE 与组件之间的已确认关系。所有读取接口要求登录，建立和解除关联仅允许超级管理员。

## 接口

- `GET /associations/`：分页查询关联，可通过 `vulnerability_id` 或 `component_id` 筛选。响应同时包含 CVE 编号、严重等级、组件名称和 PURL，便于双向详情展示。
- `GET /associations/suggestions?vulnerability_id=...`：按组件 CPE 特征、名称和厂商与漏洞标题、描述等文本进行本地匹配。只返回建议，不自动写入关联。
- `POST /associations/`：人工确认并建立关联。请求包含两个资源 UUID，可选影响版本范围、来源说明、备注及匹配方式。
- `DELETE /associations/{association_id}`：解除关联。

## 业务规则

- 同一个 CVE 与组件只能存在一条关联，重复建立返回 HTTP 409。
- 建立的关联状态为 `CONFIRMED`，并记录确认用户。
- 建立和解除操作分别写入 `LINK`、`UNLINK` 审计日志。
- 删除 CVE 或组件时，数据库通过外键级联清理关联。
- 建议算法只使用当前数据库，不调用外部漏洞服务，也不执行项目依赖扫描；建议必须由管理员确认。
