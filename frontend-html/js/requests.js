import { api } from "./api.js";
import {
  blank,
  kinds,
  fixedItems,
  applyAiSuggestion,
  validate,
  payload,
  beijingInput,
} from "./request-domain.js";
const esc = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const fields = [
  ["window_start", "开始时间（北京时间）", "datetime-local"],
  ["window_end", "结束时间（北京时间）", "datetime-local"],
  ["expected_duration_minutes", "预计时长（分钟）", "number"],
  ["location", "服务地点", "text"],
  ["budget", "预算（元）", "number"],
  ["handover_notes", "交接说明", "text"],
  ["emergency_contact", "异常联系人", "text"],
  ["requirements", "路线及其他要求", "text"],
  ["precautions", "注意与禁止事项", "text"],
];
let initialized = false;
export function initRequests(user) {
  if (initialized) return;
  initialized = true;
  const screen = document.querySelector('[data-screen="publish"]');
  // Replace the old form, removing its keyword parser and mock submission listeners.
  screen.querySelector("form").remove();
  const box = document.createElement("div");
  box.className = "live-profile";
  screen.append(box);
  if (!user.roles.includes("owner")) {
    box.textContent = "发布求助需要宠主身份。";
    return;
  }
  box.innerHTML = `<form id="live-request-form"><label>描述您的需求<textarea name="raw_text" maxlength="10000" rows="4"></textarea></label>
 <fieldset id="request-pets"><legend>选择宠物</legend></fieldset><button type="button" id="refresh-request-pets">刷新宠物</button><button type="button" data-route="pet">管理宠物档案</button>
 <button type="button" id="parse-request">AI 内容识别</button><p>AI 结果仅为草稿，请核对并补齐后再发布。</p><ul id="ai-questions"></ul>
 <label>服务类型<select name="service_type">${Object.entries(kinds)
   .map(([v, t]) => `<option value="${v}">${t}</option>`)
   .join("")}</select></label>
 <label>费用方式<select name="fee_type"><option value="">请选择</option><option value="free">无偿</option><option value="paid">有偿</option></select></label>
 ${fields.map(([n, t, type]) => `<label>${t}<input name="${n}" type="${type}" ${type === "number" ? 'min="0" step="' + (n === "budget" ? "0.01" : "1") + '"' : ""}></label>`).join("")}
 <p id="budget-help"></p><h2>照料清单</h2><div id="request-checklist"></div><button type="button" id="add-checklist">添加照料事项</button>
 <p id="request-saved-state"></p><label><input type="checkbox" id="request-consent">我已核对宠物、时间、费用和每项照料要求</label>
 <button type="button" id="local-request">本机暂存</button><button type="button" id="save-request">保存后端草稿</button><button type="submit" id="publish-request">发布求助</button><button type="button" id="new-request">新建空白需求</button>
 </form><p id="live-request-status" class="notice" role="status"></p><h2>我的需求</h2><button type="button" id="reload-requests">刷新我的需求</button><div id="my-requests"></div>`;
  const f = box.querySelector("form"),
    status = box.querySelector("#live-request-status"),
    consent = box.querySelector("#request-consent");
  const localKey = "pethelp-html-draft-" + user.id;
  let draft = blank(),
    pets = [],
    saved = null,
    busy = false,
    lastSaved = "";
  draft.budget = "";
  function read() {
    for (const [n] of fields) draft[n] = f.elements[n].value;
    draft.expected_duration_minutes = f.elements.expected_duration_minutes.value
      ? Number(f.elements.expected_duration_minutes.value)
      : null;
    for (const n of ["raw_text", "service_type", "fee_type"])
      draft[n] = f.elements[n].value;
    draft.pet_ids = [...box.querySelectorAll("[name=request_pet]:checked")].map(
      (i) => i.value,
    );
    draft.checklist_items = [...box.querySelectorAll(".request-item")].map(
      (row, i) => {
        const get = (n) => row.querySelector(`[data-field="${n}"]`);
        const item = {
          item_key: row.dataset.key,
          position: i + 1,
          content: get("content").value,
          completion_condition: get("completion_condition").value,
          pet_id: get("pet_id").value || null,
          required: get("required").checked,
        };
        if (get("product_name"))
          Object.assign(item, {
            product_name: get("product_name").value,
            quantity: Number(get("quantity").value),
            unit: get("unit").value,
          });
        return item;
      },
    );
  }
  function render() {
    for (const n of [
      ...fields.map((x) => x[0]),
      "raw_text",
      "service_type",
      "fee_type",
    ])
      f.elements[n].value = draft[n] ?? "";
    box.querySelector("#request-pets").innerHTML =
      "<legend>选择宠物</legend>" +
      pets
        .map(
          (p) =>
            `<label><input type="checkbox" name="request_pet" value="${p.id}" ${draft.pet_ids.includes(p.id) ? "checked" : ""} ${saved ? "disabled" : ""}>${esc(p.name)}（${p.species === "dog" ? "狗" : "猫"}）</label>`,
        )
        .join("");
    if (!pets.length)
      box
        .querySelector("#request-pets")
        .insertAdjacentHTML(
          "beforeend",
          "<p>请先添加宠物档案，再刷新列表。</p>",
        );
    f.elements.service_type.disabled = Boolean(saved);
    box.querySelector("#budget-help").textContent =
      draft.service_type === "errand_buy"
        ? "这里填写商品预算；无偿代买也可以产生商品费用。服务报酬在预约阶段另行约定。"
        : "这里填写服务预算；无偿服务填 0。";
    box.querySelector("#request-checklist").innerHTML = draft.checklist_items
      .map(
        (item, i) =>
          `<fieldset class="request-item" data-key="${esc(item.item_key)}"><legend>事项 ${i + 1} · ${esc(item.item_key)}</legend><label>对应宠物<select data-field="pet_id"><option value="">共同事项</option>${pets
            .filter((p) => draft.pet_ids.includes(p.id))
            .map(
              (p) =>
                `<option value="${p.id}" ${p.id === item.pet_id ? "selected" : ""}>${esc(p.name)}</option>`,
            )
            .join(
              "",
            )}</select></label><label>照料内容<textarea data-field="content">${esc(item.content)}</textarea></label><label>完成条件<textarea data-field="completion_condition">${esc(item.completion_condition)}</textarea></label><label><input type="checkbox" data-field="required" ${item.required ? "checked" : ""}>必须完成</label>${draft.service_type === "errand_buy" && item.item_key === "purchase" ? `<label>商品名称<input data-field="product_name" value="${esc(item.product_name)}"></label><label>数量<input type="number" min="1" step="1" data-field="quantity" value="${esc(item.quantity)}"></label><label>单位<input data-field="unit" value="${esc(item.unit)}"></label>` : ""}${fixedItems(draft.service_type).some((x) => x.item_key === item.item_key) ? "" : `<button type="button" data-delete-item="${i}">移除事项</button>`}</fieldset>`,
      )
      .join("");
    box.querySelector("#request-saved-state").textContent = saved
      ? `后端状态：${saved.status} · 版本 ${saved.version}。宠物名单和服务类型已锁定。`
      : "尚未保存到后端";
    box.querySelector("#parse-request").disabled = Boolean(saved);
    consent.checked = false;
    const readonly = Boolean(saved && saved.status !== "draft");
    for (const el of f.querySelectorAll("input,textarea,select,button")) {
      if (readonly) el.disabled = !["new-request"].includes(el.id);
      else if (
        el.id !== "parse-request" &&
        el.name !== "service_type" &&
        el.name !== "request_pet"
      )
        el.disabled = false;
    }
  }
  async function run(action) {
    if (busy) return;
    busy = true;
    f.inert = true;
    status.textContent = "正在处理…";
    try {
      await action();
    } catch (e) {
      status.textContent =
        e.code === "version_conflict"
          ? "需求版本已变化，请从“我的需求”重新加载，核对后再保存。"
          : e.code === "ai_unavailable"
            ? "AI 尚未配置，已保留输入，可手动填写。"
            : e.message;
    } finally {
      busy = false;
      f.inert = false;
    }
  }
  async function loadPets() {
    let cursor = null;
    const found = [];
    do {
      const r = await api(
        "/pets?limit=100" +
          (cursor ? "&cursor=" + encodeURIComponent(cursor) : ""),
      );
      found.push(...r.items);
      cursor = r.next_cursor;
    } while (cursor);
    pets = found;
  }
  function problems() {
    const errors = validate(draft, pets);
    if (!Object.hasOwn(kinds, draft.service_type))
      errors.push("请选择支持的服务类型");
    const keys = draft.checklist_items.map((i) => i.item_key);
    if (
      new Set(keys).size !== keys.length ||
      fixedItems(draft.service_type).some((i) => !keys.includes(i.item_key))
    )
      errors.push("清单缺少必要步骤或存在重复标识");
    return errors;
  }
  async function save() {
    read();
    const errors = problems();
    if (errors.length) throw Error(errors.join("；"));
    if (saved && saved.status !== "draft")
      throw Error("需求已发布，本页不再修改；请新建需求。");
    const body = payload(draft);
    if (saved && lastSaved === JSON.stringify(body)) return;
    if (saved) {
      const { pet_ids, service_type, ...patch } = body;
      saved = await api("/requests/" + saved.id, {
        method: "PATCH",
        body: { ...patch, expected_version: saved.version },
      });
    } else saved = await api("/requests", { method: "POST", body });
    lastSaved = JSON.stringify(body);
    sessionStorage.removeItem(localKey);
    sessionStorage.setItem(localKey, JSON.stringify({ id: saved.id }));
    render();
  }
  async function list() {
    let cursor = null;
    const rows = [];
    do {
      const r = await api(
        "/requests?scope=mine&limit=100" +
          (cursor ? "&cursor=" + encodeURIComponent(cursor) : ""),
      );
      rows.push(...r.items);
      cursor = r.next_cursor;
    } while (cursor);
    const html =
      rows
        .map(
          (r) =>
            `<article class="pet-entry"><h3>${esc(kinds[r.service_type])}</h3><p>${esc(r.status)} · ${esc(beijingInput(r.window_start).replace("T", " "))}</p><button type="button" data-load-request="${r.id}">查看${r.status === "draft" ? " / 编辑草稿" : ""}</button>${r.status === "draft" ? `<button type="button" data-delete-request="${r.id}">删除草稿</button>` : ""}${["pending_match", "pending_confirm", "reserved"].includes(r.status) ? `<button type="button" data-cancel-request="${r.id}">取消需求</button>` : ""}</article>`,
        )
        .join("") || "<p>还没有需求。</p>";
    box.querySelector("#my-requests").innerHTML = html;
    const home = document.querySelector("#published-requests");
    document.querySelector('[data-screen="home"] .request')?.remove();
    home.hidden = false;
    home.innerHTML = html;
    home.classList.add("live-profile");
    window.dispatchEvent(new Event("requests-updated"));
  }
  async function load(id) {
    const r = await api("/requests/" + encodeURIComponent(id));
    saved = r;
    draft = {
      ...blank(),
      ...Object.fromEntries(
        Object.keys(blank()).map((k) => [k, r[k] ?? blank()[k]]),
      ),
      pet_ids: r.pets.map((p) => p.id),
      window_start: beijingInput(r.window_start),
      window_end: beijingInput(r.window_end),
      checklist_items: r.checklist_items.map((i) =>
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
        ),
      ),
    };
    render();
    status.textContent =
      r.status === "draft"
        ? "已加载后端草稿，可继续编辑。"
        : "已发布需求，只读查看。";
    sessionStorage.setItem(localKey, JSON.stringify({ id }));
  }
  f.addEventListener("input", (e) => {
    if (e.target !== consent) consent.checked = false;
  });
  f.elements.service_type.addEventListener("change", () => {
    read();
    draft.checklist_items = fixedItems(draft.service_type);
    draft.budget = "";
    render();
  });
  box.querySelector("#request-pets").addEventListener("change", () => {
    read();
    for (const i of draft.checklist_items)
      if (i.pet_id && !draft.pet_ids.includes(i.pet_id)) i.pet_id = null;
    render();
  });
  box.querySelector("#refresh-request-pets").onclick = () =>
    run(async () => {
      read();
      await loadPets();
      render();
      status.textContent = "宠物列表已更新";
    });
  box.querySelector("#parse-request").onclick = () =>
    run(async () => {
      read();
      if (saved) throw Error("已保存草稿请直接编辑；重新解析请新建需求。");
      if (!draft.raw_text.trim()) throw Error("请先描述需求");
      if (!draft.pet_ids.length) throw Error("请先选择宠物");
      const result = await api("/ai/parse", {
        method: "POST",
        timeout: 45000,
        body: {
          text: draft.raw_text,
          reference_time: new Date().toISOString(),
          timezone: "Asia/Shanghai",
          pet_ids: draft.pet_ids,
        },
      });
      const warnings = applyAiSuggestion(draft, result.draft, pets);
      render();
      box.querySelector("#ai-questions").innerHTML = [
        ...(result.questions || []),
        ...warnings,
      ]
        .map((q) => `<li>${esc(q)}</li>`)
        .join("");
      status.textContent = "AI 建议已填入表单，请核对并补齐。";
    });
  box.querySelector("#add-checklist").onclick = () => {
    read();
    draft.checklist_items.push({
      item_key: "care_" + crypto.randomUUID().slice(0, 8),
      position: draft.checklist_items.length + 1,
      content: "",
      completion_condition: "",
      required: true,
      pet_id: null,
    });
    render();
  };
  box.querySelector("#request-checklist").onclick = (e) => {
    const b = e.target.closest("[data-delete-item]");
    if (b) {
      read();
      draft.checklist_items.splice(Number(b.dataset.deleteItem), 1);
      render();
    }
  };
  box.querySelector("#local-request").onclick = () => {
    read();
    sessionStorage.setItem(localKey, JSON.stringify({ draft, id: saved?.id }));
    status.textContent =
      "已暂存在当前账号的当前标签页，未发布。关闭标签页将清除。";
  };
  box.querySelector("#save-request").onclick = () =>
    run(async () => {
      await save();
      await list();
      status.textContent = "已保存后端草稿，尚未发布。";
    });
  f.onsubmit = (e) => {
    e.preventDefault();
    run(async () => {
      if (!consent.checked) throw Error("请先勾选确认已核对需求。");
      read();
      if (Date.parse(payload(draft).window_start) <= Date.now())
        throw Error("请填写未来的服务时间。");
      await save();
      saved = await api("/requests/" + saved.id + "/publish", {
        method: "POST",
        body: { expected_version: saved.version },
      });
      render();
      await list();
      status.textContent = "已发布，等待匹配。";
    });
  };
  box.querySelector("#new-request").onclick = () => {
    if (!confirm("新建空白需求？未保存的输入将清除。")) return;
    saved = null;
    draft = blank();
    draft.budget = "";
    sessionStorage.removeItem(localKey);
    box.querySelector("#ai-questions").innerHTML = "";
    render();
    status.textContent = "已新建空白需求。";
  };
  box.querySelector("#reload-requests").onclick = () =>
    run(async () => {
      await list();
      status.textContent = "需求列表已更新";
    });
  document.querySelector(".app").addEventListener("click", (e) => {
    const b = e.target.closest(
      "[data-load-request],[data-delete-request],[data-cancel-request]",
    );
    if (!b) return;
    run(async () => {
      if (b.dataset.cancelRequest) {
        const reason = prompt("请填写取消需求的原因");
        if (!reason?.trim()) return;
        const r = await api("/requests/" + b.dataset.cancelRequest);
        await api("/requests/" + r.id + "/cancel", {
          method: "POST",
          body: { expected_version: r.version, reason: reason.trim() },
        });
        if (saved?.id === r.id) await load(r.id);
        await list();
        status.textContent = "需求已取消";
        return;
      }
      if (b.dataset.loadRequest) {
        location.hash = "publish";
        await loadPets();
        await load(b.dataset.loadRequest);
      } else if (confirm("确认删除这个未发布草稿？")) {
        await api("/requests/" + b.dataset.deleteRequest, { method: "DELETE" });
        if (saved?.id === b.dataset.deleteRequest) {
          saved = null;
          draft = blank();
          sessionStorage.removeItem(localKey);
          render();
        }
        await list();
        status.textContent = "草稿已删除";
      }
    });
  });
  run(async () => {
    await loadPets();
    render();
    await list();
    const local = JSON.parse(sessionStorage.getItem(localKey) || "null");
    if (local?.id) await load(local.id);
    if (local?.draft && (!saved || saved.status === "draft")) {
      draft = local.draft;
      if (saved) {
        draft.pet_ids = saved.pets.map((p) => p.id);
        draft.service_type = saved.service_type;
      }
      render();
      status.textContent = "已恢复本机暂存，尚未发布";
    } else if (!local) status.textContent = "";
  });
}
