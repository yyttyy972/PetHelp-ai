import { chromium, expect } from "@playwright/test";
const base = "http://127.0.0.1:5174";
async function call(token, path, method = "GET", body) {
  const r = await fetch(base + "/api/v0" + path, {
    method,
    headers: {
      ...(token ? { Authorization: "Bearer " + token } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(method === "POST" ? { "Idempotency-Key": crypto.randomUUID() } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw Error(path + " " + r.status + " " + (await r.text()));
  return r.json();
}
async function account(name) {
  const account = name + Date.now(),
    password = "ServiceTest2026!";
  await call("", "/auth/register", "POST", {
    account,
    password,
    display_name: name,
    roles: ["owner", "helper"],
  });
  return (await call("", "/auth/login", "POST", { account, password }))
    .access_token;
}
const owner = await account("service-owner-"),
  helper = await account("service-helper-");
const now = Date.now(),
  start = new Date(now - 300000).toISOString(),
  end = new Date(now + 3600000).toISOString();
const pet = await call(owner, "/pets", "POST", {
  name: "执行测试狗",
  species: "dog",
  birth_date: "2023-01-01",
});
const h = await call(helper, "/helpers/me", "PUT", {
  service_types: ["home_visit", "dog_walking", "errand_buy"],
  supported_species: ["dog"],
  service_area: "测试社区",
  experience: "有经验",
  service_radius_m: 1000,
  fee_pref: "both",
});
await call(helper, "/helpers/me/availability", "POST", {
  start_at: start,
  end_at: new Date(now + 7200000).toISOString(),
});
async function fixture(kind) {
  const keys = {
    home_visit: ["care_1"],
    dog_walking: ["pickup", "departure", "return"],
    errand_buy: ["purchase", "delivery"],
  }[kind];
  const r = await call(owner, "/requests", "POST", {
    pet_ids: [pet.id],
    service_type: kind,
    fee_type: kind === "errand_buy" ? "paid" : "free",
    window_start: start,
    window_end: end,
    expected_duration_minutes: 30,
    location: "测试地点",
    budget: kind === "errand_buy" ? "50" : "0",
    handover_notes: "交接",
    emergency_contact: "测试联系人",
    checklist_items: keys.map((k, i) => ({
      item_key: k,
      position: i + 1,
      pet_id: pet.id,
      content: k + "照料",
      completion_condition: "说明或凭证",
      required: true,
      ...(k === "purchase"
        ? { product_name: "狗粮", quantity: 1, unit: "袋" }
        : {}),
    })),
  });
  await call(owner, "/requests/" + r.id + "/publish", "POST", {
    expected_version: 1,
  });
  const b = await call(owner, "/requests/" + r.id + "/bookings", "POST", {
    expected_version: 1,
    helper_id: h.id,
    scheduled_start: start,
    scheduled_end: end,
    agreed_fee: kind === "errand_buy" ? "10" : "0",
  });
  for (const t of [owner, helper])
    await call(t, "/bookings/" + b.id + "/confirm", "POST", {
      expected_version: 1,
    });
  return b;
}
const browser = await chromium.launch({ channel: "msedge", headless: true });
const errors = [];
try {
  const op = await browser.newPage(),
    hp = await browser.newPage();
  for (const [p, t] of [
    [op, owner],
    [hp, helper],
  ]) {
    p.on("pageerror", (e) => errors.push(e.message));
    p.on("dialog", (d) => d.accept());
    await p.addInitScript(
      (t) => sessionStorage.setItem("pethelp-html-token", t),
      t,
    );
  }
  async function open(p, id) {
    await p.goto(base + "/#records");
    await p
      .locator("[aria-labelledby=auth-title]")
      .waitFor({ state: "hidden" });
    await p.locator("#refresh-bookings").click();
    await p.locator('[data-booking="' + id + '"]').click();
    await expect(p.locator("#service-panel .service-notice")).not.toHaveText(
      "正在加载服务记录…",
    );
  }
  for (const kind of ["home_visit", "dog_walking", "errand_buy"]) {
    const b = await fixture(kind);
    await open(op, b.id);
    await expect(op.locator("#start-service")).toHaveCount(0);
    await open(hp, b.id);
    await hp.locator("#start-service").click();
    await expect(hp.locator("#record-form")).toBeVisible();
    await hp.locator("#submit-service").click();
    await expect(hp.locator(".service-notice")).toContainText("尚未完成");
    let details = await call(helper, "/bookings/" + b.id);
    for (let i = 0; i < details.checklist_items.length; i++) {
      const item = details.checklist_items[i];
      await hp.locator("#record-form [name=item]").selectOption(item.id);
      await hp
        .locator("#record-form [name=note]")
        .fill("已完成" + item.content);
      if (i === 0)
        await hp
          .locator("#record-form [name=photos]")
          .setInputFiles("docs/home-mobile.png");
      if (item.item_key === "purchase")
        await hp.locator("#record-form [name=actual_cost]").fill("40");
      await hp.locator("#record-form button").click();
      await expect(hp.locator("#execution-records article")).toHaveCount(i + 1);
    }
    if (kind === "home_visit") {
      await hp
        .locator("#report-exception [name=description]")
        .fill("需要补充要求");
      await hp.locator("#report-exception button").click();
      await expect(hp.locator("#exception-note")).toBeVisible();
      await hp.locator("#exception-note textarea").fill("已与宠主沟通");
      await hp.locator("#exception-note button").click();
      await expect(hp.locator("#service-panel")).toContainText("已与宠主沟通");
      await open(op, b.id);
      await op
        .locator("#resolve-exception [name=resolution]")
        .fill("同意调整要求");
      await op.locator("#resolve-exception summary").click();
      await op
        .locator("#resolve-exception [name=requirements]")
        .fill("离开时关好门");
      await op.locator("#resolve-exception button").click();
      await expect(op.locator("#exception-history")).toContainText(
        "变更已批准",
      );
      await open(hp, b.id);
      await expect(hp.locator("#service-panel")).toContainText("离开时关好门");
      await hp.locator("#change-consent").check();
      await hp.locator("#confirm-change").click();
      await expect(hp.locator("#record-form")).toBeVisible();
      await expect(hp.locator("#execution-records article")).toHaveCount(1);
      details = await call(helper, "/bookings/" + b.id);
      expect(details.request_version).toBe(2);
      expect(details.checklist_items[0].execution_status).toBe("completed");
    }
    await hp.locator("#submit-service").click();
    await expect(hp.locator("#record-form")).toHaveCount(0);
    await open(op, b.id);
    await expect(op.locator("#execution-records img").first()).toBeVisible();
    await op.locator("#verify-consent").check();
    await op.locator("#verify-service").click();
    await expect(op.locator("#service-panel")).toContainText("服务已完成");
    const done = await call(owner, "/bookings/" + b.id);
    expect(done.status).toBe("completed");
    expect(done.settlement_status).toBe("simulated_settled");
    if (kind === "errand_buy")
      expect(Number(done.actual_cost) + Number(done.agreed_fee)).toBe(50);
    await open(hp, b.id);
    await expect(hp.locator("#service-panel")).toContainText("服务已完成");
  }
  const stopped = await fixture("home_visit");
  await open(hp, stopped.id);
  await hp.locator("#report-exception [name=description]").fill("无法继续服务");
  await hp.locator("#report-exception button").click();
  await expect(hp.locator("#exception-note")).toBeVisible();
  await open(op, stopped.id);
  await op.locator("#resolve-exception [name=resolution]").fill("同意终止");
  await op.locator("#resolve-exception [name=decision]").selectOption("end");
  await op.locator("#resolve-exception button").click();
  await expect(op.locator("#report-exception")).toHaveCount(0);
  expect((await call(owner, "/bookings/" + stopped.id)).status).toBe(
    "cancelled",
  );
  const completed = (await call(owner, "/bookings")).items.find(
    (b) => b.status === "completed",
  );
  await open(op, completed.id);
  await op.locator("#review-form [name=comment]").fill("认真负责，真实评价");
  await op.locator("#review-form button").click();
  await expect(op.locator(".review-status")).toHaveText("评价已提交");
  await expect(op.locator(".review-list")).toContainText("认真负责");
  await op.goto(base + "/#inbox");
  await op.locator("#refresh-messages").click();
  await op.locator('[data-conversation="' + completed.id + '"]').click();
  await op.locator("#send-message textarea").fill("谢谢帮忙，测试消息");
  await op.locator("#send-message button").click();
  await expect(op.locator("#live-messages")).toContainText("谢谢帮忙");
  const conversations = await call(helper, "/conversations?limit=100");
  expect(
    conversations.items.find((c) => c.id === completed.id).unread,
  ).toBeGreaterThan(0);
  await hp.goto(base + "/#inbox");
  await hp.locator("#refresh-messages").click();
  await hp.locator('[data-conversation="' + completed.id + '"]').click();
  await expect(hp.locator("#live-messages")).toContainText("谢谢帮忙");
  const client_id = crypto.randomUUID();
  const msg = { client_id, content: "幂等消息" };
  const first = await call(
    owner,
    "/bookings/" + completed.id + "/messages",
    "POST",
    msg,
  );
  expect(
    (await call(owner, "/bookings/" + completed.id + "/messages", "POST", msg))
      .id,
  ).toBe(first.id);
  const stranger = await account("stranger-");
  const denied = await fetch(
    base + "/api/v0/bookings/" + completed.id + "/messages",
    { headers: { Authorization: "Bearer " + stranger } },
  );
  expect(denied.status).toBe(403);
  console.log(
    "PASS: review UI; chat both parties; unread; message replay; stranger forbidden",
  );
  expect(errors).toEqual([]);
  console.log(
    "PASS: three services start/records/evidence/submit/verify; incomplete guard; change approval/reconfirmation preserves evidence; end exception; simulated settlement; helper completed view.",
  );
} finally {
  await browser.close();
}
