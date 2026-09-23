# OpenGuard 开源组件安全管理平台

OpenGuard 是一个面向课程实践的 CVE 与开源组件信息管理系统。系统包含 React 前端、FastAPI REST API 和 PostgreSQL 数据库，通过真实 HTTP 请求完成数据查询与持久化，不包含漏洞扫描器或 Agent 功能。

## 主要功能

- CVE：分页检索、条件筛选、详情、修改和删除；另提供管理员手工新增作为扩展功能。
- 组件：分页检索、详情及完整新增、修改、删除。
- 风险扩展：CVE—组件关联建议与确认、风险处置、态势仪表盘。
- 处置工作台：负责人任务视图、组合筛选、逾期/三日内到期预警和快速处理。
- 工程扩展：三级角色权限、操作审计、组件 CSV 导入、查询结果与高风险清单导出。
- 质量保障：Alembic 迁移、教师数据幂等导入、pytest 接口测试和 Playwright 端到端测试。

## 技术栈与结构

- 前端：React、TypeScript、Vite、TanStack Router/Query、Tailwind CSS、shadcn/ui。
- 后端：Python、FastAPI、Pydantic、SQLModel。
- 数据库：PostgreSQL 18、Alembic。
- 运行与测试：Docker Compose、pytest、Playwright。

```text
backend/                 FastAPI、模型、迁移、数据导入和后端测试
frontend/                React 页面、生成的 API 客户端和 E2E 测试
docs/                    数据模型、接口、权限和交付文档
../实践作业一/            教师提供的原始 SQL（保持不修改）
```

## 产品路线与开发交接

- [全栈产品化目标与实施路线](docs/PRODUCT_ROADMAP.md)：记录 SBOM 导入、OSV 匹配、项目风险看板、修复闭环、AI 助手和公开演示计划。
- [开发记录与交接说明](docs/DEVELOPMENT_HANDOFF.md)：记录当前状态、每次功能修改、验证结果、未完成事项和下一步。后续开发需要在同一次修改中同步更新该文档。

## 环境要求

- Docker Desktop（包含 Docker Compose）
- 至少约 4 GB 可用内存
- 教师数据导入时，项目同级目录需存在 `实践作业一/vul.sql` 和 `实践作业一/comp.sql`

## 首次启动

1. 创建本地配置：`cp .env.example .env`。
2. 修改 `.env` 中的 `SECRET_KEY`、`POSTGRES_PASSWORD` 和 `FIRST_SUPERUSER_PASSWORD`。不要提交 `.env`。密钥可用 `openssl rand -hex 32` 生成。
3. 构建、启动并初始化：

   ```bash
   docker compose build backend
   docker compose up -d db backend
   docker compose run --rm backend bash scripts/prestart.sh
   ```

4. 导入教师数据（可重复执行）：

   ```bash
   docker compose run --rm \
     -v "$PWD/../实践作业一:/data:ro" \
     backend python scripts/import_teacher_data.py \
     --vul-sql /data/vul.sql \
     --comp-sql /data/comp.sql
   ```

5. 访问：

   - 系统：[http://localhost:8000](http://localhost:8000)
   - Swagger：[http://localhost:8000/docs](http://localhost:8000/docs)
   - Adminer：[http://localhost:8080](http://localhost:8080)
   - Mailpit：[http://localhost:8025](http://localhost:8025)

登录邮箱和密码分别取自 `.env` 的 `FIRST_SUPERUSER` 与 `FIRST_SUPERUSER_PASSWORD`，项目文档不提供真实密码。

## 日常启动、停止与持久化

```bash
docker compose up -d db backend
docker compose ps
docker compose stop
```

数据库保存在 Docker 命名卷 `app-db-data` 中，普通停止或重启不会删除数据。只有明确需要清空本地数据库时才执行 `docker compose down -v`。

## 数据库迁移和数据导入

`backend/scripts/prestart.sh` 会等待数据库、执行 `alembic upgrade head` 并创建初始管理员。教师 SQL 不直接交给 PostgreSQL，而由专用程序完成 MySQL 语法解析、清洗、校验和幂等写入。

导入前可增加 `--dry-run` 做完整校验而不写入数据库，详见 [教师数据导入说明](docs/DATA_IMPORT.md)。字段映射和设计理由见 [数据模型说明](docs/DATA_MODEL.md)。

## 常用 REST API

业务接口位于 `/api/v1`，除登录和公开工具接口外均需要 Bearer JWT。

| 模块 | 典型路径 | 说明 |
| --- | --- | --- |
| 登录 | `POST /login/access-token` | 获取访问令牌 |
| CVE | `/vulnerabilities/` | 查询、详情、修改、删除 |
| 组件 | `/components/` | 完整 CRUD |
| 关联 | `/associations/` | 查询、建议、建立、解除 |
| 处置 | `/remediations/` | 风险处置维护 |
| 处置汇总 | `/remediations/summary` | 工作台状态、逾期和完成率指标 |
| 仪表盘 | `/dashboard/summary` | 真实数据库聚合指标 |
| 审计 | `/audit-logs/` | 关键操作追溯 |
| 导入导出 | `/transfers/` | CSV 数据交换 |

详细权限矩阵见 [角色权限、审计与 CSV 说明](docs/PERMISSIONS_AND_TRANSFERS.md)。

## 测试与代码检查

后端测试脚本会自动创建并迁移隔离的 `app_test` 数据库，不会清理日常开发库。首次运行或修改后端源码后先重新构建镜像，确保镜像包含当前源码和测试：

```bash
docker compose build backend
docker compose run --rm backend bash scripts/tests-start.sh
```

前端构建及端到端测试：

```bash
docker compose build backend playwright
docker compose up -d db backend
docker compose run --rm playwright bun run build
docker compose run --rm playwright bunx playwright test --workers=1
```

端到端用例会操作共享的演示数据，因此固定使用单工作进程，避免并发用例互相删除关联或临时记录。

后端静态检查：

```bash
docker compose run --rm backend bash scripts/lint.sh
```

## 角色说明

- 管理员：业务主数据、用户、导入、关联、处置和审计的完整权限。
- 安全人员：只读主数据，可维护关联和处置并查看审计。
- 观察者：查看仪表盘、CVE、组件和关联，可导出只读数据。

前端隐藏无权入口只用于改善体验，最终权限始终由后端校验。

## 常见问题

- 登录返回 500 或提示表不存在：运行 `docker compose run --rm backend bash scripts/prestart.sh`。
- 页面提示会话失效：重新登录；若账号异常，检查测试是否误用了开发数据库。
- 8000 端口不可访问：使用 `docker compose ps` 和 `docker compose logs backend` 检查状态。
- 导入失败：先加 `--dry-run`，根据 JSON 报告中的行号排查。
- Excel 打开中文 CSV 乱码：系统导出已包含 UTF-8 BOM，请直接打开原文件。

提交前参照 [提交检查清单](docs/SUBMISSION_CHECKLIST.md)。

## 来源与许可证

项目基于 FastAPI 官方 `full-stack-fastapi-template`（基线提交 `cb740b656d7a0a6c5e12c7bf8e50343ec94ee9c7`）二次开发，上游采用 MIT License。本项目保留原 [LICENSE](LICENSE)。教师原始 SQL 仅用于课程实践，不视为项目开源资产。
