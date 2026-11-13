<script setup lang="ts">
import { ref, reactive, computed, toRaw } from "vue";
import { Api, ApiError } from "./api";
import {
  blank,
  fixedItems,
  kinds,
  validate,
  payload,
  beijing,
  type Pet,
  type RequestRow,
  type Kind,
} from "./domain";
const crypto = globalThis.crypto;
const api = new Api(),
  mode = ref<"mock" | "api">("mock"),
  page = ref("发布需求"),
  busy = ref(false),
  notice = ref(""),
  errors = ref<string[]>([]),
  review = ref(false),
  consent = ref(false),
  connected = ref(false);
const base = ref(api.base),
  account = ref(""),
  password = ref(""),
  displayName = ref(""),
  userName = ref("演示用户");
const pets = ref<Pet[]>([
  { id: "mock-cat", name: "年糕", species: "cat", birth_date: "2024-01-01" },
  { id: "mock-dog", name: "豆豆", species: "dog", birth_date: "2023-01-01" },
]);
const pet = reactive<Pet>({
  id: "",
  name: "",
  species: "cat",
  birth_date: "",
  breed: "",
  temperament: "",
  precautions: "",
  supplies_location: "",
  care_instructions: "",
});
const availability = reactive({ start_at: "", end_at: "" }),
  windows = ref<{ id: string; start_at: string; end_at: string }[]>([]);
const helper = reactive({
  service_types: ["home_visit"] as Kind[],
  service_area: "",
  experience: "",
  supported_species: ["cat"] as string[],
  service_radius_m: 500,
  fee_pref: "both",
  address_tag: "",
});
const draft = reactive(blank()),
  questions = ref<string[]>([]),
  aiPreview = ref(""),
  saved = ref<RequestRow | null>(null),
  detail = ref<RequestRow | null>(null),
  rows = ref<RequestRow[]>([]),
  mockRows = ref<RequestRow[]>([]),
  cursor = ref<string | null>(null),
  filter = ref(""),
  scope = ref("open");
let createKey = crypto.randomUUID(),
  publishKey = crypto.randomUUID(),
  savedBody = "";
const visibleRows = computed(() =>
  rows.value.filter((r) => !filter.value || r.service_type === filter.value),
);
const availablePets = computed(() =>
  pets.value.filter(
    (p) => draft.service_type !== "dog_walking" || p.species === "dog",
  ),
);
async function run(action: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  notice.value = "";
  try {
    await action();
  } catch (e) {
    notice.value = e instanceof Error ? e.message : "操作失败";
    if (e instanceof ApiError) {
      if (e.status === 401) {
        connected.value = false;
        notice.value = "登录已失效，请重新登录。草稿仍保留。";
      }
      if (e.status === 409) notice.value += " 请重新打开详情获取最新版本。";
    }
  } finally {
    busy.value = false;
  }
}
function switchMode() {
  api.token = "";
  connected.value = false;
  rows.value = [];
  mockRows.value = [];
  pets.value =
    mode.value === "mock"
      ? [
          {
            id: "mock-cat",
            name: "年糕",
            species: "cat",
            birth_date: "2024-01-01",
          },
          {
            id: "mock-dog",
            name: "豆豆",
            species: "dog",
            birth_date: "2023-01-01",
          },
        ]
      : [];
  newDraft();
  detail.value = null;
  notice.value = "模式已切换。不会向另一模式复制任务或凭证。";
}
function newDraft() {
  Object.assign(draft, blank());
  saved.value = null;
  review.value = false;
  consent.value = false;
  questions.value = [];
  aiPreview.value = "";
  errors.value = [];
  createKey = crypto.randomUUID();
  publishKey = crypto.randomUUID();
  savedBody = "";
}
function kindChanged() {
  draft.pet_ids = [];
  draft.checklist_items = fixedItems(draft.service_type);
  draft.budget = "0.00";
}
async function login(register = false) {
  await run(async () => {
    const u = new URL(base.value);
    if (
      !["http:", "https:"].includes(u.protocol) ||
      u.username ||
      u.password ||
      u.search ||
      u.hash
    )
      throw Error("请输入有效的 HTTP(S) API 地址，不含凭证或查询参数");
    api.base = base.value;
    if (register)
      await api.call("/auth/register", "POST", {
        account: account.value,
        password: password.value,
        display_name: displayName.value,
        roles: ["owner", "helper"],
      });
    const result = await api.call<{ access_token: string }>(
      "/auth/login",
      "POST",
      { account: account.value, password: password.value },
    );
    api.token = result.access_token;
    connected.value = true;
    password.value = "";
    const me = await api.call<{ display_name: string }>("/users/me");
    userName.value = me.display_name;
    pets.value = (await api.pets()).items;
    notice.value = "已连接后端并载入宠物档案。";
  });
}
function editPet(p?: Pet) {
  Object.assign(
    pet,
    {
      id: "",
      name: "",
      species: "cat",
      birth_date: "",
      breed: "",
      temperament: "",
      precautions: "",
      supplies_location: "",
      care_instructions: "",
    },
    p || {},
  );
}
async function savePet() {
  await run(async () => {
    if (
      pet.birth_date >
      new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Shanghai" })
    )
      throw Error("出生日期不能晚于今天");
    const { id, ...body } = toRaw(pet);
    if (mode.value === "api") {
      await api.call(
        id ? `/pets/${id}` : "/pets",
        id ? "PATCH" : "POST",
        body,
        crypto.randomUUID(),
      );
      pets.value = (await api.pets()).items;
    } else {
      const value = { ...body, id: id || crypto.randomUUID() };
      const index = pets.value.findIndex((p) => p.id === id);
      if (index < 0) pets.value.push(value);
      else pets.value[index] = value;
    }
    editPet();
    notice.value = "宠物档案已保存。";
  });
}
async function saveHelper() {
  await run(async () => {
    if (!helper.service_types.length || !helper.supported_species.length)
      throw Error("请选择服务类型和宠物类型");
    if (mode.value === "api")
      await api.call("/helpers/me", "PUT", toRaw(helper), crypto.randomUUID());
    notice.value =
      mode.value === "mock"
        ? "帮手档案已保留在当前演示会话。"
        : "帮手档案已保存。";
  });
}
async function parse() {
  await run(async () => {
    questions.value = [];
    aiPreview.value = "";
    if (!draft.raw_text.trim()) throw Error("请先描述需求");
    if (mode.value === "mock") {
      questions.value = [
        "请明确起止时间与预计时长。",
        "请填写每项照料的具体要求及完成条件。",
        "请确认服务费用、交接方式及异常联系人。",
      ];
      notice.value = "这是固定补问示例，不是 AI 推理。";
      return;
    }
    const result = await api.call<{ draft: unknown; questions: unknown }>(
      "/ai/parse",
      "POST",
      {
        text: draft.raw_text,
        reference_time: new Date().toISOString(),
        timezone: "Asia/Shanghai",
        pet_ids: draft.pet_ids,
      },
    );
    aiPreview.value = JSON.stringify(result.draft, null, 2);
    questions.value = Array.isArray(result.questions)
      ? result.questions.filter((x): x is string => typeof x === "string")
      : [];
    notice.value =
      "AI 返回仅供参考，自动映射仍待 C 确认；请手动核对填写，不自动覆盖草稿。";
  });
}
function check() {
  errors.value = validate(toRaw(draft), pets.value);
  if (!errors.value.length) {
    review.value = true;
    consent.value = false;
  }
}
async function save() {
  await run(async () => {
    const problem = validate(toRaw(draft), pets.value);
    if (problem.length) throw Error(problem.join("；"));
    const body = payload(toRaw(draft));
    if (mode.value === "mock") {
      saved.value = {
        ...body,
        id: saved.value?.id || crypto.randomUUID(),
        version: (saved.value?.version || 0) + 1,
        status: "draft",
      };
      const index = mockRows.value.findIndex((x) => x.id === saved.value!.id);
      if (index < 0) mockRows.value.push(structuredClone(toRaw(saved.value)));
      else mockRows.value[index] = structuredClone(toRaw(saved.value));
    } else if (saved.value) {
      const { pet_ids, service_type, ...patch } = body;
      saved.value = await api.call<RequestRow>(
        `/requests/${saved.value.id}`,
        "PATCH",
        { ...patch, expected_version: saved.value.version },
        crypto.randomUUID(),
      );
    } else {
      const serial = JSON.stringify(body);
      if (savedBody && savedBody !== serial) createKey = crypto.randomUUID();
      savedBody = serial;
      saved.value = await api.create(body, createKey);
    }
    savedBody = JSON.stringify(payload(toRaw(draft)));
    notice.value = "已保存为草稿，尚未发布。";
  });
}
async function publish() {
  if (!saved.value || !consent.value) return;
  if (
    page.value === "发布需求" &&
    savedBody !== JSON.stringify(payload(toRaw(draft)))
  ) {
    notice.value = "草稿已修改，请重新保存后再发布。";
    return;
  }
  await run(async () => {
    if (mode.value === "api")
      saved.value = await api.publish(saved.value!, publishKey);
    else {
      saved.value!.status = "pending_match";
      const r = mockRows.value.find((x) => x.id === saved.value!.id);
      if (r) r.status = "pending_match";
    }
    notice.value = "已发布，状态：待匹配。";
    detail.value = saved.value;
    page.value = "我的需求";
    scope.value = "mine";
    await loadRows();
  });
}
async function loadRows(more = false) {
  if (mode.value === "mock") {
    rows.value = mockRows.value
      .filter((r) => scope.value === "mine" || r.status === "pending_match")
      .map((r) =>
        scope.value === "mine"
          ? r
          : {
              id: r.id,
              version: r.version,
              status: r.status,
              service_type: r.service_type,
              window_start: r.window_start,
              window_end: r.window_end,
              budget: r.budget,
              fee_type: r.fee_type,
            },
      );
    cursor.value = null;
  } else {
    const data = await api.requests(scope.value, more ? cursor.value : null);
    rows.value = more ? [...rows.value, ...data.items] : data.items;
    cursor.value = data.next_cursor;
  }
}
async function navigate(tab: string) {
  page.value = tab;
  detail.value = null;
  notice.value = "";
  if (["社区大厅", "我的需求"].includes(tab)) {
    scope.value = tab === "社区大厅" ? "open" : "mine";
    await run(() => loadRows());
  }
}
async function openDetail(r: RequestRow) {
  await run(async () => {
    detail.value =
      mode.value === "mock"
        ? r
        : await api.call<RequestRow>(`/requests/${r.id}`);
  });
}
async function saveWindow() {
  await run(async () => {
    const body = {
      start_at: beijing(availability.start_at),
      end_at: beijing(availability.end_at),
    };
    if (
      !Number.isFinite(Date.parse(body.start_at)) ||
      !Number.isFinite(Date.parse(body.end_at)) ||
      Date.parse(body.end_at) <= Date.parse(body.start_at)
    )
      throw Error("请填写有效的可服务起止时间");
    if (mode.value === "api") {
      await api.call(
        "/helpers/me/availability",
        "POST",
        body,
        crypto.randomUUID(),
      );
      windows.value = (
        await api.call<{ items: typeof windows.value }>(
          "/helpers/me/availability?limit=100",
        )
      ).items;
    } else windows.value.push({ id: crypto.randomUUID(), ...body });
    notice.value = "可服务时间已保存。";
  });
}
function editSaved(r: RequestRow) {
  if (!r.pet_ids || !r.checklist_items) {
    notice.value = "此响应缺少完整草稿，请刷新详情。";
    return;
  }
  const d = blank();
  for (const key of Object.keys(d) as (keyof typeof d)[])
    if (r[key] !== undefined)
      (d as unknown as Record<string, unknown>)[key] = structuredClone(
        toRaw(r[key] as object),
      );
  const local = (s: string) =>
    new Date(Date.parse(s) + 8 * 3600000).toISOString().slice(0, 16);
  d.window_start = local(d.window_start);
  d.window_end = local(d.window_end);
  Object.assign(draft, d);
  saved.value = r;
  savedBody = JSON.stringify(payload(toRaw(draft)));
  publishKey = crypto.randomUUID();
  consent.value = false;
  review.value = false;
  page.value = "发布需求";
}
function exportDraft() {
  const content = JSON.stringify(
    {
      schema: "pethelp-frontend-unconfirmed-v1",
      draft: toRaw(draft),
      note: "前端草稿；代买 budget 表示商品预算，服务报酬在预约阶段约定。含私密信息，请谨慎分享",
    },
    null,
    2,
  );
  const url = URL.createObjectURL(
    new Blob([content], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = "pethelp-draft.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
</script>
<template>
  <div class="layout">
    <aside>
      <div class="brand">邻宠帮<span>第十周 · 可编辑工作台</span></div>
      <nav>
        <button
          v-for="tab in [
            '发布需求',
            '社区大厅',
            '我的需求',
            '基础档案',
            '连接设置',
          ]"
          :class="{ active: page === tab }"
          @click="navigate(tab)"
        >
          {{ tab }}
        </button>
      </nav>
      <p class="aside-note">每一份托付<br />从清晰开始</p>
    </aside>
    <main>
      <header>
        <span>社区宠物临时互助</span
        ><b>{{
          mode === "mock" ? "演示用户" : connected ? userName : "未登录"
        }}</b>
      </header>
      <div class="banner">
        {{
          mode === "mock"
            ? "模拟模式 · 数据只在当前会话保留，刷新即清空"
            : "后端模式 · 状态以服务端为准，三类需求均已接通"
        }}
        · AI 尚未完成契约联调
      </div>
      <p role="status" aria-live="polite" class="message">
        {{ busy ? "正在处理，请稍候…" : notice }}
      </p>
      <fieldset :disabled="busy" class="workspace">
        <section v-if="page === '连接设置'">
          <h1>连接设置</h1>
          <article>
            <label
              >工作模式<select v-model="mode" @change="switchMode">
                <option value="mock">模拟演示</option>
                <option value="api">连接 B 的后端</option>
              </select></label
            >
            <p>切换模式会清空当前演示任务及草稿，请先导出需要保留的草稿。</p>
            <template v-if="mode === 'api'"
              ><label
                >API 地址<input
                  v-model="base"
                  :disabled="connected"
                  placeholder="http://127.0.0.1:8000/api/v0"
              /></label>
              <p class="hint">
                仅填写你信任的后端地址，登录信息将发送到此地址。令牌仅保存在内存。
              </p>
              <form v-if="!connected" @submit.prevent="login()">
                <label
                  >账号<input
                    required
                    v-model="account"
                    autocomplete="username" /></label
                ><label
                  >密码<input
                    required
                    minlength="8"
                    type="password"
                    v-model="password"
                    autocomplete="current-password" /></label
                ><label
                  >注册昵称（仅注册使用）<input v-model="displayName"
                /></label>
                <div class="actions">
                  <button class="primary">登录</button
                  ><button
                    type="button"
                    :disabled="!account || password.length < 8 || !displayName"
                    @click="login(true)"
                  >
                    注册并登录
                  </button>
                </div>
              </form>
              <button
                v-else
                @click="
                  api.token = '';
                  connected = false;
                  pets = [];
                  rows = [];
                  detail = null;
                  notice = '已退出，草稿仍保留。';
                "
              >
                退出登录
              </button></template
            >
          </article>
        </section>
        <section v-else-if="page === '基础档案'">
          <h1>照料，从了解开始</h1>
          <p>维护宠物说明和你的服务能力。核验状态由后端管理。</p>
          <div class="grid">
            <article v-for="p in pets">
              <h2>{{ p.name }} · {{ p.species === "cat" ? "猫" : "狗" }}</h2>
              <p>出生日期：{{ p.birth_date }}</p>
              <p>{{ p.care_instructions || "尚未补充照料说明" }}</p>
              <button @click="editPet(p)">编辑档案</button>
            </article>
          </div>
          <article>
            <h2>{{ pet.id ? "编辑宠物" : "新增宠物" }}</h2>
            <form @submit.prevent="savePet">
              <div class="grid">
                <label
                  >宠物名字<input
                    required
                    maxlength="60"
                    v-model="pet.name" /></label
                ><label
                  >类型<select v-model="pet.species">
                    <option value="cat">猫</option>
                    <option value="dog">狗</option>
                  </select></label
                ><label
                  >出生日期<input
                    required
                    type="date"
                    v-model="pet.birth_date" /></label
                ><label>品种<input maxlength="60" v-model="pet.breed" /></label>
              </div>
              <label>性格<input v-model="pet.temperament" /></label
              ><label>注意事项<textarea v-model="pet.precautions" /></label
              ><label>用品位置<input v-model="pet.supplies_location" /></label
              ><label
                >照料说明<textarea
                  v-model="pet.care_instructions"
                  placeholder="仅填写宠主明确提供的要求"
                />
              </label>
              <div class="actions">
                <button
                  class="primary"
                  :disabled="mode === 'api' && !connected"
                >
                  保存宠物档案</button
                ><button type="button" @click="editPet()">清空编辑</button>
              </div>
            </form>
          </article>
          <article>
            <h2>帮手档案</h2>
            <form @submit.prevent="saveHelper">
              <p>可提供的服务</p>
              <label class="inline" v-for="(label, key) in kinds"
                ><input
                  type="checkbox"
                  :value="key"
                  v-model="helper.service_types"
                />{{ label }}</label
              >
              <p>支持宠物</p>
              <label class="inline"
                ><input
                  type="checkbox"
                  value="cat"
                  v-model="helper.supported_species"
                />猫</label
              ><label class="inline"
                ><input
                  type="checkbox"
                  value="dog"
                  v-model="helper.supported_species"
                />狗</label
              ><label
                >服务区域<input required v-model="helper.service_area" /></label
              ><label
                >服务半径（米）<input
                  required
                  type="number"
                  min="1"
                  step="1"
                  v-model.number="helper.service_radius_m" /></label
              ><label
                >经验自述<textarea
                  required
                  v-model="helper.experience"
                /></label
              ><label
                >公开地点标签（不含门牌）<input
                  maxlength="50"
                  v-model="helper.address_tag" /></label
              ><label
                >费用偏好<select v-model="helper.fee_pref">
                  <option value="both">无偿或有偿均可</option>
                  <option value="free">无偿</option>
                  <option value="paid">有偿</option>
                </select></label
              ><button class="primary" :disabled="mode === 'api' && !connected">
                保存帮手档案
              </button>
            </form>
          </article>
          <article>
            <h2>可服务时间</h2>
            <p>请先保存帮手档案。时间按北京时间提交。</p>
            <form @submit.prevent="saveWindow">
              <div class="grid">
                <label
                  >可服务开始时间<input
                    type="datetime-local"
                    required
                    v-model="availability.start_at" /></label
                ><label
                  >可服务结束时间<input
                    type="datetime-local"
                    required
                    v-model="availability.end_at"
                /></label>
              </div>
              <button :disabled="mode === 'api' && !connected">
                添加可服务时间
              </button>
            </form>
            <p v-for="w in windows">{{ w.start_at }} → {{ w.end_at }}</p>
          </article>
        </section>
        <section v-else-if="page === '发布需求'">
          <div class="heading">
            <div>
              <p class="eyebrow">A LITTLE HELP, A LOT OF CARE</p>
              <h1>把需要的照料，说清楚</h1>
              <p>填写 → 检查清单 → 保存草稿 → 确认发布</p>
            </div>
          </div>
          <div class="actions">
            <button @click="exportDraft">导出当前草稿</button
            ><button @click="newDraft">新建空白需求</button>
          </div>
          <template v-if="!review"
            ><article>
              <label
                >服务类型<select
                  v-model="draft.service_type"
                  :disabled="!!saved"
                  @change="kindChanged"
                >
                  <option v-for="(label, key) in kinds" :value="key">
                    {{ label }}
                  </option>
                </select></label
              ><label
                >一句话描述需求<textarea
                  v-model="draft.raw_text"
                  placeholder="例如：周五帮年糕换水，别打开阳台门。"
                /></label
              ><button @click="parse" :disabled="mode === 'api' && !connected">
                {{ mode === "mock" ? "查看模拟补问" : "请求 AI 解析" }}
              </button>
              <p class="hint">解析失败可继续手动填写，原话和已填内容不丢失。</p>
              <ul>
                <li v-for="q in questions">{{ q }}</li>
              </ul>
              <details v-if="aiPreview">
                <summary>查看 AI 原始建议（尚未映射）</summary>
                <pre>{{ aiPreview }}</pre>
              </details>
            </article>
            <article>
              <h2>选择宠物与时间</h2>
              <p v-if="!availablePets.length">
                暂无符合类型的宠物，请先在基础档案中添加。
              </p>
              <label class="inline" v-for="p in availablePets"
                ><input
                  type="checkbox"
                  :value="p.id"
                  v-model="draft.pet_ids"
                  :disabled="!!saved"
                />{{ p.name }} · {{ p.species === "cat" ? "猫" : "狗" }}</label
              >
              <div class="grid">
                <label
                  >可开始时间（北京时间）<input
                    type="datetime-local"
                    v-model="draft.window_start" /></label
                ><label
                  >最晚结束时间（北京时间）<input
                    type="datetime-local"
                    v-model="draft.window_end" /></label
                ><label
                  >预计服务时长（分钟）<input
                    type="number"
                    min="1"
                    step="1"
                    v-model.number="draft.expected_duration_minutes" /></label
                ><label>服务地点<input v-model="draft.location" /></label>
              </div>
              <label>交接方式<input v-model="draft.handover_notes" /></label
              ><label
                >异常联系人<input v-model="draft.emergency_contact"
              /></label>
              <p class="hint">地点、交接和联系方式不展示到公开大厅。</p>
            </article>
            <article>
              <h2>逐项照料清单</h2>
              <div
                class="care-row"
                v-for="(item, i) in draft.checklist_items"
                :key="item.item_key"
              >
                <b>照料项 {{ i + 1 }}</b
                ><label
                  >适用宠物<select v-model="item.pet_id">
                    <option :value="undefined">共同事项</option>
                    <option v-for="petId in draft.pet_ids" :value="petId">
                      {{ pets.find((p) => p.id === petId)?.name }}
                    </option>
                  </select></label
                ><label>事项内容<input v-model="item.content" /></label
                ><label
                  >完成条件<input
                    v-model="item.completion_condition"
                    placeholder="由宠主说明如何核对，照片不自动证明完成" /></label
                ><template v-if="item.item_key === 'purchase'"
                  ><label
                    >商品名称与规格<input v-model="item.product_name"
                  /></label>
                  <div class="grid">
                    <label
                      >数量<input
                        type="number"
                        min="1"
                        step="1"
                        v-model.number="item.quantity" /></label
                    ><label
                      >单位<input v-model="item.unit"
                    /></label></div></template
                ><button
                  v-if="
                    draft.service_type === 'home_visit' &&
                    draft.checklist_items.length > 1
                  "
                  @click="draft.checklist_items.splice(i, 1)"
                >
                  删除此项
                </button>
              </div>
              <button
                v-if="draft.service_type === 'home_visit'"
                @click="
                  draft.checklist_items.push({
                    item_key: 'care_' + crypto.randomUUID(),
                    position: draft.checklist_items.length + 1,
                    content: '',
                    completion_condition: '',
                    required: true,
                  })
                "
              >
                添加照料项
              </button>
              <p v-if="draft.service_type === 'home_visit'" class="hint">
                本次需求的用品位置请写入对应照料项内容；多宠专属要求请选择具体宠物。
              </p>
              <label
                >{{
                  draft.service_type === "dog_walking"
                    ? "路线说明"
                    : "补充要求"
                }}<textarea
                  v-model="draft.requirements"
                  :placeholder="
                    draft.service_type === 'dog_walking'
                      ? '填写遛狗路线、范围和交通说明'
                      : '填写需求的其他补充说明'
                  "
                /></label
              ><label
                >{{
                  draft.service_type === "dog_walking"
                    ? "行为注意与禁止事项"
                    : "注意与禁止事项"
                }}<textarea v-model="draft.precautions" />
              </label>
            </article>
            <article>
              <h2>费用约定</h2>
              <label
                >费用方式<select
                  v-model="draft.fee_type"
                  @change="
                    draft.service_type !== 'errand_buy' &&
                    draft.fee_type === 'free' &&
                    (draft.budget = '0.00')
                  "
                >
                  <option value="free">无偿互助</option>
                  <option value="paid">有偿服务</option>
                </select></label
              ><label
                >{{
                  draft.service_type === "errand_buy"
                    ? "商品预算上限（元）"
                    : "服务预算（元）"
                }}<input
                  :disabled="
                    draft.service_type !== 'errand_buy' &&
                    draft.fee_type === 'free'
                  "
                  type="number"
                  min="0"
                  step="0.01"
                  v-model="draft.budget" /></label
              ><template v-if="draft.service_type === 'errand_buy'">
                <p class="hint">
                  代买 budget
                  表示商品预算；发布阶段不填写服务报酬，服务报酬在预约的
                  agreed_fee 中约定，实际商品费用记录到 actual_cost。
                </p></template
              >
            </article>
            <ul role="alert" class="message">
              <li v-for="error in errors">{{ error }}</li>
            </ul>
            <button class="primary" @click="check">检查草稿 →</button></template
          >
          <article v-else>
            <h2>核对本次托付</h2>
            <p>
              {{ kinds[draft.service_type] }} ·
              {{
                draft.pet_ids
                  .map((id) => pets.find((p) => p.id === id)?.name)
                  .join("、")
              }}
            </p>
            <p>
              {{ draft.window_start }} 至 {{ draft.window_end }}（北京时间），{{
                draft.expected_duration_minutes
              }}
              分钟
            </p>
            <p>地点：{{ draft.location }}；交接：{{ draft.handover_notes }}</p>
            <p>异常联系人：{{ draft.emergency_contact }}</p>
            <p>
              {{
                draft.service_type === "errand_buy" ? "商品预算" : "服务预算"
              }}：{{ draft.budget }} 元
              <span v-if="draft.service_type === 'errand_buy'">
                · 服务报酬在预约阶段约定</span
              >
            </p>
            <ul>
              <li v-for="i in draft.checklist_items">
                {{ i.content }} — 完成条件：{{ i.completion_condition
                }}<span v-if="i.product_name"
                  >；{{ i.product_name }} {{ i.quantity }}{{ i.unit }}</span
                >
              </li>
            </ul>
            <p>补充要求：{{ draft.requirements || "无" }}</p>
            <p>注意事项：{{ draft.precautions || "无" }}</p>
            <p v-if="saved">
              服务端／模拟草稿版本：{{ saved.version }} · {{ saved.status }}
            </p>
            <label class="inline"
              ><input
                type="checkbox"
                v-model="consent"
              />我已核对清单、时间和费用</label
            >
            <div class="actions">
              <button
                @click="
                  review = false;
                  consent = false;
                "
              >
                返回编辑</button
              ><button
                @click="save"
                :disabled="!consent || (mode === 'api' && !connected)"
              >
                保存草稿</button
              ><button
                class="primary"
                @click="publish"
                :disabled="!saved || !consent || saved.status !== 'draft'"
              >
                确认发布已保存版本
              </button>
            </div>
            <p class="hint">
              修改后请先重新保存，再发布。发布采用已保存的版本。
            </p>
          </article>
        </section>
        <section v-else>
          <h1>{{ page }}</h1>
          <div class="actions">
            <label
              >服务筛选<select v-model="filter">
                <option value="">全部类型</option>
                <option v-for="(label, key) in kinds" :value="key">
                  {{ label }}
                </option>
              </select></label
            ><button @click="run(() => loadRows())">刷新列表</button>
          </div>
          <p class="hint">筛选作用于已加载数据；大厅仅展示公开字段。</p>
          <article v-if="!visibleRows.length">
            <h2>暂时没有需求</h2>
            <p>发布一份需求，或稍后刷新。</p>
          </article>
          <article v-for="r in visibleRows" :key="r.id">
            <h2>{{ kinds[r.service_type] }}</h2>
            <p>
              {{ r.window_start }} · {{ r.status }} ·
              {{ r.service_type === "errand_buy" ? "商品预算" : "服务预算" }}
              {{ r.budget }} 元
            </p>
            <button @click="openDetail(r)">查看详情</button>
          </article>
          <button v-if="cursor" @click="run(() => loadRows(true))">
            加载更多
          </button>
          <article v-if="detail">
            <h2>需求详情</h2>
            <p>
              {{ kinds[detail.service_type] }} · {{ detail.status }} · 版本
              {{ detail.version }}
            </p>
            <p>{{ detail.window_start }} → {{ detail.window_end }}</p>
            <template v-if="page === '我的需求'"
              ><p v-if="detail.location">地点：{{ detail.location }}</p>
              <p v-if="detail.handover_notes">
                交接：{{ detail.handover_notes }}
              </p>
              <p v-if="detail.emergency_contact">
                异常联系人：{{ detail.emergency_contact }}
              </p>
              <ul>
                <li v-for="i in detail.checklist_items">
                  {{ i.content }} — {{ i.completion_condition }}
                </li>
              </ul>
              <button
                v-if="detail.status === 'draft'"
                @click="editSaved(detail)"
              >
                编辑草稿</button
              ><button
                v-if="detail.status === 'draft'"
                @click="
                  saved = detail;
                  publishKey = crypto.randomUUID();
                  consent = false;
                  page = '草稿发布';
                "
              >
                发布此草稿
              </button></template
            ><button @click="detail = null">关闭详情</button>
          </article>
          <article v-if="page === '草稿发布' && saved">
            <h2>确认发布草稿</h2>
            <p>需求 {{ saved.id }}，版本 {{ saved.version }}</p>
            <label class="inline"
              ><input
                type="checkbox"
                v-model="consent"
              />我已在详情核对该版本</label
            ><button :disabled="!consent" @click="publish">确认发布</button>
          </article>
        </section>
      </fieldset>
      <footer>
        第十周阶段成果 · 未确认字段保留为草稿 · 不包含真实预约及结算
      </footer>
    </main>
  </div>
</template>
<style scoped>
.workspace {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.care-row {
  padding: 18px;
  background: #f5f7f2;
  border-radius: 10px;
  margin: 15px 0;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.actions {
  flex-wrap: wrap;
}
.actions button {
  align-self: center;
}
</style>
