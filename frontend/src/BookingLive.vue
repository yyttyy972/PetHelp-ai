<script setup lang="ts">
import { ref, onUnmounted, watch, nextTick } from "vue";
import { Api, ApiError } from "./api";
import { beijing, type RequestRow } from "./domain";
import BookingList from "./BookingList.vue";
import ExceptionPanel from "./ExceptionPanel.vue";
const props = defineProps<{ api: Api }>();
const requestId = ref(""),
  bookingId = ref(""),
  request = ref<RequestRow | null>(null),
  busy = ref(false),
  message = ref("");
const candidates = ref<
    { helper_id: string; display_name: string; reasons: string[] }[]
  >([]),
  helperId = ref(""),
  start = ref(""),
  end = ref(""),
  fee = ref(0),
  consent = ref(false);
const booking = ref<Record<string, unknown> | null>(null),
  records = ref<Record<string, unknown>[]>([]),
  note = ref(""),
  photos = ref<string[]>([]),
  cost = ref(0),
  reason = ref(""),
  picture = ref("");
onUnmounted(() => {
  if (picture.value) URL.revokeObjectURL(picture.value);
});
async function openBooking(id: string) {
  const data = await props.api.call<Record<string, unknown>>(
    `/bookings/${encodeURIComponent(id)}`,
  );
  requestId.value = String(data.request_id);
  bookingId.value = id;
  await nextTick();
  request.value = {
    id: String(data.request_id),
    version: Number(data.request_version),
    status: String(data.request_status),
    service_type: (data.checklist_items as { item_key: string }[]).some(
      (i) => i.item_key === "purchase",
    )
      ? "errand_buy"
      : (data.checklist_items as { item_key: string }[]).some(
            (i) => i.item_key === "pickup",
          )
        ? "dog_walking"
        : "home_visit",
    checklist_items: data.checklist_items as RequestRow["checklist_items"],
  };
  booking.value = data;
  await history();
}
const messages: Record<string, string> = {
  version_conflict: "需求已更新，请重新加载并核对新版本。",
  reservation_expired: "预约确认已超时，请重新匹配并创建预约。",
  time_conflict: "该时间已被占用，请调整预约时间。",
  forbidden: "当前账号无权执行此操作，请使用对应参与者账号。",
  invalid_state: "当前状态或预约时间不允许此操作，请刷新并核对。",
  checklist_incomplete: "必需清单尚未完成，请补齐执行记录。",
  invalid_evidence: "凭证不符合要求，请核对顺序、时间、照片和商品费用。",
};
watch(requestId, () => {
  request.value = null;
  booking.value = null;
  bookingId.value = "";
  records.value = [];
  candidates.value = [];
  consent.value = false;
  photos.value = [];
  note.value = "";
});
watch(bookingId, () => {
  booking.value = null;
  records.value = [];
  consent.value = false;
  photos.value = [];
  note.value = "";
});
async function run(fn: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  message.value = "";
  try {
    await fn();
    if (booking.value && request.value) {
      request.value.status = String(
        booking.value.request_status || booking.value.status,
      );
    }
  } catch (e) {
    message.value =
      e instanceof ApiError
        ? messages[e.code] || e.message
        : e instanceof Error
          ? e.message
          : "操作失败，请重试";
  } finally {
    busy.value = false;
  }
}
async function load() {
  request.value = await props.api.call<RequestRow>(
    `/requests/${encodeURIComponent(requestId.value.trim())}`,
  );
  candidates.value = [];
  consent.value = false;
}
async function match() {
  if (!request.value) return;
  const data = (await props.api.match(
    request.value.id,
    request.value.version,
  )) as { candidates: typeof candidates.value };
  candidates.value = data.candidates;
  if (!data.candidates.length)
    message.value = "暂无匹配邻居，请调整时间或稍后重试。";
}
async function reserve() {
  if (!request.value || !consent.value) return;
  const s = beijing(start.value),
    e = beijing(end.value);
  if (
    !helperId.value ||
    !Number.isFinite(Date.parse(s)) ||
    Date.parse(e) <= Date.parse(s)
  )
    throw Error("请选择邻居并填写有效起止时间");
  const created = (await props.api.book(request.value.id, {
    expected_version: request.value.version,
    helper_id: helperId.value,
    scheduled_start: s,
    scheduled_end: e,
    agreed_fee: fee.value,
  })) as Record<string, unknown>;
  bookingId.value = String(created.id);
  await nextTick();
  booking.value = created;
  consent.value = false;
  message.value = "预约已创建，双方可从预约列表进入并确认。";
}
async function action(value: "confirm" | "start" | "submit" | "verify") {
  if (!request.value || !bookingId.value.trim())
    throw Error("请先加载需求并填写预约编号");
  if ((value === "confirm" || value === "verify") && !consent.value)
    throw Error("请先核对并勾选确认");
  booking.value = (await props.api.bookingAction(
    bookingId.value.trim(),
    value,
    request.value.version,
  )) as Record<string, unknown>;
  consent.value = false;
  message.value = "操作成功，状态以服务器返回为准。";
}
async function history() {
  let cursor: string | undefined;
  const all: Record<string, unknown>[] = [];
  do {
    const data = (await props.api.bookingRecords(
      bookingId.value.trim(),
      cursor,
    )) as { items: Record<string, unknown>[]; next_cursor: string | null };
    all.push(...data.items);
    cursor = data.next_cursor || undefined;
  } while (cursor);
  records.value = all;
}
async function upload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  await run(async () => {
    if (file.size > 5 * 1024 * 1024) throw Error("照片不能超过 5 MB");
    const body = new FormData();
    body.append("file", file);
    body.append("purpose", "evidence");
    const response = await fetch(props.api.base + "/media", {
      method: "POST",
      headers: { Authorization: `Bearer ${props.api.token}` },
      body,
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) throw Error(`照片上传失败（${response.status}）`);
    photos.value.push((await response.json()).url);
  });
}
async function record(item: unknown) {
  const i = item as { id?: string; item_key: string };
  if (!i.id) throw Error("清单缺少服务器编号，请重新加载需求");
  if (!note.value.trim() && !photos.value.length)
    throw Error("请填写完成情况或上传照片");
  const kind = (
    ["pickup", "departure", "return", "purchase", "delivery"].includes(
      i.item_key,
    )
      ? i.item_key
      : "item_completed"
  ) as
    | "pickup"
    | "departure"
    | "return"
    | "purchase"
    | "delivery"
    | "item_completed";
  if (kind === "purchase" && !photos.value.length)
    throw Error("购买记录必须上传购买凭证");
  await props.api.addRecord(bookingId.value.trim(), {
    checklist_item_id: i.id,
    kind,
    occurred_at: new Date().toISOString(),
    note: note.value.trim(),
    photo_urls: photos.value,
    ...(kind === "purchase" ? { actual_cost: cost.value } : {}),
  });
  note.value = "";
  photos.value = [];
  message.value = "记录已保存";
  await history();
}
async function view(url: unknown) {
  if (typeof url !== "string" || !url.startsWith("/api/v0/media/"))
    throw Error("无效的凭证地址");
  const response = await fetch(
    props.api.base.replace(/\/api\/v0\/?$/, "") + url,
    {
      headers: { Authorization: `Bearer ${props.api.token}` },
      signal: AbortSignal.timeout(15000),
    },
  );
  if (!response.ok) throw Error("无法读取凭证");
  if (picture.value) URL.revokeObjectURL(picture.value);
  picture.value = URL.createObjectURL(await response.blob());
}
</script>
<template>
  <section>
    <BookingList :api="api" @open="(id) => run(() => openBooking(id))" />
    <button
      v-if="bookingId"
      :disabled="busy"
      @click="run(() => openBooking(bookingId))"
    >
      刷新预约详情
    </button>
    <h1>预约与执行</h1>
    <p>
      使用连接设置中已登录的账号。双方分别登录自己的账号进行确认、执行与核验。
    </p>
    <p role="status">{{ message }}</p>
    <fieldset :disabled="busy">
      <label>需求编号<input v-model="requestId" /></label
      ><button @click="run(load)">加载需求</button>
      <article v-if="request">
        <h2>需求版本 {{ request.version }} · {{ request.status }}</h2>
        <p>{{ request.window_start }} 至 {{ request.window_end }}</p>
        <p>{{ request.location }} · {{ request.handover_notes }}</p>
        <p>联系人：{{ request.emergency_contact }}</p>
        <ul>
          <li
            v-for="item in request.checklist_items"
            :key="item.item_key + item.position"
          >
            {{ item.content }} — {{ item.completion_condition }}
            <small>{{
              item.pet_id ? "指定宠物：" + item.pet_id : "共同事项"
            }}</small>
          </li>
        </ul>
        <button v-if="request.status === 'pending_match'" @click="run(match)">
          查找推荐邻居</button
        ><label
          v-for="candidate in candidates"
          :key="candidate.helper_id"
          class="inline"
          ><input
            type="radio"
            v-model="helperId"
            :value="candidate.helper_id"
          />{{ candidate.display_name }} ·
          {{ candidate.reasons.join("、") }}</label
        ><template v-if="candidates.length"
          ><label
            >预约开始（北京时间）<input
              type="datetime-local"
              v-model="start" /></label
          ><label
            >预约结束（北京时间）<input
              type="datetime-local"
              v-model="end" /></label
          ><label
            >约定服务报酬（元；无偿填 0，商品费用另计）<input
              type="number"
              min="0"
              step="0.01"
              v-model.number="fee" /></label
          ><button :disabled="!consent" @click="run(reserve)">
            创建预约
          </button></template
        >
      </article>
      <label>预约编号<input v-model="bookingId" /></label>
      <p class="hint">可以从上方预约列表进入详情；编号入口保留用于联调。</p>
      <label class="inline"
        ><input
          type="checkbox"
          v-model="consent"
        />已核对当前版本清单、时间、费用及执行记录</label
      >
      <div class="actions" style="flex-wrap: wrap">
        <button :disabled="!consent" @click="run(() => action('confirm'))">
          确认预约</button
        ><button @click="run(() => action('start'))">帮手开始服务</button
        ><button @click="run(history)">刷新执行记录</button>
      </div>
      <p v-if="booking">
        预约 {{ booking.id }} · {{ booking.status }} · 宠主确认：{{
          booking.owner_confirmed_at ? "已确认" : "待确认"
        }}
        · 帮手确认：{{ booking.helper_confirmed_at ? "已确认" : "待确认" }}
        <strong v-if="booking.status === 'cancelled'"
          >预约已取消，以上历史确认均已失效。</strong
        >
      </p>
      <article v-if="request && bookingId">
        <h2>执行记录与凭证</h2>
        <label>实际完成情况<textarea v-model="note" /></label
        ><label
          >上传照片凭证<input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            @change="upload"
        /></label>
        <p>本次已上传 {{ photos.length }} 张</p>
        <label v-if="request.service_type === 'errand_buy'"
          >实际商品费用（元）<input
            type="number"
            min="0"
            step="0.01"
            v-model.number="cost" /></label
        ><button
          v-for="item in request.checklist_items"
          :key="item.item_key + item.position"
          @click="run(() => record(item))"
        >
          记录：{{ item.content }}
        </button>
        <p class="hint">
          遛狗须按接狗、出发、送回顺序；代买须先购买再交付。购买必须附凭证且不超过预算。
        </p>
        <button @click="run(() => action('submit'))">帮手提交核验</button
        ><button :disabled="!consent" @click="run(() => action('verify'))">
          宠主确认完成
        </button>
      </article>
      <article v-for="(record, i) in records" :key="i">
        <p>{{ record.occurred_at }} · {{ record.kind }} · {{ record.note }}</p>
        <button
          v-for="url in record.photo_urls as string[]"
          :key="url"
          @click="run(() => view(url))"
        >
          查看凭证
        </button>
      </article>
      <img
        v-if="picture"
        :src="picture"
        alt="执行凭证"
        style="max-width: 100%"
      />
      <ExceptionPanel
        v-if="booking && request && bookingId"
        :api="api"
        :booking-id="bookingId"
        :request-id="request.id"
        :version="request.version"
        :booking-status="String(booking.status)"
        :checklist="(request.checklist_items || []) as any"
        @changed="run(() => openBooking(bookingId))"
      />
      <details>
        <summary>撤回预约</summary>
        <label>撤回原因<input v-model="reason" /></label
        ><button
          :disabled="!reason.trim() || !bookingId"
          @click="
            run(async () => {
              booking = (await api.withdrawBooking(
                bookingId.trim(),
                reason.trim(),
              )) as Record<string, unknown>;
              message = '预约已撤回';
            })
          "
        >
          确认撤回
        </button>
      </details>
    </fieldset>
  </section>
</template>
