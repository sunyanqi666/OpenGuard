import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Boxes, Link2, ListTodo, ShieldAlert } from "lucide-react"
import type { ReactNode } from "react"

import { DashboardService } from "@/client"
import { ParticleField } from "@/components/Common/ParticleField"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({ meta: [{ title: "安全态势 - OpenGuard" }] }),
})

const severityLabels: Record<string, string> = {
  CRITICAL: "严重",
  HIGH: "高危",
  MEDIUM: "中危",
  LOW: "低危",
  UNKNOWN: "未知",
}
const statusLabels: Record<string, string> = {
  PENDING: "待评估",
  IN_PROGRESS: "处理中",
  FIXED: "已修复",
  IGNORED: "已忽略",
}

function Dashboard() {
  const query = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: async () => (await DashboardService.readDashboardSummary()).data,
  })
  if (query.isPending)
    return (
      <div className="grid gap-4 md:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <Skeleton key={index} className="h-36" />
        ))}
      </div>
    )
  if (query.isError || !query.data)
    return (
      <div className="rounded-lg border border-destructive p-6 text-destructive">
        安全态势数据加载失败，请稍后重试。
      </div>
    )
  const data = query.data
  return (
    <div className="space-y-6 animate-ui-reveal">
      <section className="relative overflow-hidden rounded-2xl bg-zinc-950 px-6 py-7 text-white shadow-[0_24px_70px_rgba(0,0,0,.24)] md:px-8">
        <ParticleField className="opacity-65" />
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_80%_15%,rgba(85,115,255,.13),transparent_26%)]" />
        <div className="relative z-10 flex flex-wrap items-end justify-between gap-5">
          <div>
            <h1 className="text-3xl font-semibold tracking-[-0.035em]">
              安全态势仪表盘
            </h1>
            <p className="mt-2 text-sm text-zinc-400">
              基于当前数据库实时统计漏洞、组件关联和处置进度
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <span className="size-1.5 rounded-full bg-white shadow-[0_0_14px_white]" />
            实时数据服务在线
          </div>
        </div>
      </section>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          href="/vulnerabilities"
          label="CVE 漏洞"
          value={data.vulnerability_count}
          icon={<ShieldAlert />}
        />
        <Stat
          href="/components"
          label="开源组件"
          value={data.component_count}
          icon={<Boxes />}
        />
        <Stat
          label="已确认关联"
          value={data.association_count}
          icon={<Link2 />}
        />
        <Stat
          label="待处理风险"
          value={data.pending_risk_count}
          icon={<ListTodo />}
          danger
        />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="漏洞严重等级分布">
          <Bars
            data={data.severity_distribution.map((item) => ({
              ...item,
              label: severityLabels[item.label] ?? item.label,
            }))}
          />
        </Panel>
        <Panel title="CVSS 评分分布">
          <Bars data={data.cvss_distribution} />
        </Panel>
        <Panel title="近 12 个月发布时间趋势">
          <Bars data={data.publication_trend} />
        </Panel>
        <Panel title="风险处置状态">
          <Bars
            data={data.remediation_distribution.map((item) => ({
              ...item,
              label: statusLabels[item.label] ?? item.label,
            }))}
          />
        </Panel>
      </div>
      <Panel title="高风险组件排行">
        {data.high_risk_components.length ? (
          <div className="space-y-2">
            {data.high_risk_components.map((item, index) => (
              <div
                key={item.component_id}
                className="flex items-center justify-between gap-3 rounded-md border p-3 text-sm"
              >
                <div className="min-w-0">
                  <span className="mr-3 text-muted-foreground">
                    #{index + 1}
                  </span>
                  <span className="font-medium">{item.name}</span>
                  <div className="ml-7 truncate text-xs text-muted-foreground">
                    {item.purl}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Badge className="bg-purple-600">
                    严重 {item.critical_count}
                  </Badge>
                  <Badge variant="destructive">高危 {item.high_count}</Badge>
                  <Badge variant="outline">合计 {item.total_count}</Badge>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">
            建立漏洞组件关联后将在这里显示排行
          </p>
        )}
      </Panel>
    </div>
  )
}

const Stat = ({
  label,
  value,
  icon,
  href,
  danger,
}: {
  label: string
  value: number
  icon: ReactNode
  href?: "/vulnerabilities" | "/components"
  danger?: boolean
}) => {
  const content = (
    <div className="animate-data-rise rounded-xl border bg-card p-5 transition duration-200 hover:-translate-y-0.5 hover:border-foreground/25 hover:shadow-lg">
      <div className="flex items-center justify-between text-muted-foreground">
        <span className="text-sm">{label}</span>
        <span className={danger ? "text-red-600" : "text-foreground"}>
          {icon}
        </span>
      </div>
      <div className="mt-4 text-3xl font-semibold tracking-tight tabular-nums">
        {value.toLocaleString("zh-CN")}
      </div>
    </div>
  )
  return href ? <Link to={href}>{content}</Link> : content
}
const Panel = ({ title, children }: { title: string; children: ReactNode }) => (
  <section className="rounded-xl border bg-card p-5">
    <h2 className="mb-5 text-sm font-semibold">{title}</h2>
    {children}
  </section>
)
const Bars = ({ data }: { data: Array<{ label: string; count: number }> }) => {
  const max = Math.max(...data.map((item) => item.count), 1)
  return (
    <div className="space-y-3">
      {data.map((item) => (
        <div
          key={item.label}
          className="grid grid-cols-[72px_1fr_52px] items-center gap-3 text-sm"
        >
          <span>{item.label}</span>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full origin-left animate-[data-bar_700ms_cubic-bezier(.16,1,.3,1)_both] rounded-full bg-foreground"
              style={{ width: `${(item.count / max) * 100}%` }}
            />
          </div>
          <span className="text-right tabular-nums">{item.count}</span>
        </div>
      ))}
    </div>
  )
}
