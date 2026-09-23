import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { AlertCircle, Search, ShieldAlert } from "lucide-react"
import { type FormEvent, useState } from "react"

import { type Severity, VulnerabilitiesService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { VulnerabilityExportButton } from "@/components/Transfers/TransferButtons"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import {
  AddVulnerability,
  DeleteVulnerability,
  EditVulnerability,
  SeverityBadge,
  VulnerabilityDetails,
} from "@/components/Vulnerabilities/VulnerabilityDialogs"
import useAuth from "@/hooks/useAuth"

const PAGE_SIZE = 20

export const Route = createFileRoute("/_layout/vulnerabilities")({
  component: VulnerabilitiesPage,
  head: () => ({ meta: [{ title: "CVE 漏洞管理 - OpenGuard" }] }),
})

function VulnerabilitiesPage() {
  const { user } = useAuth()
  const [searchInput, setSearchInput] = useState("")
  const [search, setSearch] = useState("")
  const [severity, setSeverity] = useState<Severity | "ALL">("ALL")
  const [minCvss, setMinCvss] = useState("")
  const [page, setPage] = useState(0)

  const query = useQuery({
    queryKey: ["vulnerabilities", { search, severity, minCvss, page }],
    queryFn: async () =>
      (
        await VulnerabilitiesService.readVulnerabilities({
          query: {
            skip: page * PAGE_SIZE,
            limit: PAGE_SIZE,
            search: search || undefined,
            severity: severity === "ALL" ? undefined : severity,
            min_cvss: minCvss ? Number(minCvss) : undefined,
          },
        })
      ).data,
    placeholderData: keepPreviousData,
  })

  const onSearch = (event: FormEvent) => {
    event.preventDefault()
    setPage(0)
    setSearch(searchInput.trim())
  }

  const totalPages = Math.max(
    1,
    Math.ceil((query.data?.count ?? 0) / PAGE_SIZE),
  )

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="CVE 漏洞管理"
        description="查询、查看和维护教师数据集中的漏洞信息"
        icon={<ShieldAlert />}
        actions={
          <div className="flex gap-2">
            <VulnerabilityExportButton search={search} severity={severity} />
            {user?.is_superuser && <AddVulnerability />}
          </div>
        }
        signal="漏洞情报通道在线"
      />

      <form
        onSubmit={onSearch}
        className="grid gap-3 rounded-lg border bg-card p-4 md:grid-cols-[1fr_180px_160px_auto]"
      >
        <Input
          aria-label="搜索漏洞"
          placeholder="搜索 CVE 编号、标题或描述"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
        />
        <select
          aria-label="严重等级"
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={severity}
          onChange={(event) => {
            setSeverity(event.target.value as Severity | "ALL")
            setPage(0)
          }}
        >
          <option value="ALL">全部等级</option>
          <option value="CRITICAL">严重</option>
          <option value="HIGH">高危</option>
          <option value="MEDIUM">中危</option>
          <option value="LOW">低危</option>
          <option value="UNKNOWN">未知</option>
        </select>
        <Input
          aria-label="最低 CVSS"
          type="number"
          min="0"
          max="10"
          step="0.1"
          placeholder="最低 CVSS"
          value={minCvss}
          onChange={(event) => {
            setMinCvss(event.target.value)
            setPage(0)
          }}
        />
        <Button type="submit">
          <Search className="mr-2 h-4 w-4" />
          查询
        </Button>
      </form>

      {query.isError && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertTitle>漏洞数据加载失败</AlertTitle>
          <AlertDescription>请检查服务状态后重试。</AlertDescription>
        </Alert>
      )}

      <div className="overflow-hidden rounded-lg border bg-card">
        {query.isPending ? (
          <div
            className="space-y-3 p-6"
            role="status"
            aria-label="正在加载漏洞数据"
          >
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </div>
        ) : query.data?.data.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <Search className="h-10 w-10 text-muted-foreground" />
            <div>
              <h2 className="font-semibold">没有找到漏洞</h2>
              <p className="text-sm text-muted-foreground">
                请调整搜索词或筛选条件。
              </p>
            </div>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>CVE 编号</TableHead>
                <TableHead>等级</TableHead>
                <TableHead>CVSS</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>发布时间</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {query.data?.data.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="font-medium">{item.cve_id}</div>
                    <div className="max-w-[360px] truncate text-xs text-muted-foreground">
                      {item.title || item.description || "暂无描述"}
                    </div>
                  </TableCell>
                  <TableCell>
                    <SeverityBadge severity={item.severity ?? "UNKNOWN"} />
                  </TableCell>
                  <TableCell>
                    {item.cvss_score_v4 ??
                      item.cvss_score_v3 ??
                      item.cvss_score_v2 ??
                      "—"}
                  </TableCell>
                  <TableCell>{item.source_name || "—"}</TableCell>
                  <TableCell>
                    {item.source_publish_date
                      ? new Date(item.source_publish_date).toLocaleDateString(
                          "zh-CN",
                        )
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <VulnerabilityDetails vulnerability={item} />
                      {user?.is_superuser && (
                        <>
                          <EditVulnerability vulnerability={item} />
                          <DeleteVulnerability vulnerability={item} />
                        </>
                      )}
                    </div>
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
            variant="outline"
            size="sm"
            disabled={page === 0 || query.isFetching}
            onClick={() => setPage((value) => value - 1)}
          >
            上一页
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page + 1 >= totalPages || query.isFetching}
            onClick={() => setPage((value) => value + 1)}
          >
            下一页
          </Button>
        </div>
      </div>
    </div>
  )
}
