import type { ReactNode } from "react"

import { ParticleField } from "@/components/Common/ParticleField"

type PageHeaderProps = {
  title: string
  description: string
  icon?: ReactNode
  actions?: ReactNode
  signal?: string
}

export function PageHeader({
  title,
  description,
  icon,
  actions,
  signal = "安全数据通道在线",
}: PageHeaderProps) {
  return (
    <section className="relative isolate overflow-hidden rounded-2xl bg-zinc-950 px-5 py-6 text-white shadow-[0_20px_60px_rgba(0,0,0,.2)] md:px-7">
      <ParticleField className="opacity-50" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_82%_12%,rgba(110,130,255,.13),transparent_25%),linear-gradient(110deg,rgba(255,255,255,.035),transparent_42%)]" />
      <div className="relative z-10 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div className="flex min-w-0 items-start gap-3.5">
          {icon ? (
            <div className="mt-0.5 grid size-10 shrink-0 place-items-center rounded-xl border border-white/15 bg-white/[.07] text-zinc-100 shadow-[inset_0_1px_0_rgba(255,255,255,.08)] [&_svg]:size-5">
              {icon}
            </div>
          ) : null}
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-[-0.035em] md:text-[1.7rem]">
              {title}
            </h1>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-zinc-400">
              {description}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-3">
          {actions}
          <div className="flex items-center gap-2 whitespace-nowrap text-xs text-zinc-500">
            <span className="size-1.5 rounded-full bg-white shadow-[0_0_12px_rgba(255,255,255,.9)]" />
            {signal}
          </div>
        </div>
      </div>
    </section>
  )
}
