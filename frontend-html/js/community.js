import { api, hasToken } from "./api.js";
const esc = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
let initialized = false;
export function initCommunity(user) {
  if (initialized) return;
  initialized = true;
  const app = document.querySelector(".app"),
    screen = app.querySelector("[data-screen=inbox]");
  for (const child of [...screen.children])
    if (child.tagName !== "HEADER") child.remove();
  const box = document.createElement("section");
  box.className = "live-profile";
  box.innerHTML =
    '<h2>消息中心</h2><p>预约双方可以使用文字、语音、视频和实时位置沟通。麦克风、摄像头和定位均需主动授权。</p><button id="refresh-messages" type="button">刷新消息</button><div id="conversations"></div><h3 id="conversation-title"></h3><details><summary>预约动态与异常提醒</summary><div id="conversation-events"></div></details><div id="call-panel" hidden><div class="video-grid"><video id="remote-video" autoplay playsinline></video><video id="local-video" autoplay muted playsinline></video></div><button type="button" id="hangup-call">结束通话</button></div><div id="live-messages"></div><form id="send-message" hidden><label>消息<textarea name="content" maxlength="2000"></textarea></label><div class="communication-actions"><button>发送文字</button><button type="button" id="record-audio">开始录音</button><button type="button" id="video-call">发起视频</button><button type="button" id="share-location">开始共享位置</button></div></form><p id="message-status" role="status"></p>';
  screen.append(box);
  // Remove all illustrative chat history and fake application actions from reachable routes.
  for (const name of ["chat", "alien-chat", "calico-chat", "task"]) {
    const el = app.querySelector(`[data-screen="${name}"]`);
    el.innerHTML =
      '<div class="live-profile"><p>请从消息中心或任务大厅进入真实业务。</p><button type="button" data-route="inbox">消息中心</button><button type="button" data-route="tasks">任务大厅</button></div>';
  }
  let selected = null,
    after = 0,
    busy = false,
    sending = false,
    items = [],
    retry = null,
    mediaUrls = [],
    recorder = null,
    audioChunks = [],
    locationWatch = null,
    lastLocationSent = 0,
    peer = null,
    localStream = null,
    callId = null,
    signalAfter = 0;
  const status = box.querySelector("#message-status"),
    form = box.querySelector("form");
  async function sendPayload(payload) {
    if (!selected) return;
    await api("/bookings/" + selected + "/messages", {method:"POST",body:{client_id:crypto.randomUUID(),...payload}});
    await refresh();
  }
  async function hydrateAudio() {
    mediaUrls.forEach(URL.revokeObjectURL);mediaUrls=[];
    for (const audio of box.querySelectorAll('audio[data-media]')) try {
      const blob=await api(audio.dataset.media.replace('/api/v0',''),{blob:true,timeout:30000});
      const url=URL.createObjectURL(blob);mediaUrls.push(url);audio.src=url;
    } catch { audio.replaceWith(document.createTextNode('语音加载失败')); }
  }
  function stopLocation(){if(locationWatch!==null){navigator.geolocation.clearWatch(locationWatch);locationWatch=null;}box.querySelector('#share-location').textContent='开始共享位置';}
  async function postSignal(kind,payload={}){if(selected&&callId)await api(`/bookings/${selected}/signals`,{method:'POST',body:{call_id:callId,kind,payload}});}
  function makePeer(){
    const pc=new RTCPeerConnection({iceServers:[{urls:'stun:stun.l.google.com:19302'}]});
    pc.onicecandidate=e=>{if(e.candidate)postSignal('ice',e.candidate.toJSON()).catch(()=>{});};
    pc.ontrack=e=>{box.querySelector('#remote-video').srcObject=e.streams[0];};
    pc.onconnectionstatechange=()=>{if(['failed','closed','disconnected'].includes(pc.connectionState))endCall(false);};
    return pc;
  }
  async function ensureMedia(){if(!localStream)localStream=await navigator.mediaDevices.getUserMedia({video:true,audio:true});box.querySelector('#local-video').srcObject=localStream;}
  async function startCall(){
    if(!selected||peer)return;callId=crypto.randomUUID();signalAfter=0;await ensureMedia();peer=makePeer();localStream.getTracks().forEach(t=>peer.addTrack(t,localStream));
    await peer.setLocalDescription(await peer.createOffer());await postSignal('offer',{sdp:peer.localDescription.sdp,type:peer.localDescription.type});box.querySelector('#call-panel').hidden=false;status.textContent='正在等待对方接听…';
  }
  async function acceptCall(signal){
    if(peer)return;callId=signal.call_id;await ensureMedia();peer=makePeer();localStream.getTracks().forEach(t=>peer.addTrack(t,localStream));await peer.setRemoteDescription(signal.payload);await peer.setLocalDescription(await peer.createAnswer());await postSignal('answer',{sdp:peer.localDescription.sdp,type:peer.localDescription.type});box.querySelector('#call-panel').hidden=false;status.textContent='已接听视频通话';
  }
  function endCall(notify=true){if(notify)postSignal('hangup').catch(()=>{});peer?.close();peer=null;localStream?.getTracks().forEach(t=>t.stop());localStream=null;callId=null;box.querySelector('#local-video').srcObject=null;box.querySelector('#remote-video').srcObject=null;box.querySelector('#call-panel').hidden=true;}
  async function pollSignals(){
    if(!selected||document.hidden)return;
    try {const query=`?after=${signalAfter}`+(callId?`&call_id=${callId}`:'');const r=await api(`/bookings/${selected}/signals${query}`);for(const s of r.items){signalAfter=Math.max(signalAfter,s.seq);if(s.kind==='offer')await acceptCall(s);else if(s.kind==='answer'&&peer)await peer.setRemoteDescription(s.payload);else if(s.kind==='ice'&&peer)await peer.addIceCandidate(s.payload);else if(s.kind==='hangup')endCall(false);}} catch(e){if(peer)status.textContent='视频信令同步失败：'+e.message;}
  }
  async function refresh() {
    if (busy || !hasToken()) return;
    busy = true;
    try {
      let cursor = null,
        conversations = [];
      do {
        const r = await api(
          "/conversations?limit=100" + (cursor ? "&cursor=" + cursor : ""),
        );
        conversations.push(...r.items);
        cursor = r.next_cursor;
      } while (cursor);
      box.querySelector("#conversations").innerHTML =
        conversations
          .map(
            (c) =>
              `<button type="button" data-conversation="${c.id}">${esc(c.display_name)} · 预约 ${c.id.slice(0, 8)}${c.unread ? " · 未读 " + c.unread : ""}</button>`,
          )
          .join("") || "<p>暂无预约会话。</p>";
      if (selected) {
        const id = selected;
        const booking = await api("/bookings/" + id);
        let eventCursor = null,
          eventRows = [];
        try {
          do {
            const response = await api(
              "/requests/" +
                booking.request_id +
                "/events?limit=100" +
                (eventCursor ? "&cursor=" + eventCursor : ""),
            );
            eventRows.push(...response.items);
            eventCursor = response.next_cursor;
          } while (eventCursor);
        } catch {
          eventRows = [];
        }
        box.querySelector("#conversation-events").innerHTML =
          eventRows
            .filter((e) => !e.booking_id || e.booking_id === id)
            .map(
              (e) =>
                "<p>" +
                esc(e.event_type) +
                (e.payload?.note ? "：" + esc(e.payload.note) : "") +
                "</p>",
            )
            .join("") || "<p>暂无动态</p>";
        let more = false;
        do {
          const r = await api("/bookings/" + id + "/messages?after=" + after);
          if (id !== selected) return;
          items.push(...r.items);
          if (r.items.length) after = r.items.at(-1).seq;
          more = r.has_more;
        } while (more);
        box.querySelector("#live-messages").innerHTML =
          items
            .map(
              (m) =>
                `<article class="pet-entry"><strong>${m.sender_id === user.id ? "我" : "对方"}</strong>${m.kind==='audio'?`<p><audio controls preload="none" data-media="${esc(m.media_url)}"></audio></p>`:m.kind==='location'?`<p>实时位置（精度约 ${Math.round(m.accuracy_m||0)} 米）<br><a target="_blank" rel="noopener" href="https://www.openstreetmap.org/?mlat=${m.latitude}&mlon=${m.longitude}#map=18/${m.latitude}/${m.longitude}">在地图中查看</a></p>`:`<p style="white-space:pre-wrap">${esc(m.content)}</p>`}<small>${esc(new Date(m.created_at).toLocaleString())}</small></article>`,
            )
            .join("") || "<p>还没有消息。</p>";
        await hydrateAudio();
        if (!document.hidden)
          await api("/bookings/" + id + "/messages/read", {
            method: "POST",
            body: { through_seq: after },
          });
      }
      status.textContent = "";
    } catch (e) {
      status.textContent = e.message + "，点击刷新重试。";
    } finally {
      busy = false;
    }
  }
  box.addEventListener("click", (e) => {
    const b = e.target.closest("[data-conversation]");
    if (!b || busy || sending) return;
    selected = b.dataset.conversation;
    after = 0;
    items = [];
    retry = null;
    stopLocation();endCall(false);signalAfter=0;
    form.reset();
    form.hidden = false;
    box.querySelector("#conversation-title").textContent = b.textContent;
    box.querySelector("#live-messages").textContent = "正在加载…";
    refresh();
  });
  form.onsubmit = async (e) => {
    e.preventDefault();
    if (sending || !selected) return;
    const content = form.elements.content.value.trim();
    if (!content) return;
    sending = true;
    form.querySelector("button").disabled = true;
    const id = selected;
    if (!retry || retry.content !== content || retry.id !== id)
      retry = { id, content, client_id: crypto.randomUUID() };
    try {
      await api("/bookings/" + id + "/messages", {
        method: "POST",
        body: { content, client_id: retry.client_id },
      });
      form.reset();
      retry = null;
      await refresh();
    } catch (e) {
      status.textContent = e.message + "，内容已保留，可重试。";
    } finally {
      sending = false;
      form.querySelector("button").disabled = false;
    }
  };
  box.querySelector('#record-audio').onclick=async()=>{
    const button=box.querySelector('#record-audio');
    try{
      if(recorder?.state==='recording'){recorder.stop();return;}
      const stream=await navigator.mediaDevices.getUserMedia({audio:true});audioChunks=[];recorder=new MediaRecorder(stream);
      recorder.ondataavailable=e=>{if(e.data.size)audioChunks.push(e.data);};
      recorder.onstop=async()=>{button.textContent='开始录音';stream.getTracks().forEach(t=>t.stop());try{const blob=new Blob(audioChunks,{type:recorder.mimeType||'audio/webm'});const data=new FormData();data.append('file',blob,'voice.webm');const uploaded=await api('/bookings/'+selected+'/chat-media',{method:'POST',body:data,timeout:30000});await sendPayload({kind:'audio',media_url:uploaded.url});status.textContent='语音已发送';}catch(e){status.textContent=e.message;}};
      recorder.start();button.textContent='停止并发送';status.textContent='正在录音…';
    }catch(e){status.textContent='无法使用麦克风：'+e.message;}
  };
  box.querySelector('#video-call').onclick=()=>startCall().catch(e=>{endCall(false);status.textContent='无法发起视频：'+e.message;});box.querySelector('#hangup-call').onclick=()=>endCall(true);
  box.querySelector('#share-location').onclick=()=>{
    if(locationWatch!==null){stopLocation();status.textContent='已停止位置共享';return;}
    if(!navigator.geolocation){status.textContent='当前浏览器不支持定位';return;}
    box.querySelector('#share-location').textContent='停止共享位置';
    locationWatch=navigator.geolocation.watchPosition(async p=>{if(Date.now()-lastLocationSent<15000)return;lastLocationSent=Date.now();try{await sendPayload({kind:'location',latitude:p.coords.latitude,longitude:p.coords.longitude,accuracy_m:p.coords.accuracy,location_label:'实时位置'});status.textContent='位置共享中，约每 15 秒更新';}catch(e){status.textContent=e.message;}},e=>{stopLocation();status.textContent='无法获取位置：'+e.message;},{enableHighAccuracy:true,maximumAge:5000,timeout:15000});
  };
  box.querySelector("#refresh-messages").onclick = refresh;
  window.addEventListener("hashchange", () => {
    if (location.hash === "#inbox") refresh();
  });
  setInterval(() => {
    if (location.hash === "#inbox" && !document.hidden) refresh();
  }, 5000);
  setInterval(pollSignals,1000);
  if (location.hash === "#inbox") refresh();
  const privacy = app.querySelector("[data-screen=privacy]");
  for (const child of [...privacy.children])
    if (child.tagName !== "HEADER") child.remove();
  privacy.insertAdjacentHTML(
    "beforeend",
    '<section class="live-profile"><h2>隐私与安全</h2><p>宠物档案仅本人管理；大厅不展示详细地址及联系人；预约、执行凭证和聊天只向授权参与者开放。</p><p>退出登录会清除当前会话。对外发布的经验自述和评价请勿填写密码或敏感联系方式。</p></section>',
  );
  const settings = app.querySelector("[data-screen=settings] .detail-list");
  for (const b of [...settings.querySelectorAll("button")])
    if (b.textContent !== "退出登录") b.remove();
  const clear = document.createElement("button");
  clear.className = "detail-item";
  clear.textContent = "清除当前账号本机暂存";
  clear.onclick = () => {
    sessionStorage.removeItem("pethelp-html-draft-" + user.id);
    localStorage.removeItem("neighbor-pet-help-draft");
    alert("已清除本机暂存，后端资料未删除。");
  };
  settings.prepend(clear);
}

export async function mountReview(target, booking, user) {
  if (booking.status !== "completed") return;
  const box = document.createElement("section");
  box.className = "pet-entry";
  box.innerHTML =
    '<h3>服务评价</h3><p class="review-status" role="status"></p><div class="review-list"></div>';
  target.append(box);
  async function load() {
    const r = await api("/helpers/" + booking.helper_id + "/reviews");
    box.querySelector(".review-list").innerHTML =
      `<p>共 ${r.count} 条评价${r.average ? "，平均 " + esc(r.average) + " 分" : ""}</p>` +
      r.items.map((x) => `<p>${x.rating} 分 · ${esc(x.comment)}</p>`).join("");
  }
  if (booking.owner_id === user.id) {
    box.insertAdjacentHTML(
      "beforeend",
      '<form id="review-form"><label>评分<select name="rating"><option>5</option><option>4</option><option>3</option><option>2</option><option>1</option></select></label><label>评价<textarea name="comment" maxlength="2000"></textarea></label><button>提交评价</button></form>',
    );
    const f = box.querySelector("form");
    f.onsubmit = async (e) => {
      e.preventDefault();
      f.querySelector("button").disabled = true;
      try {
        await api("/bookings/" + booking.id + "/review", {
          method: "POST",
          body: {
            rating: Number(f.elements.rating.value),
            comment: f.elements.comment.value,
          },
        });
        box.querySelector(".review-status").textContent = "评价已提交";
        await load();
      } catch (e) {
        box.querySelector(".review-status").textContent = e.message;
        f.querySelector("button").disabled = false;
      }
    };
  }
  try {
    await load();
  } catch (e) {
    box.querySelector(".review-status").textContent = e.message;
  }
}
