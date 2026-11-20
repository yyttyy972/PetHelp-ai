import { test, expect, type Page } from "@playwright/test";
test("真实双账号浏览器：异常沟通、变更批准与重新确认", async ({
  browser,
  request,
}) => {
  test.setTimeout(60000);
  const base = "http://127.0.0.1:8000/api/v0";
  async function call(path: string, token: string, body?: unknown) {
    const response = await request.fetch(base + path, {
      method: body ? "POST" : "GET",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        "Idempotency-Key": crypto.randomUUID(),
      },
      data: body,
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  }
  const login = async (account: string) =>
    (await call("/auth/login", "", { account, password: "NeighborPet2026!" }))
      .access_token;
  const owner = await login("xiaolin"),
    helper = await login("jianguo"),
    now = Date.now(),
    slot = 10 * 86400000 + Math.floor(Math.random() * 100000) * 60000,
    iso = (n: number) => new Date(now + n).toISOString();
  const pet = await call("/pets", owner, {
    name: "异常流程测试犬",
    species: "dog",
    birth_date: "2024-01-01",
  });
  await call("/helpers/me/availability", helper, {
    start_at: iso(slot - 3600000),
    end_at: iso(slot + 7200000),
  });
  const demand = await call("/requests", owner, {
    pet_ids: [pet.id],
    service_type: "home_visit",
    fee_type: "free",
    window_start: iso(slot - 120000),
    window_end: iso(slot + 3600000),
    expected_duration_minutes: 10,
    location: "异常联调门厅",
    budget: "0.00",
    handover_notes: "当面交接",
    emergency_contact: "测试联系人",
    checklist_items: [
      {
        item_key: "water",
        position: 1,
        content: "换水",
        completion_condition: "记录完成情况",
        required: true,
      },
    ],
  });
  await call(`/requests/${demand.id}/publish`, owner, { expected_version: 1 });
  const booking = await call(`/requests/${demand.id}/bookings`, owner, {
    expected_version: 1,
    helper_id: "00000000-0000-4000-8000-000000000012",
    scheduled_start: iso(slot),
    scheduled_end: iso(slot + 1800000),
    agreed_fee: "0.00",
  });
  await call(`/bookings/${booking.id}/confirm`, owner, { expected_version: 1 });
  await call(`/bookings/${booking.id}/confirm`, helper, {
    expected_version: 1,
  });
  const ownerPage = await browser.newPage(),
    helperPage = await browser.newPage();
  async function open(page: Page, account: string) {
    await page.goto("/");
    await page.getByRole("button", { name: "连接设置", exact: true }).click();
    await page.getByLabel("工作模式").selectOption("api");
    await page.getByLabel("账号", { exact: true }).fill(account);
    await page.getByLabel("密码", { exact: true }).fill("NeighborPet2026!");
    await page.getByRole("button", { name: "登录", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("已连接后端");
    await page.getByRole("button", { name: "预约与执行", exact: true }).click();
    await page.getByLabel("需求编号", { exact: true }).fill(demand.id);
    await page.getByRole("button", { name: "加载需求", exact: true }).click();
    await page.getByLabel("预约编号", { exact: true }).fill(booking.id);
    await page
      .getByRole("button", { name: "刷新预约详情", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: /需求版本 1 · reserved/ }),
    ).toBeVisible();
  }
  try {
    await open(ownerPage, "xiaolin");
    await open(helperPage, "jianguo");
    await helperPage.getByLabel("异常类型").selectOption("out_of_stock");
    await helperPage
      .getByLabel("异常情况说明")
      .fill("指定用品缺货，请确认替代方案");
    await helperPage
      .getByRole("button", { name: "上报异常并暂停服务", exact: true })
      .click();
    await expect(
      helperPage.getByText("异常已上报，服务已暂停。", { exact: true }),
    ).toBeVisible();
    await ownerPage
      .getByRole("button", { name: "刷新预约详情", exact: true })
      .click();
    await expect(ownerPage.getByText(/指定用品缺货/).first()).toBeVisible();
    await ownerPage.getByLabel("追加沟通记录").fill("允许使用同规格替代品");
    await ownerPage
      .getByRole("button", { name: "保存沟通记录", exact: true })
      .click();
    await expect(
      ownerPage.getByText("沟通记录已保存。", { exact: true }),
    ).toBeVisible();
    await ownerPage.getByLabel("处理结论").fill("批准补充替代规则后继续");
    await ownerPage.getByLabel("批准的变更").selectOption("precautions");
    await ownerPage
      .getByLabel("批准值")
      .fill("缺货时使用同规格替代品，先保留购物凭证");
    await ownerPage
      .getByRole("button", { name: "提交宠主决定", exact: true })
      .click();
    await expect(
      ownerPage.getByText("变更已批准，等待帮手确认新版本。", { exact: true }),
    ).toBeVisible();
    await expect(
      ownerPage.getByRole("heading", { name: /需求版本 2 · exception/ }),
    ).toBeVisible();
    await helperPage
      .getByRole("button", { name: "刷新预约详情", exact: true })
      .click();
    await expect(
      helperPage.getByRole("heading", { name: /需求版本 2 · exception/ }),
    ).toBeVisible();
    await helperPage
      .getByText("已核对当前版本清单、时间、费用及执行记录")
      .getByRole("checkbox")
      .check();
    await helperPage
      .getByRole("button", { name: "确认预约", exact: true })
      .click();
    await expect(
      helperPage.getByRole("heading", { name: /需求版本 2 · reserved/ }),
    ).toBeVisible();
  } finally {
    await ownerPage.close();
    await helperPage.close();
  }
});
