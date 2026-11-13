import { test, expect, type Page } from "@playwright/test";

const suffix = Date.now().toString(36);
const account = `a_week10_${suffix}`;
const password = "Week10Integration2026!";

async function openApiMode(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "连接设置" }).click();
  await page.getByLabel("工作模式").selectOption("api");
  await page.getByLabel("账号", { exact: true }).fill(account);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByLabel("注册昵称").fill("A同学联调");
  await page.getByRole("button", { name: "注册并登录" }).click();
  await expect(page.getByRole("status")).toContainText("已连接后端");
}

async function addPet(page: Page, name: string, species: "cat" | "dog") {
  await page.getByLabel("宠物名字").fill(name);
  await page.getByLabel("类型").selectOption(species);
  await page.getByLabel("出生日期").fill("2024-01-01");
  await page
    .getByLabel("性格")
    .fill(species === "cat" ? "谨慎亲人" : "温和，需全程牵引");
  await page.getByLabel("用品位置").fill("入户柜内");
  await page.getByLabel("照料说明").fill("只执行宠主确认的照料清单");
  await page.getByRole("button", { name: "保存宠物档案" }).click();
  await expect(page.getByRole("status")).toContainText("宠物档案已保存");
}

async function fillCommon(
  page: Page,
  service: "home_visit" | "dog_walking" | "errand_buy",
) {
  await page.getByRole("combobox", { name: "服务类型" }).selectOption(service);
  const petName = service === "dog_walking" ? "联调小狗" : "联调猫咪";
  await page.getByRole("checkbox", { name: new RegExp(petName) }).check();
  await page.getByLabel("可开始时间").fill("2026-12-20T18:00");
  await page.getByLabel("最晚结束时间").fill("2026-12-20T19:30");
  await page.getByLabel("预计服务时长").fill("30");
  await page.getByLabel("服务地点").fill("联调私密地址A-101");
  await page.getByLabel("交接方式").fill("门厅当面交接");
  await page.getByLabel("异常联系人").fill("联调联系人 13800000000");
  const content = await page.getByLabel("事项内容").all();
  const conditions = await page.getByLabel("完成条件").all();
  await page.getByLabel("适用宠物").first().selectOption({ label: petName });
  for (let i = 0; i < content.length; i++) {
    const values =
      service === "home_visit"
        ? ["换水并清洁食盆；用品位于入户柜内"]
        : service === "dog_walking"
          ? ["核对牵引与宠物", "记录出发时间", "安全送回并交接"]
          : ["购买指定商品", "交付商品并核对凭证"];
    await content[i].fill(values[i]);
    await conditions[i].fill("记录时间和备注，由宠主核对");
  }
  if (service === "dog_walking") {
    await page.getByLabel("路线说明").fill("社区南门至中心花园，全程牵引");
    await page
      .getByLabel("行为注意与禁止事项")
      .fill("避开陌生犬，不得松开牵引");
  } else {
    await page.getByLabel("补充要求").fill("仅按已确认清单执行");
    await page.getByLabel("注意与禁止事项").fill("不得擅自喂药");
  }
  if (service === "errand_buy") {
    await page.getByLabel("商品名称与规格").fill("指定品牌猫粮 2kg");
    await page.getByLabel("数量", { exact: true }).fill("1");
    await page.getByLabel("单位", { exact: true }).fill("袋");
    await page.getByLabel("商品预算上限").fill("120");
  }
  await page.getByRole("button", { name: "检查草稿" }).click();
  await page
    .getByRole("checkbox", { name: "我已核对清单、时间和费用" })
    .check();
  await page.getByRole("button", { name: "保存草稿", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存为草稿");
}

test("真实后端：档案、时间、三类需求、草稿编辑发布和大厅隐私", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await openApiMode(page);
  await page.getByRole("button", { name: "基础档案" }).click();
  await addPet(page, "联调猫咪", "cat");
  await addPet(page, "联调小狗", "dog");

  const helperCard = page
    .locator("article")
    .filter({ has: page.getByRole("heading", { name: "帮手档案" }) });
  await helperCard.getByRole("checkbox", { name: "上门遛狗" }).check();
  await helperCard.getByRole("checkbox", { name: "用品代买" }).check();
  await helperCard.getByRole("checkbox", { name: "狗", exact: true }).check();
  await helperCard.getByLabel("服务区域").fill("邻宠社区");
  await helperCard.getByLabel("服务半径").fill("800");
  await helperCard.getByLabel("经验自述").fill("有猫狗照料经验，按清单执行");
  await helperCard.getByLabel("公开地点标签").fill("社区南门附近");
  await helperCard.getByRole("button", { name: "保存帮手档案" }).click();
  await expect(page.getByRole("status")).toContainText("帮手档案已保存");

  await page.getByLabel("可服务开始时间").fill("2026-12-20T17:00");
  await page.getByLabel("可服务结束时间").fill("2026-12-20T21:00");
  await page.getByRole("button", { name: "添加可服务时间" }).click();
  await expect(page.getByRole("status")).toContainText("可服务时间已保存");

  await page.getByRole("button", { name: "发布需求" }).click();
  await fillCommon(page, "home_visit");
  await page.getByRole("button", { name: "确认发布已保存版本" }).click();
  await expect(
    page.getByRole("heading", { name: "我的需求", exact: true }),
  ).toBeVisible();

  await page.getByRole("button", { name: "发布需求" }).click();
  await page.getByRole("button", { name: "新建空白需求" }).click();
  await fillCommon(page, "dog_walking");
  await page.getByRole("button", { name: "返回编辑" }).click();
  await page.getByLabel("行为注意与禁止事项").fill("不得松开牵引，避开陌生犬");
  await page.getByRole("button", { name: "检查草稿" }).click();
  await page
    .getByRole("checkbox", { name: "我已核对清单、时间和费用" })
    .check();
  await page.getByRole("button", { name: "确认发布已保存版本" }).click();
  await expect(page.getByRole("status")).toContainText("请重新保存");
  await page.getByRole("button", { name: "保存草稿", exact: true }).click();
  await page.getByRole("button", { name: "确认发布已保存版本" }).click();
  await expect(
    page.getByRole("heading", { name: "我的需求", exact: true }),
  ).toBeVisible();

  await page.getByRole("button", { name: "发布需求" }).click();
  await page.getByRole("button", { name: "新建空白需求" }).click();
  await fillCommon(page, "errand_buy");
  await page.getByRole("button", { name: "确认发布已保存版本" }).click();
  await expect(
    page.getByRole("heading", { name: "我的需求", exact: true }),
  ).toBeVisible();

  await page.getByRole("button", { name: "社区大厅" }).click();
  await expect(
    page.getByRole("heading", { name: "社区大厅", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "上门代看" }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "上门遛狗" }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "用品代买" }).first(),
  ).toBeVisible();
  await expect(page.getByText("商品预算 120.00 元").first()).toBeVisible();
  await expect(page.locator("main")).not.toContainText("联调私密地址A-101");

  await page.getByRole("button", { name: "我的需求" }).click();
  await expect(
    page.getByRole("heading", { name: "上门代看" }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "上门遛狗" }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "用品代买" }).first(),
  ).toBeVisible();
});
