import { expect, test } from "@playwright/test"

test("安全态势首页展示真实统计和图表", async ({ page, request }) => {
  await page.goto("/")
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  const summary = await (
    await request.get("/api/v1/dashboard/summary", {
      headers: { Authorization: `Bearer ${token}` },
    })
  ).json()
  await expect(
    page.getByRole("heading", { name: "安全态势仪表盘" }),
  ).toBeVisible()
  await expect(
    page.getByRole("link", { name: "CVE 漏洞", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByText(summary.vulnerability_count.toLocaleString("en-US")),
  ).toBeVisible()
  await expect(
    page.getByText(summary.component_count.toLocaleString("en-US")),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "漏洞严重等级分布" }),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "CVSS 评分分布" }),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "风险处置状态" }),
  ).toBeVisible()
})

test("管理员可以保存风险处置并持久化", async ({ page, request }) => {
  await page.goto("/")
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  const headers = { Authorization: `Bearer ${token}` }
  const vulnerabilities = await (
    await request.get("/api/v1/vulnerabilities/", {
      headers,
      params: { search: "CVE-2026-9999", limit: 1 },
    })
  ).json()
  const components = await (
    await request.get("/api/v1/components/", {
      headers,
      params: { search: "aiohttp", limit: 1 },
    })
  ).json()
  const vulnerability = vulnerabilities.data[0]
  const component = components.data[0]
  const existing = await (
    await request.get("/api/v1/associations/", {
      headers,
      params: { vulnerability_id: vulnerability.id },
    })
  ).json()
  for (const item of existing.data)
    if (item.component_id === component.id)
      await request.delete(`/api/v1/associations/${item.id}`, { headers })
  const association = await (
    await request.post("/api/v1/associations/", {
      headers,
      data: { vulnerability_id: vulnerability.id, component_id: component.id },
    })
  ).json()

  await page.goto("/vulnerabilities")
  await page.getByLabel("搜索漏洞").fill(vulnerability.cve_id)
  await page.getByRole("button", { name: "查询" }).click()
  await page
    .getByRole("row")
    .filter({ hasText: vulnerability.cve_id })
    .getByRole("button", { name: `查看 ${vulnerability.cve_id}` })
    .click()
  const dialog = page.getByRole("dialog")
  await dialog.getByRole("button", { name: "添加处置" }).click()
  await dialog.getByLabel("处置状态").selectOption("IN_PROGRESS")
  await dialog.getByLabel("截止日期").fill("2026-12-31")
  await dialog.getByLabel("修复版本").fill("3.10.1")
  await dialog.getByLabel("处置备注").fill("升级并完成回归测试")
  await dialog.getByRole("button", { name: "保存处置" }).click()
  await expect(page.getByText("处置进度已保存")).toBeVisible()

  const saved = await (
    await request.get("/api/v1/remediations/", {
      headers,
      params: {
        vulnerability_id: vulnerability.id,
        component_id: component.id,
      },
    })
  ).json()
  expect(saved.data[0].status).toBe("IN_PROGRESS")
  expect(saved.data[0].fixed_version).toBe("3.10.1")
  await request.delete(`/api/v1/remediations/${saved.data[0].id}`, { headers })
  await request.delete(`/api/v1/associations/${association.id}`, { headers })
})
