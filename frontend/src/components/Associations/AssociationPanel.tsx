import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link2, Search, Trash2 } from "lucide-react"
import { useState } from "react"

import {
  AssociationsService,
  ComponentsService,
  type MatchMethod,
} from "@/client"
import { RemediationEditor } from "@/components/Remediations/RemediationEditor"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

type Props =
  | { vulnerabilityId: string; componentId?: never }
  | { componentId: string; vulnerabilityId?: never }

const methodLabels: Record<MatchMethod, string> = {
  MANUAL: "人工",
  CPE: "CPE",
  NAME: "名称/厂商",
  IMPORT: "数据导入",
}

export const AssociationPanel = (props: Props) => {
  const { user } = useAuth()
  const canEdit = Boolean(user?.is_superuser || user?.role === "SECURITY")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [search, setSearch] = useState("")
  const [versionRange, setVersionRange] = useState("")
  const [sourceReference, setSourceReference] = useState("")
  const vulnerabilityId = props.vulnerabilityId
  const componentId = props.componentId
  const queryKey = ["associations", { vulnerabilityId, componentId }]

  const associations = useQuery({
    queryKey,
    queryFn: async () =>
      (
        await AssociationsService.readAssociations({
          query: {
            vulnerability_id: vulnerabilityId,
            component_id: componentId,
          },
        })
      ).data,
  })
  const suggestions = useQuery({
    queryKey: ["association-suggestions", vulnerabilityId],
    enabled: Boolean(vulnerabilityId && canEdit),
    queryFn: async () =>
      (
        await AssociationsService.readAssociationSuggestions({
          query: { vulnerability_id: vulnerabilityId! },
        })
      ).data,
  })
  const componentSearch = useQuery({
    queryKey: ["association-component-search", search],
    enabled: Boolean(vulnerabilityId && canEdit && search.trim()),
    queryFn: async () =>
      (
        await ComponentsService.readComponents({
          query: { search: search.trim(), limit: 8 },
        })
      ).data,
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["associations"] })
    queryClient.invalidateQueries({ queryKey: ["association-suggestions"] })
  }
  const create = useMutation({
    mutationFn: ({ id, method }: { id: string; method: MatchMethod }) =>
      AssociationsService.createAssociation({
        body: {
          vulnerability_id: vulnerabilityId!,
          component_id: id,
          match_method: method,
          affected_version_range: versionRange.trim() || null,
          source_reference: sourceReference.trim() || null,
        },
      }),
    onSuccess: () => {
      showSuccessToast("漏洞与组件已关联")
      setSearch("")
      setVersionRange("")
      setSourceReference("")
      refresh()
    },
    onError: handleError.bind(showErrorToast),
  })
  const remove = useMutation({
    mutationFn: (id: string) =>
      AssociationsService.deleteAssociation({ path: { association_id: id } }),
    onSuccess: () => {
      showSuccessToast("关联已解除")
      refresh()
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <section className="space-y-3 border-t pt-4">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-semibold">
          <Link2 className="h-4 w-4" />
          {vulnerabilityId ? "受影响组件" : "关联漏洞"}
        </h3>
        <Badge variant="secondary">{associations.data?.count ?? 0} 条</Badge>
      </div>

      {associations.isPending ? (
        <p className="text-sm text-muted-foreground">正在加载关联…</p>
      ) : associations.isError ? (
        <p className="text-sm text-destructive">关联数据加载失败</p>
      ) : associations.data?.data.length ? (
        <div className="space-y-2">
          {associations.data.data.map((item) => (
            <div
              key={item.id}
              className="flex items-start justify-between gap-3 rounded-md border p-3 text-sm"
            >
              <div className="min-w-0">
                <div className="font-medium">
                  {vulnerabilityId ? item.component_name : item.cve_id}
                </div>
                <div className="break-all text-xs text-muted-foreground">
                  {vulnerabilityId ? item.component_purl : item.severity}
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  <Badge variant="outline">
                    {methodLabels[item.match_method]}
                  </Badge>
                  {item.affected_version_range && (
                    <Badge variant="outline">
                      影响版本 {item.affected_version_range}
                    </Badge>
                  )}
                  {item.source_reference && (
                    <Badge variant="outline">
                      来源 {item.source_reference}
                    </Badge>
                  )}
                </div>
                <RemediationEditor
                  vulnerabilityId={item.vulnerability_id}
                  componentId={item.component_id}
                />
              </div>
              {canEdit && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive"
                  aria-label={`解除关联 ${vulnerabilityId ? item.component_name : item.cve_id}`}
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(item.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground">
          暂无已确认关联
        </p>
      )}

      {vulnerabilityId && canEdit && (
        <div className="space-y-3 rounded-md bg-muted/40 p-3">
          <h4 className="text-sm font-medium">建立关联</h4>
          <div className="grid gap-2 sm:grid-cols-2">
            <Input
              aria-label="影响版本范围"
              placeholder="影响版本，例如 [1.0,2.0)"
              value={versionRange}
              onChange={(event) => setVersionRange(event.target.value)}
            />
            <Input
              aria-label="关联来源"
              placeholder="来源，例如教师数据/CVE 公告"
              value={sourceReference}
              onChange={(event) => setSourceReference(event.target.value)}
            />
          </div>

          {suggestions.data?.length ? (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                按 CPE、组件名称或厂商生成的建议（需人工确认）
              </p>
              {suggestions.data.slice(0, 3).map((suggestion) => (
                <div
                  key={suggestion.component.id}
                  className="flex items-center justify-between gap-2 rounded-md border bg-background p-2 text-sm"
                >
                  <div className="min-w-0">
                    <div className="truncate font-medium">
                      {suggestion.component.name}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {suggestion.reason} · 置信度 {suggestion.confidence}
                    </div>
                  </div>
                  <LoadingButton
                    size="sm"
                    variant="outline"
                    loading={create.isPending}
                    onClick={() =>
                      create.mutate({
                        id: suggestion.component.id,
                        method: suggestion.match_method,
                      })
                    }
                  >
                    确认
                  </LoadingButton>
                </div>
              ))}
            </div>
          ) : null}

          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              aria-label="搜索待关联组件"
              className="pl-9"
              placeholder="按名称、PURL 或厂商搜索组件"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          {componentSearch.data?.data.map((component) => (
            <div
              key={component.id}
              className="flex items-center justify-between gap-2 rounded-md border bg-background p-2 text-sm"
            >
              <div className="min-w-0">
                <div className="truncate font-medium">{component.name}</div>
                <div className="truncate text-xs text-muted-foreground">
                  {component.purl}
                </div>
              </div>
              <LoadingButton
                size="sm"
                loading={create.isPending}
                onClick={() =>
                  create.mutate({ id: component.id, method: "MANUAL" })
                }
              >
                关联
              </LoadingButton>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
