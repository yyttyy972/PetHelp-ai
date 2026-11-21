import { test, expect, type Page } from "@playwright/test";
for (const service of ["home_visit", "dog_walking", "errand_buy"])
  test(`真实双账号浏览器：${service} 确认、执行、核验`, async ({
    browser,
    request,
  }) => {
    test.setTimeout(60000);
    const base = "http://127.0.0.1:8000/api/v0";
    async function call(
      path: string,
      token: string,
      body?: unknown,
      method?: string,
    ) {
      const r = await request.fetch(base + path, {
        method: method || (body ? "POST" : "GET"),
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          "Idempotency-Key": crypto.randomUUID(),
        },
        data: body,
      });
      expect(r.ok(), await r.text()).toBeTruthy();
      return r.json();
    }
    const login = async (account: string) =>
      (await call("/auth/login", "", { account, password: "NeighborPet2026!" }))
        .access_token;
    const helperAccount = `browser_${service}_${Date.now().toString(36)}`;
    await call("/auth/register", "", {
      account: helperAccount,
      password: "NeighborPet2026!",
      display_name: `${service}测试帮手`,
      roles: ["helper"],
    });
    const owner = await login("xiaolin"),
      helper = await login(helperAccount);
    const helperProfile = await call(
      "/helpers/me",
      helper,
      {
        service_types: ["home_visit", "dog_walking", "errand_buy"],
        service_area: "邻宠社区",
        experience: "自动化测试帮手",
        supported_species: ["cat", "dog"],
        service_radius_m: 1000,
        fee_pref: "both",
        address_tag: "测试楼栋",
      },
      "PUT",
    );
    const pet = await call("/pets", owner, {
      name: "浏览器测试犬",
      species: "dog",
      birth_date: "2024-01-01",
    });
    const keys =
      service === "dog_walking"
        ? ["pickup", "departure", "return"]
        : service === "errand_buy"
          ? ["purchase", "delivery"]
          : ["water"];
    const now = Date.now(),
      iso = (n: number) => new Date(now + n).toISOString();
    await call("/helpers/me/availability", helper, {
      start_at: iso(-3600000),
      end_at: iso(7200000),
    });
    const r = await call("/requests", owner, {
      pet_ids: [pet.id],
      service_type: service,
      fee_type: "free",
      window_start: iso(-120000),
      window_end: iso(3600000),
      expected_duration_minutes: 10,
      location: "浏览器联调门厅",
      budget: service === "errand_buy" ? "30.00" : "0.00",
      handover_notes: "当面交接",
      emergency_contact: "演示联系人",
      checklist_items: keys.map((key, i) => ({
        item_key: key,
        position: i + 1,
        content: key,
        completion_condition: "按约定执行并记录",
        required: true,
      })),
    });
    await call(`/requests/${r.id}/publish`, owner, { expected_version: 1 });
    const b = await call(`/requests/${r.id}/bookings`, owner, {
      expected_version: 1,
      helper_id: helperProfile.id,
      scheduled_start: iso(-60000),
      scheduled_end: iso(1800000),
      agreed_fee: "0.00",
    });
    const a = await browser.newPage(),
      h = await browser.newPage();
    async function open(p: Page, account: string) {
      await p.goto("/");
      await p.getByRole("button", { name: "连接设置", exact: true }).click();
      await p.getByLabel("工作模式").selectOption("api");
      await p.getByLabel("账号", { exact: true }).fill(account);
      await p.getByLabel("密码", { exact: true }).fill("NeighborPet2026!");
      await p.getByRole("button", { name: "登录", exact: true }).click();
      await expect(p.getByRole("status")).toContainText("已连接后端");
      await p.getByRole("button", { name: "预约与执行", exact: true }).click();
      await p.getByLabel("需求编号", { exact: true }).fill(r.id);
      await p.getByRole("button", { name: "加载需求", exact: true }).click();
      await expect(p.getByRole("heading", { name: /需求版本/ })).toBeVisible();
      await p.getByLabel("预约编号", { exact: true }).fill(b.id);
    }
    try {
      await open(a, "xiaolin");
      await open(h, helperAccount);
      for (const p of [a, h]) {
        await p.getByRole("checkbox").check();
        await p.getByRole("button", { name: "确认预约", exact: true }).click();
        await expect(
          p.getByText("操作成功，状态以服务器返回为准。", { exact: true }),
        ).toBeVisible();
      }
      await h
        .getByRole("button", { name: "帮手开始服务", exact: true })
        .click();
      await expect(
        h.getByRole("heading", { name: /需求版本.*in_service/ }),
      ).toBeVisible();
      await a
        .getByRole("button", { name: "帮手开始服务", exact: true })
        .click();
      await expect(
        a.getByText("当前账号无权执行此操作，请使用对应参与者账号。", {
          exact: true,
        }),
      ).toBeVisible();
      await h
        .getByRole("button", { name: "帮手提交核验", exact: true })
        .click();
      await expect(
        h.getByText("必需清单尚未完成，请补齐执行记录。", { exact: true }),
      ).toBeVisible();
      if (keys.length > 1) {
        await h.getByLabel("实际完成情况").fill("故意测试乱序");
        await h
          .getByRole("button", { name: `记录：${keys[1]}`, exact: true })
          .click();
        await expect(
          h.getByText("凭证不符合要求，请核对顺序、时间、照片和商品费用。", {
            exact: true,
          }),
        ).toBeVisible();
      }
      for (const key of keys) {
        await h.getByLabel("实际完成情况").fill(`浏览器证据-${key}`);
        if (key === "purchase") {
          await h
            .getByRole("button", { name: "记录：purchase", exact: true })
            .click();
          await expect(
            h.getByText("购买记录必须上传购买凭证", { exact: true }),
          ).toBeVisible();
          const png = await h.screenshot();
          await h
            .getByLabel("上传照片凭证")
            .setInputFiles({
              name: "演示凭证.png",
              mimeType: "image/png",
              buffer: png,
            });
          await expect(
            h.getByText("本次已上传 1 张", { exact: true }),
          ).toBeVisible();
          await h.getByLabel("实际商品费用（元）").fill("31");
          await h
            .getByRole("button", { name: "记录：purchase", exact: true })
            .click();
          await expect(
            h.getByText("凭证不符合要求，请核对顺序、时间、照片和商品费用。", {
              exact: true,
            }),
          ).toBeVisible();
          await h.getByLabel("实际商品费用（元）").fill("12.50");
        }
        await h
          .getByRole("button", { name: `记录：${key}`, exact: true })
          .click();
        await expect(h.getByText("记录已保存", { exact: true })).toBeVisible();
      }
      await h
        .getByRole("button", { name: "帮手提交核验", exact: true })
        .click();
      await expect(
        h.getByRole("heading", { name: /pending_verify/ }),
      ).toBeVisible();
      await a
        .getByRole("button", { name: "刷新执行记录", exact: true })
        .click();
      await expect(
        a.getByText(`浏览器证据-${keys[0]}`, { exact: false }),
      ).toBeVisible();
      if (service === "errand_buy") {
        await a.getByRole("button", { name: "查看凭证", exact: true }).click();
        await expect(a.getByAltText("执行凭证")).toBeVisible();
        await expect
          .poll(() =>
            a
              .getByAltText("执行凭证")
              .evaluate((img: HTMLImageElement) => img.naturalWidth),
          )
          .toBeGreaterThan(0);
      }
      await a.getByRole("checkbox").check();
      await a
        .getByRole("button", { name: "宠主确认完成", exact: true })
        .click();
      await expect(a.getByRole("heading", { name: /completed/ })).toBeVisible();
      await a
        .getByRole("button", { name: "刷新预约列表", exact: true })
        .click();
      await expect(
        a.getByRole("button", { name: "刷新预约列表", exact: true }),
      ).toBeEnabled();
      let card = a
        .locator("article")
        .filter({ has: a.locator("small", { hasText: b.id }) })
        .last();
      while (
        !(await card.count()) &&
        (await a
          .getByRole("button", { name: "加载更多预约", exact: true })
          .count())
      ) {
        const response = a.waitForResponse(
          (r) =>
            r.url().includes("/bookings?") && r.request().method() === "GET",
        );
        await a
          .getByRole("button", { name: "加载更多预约", exact: true })
          .click();
        await response;
        await expect(
          a.getByRole("button", { name: "刷新预约列表", exact: true }),
        ).toBeEnabled();
      }
      await card
        .getByRole("button", { name: "查看预约详情", exact: true })
        .click();
      await expect(a.getByLabel("预约编号", { exact: true })).toHaveValue(b.id);
      await expect(a.getByRole("heading", { name: /completed/ })).toBeVisible();
    } finally {
      await a.close();
      await h.close();
    }
  });
