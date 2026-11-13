import { test, expect, type Page } from "@playwright/test";
async function fill(page: Page, kind = "home_visit") {
  await page
    .getByRole("combobox", { name: "服务类型", exact: true })
    .selectOption(kind);
  await page.locator("input[type=checkbox]").first().check();
  await page.getByLabel("可开始时间").fill("2026-12-01T18:00");
  await page.getByLabel("最晚结束时间").fill("2026-12-01T19:00");
  await page.getByLabel("服务地点").fill("隐私门牌-A101");
  await page.getByLabel("交接方式").fill("当面交接");
  await page.getByLabel("异常联系人").fill("演示联系人");
  for (const input of await page.getByLabel("事项内容").all())
    await input.fill("按明确要求照料");
  for (const input of await page.getByLabel("完成条件").all())
    await input.fill("记录时间与备注，宠主核对");
  if (kind === "errand_buy") {
    await page.getByLabel("商品名称与规格").fill("指定品牌猫粮 2kg");
    await page.getByLabel("数量", { exact: true }).fill("1");
    await page.getByLabel("单位", { exact: true }).fill("袋");
    await page.getByLabel("商品预算上限").fill("100");
  }
  await page.getByRole("button", { name: "检查草稿" }).click();
  await page.getByRole("checkbox").check();
}
test("三类模拟需求、草稿编辑与公开隐私", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  for (const kind of ["home_visit", "dog_walking", "errand_buy"]) {
    await fill(page, kind);
    await page.getByRole("button", { name: "保存草稿", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("已保存");
    await page.getByRole("button", { name: "确认发布已保存版本" }).click();
    await page.getByRole("button", { name: "社区大厅", exact: true }).click();
    await page.getByRole("button", { name: "查看详情" }).first().click();
    await expect(page.locator("main")).not.toContainText("隐私门牌");
    await page.getByRole("button", { name: "发布需求", exact: true }).click();
    await page.getByRole("button", { name: "新建空白需求" }).click();
  }
  expect(errors).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("新增与编辑宠物档案", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "基础档案", exact: true }).click();
  await page.getByLabel("宠物名字").fill("汤圆");
  await page.getByLabel("出生日期").fill("2024-01-01");
  await page.getByRole("button", { name: "保存宠物档案" }).click();
  await expect(page.getByRole("heading", { name: "汤圆 · 猫" })).toBeVisible();
  await page
    .locator("article")
    .filter({ has: page.getByRole("heading", { name: "汤圆 · 猫" }) })
    .getByRole("button")
    .click();
  await page.getByLabel("宠物名字").fill("小汤圆");
  await page.getByRole("button", { name: "保存宠物档案" }).click();
  await expect(
    page.getByRole("heading", { name: "小汤圆 · 猫" }),
  ).toBeVisible();
});
test("修改草稿后阻止发布旧版本", async ({ page }) => {
  await page.goto("/");
  await fill(page);
  await page.getByRole("button", { name: "保存草稿", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存");
  await page.getByRole("button", { name: "返回编辑" }).click();
  await page.getByLabel("服务地点").fill("修改后的交接点");
  await page.getByRole("button", { name: "检查草稿" }).click();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "确认发布已保存版本" }).click();
  await expect(page.getByRole("status")).toContainText("请重新保存");
  await page.getByRole("button", { name: "保存草稿", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存");
  await page.getByRole("button", { name: "确认发布已保存版本" }).click();
  await expect(
    page.getByRole("heading", { name: "我的需求", exact: true }),
  ).toBeVisible();
});
test("契约桩：登录、503回退、创建与发布分离、时区和金额", async ({ page }) => {
  let created: any = null;
  let published: any = null;
  let auth = "";
  await page.route("http://127.0.0.1:8000/api/v0/**", async (route) => {
    const req = route.request(),
      path = new URL(req.url()).pathname;
    auth = req.headers()["authorization"] || auth;
    let data: any = {};
    let status = 200;
    if (path.endsWith("/auth/login"))
      data = { access_token: "test-only-token" };
    else if (path.endsWith("/users/me")) data = { display_name: "测试宠主" };
    else if (path.endsWith("/pets"))
      data = {
        items: [
          {
            id: "00000000-0000-0000-0000-000000000001",
            name: "测试猫",
            species: "cat",
            birth_date: "2024-01-01",
          },
        ],
        next_cursor: null,
      };
    else if (path.endsWith("/ai/parse")) {
      status = 503;
      data = { code: "ai_unavailable", message: "AI 暂不可用，请手动填写" };
    } else if (path.endsWith("/publish")) {
      published = req.postDataJSON();
      data = {
        ...created,
        id: "request-1",
        version: 1,
        status: "pending_match",
      };
    } else if (path.endsWith("/requests") && req.method() === "POST") {
      created = req.postDataJSON();
      data = { ...created, id: "request-1", version: 1, status: "draft" };
      expect(req.headers()["idempotency-key"]).toBeTruthy();
    } else data = { items: [], next_cursor: null };
    await route.fulfill({ status, json: data });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "连接设置" }).click();
  await page.getByLabel("工作模式").selectOption("api");
  await page.getByLabel("账号", { exact: true }).fill("test");
  await page.getByLabel("密码", { exact: true }).fill("test-password");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已连接");
  await page.getByRole("button", { name: "发布需求", exact: true }).click();
  await page.getByLabel("一句话描述需求").fill("帮忙换水");
  await page.getByRole("button", { name: "请求 AI 解析" }).click();
  await expect(page.getByRole("status")).toContainText("AI 暂不可用");
  await expect(page.getByLabel("一句话描述需求")).toHaveValue("帮忙换水");
  await fill(page);
  await page.getByRole("button", { name: "保存草稿", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存");
  expect(created.window_start).toBe("2026-12-01T18:00:00+08:00");
  expect(created.budget).toBe("0.00");
  expect(created.status).toBeUndefined();
  expect(published).toBeNull();
  expect(auth).toBe("Bearer test-only-token");
  await page.getByRole("button", { name: "确认发布已保存版本" }).click();
  await expect.poll(() => published).toEqual({ expected_version: 1 });
});
