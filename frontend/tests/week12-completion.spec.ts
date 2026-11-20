import { test, expect, type Page, type Route } from "@playwright/test";

const requestRow = {
  id: "10000000-0000-4000-8000-000000000001",
  version: 1,
  status: "pending_match",
  service_type: "home_visit",
  window_start: "2026-12-01T10:00:00+08:00",
  window_end: "2026-12-01T11:00:00+08:00",
  location: "邻宠社区门厅",
  handover_notes: "当面交接",
  emergency_contact: "小林 13800000000",
  checklist_items: [
    {
      id: "30000000-0000-4000-8000-000000000001",
      item_key: "water",
      position: 1,
      content: "换水",
      completion_condition: "水碗清洁并装满",
      required: true,
    },
  ],
};

async function enterApiMode(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "连接设置", exact: true }).click();
  await page.getByLabel("工作模式").selectOption("api");
  await page.getByLabel("账号", { exact: true }).fill("xiaolin");
  await page.getByLabel("密码", { exact: true }).fill("NeighborPet2026!");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已连接后端");
  await page.getByRole("button", { name: "预约与执行", exact: true }).click();
  await page.getByLabel("需求编号", { exact: true }).fill(requestRow.id);
  await page.getByRole("button", { name: "加载需求", exact: true }).click();
}

async function commonRoutes(route: Route) {
  const url = new URL(route.request().url());
  const path = url.pathname;
  if (path.endsWith("/auth/login"))
    return route.fulfill({ json: { access_token: "test-token" } });
  if (path.endsWith("/users/me"))
    return route.fulfill({ json: { display_name: "小林" } });
  if (path.endsWith("/pets"))
    return route.fulfill({ json: { items: [], next_cursor: null } });
  if (path.endsWith(`/requests/${requestRow.id}`))
    return route.fulfill({ json: requestRow });
  if (path.endsWith(`/requests/${requestRow.id}/match`))
    return route.fulfill({
      json: {
        candidates: [
          {
            helper_id: "20000000-0000-4000-8000-000000000001",
            display_name: "建国",
            reasons: ["时间覆盖", "同一社区"],
          },
        ],
      },
    });
  if (path.endsWith("/helpers/20000000-0000-4000-8000-000000000001"))
    return route.fulfill({
      json: {
        id: "20000000-0000-4000-8000-000000000001",
        service_types: ["home_visit", "dog_walking"],
        service_area: "邻宠社区",
        experience: "有猫狗照料经验，按清单执行",
        supported_species: ["cat", "dog"],
        service_radius_m: 800,
        fee_pref: "both",
        verification_status: "verified",
        address_tag: "社区南门附近",
      },
    });
  if (path.endsWith(`/requests/${requestRow.id}/cancel`))
    return route.fulfill({
      json: { ...requestRow, status: "cancelled" },
    });
  if (path.includes("/bookings?"))
    return route.fulfill({ json: { items: [], next_cursor: null } });
  return route.fulfill({ status: 404, json: { message: `未模拟 ${path}` } });
}

test("展示完整帮手详情并取消整个需求", async ({ page }) => {
  await page.route("**/api/v0/**", commonRoutes);
  await enterApiMode(page);
  await page.getByRole("button", { name: "查找推荐邻居" }).click();
  await expect(page.getByText("建国 · 时间覆盖、同一社区")).toBeVisible();
  await page.getByRole("button", { name: "查看帮手详情" }).click();
  await expect(page.getByText("有猫狗照料经验，按清单执行")).toBeVisible();
  await expect(page.getByText("社区南门附近")).toBeVisible();
  await page.getByText("取消整个需求").click();
  await page.getByLabel("取消原因").fill("行程发生变化");
  await page.getByRole("button", { name: "确认取消需求" }).click();
  await expect(
    page.getByText("需求已取消；关联的有效预约也已同步取消。", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /需求版本 1 · cancelled/ }),
  ).toBeVisible();
});

test("上传失败覆盖格式、大小、服务端和网络错误", async ({ page }) => {
  let mediaMode: "server" | "network" = "server";
  await page.route("**/api/v0/**", async (route) => {
    if (new URL(route.request().url()).pathname.endsWith("/media")) {
      if (mediaMode === "network") return route.abort("failed");
      return route.fulfill({
        status: 503,
        json: { message: "媒体服务暂不可用" },
      });
    }
    return commonRoutes(route);
  });
  await enterApiMode(page);
  await page.getByLabel("预约编号", { exact: true }).fill("booking-test");
  const input = page.getByLabel("上传照片凭证");

  await input.setInputFiles({
    name: "说明.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not an image"),
  });
  await expect(
    page.getByText("仅支持 JPG、PNG 或 WebP 图片", { exact: true }),
  ).toBeVisible();

  await input.setInputFiles({
    name: "超大图片.png",
    mimeType: "image/png",
    buffer: Buffer.alloc(5 * 1024 * 1024 + 1),
  });
  await expect(
    page.getByText("照片不能超过 5 MB", { exact: true }),
  ).toBeVisible();

  await input.setInputFiles({
    name: "正常大小.png",
    mimeType: "image/png",
    buffer: Buffer.from("fake png"),
  });
  await expect(
    page.getByText("媒体服务暂不可用", { exact: true }),
  ).toBeVisible();

  mediaMode = "network";
  await input.setInputFiles({
    name: "再次上传.png",
    mimeType: "image/png",
    buffer: Buffer.from("fake png 2"),
  });
  await expect(
    page.getByText("照片上传失败，请检查网络后重试", { exact: true }),
  ).toBeVisible();
});
