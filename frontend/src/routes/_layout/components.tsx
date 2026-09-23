import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { AlertCircle, Boxes, Search } from "lucide-react"
import { type FormEvent, useState } from "react"

import { ComponentsService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import {
  AddComponent,
  ComponentDetails,
  DeleteComponent,
  EditComponent,
} from "@/components/Components/ComponentDialogs"
import { ComponentTransferButtons } from "@/components/Transfers/TransferButtons"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import useAuth from "@/hooks/useAuth"

const PAGE_SIZE = 20

export const Route = createFileRoute("/_layout/components")({
  component: ComponentsPage,
  head: () => ({ meta: [{ title: "开源组件管理 - OpenGuard" }] }),
})

function ComponentsPage() {
  const { user } = useAuth()
  const [searchInput, setSearchInput] = useState("")
  const [search, setSearch] = useState("")
  const [ecosystem, setEcosystem] = useState("")
  const [language, setLanguage] = useState("")
  const [page, setPage] = useState(0)

  const query = useQuery({
    queryKey: ["components", { search, ecosystem, language, page }],
    queryFn: async () =>
      (
        await ComponentsService.readComponents({
          query: {
            skip: page * PAGE_SIZE,
            limit: PAGE_SIZE,
            search: search || undefined,
            ecosystem: ecosystem || undefined,
            language: language || undefined,
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
        title="开源组件管理"
        description="维护 Maven 及其他生态的软件组件信息"
        icon={<Boxes />}
        signal="组件资产通道在线"
        actions={
          <div className="flex flex-wrap gap-2">
            <ComponentTransferButtons
              search={search}
              ecosystem={ecosystem}
              isAdmin={Boolean(user?.is_superuser)}
            />
            {user?.is_superuser && <AddComponent />}
          </div>
        }
      />

      <form
        onSubmit={onSearch}
        className="grid gap-3 rounded-lg border bg-card p-4 md:grid-cols-[1fr_180px_180px_auto]"
      >
        <Input
          aria-label="搜索组件"
          placeholder="搜索 PURL、名称、厂商或描述"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
        />
        <Input
          aria-label="生态类型"
          placeholder="生态类型，如 maven"
          value={ecosystem}
          onChange={(event) => {
            setEcosystem(event.target.value)
            setPage(0)
          }}
        />
        <Input
          aria-label="开发语言"
          placeholder="开发语言，如 java"
          value={language}
          onChange={(event) => {
            setLanguage(event.target.value)
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
          <AlertTitle>组件数据加载失败</AlertTitle>
          <AlertDescription>请检查服务状态后重试。</AlertDescription>
        </Alert>
      )}

      <div className="overflow-hidden rounded-lg border bg-card">
        {query.isPending ? (
          <div
            className="space-y-3 p-6"
            role="status"
            aria-label="正在加载组件数据"
          >
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </div>
        ) : query.data?.data.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <Search className="h-10 w-10 text-muted-foreground" />
            <div>
              <h2 className="font-semibold">没有找到组件</h2>
              <p className="text-sm text-muted-foreground">
                请调整搜索条件，或由管理员新增组件。
              </p>
            </div>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>组件</TableHead>
                <TableHead>生态</TableHead>
                <TableHead>版本</TableHead>
                <TableHead>语言</TableHead>
                <TableHead>厂商</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {query.data?.data.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="font-medium">{item.name}</div>
                    <div className="max-w-[380px] truncate text-xs text-muted-foreground">
                      {item.purl}
                    </div>
                  </TableCell>
                  <TableCell>
                    {item.ecosystem ? (
                      <Badge variant="secondary">{item.ecosystem}</Badge>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell>{item.version || "—"}</TableCell>
                  <TableCell>{item.language || "—"}</TableCell>
                  <TableCell>{item.vendor || "—"}</TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <ComponentDetails component={item} />
                      {user?.is_superuser && (
                        <>
                          <EditComponent component={item} />
                          <DeleteComponent component={item} />
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
