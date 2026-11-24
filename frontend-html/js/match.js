import { api } from "./api.js";
import { kinds, beijingInput } from "./request-domain.js";
const esc = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const time = (v) => beijingInput(v).replace("T", " ");
let initialized = false;
export function initMatch(user) {
  if (initialized) return;
  initialized = true;
  const app = document.querySelector(".app");
  const screen = app.querySelector('[data-screen="tasks"]');
  for (const el of [...screen.children])
    if (el.tagName !== "HEADER") el.remove();
  const hall = document.createElement("main");
  hall.className = "live-profile";
  hall.innerHTML = `<h1>任务大厅</h1><p>仅展示公开信息，服务时间为北京时间。</p><label>服务类型<select id="hall-kind"><option value="">全部</option>${Object.entries(
    kinds,
  )
    .map(([k, v]) => `<option value="${k}">${v}</option>`)
    .join(
      "",
    )}</select></label><button id="hall-refresh" type="button">刷新大厅</button><p class="notice" role="status"></p><div id="hall-list"></div><button id="hall-more" type="button" hidden>加载更多</button>`;
  screen.append(hall);
  // Replace the design's illustrative recommendations; never mix demo candidates with real matches.
  const section = app.querySelector("#helpers-title").closest("section");
  section.innerHTML = `<div class="live-profile" id="match-panel"><h2>帮手推荐</h2><label>选择已发布需求<select id="match-request"><option value="">请先选择需求</option></select></label><button id="match-refresh" type="button">刷新需求</button><button id="match-run" type="button">查找合适帮手</button><p>按服务、宠物、费用和可用时间匹配；服务半径是帮手填写的范围，不代表实时距离。</p><p class="notice" role="status"></p><div id="match-results"></div></div>`;
  const panel = section.querySelector("#match-panel");
  if (!user.roles.includes("owner")) section.hidden = true;
  const home = app.querySelector('[data-screen="home"]');
  const helperHome = home.querySelector('main[data-scope="helper"]');
  if (helperHome) helperHome.remove();
  const entry = document.createElement("main");
  entry.dataset.scope = "helper";
  entry.hidden = app.dataset.role !== "helper";
  entry.className = "live-profile";
  entry.innerHTML =
    '<h2>社区求助</h2><p>看看邻居正在寻找哪些照料帮助。</p><button type="button" data-route="tasks">进入任务大厅</button>';
  home.append(entry);
  const dialog = document.createElement("dialog");
  dialog.className = "auth-panel";
  dialog.innerHTML =
    '<h2>帮手详情</h2><div id="helper-detail"></div><button type="button">关闭</button>';
  dialog.setAttribute("aria-label", "帮手详情");
  dialog.querySelector("button").onclick = () => dialog.close();
  document.body.append(dialog);
  let rows = [],
    cursor = null,
    requests = [],
    candidates = [],
    hallBusy = false,
    matchBusy = false,
    sequence = 0;
  const note = (node, text) =>
    (node.querySelector(".notice").textContent = text);
  function drawHall() {
    const kind = hall.querySelector("#hall-kind").value;
    const filtered = rows.filter((r) => !kind || r.service_type === kind);
    hall.querySelector("#hall-list").innerHTML =
      filtered
        .map(
          (r) =>
            `<article class="pet-entry" data-public-request="${esc(r.id)}"><h2>${esc(kinds[r.service_type] || r.service_type)}</h2><p>${esc(time(r.window_start))} — ${esc(time(r.window_end))}</p><p>预计 ${esc(r.expected_duration_minutes)} 分钟 · ${r.fee_type === "free" ? "无偿" : "有偿"}</p><p>${r.service_type === "errand_buy" ? "商品预算" : "服务预算"}：${esc(r.budget)} 元</p><p>状态：待匹配</p>${user.roles.includes("helper") ? `<button type="button" data-apply-request="${r.id}">申请接单</button>` : ""}</article>`,
        )
        .join("") || "<p>当前已加载数据中没有符合条件的需求。</p>";
    hall.querySelector("#hall-more").hidden = !cursor;
  }
  async function loadHall(reset = true) {
    if (hallBusy) return;
    hallBusy = true;
    hall.querySelectorAll("button").forEach((b) => (b.disabled = true));
    note(hall, "正在加载…");
    if (reset) {
      rows = [];
      cursor = null;
      drawHall();
    }
    try {
      const r = await api(
        "/requests?scope=open&limit=20" +
          (cursor ? "&cursor=" + encodeURIComponent(cursor) : ""),
      );
      rows = [
        ...rows,
        ...r.items.filter((x) => !rows.some((old) => old.id === x.id)),
      ];
      cursor = r.next_cursor;
      drawHall();
      note(
        hall,
        cursor
          ? "筛选仅作用于已加载数据，可继续加载更多。"
          : "已加载全部公开需求。",
      );
    } catch (e) {
      note(hall, e.message + " 请点击刷新重试。");
    } finally {
      hallBusy = false;
      hall.querySelectorAll("button").forEach((b) => (b.disabled = false));
    }
  }
  async function loadRequests() {
    if (!user.roles.includes("owner")) return;
    const previous = panel.querySelector("select").value;
    requests = [];
    let next = null;
    try {
      do {
        const r = await api(
          "/requests?scope=mine&limit=100" +
            (next ? "&cursor=" + encodeURIComponent(next) : ""),
        );
        requests.push(...r.items.filter((x) => x.status === "pending_match"));
        next = r.next_cursor;
      } while (next);
      panel.querySelector("select").innerHTML =
        '<option value="">请选择已发布需求</option>' +
        requests
          .map(
            (r) =>
              `<option value="${r.id}">${esc(kinds[r.service_type])} · ${esc(time(r.window_start))} · ${r.id.slice(0, 8)}</option>`,
          )
          .join("");
      if (requests.some((r) => r.id === previous))
        panel.querySelector("select").value = previous;
      note(
        panel,
        requests.length
          ? "选择需求后查看匹配结果。"
          : "没有待匹配需求，请先发布求助。",
      );
    } catch (e) {
      note(panel, e.message);
    }
  }
  async function match() {
    if (matchBusy) return;
    const id = panel.querySelector("select").value;
    if (!id) {
      note(panel, "请先选择已发布需求。");
      return;
    }
    const ticket = ++sequence;
    matchBusy = true;
    panel.querySelectorAll("button,select").forEach((b) => (b.disabled = true));
    panel.querySelector("#match-results").innerHTML = "";
    note(panel, "正在筛选帮手…");
    try {
      const request = await api("/requests/" + encodeURIComponent(id));
      if (request.status !== "pending_match")
        throw Error("该需求已不在待匹配状态，请刷新需求列表。");
      const result = await api(
        "/requests/" + encodeURIComponent(id) + "/match",
        { method: "POST", body: { expected_version: request.version } },
      );
      if (ticket !== sequence) return;
      candidates = result.candidates;
      panel.querySelector("#match-results").innerHTML =
        candidates
          .map(
            (c, i) =>
              `<article class="pet-entry" data-candidate="${esc(c.helper_id)}"><h3>${esc(c.display_name)}</h3><p>${c.verification_status === "verified" ? "身份已核验" : "身份未核验"}</p><p>费用偏好：${esc({ free: "无偿", paid: "有偿", both: "均可" }[c.fee_pref] || "未填写")}</p><p>自填服务半径：${esc(c.service_radius_m)} 米</p><ul>${c.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul><p class="match-explanation">正在获取推荐理由说明…</p><button type="button" data-helper-index="${i}">查看帮手详情</button></article>`,
          )
          .join("") ||
        "<p>暂无符合条件的帮手。可以检查服务时间或稍后重试。</p>";
      note(panel, `匹配到 ${candidates.length} 位帮手。`);
      await Promise.all(
        candidates.map(async (c) => {
          const card = panel.querySelector(`[data-candidate="${c.helper_id}"]`);
          try {
            const explanation = await api("/ai/explain-match", {
              method: "POST",
              body: { candidate: c },
            });
            if (ticket === sequence)
              card.querySelector(".match-explanation").textContent =
                "推荐依据：" +
                explanation.explanation +
                (explanation.fallback ? "（部分原因暂无法进一步解释）" : "");
          } catch (e) {
            if (ticket === sequence)
              card.querySelector(".match-explanation").textContent =
                "解释服务暂不可用，以上为匹配接口返回的原始理由。";
          }
        }),
      );
    } catch (e) {
      note(
        panel,
        e.code === "version_conflict"
          ? "需求已更新，请刷新后重新匹配。"
          : e.message,
      );
    } finally {
      matchBusy = false;
      panel
        .querySelectorAll("button,select")
        .forEach((b) => (b.disabled = false));
    }
  }
  panel.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-helper-index]");
    if (!b) return;
    const candidate = candidates[Number(b.dataset.helperIndex)];
    if (!candidate) return;
    const content = dialog.querySelector("#helper-detail");
    content.textContent = "正在加载…";
    dialog.showModal();
    try {
      const h = await api(
        "/helpers/" + encodeURIComponent(candidate.helper_id),
      );
      content.innerHTML = `<h3>${esc(candidate.display_name)}</h3><p>服务：${h.service_types.map((k) => esc(kinds[k] || k)).join("、")}</p><p>宠物：${h.supported_species.map((k) => (k === "cat" ? "猫" : "狗")).join("、")}</p><p>服务区域：${esc(h.service_area)}</p><p>经验自述：${esc(h.experience)}</p><p>自填服务半径：${esc(h.service_radius_m)} 米</p><p>核验：${h.verification_status === "verified" ? "已核验" : "未核验"}</p>`;
      const reviews=await api('/helpers/'+candidate.helper_id+'/reviews');
      const reviewBox=document.createElement('section');
      reviewBox.innerHTML='<h4>真实服务评价</h4><p>共 '+reviews.count+' 条评价</p>'+reviews.items.map(r=>'<p>'+r.rating+' 分 · '+esc(r.comment)+'</p>').join('');
      content.append(reviewBox);
    } catch (e) {
      content.textContent = e.message;
    }
  });
  panel.querySelector("#match-run").onclick = match;
  panel.querySelector("#match-refresh").onclick = () => {
    if (!matchBusy) {
      sequence++;
      panel.querySelector("#match-results").innerHTML = "";
      loadRequests();
    }
  };
  panel.querySelector("select").onchange = () => {
    sequence++;
    panel.querySelector("#match-results").innerHTML = "";
    note(panel, "点击查找合适帮手，获取当前需求的匹配结果。");
  };
  hall.querySelector("#hall-refresh").onclick = () => loadHall();
  hall.querySelector("#hall-more").onclick = () => loadHall(false);
  hall.querySelector("#hall-kind").onchange = drawHall;
  window.addEventListener("hashchange", () => {
    if (location.hash === "#tasks") loadHall();
    if (location.hash === "#home" || !location.hash) loadRequests();
  });
  window.addEventListener("requests-updated", () => loadRequests());
  loadRequests();
  if (location.hash === "#tasks") loadHall();
}
