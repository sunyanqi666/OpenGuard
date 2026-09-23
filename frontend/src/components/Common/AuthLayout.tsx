import { Appearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { ParticleField } from "@/components/Common/ParticleField"
import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="grid min-h-svh bg-background lg:grid-cols-[1.12fr_.88fr]">
      <div className="relative hidden overflow-hidden border-r border-white/10 bg-zinc-950 text-white lg:flex lg:flex-col lg:justify-between lg:p-12">
        <ParticleField className="opacity-80" />
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_75%_20%,rgba(90,120,255,.12),transparent_26%)]" />
        <div className="relative z-10">
          <Logo variant="full" asLink={false} />
        </div>
        <div className="relative z-10 max-w-xl space-y-5">
          <h1 className="text-5xl font-semibold leading-[1.02] tracking-[-0.04em]">
            看清风险。
            <br />
            做出下一步。
          </h1>
          <p className="max-w-md text-sm leading-7 text-zinc-400">
            面向开源组件的漏洞信息、关联关系与处置进度管理平台。
          </p>
        </div>
        <div className="relative z-10 flex items-center gap-3 text-xs text-zinc-500">
          <span className="size-1.5 rounded-full bg-white shadow-[0_0_14px_white]" />
          安全数据服务在线
        </div>
      </div>
      <div className="flex flex-col gap-4 bg-background p-6 md:p-10">
        <div className="flex justify-end">
          <Appearance />
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-sm animate-ui-reveal">{children}</div>
        </div>
        <Footer />
      </div>
    </div>
  )
}
