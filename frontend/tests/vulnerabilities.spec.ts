import { expect, test } from "@playwright/test"

const cveId = "CVE-2026-9999"

test.describe("CVE 漏洞管理", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/vulnerabilities")
    await expect(
      page.getByRole("heading", { name: "CVE 漏洞管理" }),
    ).toBeVisible()
  })

  test("支持检索、查看详情和分页状态", async ({ page }) => {
    await page.getByLabel("搜索漏洞").fill(cveId)
    await page.getByRole("button", { name: "查询" }).click()

    const row = page.getByRole("row").filter({ hasText: cveId })
    await expect(row).toBeVisible()
    await expect(page.getByText(/共 1 条/)).toBeVisible()
    await row.getByRole("button", { name: `查看 ${cveId}` }).click()
    await expect(page.getByRole("dialog")).toContainText(cveId)
    await expect(page.getByRole("dialog")).toContainText("漏洞描述")
  })

  test("管理员可以新增并删除 CVE", async ({ page }) => {
    const createdCveId = `CVE-2098-${Date.now()}`
    await page.getByRole("button", { name: "新增 CVE" }).click()
    const createDialog = page.getByRole("dialog", { name: "新增 CVE" })
    await createDialog.getByLabel("CVE 编号").fill(createdCveId)
    await createDialog.getByLabel("标题").fill("Playwright 新增 CVE")
    await createDialog.getByLabel("严重等级").selectOption("HIGH")
    await createDialog.getByLabel("CVSS v3").fill("8.1")
    await createDialog.getByRole("button", { name: "创建 CVE" }).click()
    await expect(page.getByText("CVE 创建成功")).toBeVisible()

    await page.getByLabel("搜索漏洞").fill(createdCveId)
    await page.getByRole("button", { name: "查询" }).click()
    const row = page.getByRole("row").filter({ hasText: createdCveId })
    await expect(row).toBeVisible()
    await row.getByRole("button", { name: `删除 ${createdCveId}` }).click()
    await page.getByRole("button", { name: "确认删除" }).click()
    await expect(page.getByText("漏洞记录已删除")).toBeVisible()
  })

  test("管理员可以修改漏洞并恢复测试字段", async ({ page, request }) => {
    await page.getByLabel("搜索漏洞").fill(cveId)
    await page.getByRole("button", { name: "查询" }).click()
    const row = page.getByRole("row").filter({ hasText: cveId })
    await row.getByRole("button", { name: `编辑 ${cveId}` }).click()
    await page.getByLabel("标题").fill("Playwright CVE 编辑验证")
    await page.getByRole("button", { name: "保存修改" }).click()
    await expect(page.getByText("漏洞信息已更新")).toBeVisible()

    const token = await page.evaluate(() =>
      localStorage.getItem("access_token"),
    )
    const response = await request.get("/api/v1/vulnerabilities/", {
      headers: { Authorization: `Bearer ${token}` },
      params: { search: cveId, limit: 1 },
    })
    const body = await response.json()
    await request.patch(`/api/v1/vulnerabilities/${body.data[0].id}`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { title: null },
    })
  })

  test("删除前必须二次确认且可以取消", async ({ page }) => {
    await page.getByLabel("搜索漏洞").fill(cveId)
    await page.getByRole("button", { name: "查询" }).click()
    const row = page.getByRole("row").filter({ hasText: cveId })
    await row.getByRole("button", { name: `删除 ${cveId}` }).click()
    await expect(
      page.getByRole("heading", { name: "确认删除漏洞？" }),
    ).toBeVisible()
    await page.getByRole("button", { name: "取消" }).click()
    await expect(row).toBeVisible()
  })

  test("管理员可以建立并解除组件关联", async ({ page, request }) => {
    const token = await page.evaluate(() =>
      localStorage.getItem("access_token"),
    )
    const headers = { Authorization: `Bearer ${token}` }
    const vulnerabilities = await (
      await request.get("/api/v1/vulnerabilities/", {
        headers,
        params: { search: cveId, limit: 1 },
      })
    ).json()
    const vulnerabilityId = vulnerabilities.data[0].id
    const marker = `association-${Date.now()}`
    const component = await (
      await request.post("/api/v1/components/", {
        headers,
        data: {
          purl: `pkg:maven/org.example/${marker}@1.0.0`,
          name: marker,
          ecosystem: "maven",
        },
      })
    ).json()

    await page.getByLabel("搜索漏洞").fill(cveId)
    await page.getByRole("button", { name: "查询" }).click()
    const row = page.getByRole("row").filter({ hasText: cveId })
    await row.getByRole("button", { name: `查看 ${cveId}` }).click()
    const dialog = page.getByRole("dialog")
    await dialog.getByLabel("影响版本范围").fill("[3.8,3.10)")
    await dialog.getByLabel("关联来源").fill("端到端测试")
    await dialog.getByLabel("搜索待关联组件").fill(marker)
    await dialog.getByRole("button", { name: "关联", exact: true }).click()
    await expect(page.getByText("漏洞与组件已关联")).toBeVisible()
    await expect(dialog).toContainText(component.name)
    await expect(dialog).toContainText("[3.8,3.10)")
    await dialog
      .getByRole("button", { name: `解除关联 ${component.name}` })
      .click()
    await expect(page.getByText("关联已解除")).toBeVisible()
    await expect(
      dialog.getByRole("button", { name: `解除关联 ${component.name}` }),
    ).not.toBeVisible()
    await request.delete(`/api/v1/components/${component.id}`, { headers })
  })
})
