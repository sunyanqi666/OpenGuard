import { Download, Upload } from "lucide-react"
import { useRef, useState } from "react"

import { TransfersService } from "@/client"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const download = async (path: string, filename: string) => {
  const token = localStorage.getItem("access_token")
  const response = await fetch(path, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error("导出失败")
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export const ComponentTransferButtons = ({
  search,
  ecosystem,
  isAdmin,
}: {
  search: string
  ecosystem: string
  isAdmin: boolean
}) => {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const importFile = async (file?: File) => {
    if (!file) return
    setBusy(true)
    try {
      const result = (
        await TransfersService.importComponentsCsv({ body: { file } })
      ).data
      showSuccessToast(
        `导入完成：新增 ${result.created}，更新 ${result.updated}，失败 ${result.failed}`,
      )
    } catch (error) {
      handleError.bind(showErrorToast)(
        error instanceof Error ? error : new Error("导入失败"),
      )
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ""
    }
  }
  return (
    <div className="flex flex-wrap gap-2">
      {isAdmin && (
        <>
          <input
            ref={inputRef}
            className="hidden"
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => importFile(event.target.files?.[0])}
          />
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="mr-2 h-4 w-4" />
            导入 CSV
          </Button>
        </>
      )}
      <Button
        variant="outline"
        onClick={() =>
          download(
            `/api/v1/transfers/components/export?search=${encodeURIComponent(search)}&ecosystem=${encodeURIComponent(ecosystem)}`,
            "components.csv",
          )
        }
      >
        <Download className="mr-2 h-4 w-4" />
        导出当前结果
      </Button>
      <Button
        variant="outline"
        onClick={() =>
          download(
            "/api/v1/transfers/high-risk-components/export",
            "high-risk-components.csv",
          )
        }
      >
        <Download className="mr-2 h-4 w-4" />
        高风险清单
      </Button>
    </div>
  )
}

export const VulnerabilityExportButton = ({
  search,
  severity,
}: {
  search: string
  severity: string
}) => (
  <Button
    variant="outline"
    onClick={() =>
      download(
        `/api/v1/transfers/vulnerabilities/export?search=${encodeURIComponent(search)}${severity && severity !== "ALL" ? `&severity=${severity}` : ""}`,
        "vulnerabilities.csv",
      )
    }
  >
    <Download className="mr-2 h-4 w-4" />
    导出当前结果
  </Button>
)
