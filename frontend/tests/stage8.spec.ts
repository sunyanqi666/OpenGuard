import { expect, test } from "@playwright/test"

test("管理员可以查看审计日志并导入组件 CSV", async ({ page, request }) => {
  await page.goto("/audit")
  await expect(page.getByRole("heading", { name: "审计日志" })).toBeVisible()
  await expect(page.getByLabel("操作类型")).toBeVisible()

  await page.goto("/components")
  await expect(page.getByRole("button", { name: "导出当前结果" })).toBeVisible()
  await expect(page.getByRole("button", { name: "高风险清单" })).toBeVisible()
  await page.locator('input[type="file"]').setInputFiles({
    name: "components.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "purl,name,version,ecosystem,vendor,language\n" +
        "pkg:maven/org.example/e2e-stage-eight,e2e-stage-eight,1.0.0,maven,org.example,java\n",
    ),
  })
  await expect(page.getByText(/导入完成：新增 1/)).toBeVisible()
  await page.getByLabel("搜索组件").fill("e2e-stage-eight")
  await page.getByRole("button", { name: "查询" }).click()
  await expect(
    page.getByRole("row").filter({ hasText: "e2e-stage-eight" }),
  ).toBeVisible()

  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  const headers = { Authorization: `Bearer ${token}` }
  const response = await request.get("/api/v1/components/", {
    headers,
    params: { search: "e2e-stage-eight", limit: 1 },
  })
  const component = (await response.json()).data[0]
  await request.delete(`/api/v1/components/${component.id}`, { headers })
})
