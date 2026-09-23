# 教师数据导入说明

OpenGuard 使用独立导入程序读取教师提供的 MySQL SQL，不修改原始文件，也不把原始数据写进 Alembic 迁移。

## 前置条件

1. 项目数据库已经启动。
2. 已执行 `alembic upgrade head`。
3. 教师文件位于项目同级目录 `../实践作业一/`。

## 试运行

试运行会完整解析、校验并写入当前事务，最后回滚，不改变数据库：

```bash
docker compose run --rm \
  -v "$PWD/../实践作业一:/data:ro" \
  backend python scripts/import_teacher_data.py \
  --vul-sql /data/vul.sql \
  --comp-sql /data/comp.sql \
  --dry-run
```

## 正式导入

```bash
docker compose run --rm \
  -v "$PWD/../实践作业一:/data:ro" \
  backend python scripts/import_teacher_data.py \
  --vul-sql /data/vul.sql \
  --comp-sql /data/comp.sql
```

程序输出 JSON 报告，其中：

- `inserted`：新插入数量；
- `updated`：业务键已存在但内容变化的数量；
- `unchanged`：业务键和内容均未变化的数量；
- `failed`：校验或转换失败的数量；
- `errors`：最多记录前 20 条错误详情。

任意失败会使命令返回非零退出码。CVE 与组件在同一事务中提交；正式导入完成前发生异常时，不应留下部分数据。

## 幂等规则

- CVE 按 `cve_id` 查找。
- 组件按 `purl` 查找。
- 不存在则新增，内容变化则更新，完全相同则记为 `unchanged`。
- 重复执行相同文件不会产生重复记录。

## 数据转换

- MySQL `NULL` 转为 Python/数据库 NULL。
- 语义为空的空字符串转为 NULL。
- `affected_version` 和 `cwe_id` 从 JSON 字符串转为 JSON 数组。
- CVSS 转为定点小数，并校验 0–10。
- 无时区的教师日期按 UTC 解释。
- 严重等级规范为大写枚举。
- 原始 `type` 字段分别映射为 `vulnerability_type` 和 `ecosystem`。

完整字段映射参见 [DATA_MODEL.md](DATA_MODEL.md)。

## 2026-09-21 导入验证

- 试运行：1000 条 CVE、398 条组件，失败 0。
- 首次正式导入：新增 1000 条 CVE、398 条组件，失败 0。
- 第二次正式导入：新增 0、更新 0、未变化 1000/398、失败 0。
- 数据库核对：1000 个唯一 CVE ID、398 个唯一 PURL、154 条组件版本为空。
- 严重等级：CRITICAL 59、HIGH 448、MEDIUM 388、LOW 105。
