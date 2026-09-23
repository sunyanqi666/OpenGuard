# OpenGuard 数据模型与教师数据字段映射

本文档冻结阶段 1 的数据模型，作为后续导入脚本、REST API、前端页面和实验报告的共同依据。

## 1. 原始数据概况

| 数据集 | 记录数 | 唯一业务键 | 主要数据特征 |
| --- | ---: | --- | --- |
| `tmp_vul` | 1000 | `cve_id` | 1000 个 CVE ID 均唯一且格式合法；`title` 全为空；CVSS v3 全部有值 |
| `tmp_comp` | 398 | `purl` | 398 个 PURL 均唯一；154 条版本为空；107 条类型为空；名称全部存在 |

组件数据并不只包含 Maven，还包含 GitHub、npm、Composer、Cargo、Generic 等生态。系统完整保留教师数据，在界面中提供生态筛选并重点展示 Maven/PURL 语义，不丢弃其他记录。

## 2. 核心表

| 表 | 用途 | 主键/业务键 |
| --- | --- | --- |
| `vulnerability` | CVE 漏洞主数据 | UUID 主键；`cve_id` 唯一 |
| `component` | 软件组件主数据 | UUID 主键；`purl` 唯一 |
| `vulnerability_component` | 漏洞与组件多对多关联及匹配确认 | UUID 主键；漏洞和组件组合唯一 |
| `remediation` | 针对漏洞及可选组件的处置记录 | UUID 主键 |
| `audit_log` | 关键业务操作审计 | UUID 主键 |
| `user` | 模板已有用户、登录和权限数据 | UUID 主键；邮箱唯一 |

内部 UUID 避免外部业务编号变化影响外键；CVE ID 和 PURL 仍以唯一索引保证业务唯一性。

## 3. CVE 字段映射

| 教师字段 | 新字段 | 类型/规则 | 处理说明 |
| --- | --- | --- | --- |
| `source_id` | `source_id` | varchar(64)，可空 | 原样保留来源内部编号 |
| `source_name` | `source_name` | varchar(32)，可空，索引 | 用于来源筛选 |
| `source_publish_date` | `source_publish_date` | timestamptz，可空 | 按 UTC 语义导入 |
| `source_update_date` | `source_update_date` | timestamptz，可空 | 按 UTC 语义导入 |
| `source_link` | `source_link` | varchar(2048)，可空 | 扩大长度以兼容 URL |
| `affected_version` | `affected_versions` | JSON 数组 | 原数据是 JSON 字符串；导入时解析为字符串数组 |
| `cvss_score_v4` | `cvss_score_v4` | numeric(3,1)，0–10，可空 | 保留一位小数并增加范围约束 |
| `cvss_score_v3` | `cvss_score_v3` | numeric(3,1)，0–10，可空 | 同上 |
| `cvss_score_v2` | `cvss_score_v2` | numeric(3,1)，0–10，可空 | 同上 |
| `severity` | `severity` | 枚举字符串，索引 | `CRITICAL/HIGH/MEDIUM/LOW/UNKNOWN` |
| `type` | `vulnerability_type` | varchar(255)，可空 | 避免使用含义模糊的 Python/SQL 名称 `type` |
| `cwe_id` | `cwe_ids` | JSON 数组 | 原数据是 JSON 字符串；导入时解析 |
| `description` | `description` | text，可空 | 原样保留长文本 |
| `cve_id` | `cve_id` | varchar(32)，唯一索引 | 强制 `CVE-YYYY-NNNN...` 格式 |
| `title` | `title` | varchar(512)，可空 | 教师数据全部为空，不伪造标题；界面可回退显示 CVE ID |

新增系统字段：`id`、`created_at`、`updated_at`。

## 4. 组件字段映射

| 教师字段 | 新字段 | 类型/规则 | 处理说明 |
| --- | --- | --- | --- |
| `purl` | `purl` | varchar(1024)，唯一索引 | 必须以 `pkg:` 开头并包含包路径 |
| `cpe` | `cpe` | varchar(1024)，可空，索引 | 用于后续关联建议 |
| `type` | `ecosystem` | varchar(64)，可空，索引 | 避免与语言关键字混淆；表示 npm、github 等生态 |
| `vendor` | `vendor` | varchar(255)，可空，索引 | 空字符串导入为 NULL |
| `name` | `name` | varchar(255)，必填，索引 | 禁止纯空白名称 |
| `version` | `version` | varchar(255)，可空 | 154 条教师数据为空，因此不能设为必填 |
| `license` | `license` | text，可空 | 原值可能是 JSON 形式文本，阶段 2 原样保留 |
| `description` | `description` | text，可空 | 原样保留 |
| `repository` | `repository` | varchar(2048)，可空 | 空字符串导入为 NULL |
| `publish_date` | `publish_date` | timestamptz，可空 | 按 UTC 语义导入 |
| `language` | `language` | varchar(64)，可空，索引 | 用于筛选统计 |
| `record_time` | `source_record_time` | timestamptz，可空 | 明确这是源数据记录时间，不与系统创建时间混淆 |

新增系统字段：`id`、`created_at`、`updated_at`。

## 5. 关联、处置与审计规则

### 漏洞组件关联

- 同一漏洞和组件只能存在一条关联。
- 状态：`SUGGESTED`（建议）、`CONFIRMED`（已确认）、`REJECTED`（已拒绝）。
- 匹配方式：`MANUAL`、`CPE`、`NAME`、`IMPORT`。
- 匹配置信度可空；有值时范围必须是 0–1。
- 删除漏洞或组件时级联删除对应关联。

### 处置记录

- 处置必须属于一个漏洞，可以进一步指定组件。
- 状态：`PENDING`、`IN_PROGRESS`、`FIXED`、`IGNORED`。
- 可记录负责人、备注、截止日期及修复版本。
- 删除用户时保留处置记录并将负责人置空。

### 审计日志

- 动作：`CREATE`、`UPDATE`、`DELETE`、`LINK`、`UNLINK`、`STATUS_CHANGE`。
- 记录资源类型、资源 UUID、摘要和 JSON 形式的字段变化。
- 删除用户时保留日志并将操作人置空。

## 6. API 行为约定

- CVE 公共管理界面只开放查询、修改和删除；可信导入流程保留创建 Schema。
- 组件开放完整 CRUD。
- 重复 CVE ID 或 PURL 返回 HTTP 409。
- 参数或字段校验失败返回 HTTP 422。
- 资源不存在返回 HTTP 404。
- 删除操作必须由前端二次确认，后端仍执行权限校验。

## 7. 迁移与导入边界

- Alembic 迁移只创建结构和约束，不直接嵌入教师数据。
- 阶段 2 使用独立、可重复执行的导入脚本转换 MySQL SQL。
- 原始 SQL 永不修改；空字符串按字段语义转换为 NULL。
- 导入使用 CVE ID/PURL 幂等更新或跳过，重复执行不得产生重复记录。
