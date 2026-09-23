# OpenGuard 产品目标与全栈改造路线

> 文档状态：持续维护
>
> 最近更新：2026-09-23
>
> 配套交接文档：[DEVELOPMENT_HANDOFF.md](DEVELOPMENT_HANDOFF.md)

## 1. 项目目标

OpenGuard 将从课程场景下的 CVE 与组件信息管理系统，逐步升级为一个可公开演示的开源依赖风险管理平台。

产品需要完成以下业务闭环：

```text
创建项目
  → 上传 CycloneDX SBOM
  → 解析项目依赖
  → 调用 OSV 匹配真实漏洞
  → 生成项目风险与优先级
  → AI 生成有依据的修复建议
  → 指派、修复和人工复核
  → 上传新版 SBOM 重新扫描
  → 验证风险消失并关闭
```

这个改造同时服务于两个目标：

1. 做出能够解决真实问题、具有完整用户流程的产品。
2. 展示全栈岗位关注的前端、API、数据建模、异步任务、外部服务集成、AI、测试、部署和可观测性能力。

## 2. 产品边界

### 2.1 目标用户

- 开发者：查看自己项目中的脆弱依赖，获取修复建议并提交修复结果。
- 安全人员：导入或扫描项目、评估风险、分派任务并验证修复。
- 管理员：管理用户、权限、数据源和系统配置。
- 公开演示访客：使用受限账号体验完整流程。

### 2.2 第一版支持范围

- SBOM 格式：CycloneDX JSON。
- 依赖生态：优先支持 npm 和 PyPI，再扩展 Maven、Go 等生态。
- 漏洞来源：OSV；后续可补充 CISA KEV、NVD 或其他可信来源。
- AI 场景：针对单个项目风险生成结构化修复建议。
- 部署方式：Docker Compose 生产部署，并提供可访问的演示环境。

### 2.3 暂不作为第一版目标

- 自研代码静态分析器、容器镜像扫描器或主机扫描 Agent。
- 自动修改代码并直接合并分支。
- 依赖关系图的完整调用链分析。
- 企业级多租户计费和复杂审批流。

## 3. 当前项目基线

截至 2026-09-23，项目已经具备：

- React 19、TypeScript、Vite、TanStack Router/Query 和 Tailwind CSS 前端。
- FastAPI、SQLModel、Pydantic 和 PostgreSQL 后端。
- CVE 与组件管理、关联建议、风险处置、态势仪表盘。
- 管理员、安全人员和观察者三级权限。
- 操作审计、组件 CSV 导入和查询结果导出。
- Alembic 数据库迁移、OpenAPI 客户端生成。
- pytest 接口测试、Playwright 端到端测试和 GitHub Actions。
- Docker Compose 本地及部署配置。

当前 `Component` 是全局组件主数据，`VulnerabilityComponent` 表达全局漏洞关联，`Remediation` 表达现有处置记录。新功能需要补充“项目实际使用了某个版本的组件”这一层，不能直接把全局组件表当成项目依赖清单。

## 4. 目标架构

```text
React Web
  ├─ 项目与 SBOM 页面
  ├─ 项目风险看板
  ├─ 风险详情与修复时间线
  └─ AI 修复助手
          │
          ▼
FastAPI REST API
  ├─ 项目与权限服务
  ├─ SBOM 解析服务
  ├─ OSV 客户端与风险匹配服务
  ├─ 风险工作流服务
  └─ AI Provider 与结构化输出校验
          │
          ├────────► OSV API
          ├────────► AI 模型 API
          │
          ▼
PostgreSQL
  ├─ 项目、项目组件、导入批次
  ├─ 扫描任务、项目风险
  ├─ 修复事件、AI 建议
  └─ 用户、全局组件、漏洞、审计

后续扩展：Redis + 后台任务 Worker + OpenTelemetry/Sentry
```

## 5. 计划数据模型

最终字段以迁移和实现为准。开始编码前应先在 `docs/DATA_MODEL.md` 中补充详细约束。

| 实体 | 用途 | 建议关键字段 |
| --- | --- | --- |
| `Project` | 被管理的软件项目 | `name`、`description`、`repository_url`、`owner_id`、`criticality` |
| `SbomImport` | 一次 SBOM 上传及解析结果 | `project_id`、`filename`、`format`、`serial_number`、`status`、`error_summary` |
| `ProjectComponent` | 某项目实际使用的组件版本 | `project_id`、`component_id`、`purl`、`ecosystem`、`name`、`version`、`is_direct` |
| `ScanJob` | 一次漏洞匹配任务 | `project_id`、`sbom_import_id`、`status`、`progress`、`started_at`、`finished_at` |
| `ProjectRisk` | 项目中的具体漏洞风险 | `project_component_id`、`vulnerability_id`、`status`、`priority_score`、`assignee_id`、`due_date` |
| `RiskEvent` | 风险状态和人工操作时间线 | `risk_id`、`event_type`、`actor_id`、`before`、`after`、`created_at` |
| `AiRemediationAdvice` | AI 生成且可追溯的建议 | `risk_id`、`provider`、`model`、`input_fingerprint`、`content`、`citations`、`confidence` |

核心约束：

- 同一项目、PURL 和版本不得重复生成项目组件。
- 同一项目组件与同一漏洞最多存在一个活动风险。
- 导入和扫描必须可重复执行，不得产生重复风险。
- 删除项目时应明确级联范围；审计记录尽量保留。
- OSV 原始响应可保存必要快照，避免后续无法解释匹配依据。
- AI 建议是辅助内容，不能覆盖 OSV 等结构化事实数据。

## 6. 风险状态与闭环

建议的项目风险状态：

```text
OPEN（待确认）
  ├─→ IN_PROGRESS（待修复）
  │      └─→ READY_FOR_REVIEW（待验证）
  │               ├─→ RESOLVED（已关闭）
  │               └─→ IN_PROGRESS（验证失败）
  ├─→ FALSE_POSITIVE（误报）
  └─→ ACCEPTED（接受风险）
```

规则：

- 每次状态变化均写入 `RiskEvent` 和审计日志。
- `FALSE_POSITIVE` 与 `ACCEPTED` 必须填写原因。
- 新版 SBOM 重新扫描后，不再匹配的风险进入待验证状态或提示确认关闭。
- 仍然匹配的风险保持或重新进入修复状态，并记录复测结果。
- 风险详情要展示负责人、截止时间、修复版本、备注和完整时间线。

## 7. AI 修复助手设计

AI 功能应嵌入风险处理流程，不做与业务数据分离的通用聊天页。

### 7.1 输入

- 包生态、包名、当前版本和 PURL。
- OSV 漏洞描述、受影响范围、修复版本和参考链接。
- CVE、CVSS、CWE、KEV 等已经过验证的结构化信息。
- 用户允许提供的项目技术栈和必要上下文。

### 7.2 结构化输出

```json
{
  "summary": "风险的中文解释",
  "affected_reason": "当前项目可能受影响的原因",
  "recommended_version": "建议升级版本",
  "steps": ["修复步骤"],
  "verification": ["验证方法"],
  "breaking_change_risks": ["可能的兼容性问题"],
  "confidence": "high | medium | low",
  "citations": ["可信来源链接"]
}
```

### 7.3 可信性要求

- 推荐版本必须来自后端提供的结构化漏洞数据，模型不能自行创造版本号。
- 引用只能从允许的来源集合中选择，并由后端校验。
- 缺少证据时明确返回未知项和所需信息。
- AI 输出经 Pydantic Schema 校验后再返回前端。
- AI 建议必须经过人工编辑或确认，才能创建正式修复任务。
- 保存模型、提示词版本、输入指纹和生成时间，支持复现与审计。
- 对演示环境设置速率限制、超时、成本上限和降级提示。

### 7.4 实现接口

后端定义独立的 `AIProvider` 抽象，业务层只依赖统一接口。第一版接入一个提供商，同时保留兼容其他 API 或本地模型的能力。

建议接口：

```text
POST /api/v1/project-risks/{risk_id}/ai-advice
GET  /api/v1/project-risks/{risk_id}/ai-advice
POST /api/v1/project-risks/{risk_id}/ai-advice/{advice_id}/accept
```

## 8. API 与页面规划

### 8.1 后端接口

```text
POST /api/v1/projects
GET  /api/v1/projects
GET  /api/v1/projects/{project_id}
PATCH /api/v1/projects/{project_id}
DELETE /api/v1/projects/{project_id}

POST /api/v1/projects/{project_id}/sboms
GET  /api/v1/projects/{project_id}/sboms
GET  /api/v1/projects/{project_id}/sboms/{import_id}

POST /api/v1/projects/{project_id}/scans
GET  /api/v1/projects/{project_id}/scans/{scan_id}

GET   /api/v1/projects/{project_id}/components
GET   /api/v1/projects/{project_id}/risks
GET   /api/v1/project-risks/{risk_id}
PATCH /api/v1/project-risks/{risk_id}
POST  /api/v1/project-risks/{risk_id}/events

GET /api/v1/projects/{project_id}/dashboard
GET /api/v1/projects/{project_id}/sbom-diff
```

### 8.2 前端页面

- `/projects`：项目列表、创建入口和总体风险摘要。
- `/projects/{id}`：项目概览和风险看板。
- `/projects/{id}/components`：项目依赖及版本列表。
- `/projects/{id}/sboms`：上传、导入记录和新旧版本对比。
- `/projects/{id}/risks`：风险筛选、排序和批量操作。
- `/projects/{id}/risks/{riskId}`：证据、修复状态、AI 建议和时间线。

## 9. 分阶段实施计划

### 阶段 0：文档和基线保护

状态：已完成。

- [x] 建立产品路线文档。
- [x] 建立持续更新的开发交接日志。
- [x] 在 README 中增加文档入口。
- [ ] 在开始新功能前运行一次完整基线测试并记录结果。

### 阶段 1：项目与 SBOM 导入

状态：未开始。

- [ ] 新增 `Project`、`SbomImport`、`ProjectComponent` 模型及迁移。
- [ ] 完成项目 CRUD 和权限校验。
- [ ] 实现 CycloneDX JSON 文件校验与解析。
- [ ] 使用 PURL 标准化生态、名称和版本。
- [ ] 实现幂等导入、错误报告和导入详情。
- [ ] 完成项目列表、项目详情、上传和组件页面。
- [ ] 增加后端接口测试与 Playwright 主流程测试。

验收标准：上传一个真实 CycloneDX JSON 后，可以准确查看项目依赖、版本、导入结果和错误信息。

### 阶段 2：OSV 自动匹配

状态：未开始。

- [ ] 实现 OSV 客户端、生态映射、超时和错误处理。
- [ ] 使用批量查询减少外部请求。
- [ ] 新增 `ScanJob`、`ProjectRisk` 及相应迁移。
- [ ] 保存匹配依据和必要的 OSV 数据快照。
- [ ] 保证重复扫描不会创建重复风险。
- [ ] 前端显示扫描进度、错误、空状态和风险列表。
- [ ] 使用模拟 OSV 响应编写稳定测试。

验收标准：导入含有已知脆弱版本的 SBOM 后，系统能生成真实风险并展示来源和匹配依据。

### 阶段 3：项目风险看板

状态：未开始。

- [ ] 聚合严重程度、状态、负责人、逾期和趋势指标。
- [ ] 接入 CISA KEV 数据或标记机制。
- [ ] 定义透明、可解释的风险优先级规则。
- [ ] 实现风险筛选、排序和高风险组件排行。
- [ ] 实现项目看板及图表的加载、错误和空状态。

验收标准：用户可以在十几秒内识别最优先处理的风险，并看到排序依据。

### 阶段 4：修复闭环

状态：未开始。

- [ ] 新增 `RiskEvent`，实现状态机和转换校验。
- [ ] 支持负责人、截止时间、修复版本和处置说明。
- [ ] 为误报与接受风险增加必填理由。
- [ ] 实现风险详情时间线和快速处理操作。
- [ ] 复用或迁移现有 `Remediation` 能力，避免两套流程长期并存。
- [ ] 补充权限、并发更新和审计测试。

验收标准：一个风险可以从发现、指派、修复、待验证走到关闭，所有操作均可追溯。

### 阶段 5：AI 修复助手

状态：未开始。

- [ ] 定义 `AIProvider` 接口和配置。
- [ ] 定义 AI 输入快照与结构化输出 Schema。
- [ ] 实现来源白名单、引用校验和版本事实约束。
- [ ] 保存生成记录、模型信息和输入指纹。
- [ ] 实现 AI 建议卡片、编辑、重新生成和人工确认。
- [ ] 支持从确认后的建议创建修复任务。
- [ ] 增加速率限制、超时、失败降级和成本保护。
- [ ] 使用固定响应测试业务逻辑，避免测试依赖真实模型。

验收标准：AI 能为真实风险生成带来源、可编辑且可审计的修复建议，未经确认不会改变风险状态。

### 阶段 6：新版 SBOM 对比与自动复测

状态：未开始。

- [ ] 比较两次 SBOM 中新增、删除、升级和降级的组件。
- [ ] 重新执行 OSV 匹配并关联历史风险。
- [ ] 对消失、持续或新引入的风险给出明确结果。
- [ ] 验证失败时重新进入修复流程并写入事件。
- [ ] 实现 SBOM 差异和复测结果页面。

验收标准：上传修复后的 SBOM，可以证明目标漏洞是否消失，并保留前后证据。

### 阶段 7：异步处理与可观测性

状态：未开始。

- [ ] 引入 Redis 和后台任务 Worker。
- [ ] 将 SBOM 解析、OSV 扫描和 AI 生成改为可重试任务。
- [ ] 定义任务状态、进度、幂等键和失败恢复策略。
- [ ] 增加结构化日志、请求 ID、指标和链路追踪。
- [ ] 记录外部 API 延迟、错误率和 AI 消耗。
- [ ] 增加健康检查和依赖服务状态。

验收标准：长任务不会阻塞 HTTP 请求，失败可观察、可重试且不会重复写入数据。

### 阶段 8：公开演示与求职材料

状态：未开始。

- [ ] 准备生产 Docker 配置和托管环境。
- [ ] 配置 HTTPS、域名、密钥、备份和恢复。
- [ ] 准备只读账号和受限体验账号。
- [ ] 预置有漏洞和已修复的两份 SBOM。
- [ ] 定时恢复演示数据，限制上传大小和 AI 次数。
- [ ] 完成 README 架构说明、截图、在线地址和设计取舍。
- [ ] 录制 2～3 分钟完整演示视频。

验收标准：招聘方无需本地安装即可体验主流程，演示数据可以自动恢复且不会泄露密钥。

## 10. 测试策略

- 单元测试：PURL 解析、CycloneDX 校验、生态映射、优先级规则、状态机、AI 输出校验。
- 接口测试：权限、导入、扫描、风险更新、AI 建议和复测流程。
- 外部服务测试：使用录制或固定模拟响应，不依赖 OSV 和模型服务实时可用。
- 端到端测试：至少覆盖“上传 → 扫描 → 查看风险 → 生成建议 → 修复 → 复测”。
- 迁移测试：空数据库升级和已有数据升级均需要验证。
- 安全测试：上传大小与格式、越权访问、恶意 JSON、提示词注入和敏感信息泄露。

## 11. 完成定义

一项任务只有同时满足以下条件才可以在路线图中标记完成：

- 后端模型、迁移和 API 行为一致。
- 前端包含正常、加载、空数据和错误状态。
- 权限和审计规则已经实现。
- 核心路径有与风险相称的自动化测试。
- OpenAPI 客户端已重新生成且前端构建通过。
- 文档、配置样例和运行说明已同步更新。
- `DEVELOPMENT_HANDOFF.md` 已增加本次修改记录。

## 12. 产品演示主线

最终演示控制在 2～3 分钟：

1. 创建或打开示例项目。
2. 上传含有脆弱依赖的 SBOM。
3. 查看 OSV 自动发现的高优先级风险。
4. 打开风险详情并让 AI 生成带引用的修复方案。
5. 人工确认方案并将任务指派给开发者。
6. 上传升级依赖后的新版 SBOM。
7. 系统比较差异、重新扫描并确认风险已经消失。
8. 在时间线和看板中展示完整的处置证据。
