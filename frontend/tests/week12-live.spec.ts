import { test, expect } from "@playwright/test";

test("真实后端：查看推荐帮手详情并取消需求", async ({ page, request }) => {
  test.setTimeout(60000);
  const base = "http://127.0.0.1:8000/api/v0";
  async function call(
    path: string,
    token: string,
    body?: unknown,
    method?: string,
  ) {
    const response = await request.fetch(base + path, {
      method: method || (body ? "POST" : "GET"),
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
  const suffix = Date.now().toString(36);
  const helperAccount = `detail_${suffix}`;
  const helperName = `详情测试帮手${suffix.slice(-4)}`;
  await call("/auth/register", "", {
    account: helperAccount,
    password: "NeighborPet2026!",
    display_name: helperName,
    roles: ["helper"],
  });
  const helperToken = await login(helperAccount);
  await call(
    "/helpers/me",
    helperToken,
    {
      service_types: ["home_visit"],
      service_area: "邻宠社区",
      experience: "真实后端详情展示测试",
      supported_species: ["dog"],
      service_radius_m: 900,
      fee_pref: "both",
      address_tag: "社区北门附近",
    },
    "PUT",
  );
  const ownerToken = await login("xiaolin");
  const pet = await call("/pets", ownerToken, {
    name: `详情测试犬${suffix.slice(-4)}`,
    species: "dog",
    birth_date: "2024-01-01",
  });
  const start = new Date(Date.now() + 20 * 86400000);
  const end = new Date(start.getTime() + 3600000);
  await call("/helpers/me/availability", helperToken, {
    start_at: new Date(start.getTime() - 3600000).toISOString(),
    end_at: new Date(end.getTime() + 3600000).toISOString(),
  });
  const demand = await call("/requests", ownerToken, {
    pet_ids: [pet.id],
    service_type: "home_visit",
    fee_type: "free",
    window_start: start.toISOString(),
    window_end: end.toISOString(),
    expected_duration_minutes: 20,
    location: "邻宠社区门厅",
    budget: "0.00",
    handover_notes: "当面交接",
    emergency_contact: "测试联系人",
    checklist_items: [
      {
        item_key: "water",
        position: 1,
        content: "换水",
        completion_condition: "水碗清洁并装满",
        required: true,
      },
    ],
  });
  await call(`/requests/${demand.id}/publish`, ownerToken, {
    expected_version: 1,
  });

  await page.goto("/");
  await page.getByRole("button", { name: "连接设置", exact: true }).click();
  await page.getByLabel("工作模式").selectOption("api");
  await page.getByLabel("账号", { exact: true }).fill("xiaolin");
  await page.getByLabel("密码", { exact: true }).fill("NeighborPet2026!");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已连接后端");
  await page.getByRole("button", { name: "预约与执行", exact: true }).click();
  await page.getByLabel("需求编号", { exact: true }).fill(demand.id);
  await page.getByRole("button", { name: "加载需求", exact: true }).click();
  await page.getByRole("button", { name: "查找推荐邻居" }).click();
  const candidate = page
    .locator("article")
    .filter({ hasText: helperName })
    .filter({
      has: page.getByRole("button", { name: "查看帮手详情", exact: true }),
    })
    .last();
  await expect(candidate).toBeVisible();
  await candidate.getByRole("button", { name: "查看帮手详情" }).click();
  await expect(candidate.getByText("真实后端详情展示测试")).toBeVisible();
  await expect(candidate.getByText("社区北门附近")).toBeVisible();

  await page.getByText("取消整个需求").click();
  await page.getByLabel("取消原因").fill("自动化验证取消入口");
  await page.getByRole("button", { name: "确认取消需求" }).click();
  await expect(
    page.getByRole("heading", { name: /需求版本 1 · cancelled/ }),
  ).toBeVisible();
  const cancelled = await call(`/requests/${demand.id}`, ownerToken);
  expect(cancelled.status).toBe("cancelled");
});
