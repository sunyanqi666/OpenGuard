import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ClipboardList, Search } from "lucide-react"
import { useState } from "react"

import { type AuditAction, AuditLogsService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const PAGE_SIZE = 20
const labels: Record<AuditAction, string> = {
  CREATE: "新增",
  UPDATE: "修改",
  DELETE: "删除",
  LINK: "建立关联",
  UNLINK: "解除关联",
  STATUS_CHANGE: "状态变化",
}

export const Route = createFileRoute("/_layout/audit")({
  component: AuditPage,
  head: () => ({ meta: [{ title: "审计日志 - OpenGuard" }] }),
})

function AuditPage() {
  const [action, setAction] = useState<AuditAction | "">("")
  const [resourceType, setResourceType] = useState("")
  const [page, setPage] = useState(0)
  const query = useQuery({
    queryKey: ["audit-logs", action, resourceType, page],
    queryFn: async () =>
      (
        await AuditLogsService.logsReadAuditLogs({
          query: {
            skip: page * PAGE_SIZE,
            limit: PAGE_SIZE,
            action: action || undefined,
            resource_type: resourceType || undefined,
          },
        })
      ).data,
    placeholderData: keepPreviousData,
  })
  const totalPages = Math.max(
    1,
    Math.ceil((query.data?.count ?? 0) / PAGE_SIZE),
  )
  return (
    <div className="space-y-6">
      <PageHeader
        title="审计日志"
        description="追踪关键数据变更、关联和处置操作"
        icon={<ClipboardList />}
        signal="审计事件实时记录"
      />
      <div className="grid gap-3 rounded-lg border bg-card p-4 sm:grid-cols-2">
        <select
          aria-label="操作类型"
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={action}
          onChange={(event) => {
            setAction(event.target.value as AuditAction | "")
            setPage(0)
          }}
        >
          <option value="">全部操作</option>
          {Object.entries(labels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <Input
          aria-label="资源类型"
          placeholder="资源类型，如 component"
          value={resourceType}
          onChange={(event) => {
            setResourceType(event.target.value)
            setPage(0)
          }}
        />
      </div>
      <div className="overflow-hidden rounded-lg border bg-card">
        {query.isPending ? (
          <div className="space-y-3 p-6">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-10" />
            ))}
          </div>
        ) : !query.data?.data.length ? (
          <div className="py-14 text-center text-muted-foreground">
            <Search className="mx-auto mb-2" />
            暂无审计记录
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>时间</TableHead>
                <TableHead>操作</TableHead>
                <TableHead>资源</TableHead>
                <TableHead>操作人</TableHead>
                <TableHead>摘要</TableHead>
                <TableHead>变更详情</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {query.data.data.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="whitespace-nowrap">
                    {new Date(item.created_at).toLocaleString("zh-CN")}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{labels[item.action]}</Badge>
                  </TableCell>
                  <TableCell>{item.resource_type}</TableCell>
                  <TableCell>{item.actor_email || "系统"}</TableCell>
                  <TableCell>{item.summary || "—"}</TableCell>
                  <TableCell>
                    <details>
                      <summary className="cursor-pointer text-primary">
                        查看
                      </summary>
                      <pre className="mt-2 max-w-80 overflow-auto whitespace-pre-wrap rounded bg-muted p-2 text-xs">
                        {JSON.stringify(item.changes, null, 2)}
                      </pre>
                    </details>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          共 {query.data?.count ?? 0} 条，第 {page + 1}/{totalPages} 页
        </span>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={page === 0}
            onClick={() => setPage((value) => value - 1)}
          >
            上一页
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={page + 1 >= totalPages}
            onClick={() => setPage((value) => value + 1)}
          >
            下一页
          </Button>
        </div>
      </div>
    </div>
  )
}
