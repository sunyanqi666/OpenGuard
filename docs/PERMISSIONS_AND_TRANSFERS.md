# 角色权限、审计与 CSV 导入导出

本文档对应阶段 8，说明三级角色、审计查询和 CSV 数据交换规则。

## 1. 角色权限

| 功能 | 管理员 `ADMIN` | 安全人员 `SECURITY` | 观察者 `VIEWER` |
| --- | --- | --- | --- |
| 查看仪表盘、CVE、组件及关联 | 允许 | 允许 | 允许 |
| 修改、删除 CVE | 允许 | 不允许 | 不允许 |
| 新增、修改、删除组件 | 允许 | 不允许 | 不允许 |
| 建立或解除 CVE—组件关联 | 允许 | 允许 | 不允许 |
| 新增、修改、删除处置记录 | 允许 | 允许 | 不允许 |
| 查看审计日志 | 允许 | 允许 | 不允许 |
| CSV 导入组件 | 允许 | 不允许 | 不允许 |
| CSV 导出业务数据 | 允许 | 允许 | 允许 |
| 用户管理 | 允许 | 不允许 | 不允许 |

前端根据角色隐藏无权操作的菜单和按钮，后端仍会独立校验权限。直接构造越权请求时，接口返回 HTTP 403；登录失效或用户不存在时返回 HTTP 401。

## 2. 审计日志

接口：`GET /api/v1/audit-logs/`

管理员和安全人员可按操作类型、资源类型、操作者和时间范围筛选。列表包含操作时间、操作者邮箱、操作、资源、摘要和变更详情。新增、修改、删除、关联、解除关联和处置状态变化均可追溯。

## 3. 组件 CSV 导入

接口：`POST /api/v1/transfers/components/import`

仅管理员可导入 UTF-8 CSV。首行必须包含：

- `purl`：必填，且以 `pkg:` 开头；作为组件唯一业务键。
- `name`：必填，不能为空白。

可选列：`cpe`、`ecosystem`、`vendor`、`version`、`license`、`description`、`repository`、`publish_date`、`language`。

同一 PURL 已存在时更新组件，否则创建组件。响应会返回创建、更新、跳过、失败数量，以及带行号的错误列表。单行失败不会阻止其他有效行处理；导入汇总写入审计日志。

## 4. CSV 导出

- `GET /api/v1/transfers/components/export`：导出组件，可使用当前 `search` 和 `ecosystem` 筛选。
- `GET /api/v1/transfers/vulnerabilities/export`：导出 CVE，可使用当前 `search`、`severity` 和 `high_risk_only` 筛选。
- `GET /api/v1/transfers/high-risk-components/export`：导出高风险组件清单。

导出文件使用带 BOM 的 UTF-8 CSV，便于 Excel 正确识别中文。组件和 CVE 页面上的导出按钮会沿用当前筛选条件。

## 5. 数据库迁移

迁移 `c184af6934c2_add_user_roles.py` 为用户表增加 `role` 字段，并把已有超级管理员映射为 `ADMIN`。新用户默认角色为 `VIEWER`。
