import { api } from "./api.js";
import {mountReview} from './community.js';
import { beijing, beijingInput } from "./request-domain.js";
const esc = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const reasons = {
  cannot_enter: "无法进入",
  pet_hiding: "宠物躲藏",
  service_timeout: "服务超时",
  over_budget: "超出商品预算",
  out_of_stock: "商品缺货",
  verification_dispute: "验收争议",
  other: "其他异常",
};
async function all(path) {
  const rows = [];
  let cursor = null;
  do {
    const r = await api(
      path +
        "?limit=100" +
        (cursor ? "&cursor=" + encodeURIComponent(cursor) : ""),
    );
    rows.push(...r.items);
    cursor = r.next_cursor;
  } while (cursor);
  return rows;
}
let imageUrls = [];
const cleanItem = (i) =>
  Object.fromEntries(
    [
      "item_key",
      "pet_id",
      "position",
      "content",
      "completion_condition",
      "required",
      "product_name",
      "quantity",
      "unit",
    ]
      .filter((k) => i[k] != null)
      .map((k) => [k, i[k]]),
  );
export async function mountService(target, booking, user, refresh) {
  imageUrls.forEach(URL.revokeObjectURL);
  imageUrls = [];
  const box = document.createElement("section");
  box.id = "service-panel";
  box.innerHTML =
    '<h3>服务执行</h3><p class="service-notice" role="status">正在加载服务记录…</p>';
  target.append(box);
  const owner = booking.owner_id === user.id,
    helper = !owner;
  let busy = false;
  const tell = (text) =>
    (box.querySelector(".service-notice").textContent = text);
  async function run(fn) {
    if (busy) return;
    busy = true;
    box.inert = true;
    tell("正在处理…");
    try {
      await fn();
    } catch (e) {
      tell(
        {
          checklist_incomplete: "必做清单或固定步骤尚未完成，请补齐记录。",
          invalid_evidence:
            "记录不符合要求，请检查时间、步骤顺序、照片及金额。",
          version_conflict: "版本已更新，请刷新预约后操作。",
          schedule_extension_required:
            "服务已超时，请由宠主批准未来的结束时间。",
          time_conflict: "延期与可用时间或其他预约冲突。",
          executed_item_immutable: "已有执行证据的清单项不能修改。",
          confirmation_pending: "变更已批准，等待帮手重新确认。",
          invalid_state: "当前状态或服务时间不允许此操作，请刷新核对。",
        }[e.code] || e.message,
      );
    } finally {
      busy = false;
      box.inert = false;
    }
  }
  let records, exceptions, events, request;
  try {
    [records, exceptions, events] = await Promise.all([
      all("/bookings/" + booking.id + "/records"),
      all("/bookings/" + booking.id + "/exceptions"),
      all("/requests/" + booking.request_id + "/events"),
    ]);
    if (owner || !["cancelled", "completed"].includes(booking.status))
      request = await api("/requests/" + booking.request_id);
  } catch (e) {
    tell(e.message + " 请重新打开预约详情。");
    return;
  }
  const active = exceptions.find((x) => x.status === "open");
  const changeFields = `<label>新商品/服务预算（元；不改则留空）<input name="budget" type="number" min="0" step="0.01"></label><label>新需求结束时间（北京时间）<input name="window_end" type="datetime-local"></label><label>新预约结束时间（北京时间）<input name="scheduled_end" type="datetime-local"></label><label>新注意事项（不改则留空）<textarea name="precautions"></textarea></label><label>新路线/要求（不改则留空）<textarea name="requirements"></textarea></label>`;
  const fixed = ["pickup", "departure", "return", "purchase", "delivery"];
  box.innerHTML = `<h3>服务执行</h3><button type="button" id="refresh-service">刷新服务状态</button>
 ${helper && booking.status === "reserved" ? '<p>须在预约开始时间到达后，才能开始服务。</p><button type="button" id="start-service">开始服务</button>' : ""}
 ${helper && booking.status === "in_service" ? `<form id="record-form"><label>清单事项<select name="item">${booking.checklist_items.map((i) => `<option value="${i.id}">${esc(i.content)}（${esc(i.execution_status)}）</option>`).join("")}</select></label><label>执行时间（北京时间）<input type="datetime-local" name="occurred_at" required value="${beijingInput(new Date().toISOString())}"></label><label>执行说明<textarea name="note"></textarea></label><label>照片凭证（JPG/PNG/WebP，每张最多5MB）<input type="file" name="photos" accept="image/jpeg,image/png,image/webp" multiple></label><label>实际商品费用（仅购买步骤）<input name="actual_cost" type="number" min="0" step="0.01"></label><button type="submit">保存执行记录</button></form><button type="button" id="submit-service">提交完成，等待验收</button>` : ""}
 ${owner && booking.status === "pending_verify" ? '<label><input type="checkbox" id="verify-consent">我已核对全部照料记录及凭证</label><button type="button" id="verify-service">验收通过</button>' : ""}
 ${booking.status === "completed" ? `<p>服务已完成。${booking.settlement_status === "simulated_settled" ? "模拟结算已完成，并非实际支付。" : ""}</p><p>服务报酬 ${esc(booking.agreed_fee)} 元；实际商品费用 ${esc(booking.actual_cost ?? "0.00")} 元。</p>` : ""}
 <h3>执行记录与凭证</h3><div id="execution-records">${records.map((r) => `<article class="pet-entry"><p>${esc(beijingInput(r.occurred_at).replace("T", " "))} · ${esc(r.kind)}</p><p>${esc(r.note)}</p>${r.actual_cost != null ? `<p>实际商品费用：${esc(r.actual_cost)} 元</p>` : ""}<div data-record-images="${r.id}"></div></article>`).join("") || "<p>暂无执行记录。</p>"}</div>
 <h3>异常处理</h3>${
   ["reserved", "in_service", "pending_verify"].includes(booking.status)
     ? `<form id="report-exception"><label>异常原因<select name="reason">${Object.entries(
         reasons,
       )
         .filter(
           ([k]) =>
             k !== "verification_dispute" ||
             (owner && booking.status === "pending_verify"),
         )
         .map(([k, v]) => `<option value="${k}">${v}</option>`)
         .join(
           "",
         )}</select></label><label>情况说明<textarea name="description" required></textarea></label><details><summary>建议变更（可选）</summary>${changeFields}</details><button type="submit">上报异常</button></form>`
     : ""
 }
 <div id="exception-history">${exceptions.map((x) => `<article><h4>${esc(reasons[x.reason_code] || x.reason_code)} · ${x.status === "open" ? "处理中" : "已解决"}</h4><p>${esc(x.description)}</p>${x.proposed_change ? `<p>建议预算：${esc(x.proposed_change.budget ?? "未调整")}；建议结束：${esc(x.proposed_change.scheduled_end ? beijingInput(x.proposed_change.scheduled_end) : "未调整")}</p>` : ""}${x.approved_change ? "<p>变更已批准，确认后生效。</p>" : ""}<p>${esc(x.resolution || "")}</p></article>`).join("") || "<p>暂无异常。</p>"}</div>
 ${active ? `<form id="exception-note"><label>沟通说明<textarea name="note" required></textarea></label><button>补充说明</button></form>${owner ? `<form id="resolve-exception"><label>处理说明<textarea name="resolution" required></textarea></label><label>处理决定<select name="decision"><option value="resume">解决后恢复服务</option><option value="end">终止服务</option></select></label><details><summary>批准变更（可选，填入明确内容）</summary>${changeFields}<label><input type="checkbox" name="edit_checklist">批准下方整份清单调整</label><div id="change-checklist">${booking.checklist_items.map((i) => `<fieldset data-change-item="${i.id}"><legend>${esc(i.item_key)}</legend><label>照料内容<textarea data-content ${["completed", "waived"].includes(i.execution_status) ? "readonly" : ""}>${esc(i.content)}</textarea></label><label>完成条件<textarea data-condition ${["completed", "waived"].includes(i.execution_status) ? "readonly" : ""}>${esc(i.completion_condition)}</textarea></label>${!fixed.includes(i.item_key) && i.execution_status !== "completed" ? `<label><input type="checkbox" name="waive" value="${esc(i.item_key)}">批准豁免</label>` : ""}</fieldset>`).join("")}</div></details><button>提交处理决定</button></form>` : active.approved_change ? '<p>请核对新预算、结束时间与当前版本清单，再确认变更。</p><label><input type="checkbox" id="change-consent">我已核对变更</label><button type="button" id="confirm-change">确认变更并恢复</button>' : "<p>等待宠主处理异常。</p>"}` : ""}
 ${request ? `<p>当前需求预算：${esc(request.budget)} 元；需求结束：${esc(beijingInput(request.window_end))}；预约结束：${esc(beijingInput(booking.scheduled_end))}</p><p>当前注意事项：${esc(request.precautions || "无")}</p><p>当前路线/要求：${esc(request.requirements || "无")}</p>` : ""}
 <h3>沟通与事件</h3><ul>${events.map((e) => `<li>${esc(e.event_type)}${e.payload?.note ? "：" + esc(e.payload.note) : ""}${e.payload?.reason_code ? "：" + esc(reasons[e.payload.reason_code] || e.payload.reason_code) : ""}</li>`).join("")}</ul><p class="service-notice" role="status"></p>`;
  async function action(name) {
    await api("/bookings/" + booking.id + "/" + name, {
      method: "POST",
      body: { expected_version: booking.request_version },
    });
    await refresh();
  }
  box.querySelector("#refresh-service").onclick = () => run(refresh);
  box
    .querySelector("#start-service")
    ?.addEventListener("click", () => run(() => action("start")));
  box
    .querySelector("#submit-service")
    ?.addEventListener("click", () => run(() => action("submit")));
  box.querySelector("#verify-service")?.addEventListener("click", () =>
    run(async () => {
      if (!box.querySelector("#verify-consent").checked)
        throw Error("请先核对并勾选验收确认。");
      await action("verify");
    }),
  );
  box.querySelector("#record-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    run(async () => {
      const f = e.target,
        i = booking.checklist_items.find(
          (i) => i.id === f.elements.namedItem("item").value,
        );
      const body = {
        checklist_item_id: i.id,
        kind: fixed.includes(i.item_key) ? i.item_key : "item_completed",
        occurred_at: beijing(f.elements.occurred_at.value),
        note: f.elements.note.value.trim() || null,
        photo_urls: [],
      };
      const files = [...f.elements.photos.files];
      if (!files.length && !body.note) throw Error("请填写说明或上传照片。");
      if (
        body.kind === "purchase" &&
        (!files.length || !f.elements.actual_cost.value)
      )
        throw Error("购买步骤必须提供凭证照片和实际商品费用。");
      for (const file of files) {
        if (
          file.size > 5 * 1024 * 1024 ||
          !["image/jpeg", "image/png", "image/webp"].includes(file.type)
        )
          throw Error("请选择5MB以内的JPG/PNG/WebP图片。");
        const data = new FormData();
        data.append("purpose", "evidence");
        data.append("file", file);
        body.photo_urls.push(
          (await api("/media", { method: "POST", body: data })).url,
        );
      }
      if (body.kind === "purchase")
        body.actual_cost = f.elements.actual_cost.value;
      await api("/bookings/" + booking.id + "/records", {
        method: "POST",
        body,
      });
      await refresh();
    });
  });
  function changes(f) {
    const c = {};
    for (const key of ["budget", "precautions", "requirements"])
      if (f.elements[key].value.trim()) c[key] = f.elements[key].value.trim();
    for (const key of ["window_end", "scheduled_end"])
      if (f.elements[key].value) c[key] = beijing(f.elements[key].value);
    if (f.elements.edit_checklist?.checked)
      c.checklist_items = booking.checklist_items.map((i) => {
        const row = f.querySelector(`[data-change-item="${i.id}"]`);
        return {
          ...cleanItem(i),
          content: row.querySelector("[data-content]").value,
          completion_condition: row.querySelector("[data-condition]").value,
        };
      });
    const waived = [...f.querySelectorAll("[name=waive]:checked")].map(
      (i) => i.value,
    );
    if (waived.length) c.waive_item_keys = waived;
    return Object.keys(c).length ? c : undefined;
  }
  box.querySelector("#report-exception")?.addEventListener("submit", (e) => {
    e.preventDefault();
    run(async () => {
      const f = e.target;
      await api("/bookings/" + booking.id + "/exceptions", {
        method: "POST",
        body: {
          expected_version: booking.request_version,
          reason_code: f.elements.reason.value,
          description: f.elements.description.value,
          proposed_change: changes(f),
        },
      });
      await refresh();
    });
  });
  box.querySelector("#exception-note")?.addEventListener("submit", (e) => {
    e.preventDefault();
    run(async () => {
      await api("/exceptions/" + active.id + "/notes", {
        method: "POST",
        body: { note: e.target.elements.note.value },
      });
      await refresh();
    });
  });
  box.querySelector("#resolve-exception")?.addEventListener("submit", (e) => {
    e.preventDefault();
    run(async () => {
      const f = e.target,
        decision = f.elements.decision.value;
      if (
        decision === "end" &&
        !confirm("确认终止这次服务？执行记录将保留，不会自动结算。")
      )
        return;
      await api("/exceptions/" + active.id + "/resolve", {
        method: "POST",
        body: {
          expected_version: booking.request_version,
          decision,
          resolution: f.elements.resolution.value,
          ...(decision === "resume" ? { approved_change: changes(f) } : {}),
        },
      });
      await refresh();
    });
  });
  box.querySelector("#confirm-change")?.addEventListener("click", () =>
    run(async () => {
      if (!box.querySelector("#change-consent").checked)
        throw Error("请先核对并勾选变更确认。");
      await action("confirm");
    }),
  );
  await mountReview(box,booking,user);
  for (const r of records)
    for (const path of r.photo_urls || []) {
      const container = box.querySelector(`[data-record-images="${r.id}"]`);
      try {
        const blob = await api(path.replace("/api/v0", ""), { blob: true });
        if (!box.isConnected) return;
        const url = URL.createObjectURL(blob);
        imageUrls.push(url);
        const img = document.createElement("img");
        img.alt = "执行凭证";
        img.src = url;
        container.append(img);
      } catch (e) {
        container.append(document.createTextNode("凭证加载失败，请刷新重试。"));
      }
    }
}
