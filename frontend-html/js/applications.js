import { api } from "./api.js";
import { kinds, beijingInput, beijing } from "./request-domain.js";
import { mountService } from "./service.js";
const esc = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const time = (x) => beijingInput(x).replace("T", " ");
const statuses = {
  pending: "待处理",
  accepted: "已接受",
  rejected: "未选中",
  withdrawn: "已撤回",
  pending_confirm: "待双方确认",
  reserved: "预约成功",
  cancelled: "已取消",
  in_service: "服务中",
  pending_verify: "待验收",
  completed: "已完成",
  exception: "异常处理中",
};
async function all(path) {
  let cursor = null;
  const result = [];
  do {
    const r = await api(
      path +
        (path.includes("?") ? "&" : "?") +
        "limit=100" +
        (cursor ? "&cursor=" + encodeURIComponent(cursor) : ""),
    );
    result.push(...r.items);
    cursor = r.next_cursor;
  } while (cursor);
  return result;
}
let initialized = false;
export function initApplications(user) {
  if (initialized) return;
  initialized = true;
  const app = document.querySelector(".app");
  const box = document.createElement("section");
  box.className = "live-profile";
  box.id = "application-panel";
  box.innerHTML = `<h2>申请管理</h2>${user.roles.includes("owner") ? '<label>我发布的需求<select id="application-request"><option value="">请选择</option></select></label><button type="button" id="load-owner-applications">查看申请</button>' : ""}<button type="button" id="refresh-applications">刷新申请</button><div id="application-list"></div><p class="notice" role="status"></p>`;
  app.querySelector('[data-screen="tasks"]').append(box);
  const records = app.querySelector('[data-screen="records"]');
  for (const child of [...records.children])
    if (child.tagName !== "HEADER") child.remove();
  const bookings = document.createElement("div");
  bookings.className = "live-profile";
  bookings.innerHTML =
    '<h2>我的预约</h2><button type="button" id="refresh-bookings">刷新预约</button><div id="booking-list"></div><div id="booking-detail"></div><p class="notice" role="status"></p>';
  records.append(bookings);
  const dialog = document.createElement("dialog");
  dialog.className = "auth-panel";
  dialog.setAttribute("aria-label", "申请接单");
  dialog.innerHTML = `<h2>申请接单</h2><p>提交申请不会立即占用需求。宠主选择后，还需双方确认预约。</p><form id="application-form"><label>开始时间（北京时间）<input name="start" type="datetime-local" required></label><label>结束时间（北京时间）<input name="end" type="datetime-local" required></label><label>服务报酬（不含商品费用）<input name="fee" type="number" min="0" step="0.01" required></label><label>申请说明<textarea name="note" maxlength="2000"></textarea></label><button type="submit">提交申请</button><button type="button" id="close-application">取消</button></form><p role="status" id="application-status"></p>`;
  document.body.append(dialog);
  const f = dialog.querySelector("form");
  let selected = null,
    busy = false,
    current = null,
    ownerMode = false;
  const notice = (where, text) =>
    (where.querySelector(".notice").textContent = text);
  async function run(where, fn) {
    if (busy) {
      if (where === dialog)
        dialog.querySelector("#application-status").textContent =
          "正在处理上一项操作，请稍后重试。";
      else notice(where, "正在处理上一项操作，请稍后重试。");
      return;
    }
    busy = true;
    where.inert = true;
    try {
      await fn();
    } catch (e) {
      const message =
        {
          time_conflict: "该时段不可用或已被预约，请调整时间后重试。",
          version_conflict: "需求已变更，请刷新后重新申请或选择。",
          invalid_profile: "服务偏好与需求不符，请先完善帮手档案。",
          not_found: "请先建立帮手档案和可用时间。",
          forbidden: "当前账号没有此操作权限，不能申请自己的需求。",
          booking_exists: "该需求已有预约，请刷新状态。",
          reservation_expired: "确认已超时，请重新申请预约。",
        }[e.code] || e.message;
      if (where === dialog)
        dialog.querySelector("#application-status").textContent = message;
      else notice(where, message);
    } finally {
      busy = false;
      where.inert = false;
    }
  }
  function draw(rows, owner = false) {
    ownerMode = owner;
    box.querySelector("#application-list").innerHTML =
      rows
        .map(
          (a) =>
            `<article class="pet-entry" data-application="${a.id}"><h3>${esc(owner ? a.display_name : kinds[a.service_type])}</h3><p>${esc(statuses[a.status])}${a.status === "pending" && !a.actionable ? "（需求已变更或暂不可接受）" : ""}</p><p>${esc(time(a.scheduled_start))} — ${esc(time(a.scheduled_end))}</p><p>服务报酬：${esc(a.agreed_fee)} 元</p><p>${esc(a.note)}</p>${owner && a.actionable ? `<button type="button" data-accept="${a.id}" data-version="${a.current_version}">选择此帮手</button>` : ""}${a.status === "pending" ? `<button type="button" data-${owner ? "reject" : "withdraw"}="${a.id}">${owner ? "拒绝申请" : "撤回申请"}</button>` : ""}${a.booking_id ? '<button type="button" data-route="records">查看预约</button>' : ""}</article>`,
        )
        .join("") || "<p>暂无申请。</p>";
  }
  async function refresh() {
    if (user.roles.includes("owner")) {
      const previous = box.querySelector("select").value;
      const requests = await all("/requests?scope=mine");
      box.querySelector("select").innerHTML =
        '<option value="">请选择需求</option>' +
        requests
          .map(
            (r) =>
              `<option value="${r.id}">${esc(kinds[r.service_type])} · ${esc(time(r.window_start))}</option>`,
          )
          .join("");
      if (requests.some((r) => r.id === previous))
        box.querySelector("select").value = previous;
    }
    if (user.roles.includes("helper")) draw(await all("/applications"));
    else draw([], true);
    notice(box, "申请列表已更新");
  }
  async function ownerList() {
    const id = box.querySelector("select")?.value;
    if (!id) throw Error("请先选择需求");
    draw(await all("/requests/" + id + "/applications"), true);
    notice(box, "已加载该需求的申请");
  }
  async function listBookings() {
    const rows = await all("/bookings?role=all");
    bookings.querySelector("#booking-list").innerHTML =
      rows
        .map(
          (b) =>
            `<article class="pet-entry"><p>${esc(statuses[b.status] || b.status)} · ${esc(time(b.scheduled_start))}</p><p>服务报酬：${esc(b.agreed_fee)} 元</p><button type="button" data-booking="${b.id}">预约详情</button></article>`,
        )
        .join("") || "<p>暂无预约。</p>";
  }
  async function detail(id) {
    current = await api("/bookings/" + id);
    const b = current;
    bookings.querySelector("#booking-detail").innerHTML =
      `<h3>预约详情</h3><p>状态：${esc(statuses[b.status] || b.status)}</p><p>${esc(time(b.scheduled_start))} — ${esc(time(b.scheduled_end))}</p><p>服务报酬：${esc(b.agreed_fee)} 元</p><p>宠主${b.owner_confirmed_at ? "已" : "未"}确认，帮手${b.helper_confirmed_at ? "已" : "未"}确认${b.status === "cancelled" ? "（历史确认已失效）" : ""}</p><h3>预约版本照料清单</h3><ul>${b.checklist_items.map((i) => `<li>${esc(i.content)}；完成条件：${esc(i.completion_condition)}</li>`).join("")}</ul>${b.status === "pending_confirm" ? '<label><input type="checkbox" id="booking-consent">我已核对时间、报酬和照料清单</label><button type="button" id="confirm-booking">确认预约</button>' : ""}${["pending_confirm", "reserved"].includes(b.status) ? '<label>撤回原因<input id="withdraw-reason" maxlength="2000"></label><button type="button" id="withdraw-booking">撤回预约</button>' : ""}`;
  }
  async function serviceDetail(id) {
    await detail(id);
    await mountService(
      bookings.querySelector("#booking-detail"),
      current,
      user,
      async () => {
        await serviceDetail(id);
        await listBookings();
      },
    );
  }
  app.addEventListener("click", (e) => {
    const b = e.target.closest("[data-apply-request]");
    if (!b) return;
    run(box, async () => {
      selected = await api("/requests/" + b.dataset.applyRequest);
      if (selected.status !== "pending_match")
        throw Error("该需求已不再接受申请");
      f.reset();
      f.elements.start.value = beijingInput(selected.window_start);
      f.elements.end.value = beijingInput(
        new Date(
          new Date(selected.window_start).getTime() +
            selected.expected_duration_minutes * 60000,
        ).toISOString(),
      );
      f.elements.fee.value = selected.fee_type === "free" ? "0" : "";
      f.elements.fee.readOnly = selected.fee_type === "free";
      dialog.querySelector("#application-status").textContent =
        "请确认所选时段在你的可用时间内。";
      dialog.showModal();
    });
  });
  dialog.querySelector("#close-application").onclick = () => dialog.close();
  f.onsubmit = (e) => {
    e.preventDefault();
    run(dialog, async () => {
      if (f.elements.end.value <= f.elements.start.value)
        throw Error("结束时间必须晚于开始时间");
      await api("/requests/" + selected.id + "/applications", {
        method: "POST",
        body: {
          expected_version: selected.version,
          scheduled_start: beijing(f.elements.start.value),
          scheduled_end: beijing(f.elements.end.value),
          agreed_fee: f.elements.fee.value,
          note: f.elements.note.value,
        },
      });
      dialog.close();
      await refresh();
      notice(box, "申请已提交，等待宠主选择。");
    });
  };
  box.querySelector("#refresh-applications").onclick = () => run(box, refresh);
  box
    .querySelector("#load-owner-applications")
    ?.addEventListener("click", () => run(box, ownerList));
  box.addEventListener("click", (e) => {
    const b = e.target.closest("[data-accept],[data-reject],[data-withdraw]");
    if (!b) return;
    run(box, async () => {
      if (b.dataset.accept) {
        if (!confirm("确认选择此帮手并按申请中的时间和报酬创建预约？")) return;
        await api("/applications/" + b.dataset.accept + "/accept", {
          method: "POST",
          body: { expected_version: Number(b.dataset.version) },
        });
        await ownerList();
        await listBookings();
        notice(box, "已选择帮手，预约待双方确认。");
      } else {
        const action = b.dataset.reject ? "reject" : "withdraw",
          id = b.dataset.reject || b.dataset.withdraw;
        await api("/applications/" + id + "/" + action, { method: "POST" });
        if (ownerMode) await ownerList();
        else await refresh();
      }
    });
  });
  bookings.querySelector("#refresh-bookings").onclick = () =>
    run(bookings, listBookings);
  bookings.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.booking)
      run(bookings, () => serviceDetail(b.dataset.booking));
    if (b.id === "confirm-booking")
      run(bookings, async () => {
        if (!bookings.querySelector("#booking-consent").checked)
          throw Error("请先核对并勾选确认");
        await api("/bookings/" + current.id + "/confirm", {
          method: "POST",
          body: { expected_version: current.request_version },
        });
        await serviceDetail(current.id);
        await listBookings();
        notice(bookings, "确认成功；双方确认后预约生效。");
      });
    if (b.id === "withdraw-booking")
      run(bookings, async () => {
        const reason = bookings.querySelector("#withdraw-reason").value.trim();
        if (!reason) throw Error("请填写撤回原因");
        await api("/bookings/" + current.id + "/withdraw", {
          method: "POST",
          body: { reason },
        });
        await serviceDetail(current.id);
        await listBookings();
        notice(bookings, "预约已撤回");
      });
  });
  window.addEventListener("hashchange", () => {
    if (location.hash === "#tasks") run(box, refresh);
    if (location.hash === "#records") run(bookings, listBookings);
  });
  if (location.hash === "#tasks") run(box, refresh);
  if (location.hash === "#records") run(bookings, listBookings);
}
