import { chromium, expect } from "@playwright/test";
const base = "http://127.0.0.1:5174",
  suffix = Date.now();
async function api(token, path, method = "GET", body) {
  const r = await fetch(base + "/api/v0" + path, {
    method,
    headers: {
      ...(token ? { Authorization: "Bearer " + token } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw Error(path + ": " + r.status);
  return r.json();
}
async function account(name) {
  const account = name + suffix,
    password = "MatchTest2026!";
  await api(null, "/auth/register", "POST", {
    account,
    password,
    display_name: name,
    roles: ["owner", "helper"],
  });
  return (await api(null, "/auth/login", "POST", { account, password }))
    .access_token;
}
const owner = await account("match-owner-"),
  helper = await account("match-helper-");
const hp = await api(helper, "/helpers/me", "PUT", {
  service_types: ["home_visit"],
  service_area: "测试社区",
  experience: "有猫咪照料经验",
  supported_species: ["cat"],
  service_radius_m: 1000,
  fee_pref: "free",
});
await api(helper, "/helpers/me/availability", "POST", {
  start_at: "2027-09-01T10:00:00+08:00",
  end_at: "2027-09-01T12:00:00+08:00",
});
const pet = await api(owner, "/pets", "POST", {
  name: "匹配猫",
  species: "cat",
  birth_date: "2023-01-01",
});
const request = await api(owner, "/requests", "POST", {
  pet_ids: [pet.id],
  service_type: "home_visit",
  fee_type: "free",
  window_start: "2027-09-01T10:00:00+08:00",
  window_end: "2027-09-01T11:00:00+08:00",
  expected_duration_minutes: 30,
  location: "SECRET-门牌-301",
  budget: "0.00",
  handover_notes: "SECRET-钥匙",
  emergency_contact: "SECRET-电话",
  checklist_items: [
    {
      item_key: "care_1",
      pet_id: pet.id,
      position: 1,
      content: "喂猫",
      completion_condition: "照片",
      required: true,
    },
  ],
});
await api(owner, "/requests/" + request.id + "/publish", "POST", {
  expected_version: 1,
});
const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  const p = await browser.newPage({ viewport: { width: 390, height: 844 } }),
    errors = [];
  p.on("pageerror", (e) => errors.push(e.message));
  await p.addInitScript(
    (t) => sessionStorage.setItem("pethelp-html-token", t),
    owner,
  );
  await p.goto(base + "/#home");
  await p.locator("[aria-labelledby=auth-title]").waitFor({ state: "hidden" });
  await expect(
    p.locator('#match-request option[value="' + request.id + '"]'),
  ).toHaveCount(1);
  await p.locator("#match-request").selectOption(request.id);
  await p.locator("#match-run").click();
  const card = p.locator('[data-candidate="' + hp.id + '"]');
  await expect(card).toBeVisible();
  await expect(card.locator(".match-explanation")).toContainText("推荐依据");
  await card.getByRole("button", { name: "查看帮手详情" }).click();
  await expect(p.locator("#helper-detail")).toContainText("有猫咪照料经验");
  await p.getByRole("button", { name: "关闭", exact: true }).click();
  await p.goto(base + "/#tasks");
  await p.locator("[aria-labelledby=auth-title]").waitFor({ state: "hidden" });
  while (
    (await p.locator('[data-public-request="' + request.id + '"]').count()) ===
    0
  ) {
    await expect(p.locator("#hall-more")).toBeVisible();
    await p.locator("#hall-more").click();
    await expect(p.locator("#hall-more")).toBeEnabled();
  }
  const publicCard = p.locator('[data-public-request="' + request.id + '"]');
  await expect(publicCard).toContainText("上门代看");
  expect(await p.locator("#hall-list").textContent()).not.toContain("SECRET-");
  await p.locator("#hall-kind").selectOption("dog_walking");
  await expect(publicCard).toHaveCount(0);
  await p.goto(base + "/#home");
  await p.locator("[aria-labelledby=auth-title]").waitFor({ state: "hidden" });
  await p.locator("#match-request").selectOption(request.id);
  await p.route("**/api/v0/ai/explain-match", (r) =>
    r.fulfill({ status: 503, body: "unavailable" }),
  );
  await p.locator("#match-run").click();
  await expect(card.locator(".match-explanation")).toContainText("原始理由");
  await api(helper, "/helpers/me", "PUT", {
    service_types: ["dog_walking"],
    service_area: "测试社区",
    experience: "改成仅遛狗",
    supported_species: ["dog"],
    service_radius_m: 1000,
    fee_pref: "free",
  });
  await p.locator("#match-run").click();
  await expect(p.locator("#match-run")).toBeEnabled();
  await expect(card).toHaveCount(0);
  expect(errors).toEqual([]);
  console.log(
    "PASS: real matching; helper detail; public hall paging/filter/privacy; explanation fallback; incompatible helper excluded.",
  );
} finally {
  await browser.close();
}
