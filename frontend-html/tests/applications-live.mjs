import { chromium, expect } from "@playwright/test";
const base = "http://127.0.0.1:5174";
async function raw(t, path, method = "GET", body) {
  return fetch(base + "/api/v0" + path, {
    method,
    headers: {
      ...(t ? { Authorization: "Bearer " + t } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
}
async function call(t, path, method = "GET", body) {
  const r = await raw(t, path, method, body);
  if (!r.ok) throw Error(path + ": " + r.status + " " + (await r.text()));
  return r.status === 204 ? null : r.json();
}
async function account(name) {
  const account = name + Date.now() + Math.random().toString(16).slice(2, 7),
    password = "ApplyTest2026!";
  await call(null, "/auth/register", "POST", {
    account,
    password,
    display_name: name,
    roles: ["owner", "helper"],
  });
  return (await call(null, "/auth/login", "POST", { account, password }))
    .access_token;
}
const owner = await account("申请宠主"),
  h1 = await account("申请帮手一"),
  h2 = await account("申请帮手二"),
  outsider = await account("无关账号");
for (const t of [h1, h2]) {
  await call(t, "/helpers/me", "PUT", {
    service_types: ["home_visit"],
    service_area: "测试社区",
    experience: "照料猫咪",
    supported_species: ["cat"],
    service_radius_m: 1000,
    fee_pref: "free",
  });
  await call(t, "/helpers/me/availability", "POST", {
    start_at: "2027-10-01T10:00:00+08:00",
    end_at: "2027-10-01T13:00:00+08:00",
  });
}
const pet = await call(owner, "/pets", "POST", {
  name: "申请测试猫",
  species: "cat",
  birth_date: "2023-01-01",
});
async function request() {
  const r = await call(owner, "/requests", "POST", {
    pet_ids: [pet.id],
    service_type: "home_visit",
    fee_type: "free",
    window_start: "2027-10-01T10:00:00+08:00",
    window_end: "2027-10-01T13:00:00+08:00",
    expected_duration_minutes: 30,
    location: "测试地点",
    budget: "0.00",
    handover_notes: "门口交接",
    emergency_contact: "测试联系人",
    checklist_items: [
      {
        item_key: "care_1",
        position: 1,
        pet_id: pet.id,
        content: "喂猫",
        completion_condition: "照片",
        required: true,
      },
    ],
  });
  await call(owner, "/requests/" + r.id + "/publish", "POST", {
    expected_version: 1,
  });
  return r;
}
const r = await request(),
  proposal = {
    expected_version: 1,
    scheduled_start: "2027-10-01T10:00:00+08:00",
    scheduled_end: "2027-10-01T10:30:00+08:00",
    agreed_fee: "0.00",
    note: "可以照料",
  };
const second = await call(
  h2,
  "/requests/" + r.id + "/applications",
  "POST",
  proposal,
);
expect(
  (await call(h2, "/requests/" + r.id + "/applications", "POST", proposal)).id,
).toBe(second.id);
expect((await raw(h1, "/requests/" + r.id + "/applications")).status).toBe(403);
expect(
  (
    await raw(h1, "/applications/" + second.id + "/accept", "POST", {
      expected_version: 1,
    })
  ).status,
).toBe(403);
const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  const helperPage = await browser.newPage(),
    ownerPage = await browser.newPage(),
    errors = [];
  for (const [p, t] of [
    [helperPage, h1],
    [ownerPage, owner],
  ]) {
    p.on("pageerror", (e) => errors.push(e.message));
    p.on("dialog", (d) => d.accept());
    await p.addInitScript(
      (t) => sessionStorage.setItem("pethelp-html-token", t),
      t,
    );
    await p.goto(base + "/#tasks");
    await p
      .locator("[aria-labelledby=auth-title]")
      .waitFor({ state: "hidden" });
  }
  const card = helperPage.locator('[data-public-request="' + r.id + '"]');
  while ((await card.count()) === 0) {
    await expect(helperPage.locator("#hall-more")).toBeVisible();
    await helperPage.locator("#hall-more").click();
    await expect(helperPage.locator("#hall-more")).toBeEnabled();
  }
  await expect(helperPage.locator("#application-panel .notice")).toHaveText(
    "申请列表已更新",
  );
  await card.getByRole("button", { name: "申请接单" }).click();
  await helperPage.locator("#application-form [name=note]").fill("我来帮忙");
  await helperPage.locator("#application-form button[type=submit]").click();
  await expect(helperPage.locator("#application-panel .notice")).toHaveText(
    "申请已提交，等待宠主选择。",
  );
  const first = (await call(h1, "/applications")).items[0];
  await ownerPage.locator("#application-request").selectOption(r.id);
  await ownerPage.locator("#load-owner-applications").click();
  await expect(ownerPage.locator("[data-application]")).toHaveCount(2);
  await ownerPage.locator('[data-accept="' + first.id + '"]').click();
  await expect(ownerPage.locator("#application-panel .notice")).toContainText(
    "已选择帮手",
  );
  const accepted = (await call(h1, "/applications")).items[0];
  expect(accepted.status).toBe("accepted");
  expect((await call(h2, "/applications")).items[0].status).toBe("rejected");
  const replay = await call(
    owner,
    "/applications/" + first.id + "/accept",
    "POST",
    { expected_version: 1 },
  );
  expect(replay.id).toBe(accepted.booking_id);
  expect((await raw(outsider, "/bookings/" + replay.id)).status).toBe(403);
  for (const p of [ownerPage, helperPage]) {
    await p.goto(base + "/#records");
    await p
      .locator("[aria-labelledby=auth-title]")
      .waitFor({ state: "hidden" });
    await p.locator('[data-booking="' + replay.id + '"]').click();
    await p.locator("#booking-consent").check();
    await p.locator("#confirm-booking").click();
    await expect(p.locator("[data-screen=records] .notice")).toContainText(
      "确认成功",
    );
  }
  expect((await call(owner, "/bookings/" + replay.id)).status).toBe("reserved");
  await helperPage.locator("#withdraw-reason").fill("测试撤回");
  await helperPage.locator("#withdraw-booking").click();
  await expect(helperPage.locator("[data-screen=records] .notice")).toHaveText(
    "预约已撤回",
  );
  expect((await call(owner, "/requests/" + r.id)).status).toBe("pending_match");
  const race = await request();
  const a = await call(
      h1,
      "/requests/" + race.id + "/applications",
      "POST",
      proposal,
    ),
    b = await call(
      h2,
      "/requests/" + race.id + "/applications",
      "POST",
      proposal,
    );
  const results = await Promise.all(
    [a, b].map((x) =>
      raw(owner, "/applications/" + x.id + "/accept", "POST", {
        expected_version: 1,
      }),
    ),
  );
  expect(results.map((r) => r.status).sort()).toEqual([200, 409]);
  const stale = await request();
  const s = await call(h1, "/requests/" + stale.id + "/applications", "POST", {
    ...proposal,
    scheduled_start: "2027-10-01T12:00:00+08:00",
    scheduled_end: "2027-10-01T12:30:00+08:00",
  });
  await call(owner, "/requests/" + stale.id, "PATCH", {
    expected_version: 1,
    location: "地点变更",
  });
  expect(
    (
      await raw(owner, "/applications/" + s.id + "/accept", "POST", {
        expected_version: 2,
      })
    ).status,
  ).toBe(409);
  await call(h1, "/applications/" + s.id + "/withdraw", "POST");
  expect(
    (await call(h1, "/applications")).items.find((a) => a.id === s.id).status,
  ).toBe("withdrawn");
  expect(errors).toEqual([]);
  console.log(
    "PASS: apply UI; multiple applicants; duplicate/replay; owner select; both confirm; withdraw; privacy; concurrent selection; stale version.",
  );
} finally {
  await browser.close();
}
