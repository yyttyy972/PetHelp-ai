import { chromium, expect } from "@playwright/test";
const base = "http://127.0.0.1:5174";
let token;
async function call(path, method = "GET", body) {
  const r = await fetch(base + "/api/v0" + path, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: "Bearer " + token } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw Error(`${path}: ${r.status}`);
  return r.status === 204 ? null : r.json();
}
const account = "html-request-" + Date.now();
const password = "RequestTest2026!";
await call("/auth/register", "POST", {
  account,
  password,
  display_name: "发布验收",
  roles: ["owner", "helper"],
});
token = (await call("/auth/login", "POST", { account, password })).access_token;
const pet = await call("/pets", "POST", {
  name: "验收狗",
  species: "dog",
  birth_date: "2023-01-01",
});
const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  const p = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  p.on("pageerror", (e) => errors.push(e.message));
  p.on("dialog", (d) => d.accept());
  await p.addInitScript(
    (t) => sessionStorage.setItem("pethelp-html-token", t),
    token,
  );
  await p.goto(base + "/#publish");
  await p.locator("[aria-labelledby=auth-title]").waitFor({ state: "hidden" });
  const f = p.locator("#live-request-form");
  const notice = p.locator("#live-request-status");
  await expect(p.locator("[name=request_pet]")).toHaveCount(1);
  await f
    .locator("[name=raw_text]")
    .fill("今晚帮我上门照看狗狗，时间还没确定。");
  await p.locator("#local-request").click();
  await p.reload();
  await p.locator("[aria-labelledby=auth-title]").waitFor({ state: "hidden" });
  await expect(f.locator("[name=raw_text]")).toHaveValue(
    "今晚帮我上门照看狗狗，时间还没确定。",
  );
  await p.locator("[name=request_pet]").check();
  await p.locator("#parse-request").click();
  await expect(notice).toContainText("AI 建议已填入", { timeout: 60000 });
  expect(await p.locator("#ai-questions li").count()).toBeGreaterThan(0);
  await p.locator("#save-request").click();
  await expect(notice).not.toHaveText("正在处理…");
  expect((await call("/requests")).items).toHaveLength(0);
  for (const kind of ["home_visit", "dog_walking", "errand_buy"]) {
    await p.locator("#new-request").click();
    await p.locator("[name=request_pet]").check();
    await f.locator("[name=service_type]").selectOption(kind);
    await f.locator("[name=fee_type]").selectOption("free");
    await f.locator("[name=window_start]").fill("2027-06-01T10:00");
    await f.locator("[name=window_end]").fill("2027-06-01T11:00");
    await f.locator("[name=expected_duration_minutes]").fill("30");
    await f.locator("[name=location]").fill("测试社区一号门");
    await f.locator("[name=budget]").fill(kind === "errand_buy" ? "50" : "0");
    await f.locator("[name=handover_notes]").fill("门口交接");
    await f.locator("[name=emergency_contact]").fill("测试联系人 13800000000");
    const items = p.locator(".request-item");
    for (let i = 0; i < (await items.count()); i++) {
      await items
        .nth(i)
        .locator("[data-field=content]")
        .fill("照料步骤" + i);
      await items
        .nth(i)
        .locator("[data-field=completion_condition]")
        .fill("上传照片确认");
    }
    if (kind === "errand_buy") {
      await p.locator("[data-field=product_name]").fill("狗粮");
      await p.locator("[data-field=quantity]").fill("1");
      await p.locator("[data-field=unit]").fill("袋");
    }
    await p.locator("#save-request").click();
    await expect(notice).toHaveText("已保存后端草稿，尚未发布。");
    await expect(f.locator("[name=service_type]")).toBeDisabled();
    let row = (await call("/requests")).items.find(
      (r) => r.service_type === kind,
    );
    expect(row.status).toBe("draft");
    expect(row.pets[0].id).toBe(pet.id);
    await f.locator("[name=location]").fill("测试社区二号门");
    await p.locator("#save-request").click();
    await expect(notice).toHaveText("已保存后端草稿，尚未发布。");
    expect((await call("/requests/" + row.id)).version).toBe(2);
    await p.reload();
    await p.locator("[aria-labelledby=auth-title]").waitFor({ state: "hidden" });
    await expect(f.locator("[name=location]")).toHaveValue("测试社区二号门");
    if (kind === "home_visit") {
      await call("/requests/" + row.id, "PATCH", {
        expected_version: 2,
        location: "另一会话修改",
      });
      await f.locator("[name=location]").fill("本机冲突修改");
      await p.locator("#save-request").click();
      await expect(notice).toContainText("版本已变化");
      await p.locator("#my-requests [data-load-request]").first().click();
      await expect(f.locator("[name=location]")).toHaveValue("另一会话修改");
    }
    await p.locator("#request-consent").check();
    await p.locator("#publish-request").click();
    await expect(notice).toHaveText("已发布，等待匹配。");
    row = await call("/requests/" + row.id);
    expect(row.status).toBe("pending_match");
    await expect(p.locator("#publish-request")).toBeDisabled();
    if (kind === "errand_buy") {
      expect(Number(row.budget)).toBe(50);
      expect(row.fee_type).toBe("free");
    }
  }
  expect(
    (await call("/requests?scope=open")).items.filter((r) =>
      ["home_visit", "dog_walking", "errand_buy"].includes(r.service_type),
    ).length,
  ).toBeGreaterThanOrEqual(3);
  await p.locator("#new-request").click();
  await f.locator("[name=raw_text]").fill("网络失败时保留这句话");
  await p.locator("[name=request_pet]").check();
  // Explicit fault injection only in test: production never falls back to fixture data.
  await p.route("**/api/v0/ai/parse", (route) =>
    route.fulfill({
      status: 502,
      contentType: "application/json",
      body: JSON.stringify({
        code: "ai_upstream_error",
        message: "AI暂不可用",
      }),
    }),
  );
  await p.locator("#parse-request").click();
  await expect(notice).toHaveText("AI暂不可用");
  await expect(f.locator("[name=raw_text]")).toHaveValue(
    "网络失败时保留这句话",
  );
  expect(errors).toEqual([]);
  console.log(
    "PASS: real AI questions; local restore; validation; three-service create/edit/publish; refresh; version conflict; errand goods budget; AI failure retains input.",
  );
} finally {
  await browser.close();
}
