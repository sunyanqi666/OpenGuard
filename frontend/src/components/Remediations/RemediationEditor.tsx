import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ClipboardCheck } from "lucide-react"
import { useEffect, useState } from "react"

import {
  type RemediationStatus,
  RemediationsService,
  UsersService,
} from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const labels: Record<RemediationStatus, string> = {
  PENDING: "待评估",
  IN_PROGRESS: "处理中",
  FIXED: "已修复",
  IGNORED: "已忽略",
}

export const RemediationEditor = ({
  vulnerabilityId,
  componentId,
}: {
  vulnerabilityId: string
  componentId: string
}) => {
  const { user } = useAuth()
  const canEdit = Boolean(user?.is_superuser || user?.role === "SECURITY")
  const [expanded, setExpanded] = useState(false)
  const [remediationStatus, setRemediationStatus] =
    useState<RemediationStatus>("PENDING")
  const [assigneeId, setAssigneeId] = useState("")
  const [dueDate, setDueDate] = useState("")
  const [fixedVersion, setFixedVersion] = useState("")
  const [notes, setNotes] = useState("")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryKey = ["remediation", vulnerabilityId, componentId]
  const query = useQuery({
    queryKey,
    queryFn: async () =>
      (
        await RemediationsService.readRemediations({
          query: {
            vulnerability_id: vulnerabilityId,
            component_id: componentId,
            limit: 1,
          },
        })
      ).data,
  })
  const users = useQuery({
    queryKey: ["remediation-users"],
    enabled: Boolean(canEdit && expanded),
    queryFn: async () =>
      (await UsersService.readUsers({ query: { limit: 100 } })).data,
  })
  const current = query.data?.data[0]
  useEffect(() => {
    if (current) {
      setRemediationStatus(current.status)
      setAssigneeId(current.assignee_id ?? "")
      setDueDate(current.due_date ?? "")
      setFixedVersion(current.fixed_version ?? "")
      setNotes(current.notes ?? "")
    }
  }, [current])
  const mutation = useMutation({
    mutationFn: () => {
      const body = {
        status: remediationStatus,
        assignee_id: assigneeId || null,
        due_date: dueDate || null,
        fixed_version: fixedVersion.trim() || null,
        notes: notes.trim() || null,
      }
      return current
        ? RemediationsService.updateRemediation({
            path: { remediation_id: current.id },
            body,
          })
        : RemediationsService.createRemediation({
            body: {
              vulnerability_id: vulnerabilityId,
              component_id: componentId,
              ...body,
            },
          })
    },
    onSuccess: () => {
      showSuccessToast("处置进度已保存")
      queryClient.invalidateQueries({ queryKey })
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] })
      setExpanded(false)
    },
    onError: handleError.bind(showErrorToast),
  })
  return (
    <div className="mt-2 border-t pt-2">
      <Button
        size="sm"
        variant="ghost"
        className="h-7 px-2 text-xs"
        onClick={() => setExpanded((value) => !value)}
      >
        <ClipboardCheck className="mr-1 h-3 w-3" />
        {current ? labels[current.status] : "添加处置"}
      </Button>
      {expanded && (
        <div className="mt-2 grid gap-2 rounded-md bg-muted/50 p-2 sm:grid-cols-2">
          <select
            aria-label="处置状态"
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={remediationStatus}
            onChange={(event) =>
              setRemediationStatus(event.target.value as RemediationStatus)
            }
          >
            {Object.entries(labels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            aria-label="负责人"
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={assigneeId}
            onChange={(event) => setAssigneeId(event.target.value)}
          >
            <option value="">未分配</option>
            {users.data?.data.map((item) => (
              <option key={item.id} value={item.id}>
                {item.full_name || item.email}
              </option>
            ))}
          </select>
          <Input
            aria-label="截止日期"
            type="date"
            value={dueDate}
            onChange={(event) => setDueDate(event.target.value)}
          />
          <Input
            aria-label="修复版本"
            placeholder="修复版本"
            value={fixedVersion}
            onChange={(event) => setFixedVersion(event.target.value)}
          />
          <textarea
            aria-label="处置备注"
            className="min-h-16 rounded-md border bg-background p-2 text-sm sm:col-span-2"
            placeholder="处置备注"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
          {canEdit && (
            <LoadingButton
              size="sm"
              className="sm:col-span-2"
              loading={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              保存处置
            </LoadingButton>
          )}
        </div>
      )}
    </div>
  )
}
