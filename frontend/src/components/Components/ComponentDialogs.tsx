import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Eye, Pencil, Plus, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type ComponentPublic, ComponentsService } from "@/client"
import { AssociationPanel } from "@/components/Associations/AssociationPanel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const optionalUrl = z
  .string()
  .refine(
    (value) => value === "" || /^https?:\/\//.test(value),
    "请输入 HTTP 或 HTTPS 地址",
  )

const componentSchema = z.object({
  purl: z
    .string()
    .startsWith("pkg:", "PURL 必须以 pkg: 开头")
    .refine((value) => value.includes("/"), "PURL 必须包含包路径"),
  name: z.string().trim().min(1, "组件名称不能为空"),
  ecosystem: z.string(),
  vendor: z.string(),
  version: z.string(),
  language: z.string(),
  repository: optionalUrl,
  description: z.string(),
})

type ComponentFormData = z.infer<typeof componentSchema>

const emptyValues: ComponentFormData = {
  purl: "pkg:maven/",
  name: "",
  ecosystem: "maven",
  vendor: "",
  version: "",
  language: "java",
  repository: "",
  description: "",
}

export const AddComponent = () => <ComponentFormDialog mode="create" />

export const EditComponent = ({
  component,
}: {
  component: ComponentPublic
}) => <ComponentFormDialog mode="edit" component={component} />

const ComponentFormDialog = ({
  mode,
  component,
}: {
  mode: "create" | "edit"
  component?: ComponentPublic
}) => {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const form = useForm<ComponentFormData>({
    resolver: zodResolver(componentSchema),
    defaultValues: emptyValues,
  })

  useEffect(() => {
    if (!open) return
    form.reset(
      component
        ? {
            purl: component.purl,
            name: component.name,
            ecosystem: component.ecosystem ?? "",
            vendor: component.vendor ?? "",
            version: component.version ?? "",
            language: component.language ?? "",
            repository: component.repository ?? "",
            description: component.description ?? "",
          }
        : emptyValues,
    )
  }, [component, form, open])

  const mutation = useMutation({
    mutationFn: async (data: ComponentFormData) => {
      const body = {
        purl: data.purl.trim(),
        name: data.name.trim(),
        ecosystem: data.ecosystem.trim() || null,
        vendor: data.vendor.trim() || null,
        version: data.version.trim() || null,
        language: data.language.trim() || null,
        repository: data.repository.trim() || null,
        description: data.description.trim() || null,
      }
      return mode === "create"
        ? ComponentsService.createComponent({ body })
        : ComponentsService.updateComponent({
            path: { component_id: component!.id },
            body,
          })
    },
    onSuccess: () => {
      showSuccessToast(mode === "create" ? "组件创建成功" : "组件信息已更新")
      setOpen(false)
      queryClient.invalidateQueries({ queryKey: ["components"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {mode === "create" ? (
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            新增组件
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            aria-label={`编辑 ${component?.name}`}
          >
            <Pencil className="h-4 w-4" />
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "新增组件" : `编辑 ${component?.name}`}
          </DialogTitle>
          <DialogDescription>
            填写组件标识和基础元数据，PURL 必须保持唯一。
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
            className="space-y-4"
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                control={form.control}
                name="purl"
                label="PURL"
                required
                placeholder="pkg:maven/group/artifact@1.0.0"
              />
              <Field
                control={form.control}
                name="name"
                label="组件名称"
                required
                placeholder="artifact"
              />
              <Field
                control={form.control}
                name="ecosystem"
                label="生态类型"
                placeholder="maven"
              />
              <Field
                control={form.control}
                name="vendor"
                label="厂商/组织"
                placeholder="org.example"
              />
              <Field
                control={form.control}
                name="version"
                label="版本"
                placeholder="1.0.0"
              />
              <Field
                control={form.control}
                name="language"
                label="开发语言"
                placeholder="java"
              />
              <div className="sm:col-span-2">
                <Field
                  control={form.control}
                  name="repository"
                  label="仓库地址"
                  placeholder="https://github.com/example/project"
                />
              </div>
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel>组件描述</FormLabel>
                    <FormControl>
                      <textarea
                        className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline">
                  取消
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                {mode === "create" ? "创建组件" : "保存修改"}
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

const Field = ({ control, name, label, required, placeholder }: any) => (
  <FormField
    control={control}
    name={name}
    render={({ field }) => (
      <FormItem>
        <FormLabel>
          {label}
          {required && <span className="text-destructive"> *</span>}
        </FormLabel>
        <FormControl>
          <Input placeholder={placeholder} {...field} />
        </FormControl>
        <FormMessage />
      </FormItem>
    )}
  />
)

export const ComponentDetails = ({
  component,
}: {
  component: ComponentPublic
}) => (
  <Dialog>
    <DialogTrigger asChild>
      <Button variant="ghost" size="sm" aria-label={`查看 ${component.name}`}>
        <Eye className="h-4 w-4" />
      </Button>
    </DialogTrigger>
    <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>{component.name}</DialogTitle>
        <DialogDescription className="break-all">
          {component.purl}
        </DialogDescription>
      </DialogHeader>
      <div className="flex flex-wrap gap-2">
        {component.ecosystem && (
          <Badge variant="secondary">{component.ecosystem}</Badge>
        )}
        {component.language && (
          <Badge variant="outline">{component.language}</Badge>
        )}
        {component.version && <Badge>v{component.version}</Badge>}
      </div>
      <dl className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
        <Detail label="厂商/组织" value={component.vendor} />
        <Detail label="CPE" value={component.cpe} />
        <Detail label="许可证" value={component.license} />
        <Detail label="发布日期" value={formatDate(component.publish_date)} />
        <div className="sm:col-span-2">
          <dt className="text-muted-foreground">组件描述</dt>
          <dd className="mt-1 whitespace-pre-wrap">
            {component.description || "暂无描述"}
          </dd>
        </div>
        {component.repository && (
          <div className="sm:col-span-2">
            <dt className="text-muted-foreground">代码仓库</dt>
            <dd className="mt-1 break-all">
              <a
                className="text-primary underline"
                href={component.repository}
                target="_blank"
                rel="noreferrer"
              >
                {component.repository}
              </a>
            </dd>
          </div>
        )}
      </dl>
      <AssociationPanel componentId={component.id} />
    </DialogContent>
  </Dialog>
)

export const DeleteComponent = ({
  component,
}: {
  component: ComponentPublic
}) => {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const mutation = useMutation({
    mutationFn: () =>
      ComponentsService.deleteComponent({
        path: { component_id: component.id },
      }),
    onSuccess: () => {
      showSuccessToast("组件已删除")
      setOpen(false)
      queryClient.invalidateQueries({ queryKey: ["components"] })
    },
    onError: handleError.bind(showErrorToast),
  })
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="text-destructive"
          aria-label={`删除 ${component.name}`}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>确认删除组件？</DialogTitle>
          <DialogDescription>
            将永久删除 {component.name} 及其漏洞关联和处置记录，此操作无法撤销。
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">取消</Button>
          </DialogClose>
          <LoadingButton
            variant="destructive"
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            确认删除
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

const Detail = ({ label, value }: { label: string; value?: string | null }) => (
  <div>
    <dt className="text-muted-foreground">{label}</dt>
    <dd className="mt-1 break-words">{value || "—"}</dd>
  </div>
)
const formatDate = (value?: string | null) =>
  value ? new Date(value).toLocaleDateString("zh-CN") : "—"
