import { expect, test } from "@playwright/test"

test("管理员可以完成组件 CRUD，重复 PURL 会提示冲突", async ({ page }) => {
  const suffix = Math.random().toString(36).slice(2, 9)
  const name = `000-e2e-${suffix}`
  const updatedName = `${name}-updated`
  const purl = `pkg:maven/org.example/${name}@1.0.0`

  await page.goto("/components")
  await expect(
    page.getByRole("heading", { name: "开源组件管理" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "新增组件" }).click()
  await page.getByLabel("PURL").fill(purl)
  await page.getByLabel("组件名称").fill(name)
  await page.getByLabel("版本").fill("1.0.0")
  await page.getByLabel("仓库地址").fill("https://example.com/e2e")
  await page.getByRole("button", { name: "创建组件" }).click()
  await expect(page.getByText("组件创建成功")).toBeVisible()

  const row = page.getByRole("row").filter({ hasText: purl })
  await expect(row).toBeVisible()
  await row.getByRole("button", { name: `查看 ${name}` }).click()
  await expect(page.getByRole("dialog")).toContainText(purl)
  await page.keyboard.press("Escape")

  await page.getByRole("button", { name: "新增组件" }).click()
  await page.getByLabel("PURL").fill(purl)
  await page.getByLabel("组件名称").fill(`${name}-duplicate`)
  await page.getByRole("button", { name: "创建组件" }).click()
  await expect(
    page.getByText("A component with this PURL already exists"),
  ).toBeVisible()
  await page.getByRole("button", { name: "取消" }).click()

  await row.getByRole("button", { name: `编辑 ${name}` }).click()
  await page.getByLabel("组件名称").fill(updatedName)
  await page.getByLabel("版本").fill("2.0.0")
  await page.getByRole("button", { name: "保存修改" }).click()
  await expect(page.getByText("组件信息已更新")).toBeVisible()

  const updatedRow = page.getByRole("row").filter({ hasText: purl })
  await expect(updatedRow).toContainText(updatedName)
  await updatedRow.getByRole("button", { name: `删除 ${updatedName}` }).click()
  await expect(
    page.getByRole("heading", { name: "确认删除组件？" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "确认删除" }).click()
  await expect(page.getByText("组件已删除")).toBeVisible()
  await expect(page.getByText(purl)).not.toBeVisible()
})

test("组件页面支持搜索和无数据状态", async ({ page }) => {
  await page.goto("/components")
  await page
    .getByLabel("搜索组件")
    .fill("definitely-not-existing-component-xyz")
  await page.getByRole("button", { name: "查询" }).click()
  await expect(
    page.getByRole("heading", { name: "没有找到组件" }),
  ).toBeVisible()
})
