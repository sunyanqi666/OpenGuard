import {
  Boxes,
  ClipboardCheck,
  ClipboardList,
  Home,
  ShieldAlert,
  Users,
} from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [
  { icon: Home, title: "仪表盘", path: "/" },
  { icon: ShieldAlert, title: "CVE 漏洞", path: "/vulnerabilities" },
  { icon: Boxes, title: "开源组件", path: "/components" },
  { icon: ClipboardCheck, title: "处置工作台", path: "/remediations" },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()

  const canAudit = currentUser?.is_superuser || currentUser?.role === "SECURITY"
  const items = [
    ...baseItems,
    ...(canAudit
      ? [{ icon: ClipboardList, title: "审计日志", path: "/audit" }]
      : []),
    ...(currentUser?.is_superuser
      ? [{ icon: Users, title: "用户管理", path: "/admin" }]
      : []),
  ]

  return (
    <Sidebar collapsible="icon" className="border-sidebar-border/70">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
