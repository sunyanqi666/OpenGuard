import { expect, test } from "@playwright/test"

test("处置工作台支持创建、逾期展示、筛选和快速更新", async ({
  page,
  request,
}) => {
  test.setTimeout(60_000)
  await page.goto("/")
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  const headers = { Authorization: `Bearer ${token}` }
  const vulnerabilities = await (
    await request.get("/api/v1/vulnerabilities/", {
      headers,
      params: { search: "CVE-2026-9999", limit: 1 },
    })
  ).json()
  const marker = `stage-ten-${Date.now()}`
  const component = await (
    await request.post("/api/v1/components/", {
      headers,
      data: {
        purl: `pkg:maven/org.example/${marker}@1.0.0`,
        name: marker,
        version: "1.0.0",
        ecosystem: "maven",
      },
    })
  ).json()
  const vulnerability = vulnerabilities.data[0]
  const association = await (
    await request.post("/api/v1/associations/", {
      headers,
      data: { vulnerability_id: vulnerability.id, component_id: component.id },
    })
  ).json()
  let remediationId: string | undefined

  try {
    await page.goto("/remediations")
    await expect(
      page.getByRole("heading", { name: "风险处置工作台" }),
    ).toBeVisible()
    await page.getByRole("button", { name: "新增处置任务" }).first().click()
    await page
      .getByLabel("选择漏洞组件关联")
      .selectOption({
        label: `${vulnerability.cve_id} · ${component.name} · ${component.purl}`,
      })
    await page.getByLabel("截止日期", { exact: true }).fill("2000-01-01")
    await page.getByLabel("新增任务备注").fill("stage-ten-overdue")
    await page.getByRole("button", { name: "创建任务" }).click()
    await expect(page.getByText("处置任务已创建")).toBeVisible()
    const created = await (
      await request.get("/api/v1/remediations/", {
        headers,
        params: { search: component.name, limit: 1 },
      })
    ).json()
    remediationId = created.data[0].id
    await expect(page.getByRole("button", { name: /已经逾期/ })).toBeVisible()
    await page.getByLabel("搜索处置任务").fill(component.name)
    await page.getByRole("button", { name: "查询" }).click()
    const row = page.getByRole("row").filter({ hasText: component.name })
    await expect(row).toContainText("已逾期")
    await row.getByRole("button", { name: "处理" }).click()
    await page.getByLabel("工作台处置状态").selectOption("FIXED")
    await page.getByLabel("修复版本", { exact: true }).fill("3.11.0")
    await page.getByRole("button", { name: "保存修改" }).click()
    await expect(page.getByText("处置任务已更新")).toBeVisible()
    await expect(row).toContainText("已修复")
    await expect(row).toContainText("3.11.0")
  } finally {
    if (remediationId)
      await request.delete(`/api/v1/remediations/${remediationId}`, { headers })
    await request.delete(`/api/v1/associations/${association.id}`, { headers })
    await request.delete(`/api/v1/components/${component.id}`, { headers })
  }
})
