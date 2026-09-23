import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  Plus,
  Search,
} from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"

import {
  AssociationsService,
  type RemediationPublic,
  type RemediationStatus,
  RemediationsService,
  type Severity,
  UsersService,
  type VulnerabilityComponentPublic,
} from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
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
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const PAGE_SIZE = 20
const statusLabels: Record<RemediationStatus, string> = {
  PENDING: "待评估",
  IN_PROGRESS: "处理中",
  FIXED: "已修复",
  IGNORED: "已忽略",
}
const severityLabels: Record<Severity, string> = {
  CRITICAL: "严重",
  HIGH: "高危",
  MEDIUM: "中危",
  LOW: "低危",
  UNKNOWN: "未知",
}

type Filters = {
  search: string
  status: RemediationStatus | ""
  severity: Severity | ""
  assigneeId: string
  dueState: "" | "overdue" | "soon"
  myOnly: boolean
}

const emptyFilters: Filters = {
  search: "",
  status: "",
  severity: "",
  assigneeId: "",
  dueState: "",
  myOnly: false,
}

export const Route = createFileRoute("/_layout/remediations")({
  component: RemediationWorkbench,
  head: () => ({ meta: [{ title: "处置工作台 - OpenGuard" }] }),
})

function RemediationWorkbench() {
  const { user } = useAuth()
  const canEdit = Boolean(user?.is_superuser || user?.role === "SECURITY")
  const [draft, setDraft] = useState<Filters>(emptyFilters)
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const [page, setPage] = useState(0)
  const [editing, setEditing] = useState<RemediationPublic | null>(null)
  const [creating, setCreating] = useState(false)

  const summary = useQuery({
    queryKey: ["remediation-summary", filters.myOnly],
    queryFn: async () =>
      (
        await RemediationsService.readRemediationSummary({
          query: { my_only: filters.myOnly },
        })
      ).data,
  })
  const users = useQuery({
    queryKey: ["remediation-users"],
    queryFn: async () =>
      (await UsersService.readUsers({ query: { limit: 100 } })).data,
  })
  const records = useQuery({
    queryKey: ["remediation-workbench", filters, page],
    queryFn: async () =>
      (
        await RemediationsService.readRemediations({
          query: {
            search: filters.search || undefined,
            status: filters.status || undefined,
            severity: filters.severity || undefined,
            assignee_id: filters.assigneeId || undefined,
            overdue_only: filters.dueState === "overdue",
            due_soon_only: filters.dueState === "soon",
            my_only: filters.myOnly,
            skip: page * PAGE_SIZE,
            limit: PAGE_SIZE,
          },
        })
      ).data,
    placeholderData: keepPreviousData,
  })
  const totalPages = Math.max(
    1,
    Math.ceil((records.data?.count ?? 0) / PAGE_SIZE),
  )
  const hasActiveFilters = Boolean(
    filters.search ||
      filters.status ||
      filters.severity ||
      filters.assigneeId ||
      filters.dueState ||
      filters.myOnly,
  )

  const applyFilters = (event: FormEvent) => {
    event.preventDefault()
    setFilters(draft)
    setPage(0)
  }
  const chooseDueState = (dueState: Filters["dueState"]) => {
    const next = { ...draft, dueState }
    setDraft(next)
    setFilters(next)
    setPage(0)
  }
  const reset = () => {
    setDraft(emptyFilters)
    setFilters(emptyFilters)
    setPage(0)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="风险处置工作台"
        description="集中跟踪已建立的处置任务；原始漏洞请在 CVE 页面查询"
        icon={<ClipboardCheck />}
        signal="处置状态持续同步"
        actions={
          canEdit ? (
            <Button onClick={() => setCreating(true)}>
              <Plus className="mr-2 h-4 w-4" />
              新增处置任务
            </Button>
          ) : undefined
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <SummaryCard label="待评估" value={summary.data?.pending} />
        <SummaryCard label="处理中" value={summary.data?.in_progress} />
        <SummaryCard
          label="即将到期"
          value={summary.data?.due_soon}
          tone="warning"
          onClick={() => chooseDueState("soon")}
        />
        <SummaryCard
          label="已经逾期"
          value={summary.data?.overdue}
          tone="danger"
          onClick={() => chooseDueState("overdue")}
        />
        <SummaryCard
          label="本月已修复"
          value={summary.data?.completed_this_month}
          tone="success"
        />
        <SummaryCard
          label="完成率"
          value={summary.data ? `${summary.data.completion_rate}%` : undefined}
          tone="success"
        />
      </div>

      <form
        onSubmit={applyFilters}
        className="grid gap-3 rounded-lg border bg-card p-4 md:grid-cols-3 xl:grid-cols-6"
      >
        <Input
          aria-label="搜索处置任务"
          placeholder="搜索处置任务"
          value={draft.search}
          onChange={(event) =>
            setDraft({ ...draft, search: event.target.value })
          }
        />
        <select
          aria-label="处置状态筛选"
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={draft.status}
          onChange={(event) =>
            setDraft({
              ...draft,
              status: event.target.value as Filters["status"],
            })
          }
        >
          <option value="">全部状态</option>
          {Object.entries(statusLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          aria-label="严重等级筛选"
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={draft.severity}
          onChange={(event) =>
            setDraft({
              ...draft,
              severity: event.target.value as Filters["severity"],
            })
          }
        >
          <option value="">全部等级</option>
          {Object.entries(severityLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          aria-label="负责人筛选"
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={draft.assigneeId}
          onChange={(event) =>
            setDraft({ ...draft, assigneeId: event.target.value })
          }
        >
          <option value="">全部负责人</option>
          {users.data?.data.map((item) => (
            <option key={item.id} value={item.id}>
              {item.full_name || item.email}
            </option>
          ))}
        </select>
        <select
          aria-label="到期状态筛选"
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={draft.dueState}
          onChange={(event) =>
            setDraft({
              ...draft,
              dueState: event.target.value as Filters["dueState"],
            })
          }
        >
          <option value="">全部到期状态</option>
          <option value="soon">三日内到期</option>
          <option value="overdue">已经逾期</option>
        </select>
        <label className="flex h-9 items-center gap-2 rounded-md border px-3 text-sm">
          <input
            type="checkbox"
            checked={draft.myOnly}
            onChange={(event) =>
              setDraft({ ...draft, myOnly: event.target.checked })
            }
          />
          只看我的任务
        </label>
        <div className="flex gap-2 md:col-span-3 xl:col-span-6">
          <Button type="submit">
            <Search className="mr-2 h-4 w-4" />
            查询
          </Button>
          <Button type="button" variant="outline" onClick={reset}>
            重置
          </Button>
        </div>
      </form>

      <div className="overflow-hidden rounded-lg border bg-card">
        {records.isPending ? (
          <div className="space-y-3 p-6">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-12" />
            ))}
          </div>
        ) : records.isError ? (
          <div className="p-8 text-center text-destructive">
            处置任务加载失败，请稍后重试。
          </div>
        ) : !records.data?.data.length ? (
          <div className="py-16 text-center text-muted-foreground">
            <ClipboardCheck className="mx-auto mb-3 h-10 w-10" />
            <p className="font-medium text-foreground">
              {hasActiveFilters
                ? "暂无符合条件的处置任务"
                : "当前还没有处置任务"}
            </p>
            <p className="mt-1 text-sm">
              工作台只查询处置任务，不直接查询全部 CVE
            </p>
            <div className="mt-4 flex justify-center gap-2">
              {canEdit && (
                <Button onClick={() => setCreating(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  新增处置任务
                </Button>
              )}
              <Button asChild variant="outline">
                <Link to="/vulnerabilities">前往 CVE 页面</Link>
              </Button>
            </div>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>风险对象</TableHead>
                <TableHead>等级</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>负责人</TableHead>
                <TableHead>截止日期</TableHead>
                <TableHead>修复版本</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.data.data.map((item) => {
                const due = getDueState(item)
                return (
                  <TableRow key={item.id}>
                    <TableCell>
                      <div className="font-medium">
                        <Link to="/vulnerabilities" className="hover:underline">
                          {item.cve_id}
                        </Link>
                      </div>
                      <div className="text-sm">
                        {item.component_name || "组件已删除"}
                      </div>
                      <div className="max-w-72 truncate text-xs text-muted-foreground">
                        {item.component_purl}
                      </div>
                    </TableCell>
                    <TableCell>
                      <SeverityBadge severity={item.vulnerability_severity} />
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={item.status} />
                    </TableCell>
                    <TableCell>
                      {item.assignee_name || (
                        <span className="text-muted-foreground">未分配</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <DueBadge state={due} date={item.due_date} />
                    </TableCell>
                    <TableCell>{item.fixed_version || "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setEditing(item)}
                      >
                        {canEdit ? "处理" : "查看"}
                      </Button>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          共 {records.data?.count ?? 0} 条，第 {page + 1}/{totalPages} 页
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

      <WorkbenchEditor
        item={editing}
        canEdit={canEdit}
        users={users.data?.data ?? []}
        onClose={() => setEditing(null)}
      />
      <CreateRemediationDialog
        open={creating}
        users={users.data?.data ?? []}
        onClose={() => setCreating(false)}
      />
    </div>
  )
}

function SummaryCard({
  label,
  value,
  tone = "default",
  onClick,
}: {
  label: string
  value?: number | string
  tone?: "default" | "warning" | "danger" | "success"
  onClick?: () => void
}) {
  const colors = {
    default: "text-foreground",
    warning: "text-amber-600",
    danger: "text-red-600",
    success: "text-emerald-600",
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className="rounded-lg border bg-card p-4 text-left transition enabled:hover:border-primary/50"
    >
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className={`mt-2 text-2xl font-bold ${colors[tone]}`}>
        {value ?? "—"}
      </div>
    </button>
  )
}

function getDueState(
  item: RemediationPublic,
): "none" | "normal" | "soon" | "overdue" | "done" {
  if (item.status === "FIXED" || item.status === "IGNORED") return "done"
  if (!item.due_date) return "none"
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(`${item.due_date}T00:00:00`)
  if (due < today) return "overdue"
  const days = Math.round((due.getTime() - today.getTime()) / 86_400_000)
  return days <= 3 ? "soon" : "normal"
}

function DueBadge({
  state,
  date,
}: {
  state: ReturnType<typeof getDueState>
  date?: string | null
}) {
  if (!date) return <span className="text-muted-foreground">未设置</span>
  const config = {
    none: ["", ""],
    normal: ["outline", date],
    soon: ["secondary", `${date} · 即将到期`],
    overdue: ["destructive", `${date} · 已逾期`],
    done: ["outline", date],
  } as const
  const [variant, label] = config[state]
  return (
    <Badge variant={variant || "outline"}>
      {state === "overdue" ? (
        <AlertTriangle className="mr-1 h-3 w-3" />
      ) : state === "soon" ? (
        <CalendarClock className="mr-1 h-3 w-3" />
      ) : state === "done" ? (
        <CheckCircle2 className="mr-1 h-3 w-3" />
      ) : null}
      {label}
    </Badge>
  )
}

function StatusBadge({ status }: { status: RemediationStatus }) {
  return (
    <Badge
      variant={
        status === "FIXED"
          ? "default"
          : status === "IN_PROGRESS"
            ? "secondary"
            : "outline"
      }
    >
      {statusLabels[status]}
    </Badge>
  )
}

function SeverityBadge({ severity }: { severity?: Severity | null }) {
  if (!severity) return <Badge variant="outline">未知</Badge>
  return (
    <Badge
      variant={
        severity === "CRITICAL" || severity === "HIGH"
          ? "destructive"
          : "secondary"
      }
    >
      {severityLabels[severity]}
    </Badge>
  )
}

function CreateRemediationDialog({
  open,
  users,
  onClose,
}: {
  open: boolean
  users: Array<{ id: string; full_name?: string | null; email: string }>
  onClose: () => void
}) {
  const [associationId, setAssociationId] = useState("")
  const [status, setStatus] = useState<RemediationStatus>("PENDING")
  const [assigneeId, setAssigneeId] = useState("")
  const [dueDate, setDueDate] = useState("")
  const [fixedVersion, setFixedVersion] = useState("")
  const [notes, setNotes] = useState("")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const associations = useQuery({
    queryKey: ["remediation-available-associations"],
    queryFn: async () =>
      (await AssociationsService.readAssociations({ query: { limit: 200 } }))
        .data,
    enabled: open,
  })
  const remediations = useQuery({
    queryKey: ["remediation-existing-pairs"],
    queryFn: async () =>
      (await RemediationsService.readRemediations({ query: { limit: 200 } }))
        .data,
    enabled: open,
  })
  const available = useMemo(() => {
    const existing = new Set(
      (remediations.data?.data ?? []).map(
        (item) => `${item.vulnerability_id}:${item.component_id}`,
      ),
    )
    return (associations.data?.data ?? []).filter(
      (item) =>
        item.status === "CONFIRMED" &&
        !existing.has(`${item.vulnerability_id}:${item.component_id}`),
    )
  }, [associations.data, remediations.data])
  const selected = available.find((item) => item.id === associationId)
  const reset = () => {
    setAssociationId("")
    setStatus("PENDING")
    setAssigneeId("")
    setDueDate("")
    setFixedVersion("")
    setNotes("")
  }
  const close = () => {
    reset()
    onClose()
  }
  const mutation = useMutation({
    mutationFn: () =>
      RemediationsService.createRemediation({
        body: {
          vulnerability_id: selected!.vulnerability_id,
          component_id: selected!.component_id,
          status,
          assignee_id: assigneeId || null,
          due_date: dueDate || null,
          fixed_version: fixedVersion.trim() || null,
          notes: notes.trim() || null,
        },
      }),
    onSuccess: () => {
      showSuccessToast("处置任务已创建")
      queryClient.invalidateQueries({ queryKey: ["remediation-workbench"] })
      queryClient.invalidateQueries({ queryKey: ["remediation-summary"] })
      queryClient.invalidateQueries({
        queryKey: ["remediation-available-associations"],
      })
      queryClient.invalidateQueries({
        queryKey: ["remediation-existing-pairs"],
      })
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] })
      close()
    },
    onError: handleError.bind(showErrorToast),
  })
  const loading = associations.isPending || remediations.isPending
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) close()
      }}
    >
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>新增处置任务</DialogTitle>
          <DialogDescription>
            从已确认的 CVE 与组件关联中选择风险对象，再设置负责人和处置计划。
          </DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="space-y-3 py-4">
            <Skeleton className="h-10" />
            <Skeleton className="h-32" />
          </div>
        ) : associations.isError || remediations.isError ? (
          <div className="rounded-md border border-destructive/40 p-4 text-sm text-destructive">
            可用关联加载失败，请稍后重试。
          </div>
        ) : available.length === 0 ? (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <ClipboardCheck className="mx-auto mb-3 h-9 w-9 text-muted-foreground" />
            <p className="font-medium">暂无可创建任务的已确认关联</p>
            <p className="mt-1 text-sm text-muted-foreground">
              请先在 CVE 详情中建立并确认组件关联，已有任务的关联不会重复显示。
            </p>
            <Button asChild className="mt-4" variant="outline">
              <Link to="/vulnerabilities" onClick={close}>
                前往 CVE 页面建立关联
              </Link>
            </Button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-1 text-sm sm:col-span-2">
              <span>风险对象</span>
              <select
                aria-label="选择漏洞组件关联"
                className="h-10 w-full rounded-md border bg-background px-3"
                value={associationId}
                onChange={(event) => setAssociationId(event.target.value)}
              >
                <option value="">请选择已确认的关联</option>
                {available.map((item: VulnerabilityComponentPublic) => (
                  <option key={item.id} value={item.id}>
                    {item.cve_id} · {item.component_name} ·{" "}
                    {item.component_purl}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span>初始状态</span>
              <select
                aria-label="新增任务状态"
                className="h-9 w-full rounded-md border bg-background px-3"
                value={status}
                onChange={(event) =>
                  setStatus(event.target.value as RemediationStatus)
                }
              >
                {Object.entries(statusLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span>负责人</span>
              <select
                aria-label="新增任务负责人"
                className="h-9 w-full rounded-md border bg-background px-3"
                value={assigneeId}
                onChange={(event) => setAssigneeId(event.target.value)}
              >
                <option value="">未分配</option>
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.full_name || user.email}
                  </option>
                ))}
              </select>
            </label>
            <label
              htmlFor="create-remediation-due-date"
              className="space-y-1 text-sm"
            >
              <span>截止日期</span>
              <Input
                id="create-remediation-due-date"
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
              />
            </label>
            <label
              htmlFor="create-remediation-fixed-version"
              className="space-y-1 text-sm"
            >
              <span>目标修复版本</span>
              <Input
                id="create-remediation-fixed-version"
                value={fixedVersion}
                onChange={(event) => setFixedVersion(event.target.value)}
              />
            </label>
            <label className="space-y-1 text-sm sm:col-span-2">
              <span>处置备注</span>
              <textarea
                aria-label="新增任务备注"
                className="min-h-24 w-full rounded-md border bg-background p-3"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </label>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          {available.length > 0 && (
            <LoadingButton
              loading={mutation.isPending}
              disabled={!selected}
              onClick={() => mutation.mutate()}
            >
              创建任务
            </LoadingButton>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function WorkbenchEditor({
  item,
  canEdit,
  users,
  onClose,
}: {
  item: RemediationPublic | null
  canEdit: boolean
  users: Array<{ id: string; full_name?: string | null; email: string }>
  onClose: () => void
}) {
  const [status, setStatus] = useState<RemediationStatus>("PENDING")
  const [assigneeId, setAssigneeId] = useState("")
  const [dueDate, setDueDate] = useState("")
  const [fixedVersion, setFixedVersion] = useState("")
  const [notes, setNotes] = useState("")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  useEffect(() => {
    if (!item) return
    setStatus(item.status)
    setAssigneeId(item.assignee_id ?? "")
    setDueDate(item.due_date ?? "")
    setFixedVersion(item.fixed_version ?? "")
    setNotes(item.notes ?? "")
  }, [item])
  const mutation = useMutation({
    mutationFn: () =>
      RemediationsService.updateRemediation({
        path: { remediation_id: item!.id },
        body: {
          status,
          assignee_id: assigneeId || null,
          due_date: dueDate || null,
          fixed_version: fixedVersion.trim() || null,
          notes: notes.trim() || null,
        },
      }),
    onSuccess: () => {
      showSuccessToast("处置任务已更新")
      queryClient.invalidateQueries({ queryKey: ["remediation-workbench"] })
      queryClient.invalidateQueries({ queryKey: ["remediation-summary"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] })
      onClose()
    },
    onError: handleError.bind(showErrorToast),
  })
  const title = useMemo(
    () =>
      item ? `${item.cve_id} · ${item.component_name || "组件"}` : "处置任务",
    [item],
  )
  return (
    <Dialog
      open={Boolean(item)}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {canEdit
              ? "更新负责人、截止日期、修复版本和处置进度。"
              : "当前账号为只读权限。"}
          </DialogDescription>
        </DialogHeader>
        {item && (
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-1 text-sm">
              <span>处置状态</span>
              <select
                aria-label="工作台处置状态"
                disabled={!canEdit}
                className="h-9 w-full rounded-md border bg-background px-3"
                value={status}
                onChange={(event) =>
                  setStatus(event.target.value as RemediationStatus)
                }
              >
                {Object.entries(statusLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span>负责人</span>
              <select
                aria-label="工作台负责人"
                disabled={!canEdit}
                className="h-9 w-full rounded-md border bg-background px-3"
                value={assigneeId}
                onChange={(event) => setAssigneeId(event.target.value)}
              >
                <option value="">未分配</option>
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.full_name || user.email}
                  </option>
                ))}
              </select>
            </label>
            <label
              htmlFor="edit-remediation-due-date"
              className="space-y-1 text-sm"
            >
              <span>截止日期</span>
              <Input
                id="edit-remediation-due-date"
                disabled={!canEdit}
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
              />
            </label>
            <label
              htmlFor="edit-remediation-fixed-version"
              className="space-y-1 text-sm"
            >
              <span>修复版本</span>
              <Input
                id="edit-remediation-fixed-version"
                disabled={!canEdit}
                value={fixedVersion}
                onChange={(event) => setFixedVersion(event.target.value)}
              />
            </label>
            <label className="space-y-1 text-sm sm:col-span-2">
              <span>处置备注</span>
              <textarea
                aria-label="工作台处置备注"
                disabled={!canEdit}
                className="min-h-28 w-full rounded-md border bg-background p-3"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </label>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            关闭
          </Button>
          {canEdit && (
            <LoadingButton
              loading={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              保存修改
            </LoadingButton>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
