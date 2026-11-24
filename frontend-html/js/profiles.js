import {api} from './api.js';
import '../css/profiles.css';

const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const field = (name,label,type='text',required=false) => `<label>${label}<input name="${name}" type="${type}" ${required?'required':''}></label>`;
const area = (name,label) => `<label>${label}<textarea name="${name}" rows="2"></textarea></label>`;
const select = (name,label,choices) => `<label>${label}<select name="${name}">${choices.map(([v,t])=>`<option value="${v}">${t}</option>`).join('')}</select></label>`;
const checks = (name,label,choices) => `<fieldset><legend>${label}</legend>${choices.map(([v,t])=>`<label><input type="checkbox" name="${name}" value="${v}"> ${t}</label>`).join('')}</fieldset>`;
function panel(screen,html) {
  const section = document.querySelector(`[data-screen="${screen}"]`);
  for(const child of [...section.children]) if(child.tagName!=='HEADER') child.remove();
  const box=document.createElement('div'); box.className='live-profile';box.innerHTML=html;section.append(box);return box;
}
function form(box,html) {
  box.innerHTML=html+'<p class="notice" role="status" aria-live="polite"></p>';
  return box.querySelector('form');
}
function notice(box,text) {box.querySelector('.notice').textContent=text;}
async function run(box,action) {
  if(box.dataset.busy) return;
  box.dataset.busy='1';const controls=[...box.querySelectorAll('button')];controls.forEach(b=>b.disabled=true);
  notice(box,'正在处理…');
  try {await action();} catch(e){notice(box,e.code==='resource_in_use'?'该资料正被需求或预约使用，暂时不能删除或修改类型。':e.message);}
  finally {delete box.dataset.busy;controls.forEach(b=>b.disabled=false);}
}
function values(form) {return Object.fromEntries(new FormData(form));}
function populate(form,row) {for(const [name,value] of Object.entries(row)) {const el=form.elements.namedItem(name);if(el && 'value' in el && el.type!=='file')el.value=value??'';}}
async function all(path) {
  const rows=[];let cursor=null;
  do {const data=await api(path+'?limit=100'+(cursor?'&cursor='+encodeURIComponent(cursor):''));rows.push(...data.items);cursor=data.next_cursor;}while(cursor);
  return rows;
}
async function upload(file,purpose) {
  if(!file?.size)return null;
  if(file.size>5*1024*1024||!['image/jpeg','image/png','image/webp'].includes(file.type))throw Error('请选择不超过 5MB 的 JPG、PNG 或 WebP 图片。');
  const body=new FormData();body.append('purpose',purpose);body.append('file',file);
  return (await api('/media',{method:'POST',body})).url;
}
let initialized=false;
export function initProfiles(user,onUser) {
  if(initialized)return; initialized=true;
  // Personal information is available to either role; only preferences require helper permissions.
  const bioLink=document.querySelector('[data-route="bio"][data-scope]');bioLink.removeAttribute('data-scope');bioLink.hidden=false;
  const bio=panel('bio','');
  const bf=form(bio,`<form id="profile-form">${field('display_name','昵称','text',true)}${area('address','常用地址（仅本人资料）')}${field('avatar','头像（可选，最大5MB）','file')}<button>保存个人资料</button></form>`);
  bf.elements.avatar.accept='image/png,image/jpeg,image/webp';populate(bf,user);
  const avatar=document.querySelector('.profile-card img');
  avatar.hidden=!user.avatar_url;if(user.avatar_url)avatar.src=user.avatar_url;
  bf.addEventListener('submit',e=>{e.preventDefault();run(bio,async()=>{
    const body={display_name:bf.elements.display_name.value.trim(),address:bf.elements.address.value.trim()||null};
    const url=await upload(bf.elements.avatar.files[0],'avatar');if(url)body.avatar_url=url;
    user=await api('/users/me',{method:'PATCH',body});onUser(user);if(user.avatar_url){avatar.src=user.avatar_url;avatar.hidden=false;}
    bf.elements.avatar.value='';notice(bio,'个人资料已保存');
  });});
  initAddresses();
  if(user.roles.includes('owner'))initPets();else panel('pet','<p>当前账号没有宠主身份。</p>');
  if(user.roles.includes('helper'))initHelper();else panel('preferences','<p>当前账号没有帮手身份。</p>');
}
function initAddresses(){
  const box=panel('addresses','');let rows=[],editing=null;
  const f=form(box,`<h2>地址簿</h2><p>详细地址仅本人可见，不会在大厅公开。</p><div id="address-list"></div><button type="button" id="new-address">新增地址</button><h3 id="address-title">新增地址</h3><form id="address-form">
    ${field('label','标签（如：家、公司）','text',true)}${field('contact_name','联系人','text',true)}${field('contact_phone','联系电话','tel',true)}${area('address','详细地址')}
    ${field('latitude','纬度（可选）','number')}${field('longitude','经度（可选）','number')}<label><input name="is_default" type="checkbox"> 设为默认地址</label><button>保存地址</button><button type="button" id="cancel-address">取消编辑</button></form>`);
  f.elements.address.required=true;f.elements.latitude.step=f.elements.longitude.step='any';
  function reset(){editing=null;f.reset();box.querySelector('#address-title').textContent='新增地址';}
  async function load(){
    rows=(await api('/addresses')).items;
    box.querySelector('#address-list').innerHTML=rows.length?rows.map(a=>`<article class="pet-entry"><h3>${escape(a.label)}${a.is_default?' · 默认':''}</h3><p>${escape(a.contact_name)} · ${escape(a.contact_phone)}</p><p>${escape(a.address)}</p><button type="button" data-edit-address="${a.id}">编辑</button><button type="button" data-delete-address="${a.id}">删除</button></article>`).join(''):'<p>还没有保存的地址。</p>';
  }
  box.querySelector('#new-address').onclick=()=>{reset();f.scrollIntoView({block:'start'});};box.querySelector('#cancel-address').onclick=reset;
  box.addEventListener('click',e=>{
    const edit=e.target.closest('[data-edit-address]');if(edit){editing=rows.find(x=>x.id===edit.dataset.editAddress);populate(f,editing);f.elements.is_default.checked=editing.is_default;box.querySelector('#address-title').textContent='编辑地址';}
    const del=e.target.closest('[data-delete-address]');if(del&&confirm('确认删除该地址？'))run(box,async()=>{await api('/addresses/'+del.dataset.deleteAddress,{method:'DELETE'});reset();await load();notice(box,'地址已删除');});
  });
  f.onsubmit=e=>{e.preventDefault();run(box,async()=>{const data=values(f);data.is_default=f.elements.is_default.checked;for(const k of ['latitude','longitude'])data[k]=data[k]===''?null:Number(data[k]);await api(editing?'/addresses/'+editing.id:'/addresses',{method:editing?'PATCH':'POST',body:data});reset();await load();notice(box,'地址已保存');});};
  run(box,async()=>{await load();notice(box,'');});
}
function initPets() {
  const box=panel('pet','');let editing=null;let rows=[];let urls=[];
  const f=form(box,`<button type="button" id="add-pet">新增宠物</button><div id="pet-list"></div><button type="button" id="reload-pets">刷新宠物列表</button><h2 id="pet-editor-title">新增宠物</h2><form id="pet-form">
    ${field('name','宠物名字','text',true)}${select('species','种类',[['cat','猫'],['dog','狗']])}${field('breed','品种')}${field('birth_date','出生日期','date',true)}
    ${area('temperament','性格')}${area('precautions','注意事项')}${area('supplies_location','用品位置')}${area('care_instructions','照料说明')}${field('photo','照片（可选，最大5MB）','file')}
    <button>保存宠物</button><button type="button" id="new-pet">取消编辑 / 新增</button></form>`);
  f.elements.photo.accept='image/png,image/jpeg,image/webp';
  f.elements.birth_date.max=new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,10);
  function reset(){editing=null;f.reset();box.querySelector('#pet-editor-title').textContent='新增宠物';}
  async function load(){
    rows=await all('/pets');urls.forEach(URL.revokeObjectURL);urls=[];
    const list=box.querySelector('#pet-list');list.innerHTML=rows.length?rows.map(p=>`<article class="pet-entry" data-id="${escape(p.id)}"><h2>${escape(p.name)}</h2><p>${p.species==='cat'?'猫':'狗'} · ${escape(p.breed||'未填写品种')} · 出生于 ${escape(p.birth_date)}</p><p>${escape(p.precautions||'')}</p>${p.photo_url?'<img alt="宠物照片" hidden>':''}<button type="button" data-edit="${p.id}">编辑</button><button type="button" data-delete="${p.id}">删除</button></article>`).join(''):'<p>还没有宠物档案，添加第一位毛孩子吧。</p>';
    for(const p of rows.filter(p=>p.photo_url)) {
      try {const image=await api(p.photo_url.replace('/api/v0',''),{blob:true});const url=URL.createObjectURL(image);urls.push(url);const img=list.querySelector(`[data-id="${p.id}"] img`);img.src=url;img.hidden=false;}
      catch(e){throw Error('档案已加载，照片读取失败：'+e.message);}
    }
  }
  box.querySelector('#new-pet').onclick=reset;
  box.querySelector('#add-pet').onclick=()=>{reset();f.scrollIntoView({block:'start'});f.elements.name.focus();};
  box.querySelector('#reload-pets').onclick=()=>run(box,async()=>{await load();notice(box,'列表已刷新');});
  box.addEventListener('click',e=>{
    const edit=e.target.closest('[data-edit]');if(edit){editing=rows.find(p=>p.id===edit.dataset.edit);populate(f,editing);f.elements.photo.value='';box.querySelector('#pet-editor-title').textContent='编辑宠物';}
    const del=e.target.closest('[data-delete]');if(del && confirm('确认删除这只宠物的档案？'))run(box,async()=>{await api('/pets/'+del.dataset.delete,{method:'DELETE'});if(editing?.id===del.dataset.delete)reset();await load();notice(box,'宠物档案已删除');});
  });
  f.onsubmit=e=>{e.preventDefault();run(box,async()=>{
    const body=values(f);delete body.photo;for(const k of ['breed','temperament','precautions','supplies_location','care_instructions'])body[k]=body[k].trim()||null;
    const photo=await upload(f.elements.photo.files[0],'pet');body.photo_url=photo||editing?.photo_url||null;
    await api(editing?'/pets/'+editing.id:'/pets',{method:editing?'PATCH':'POST',body});reset();await load();notice(box,'宠物档案已保存');
  });};
  run(box,async()=>{await load();notice(box,'');});
}
function initHelper(){
  const box=panel('preferences','');let hasProfile=false;
  const f=form(box,`<form id="helper-form">${checks('service_types','服务类型',[['home_visit','上门代看'],['dog_walking','遛狗'],['errand_buy','跑腿代买']])}${checks('supported_species','照料宠物',[['cat','猫'],['dog','狗']])}${field('service_area','服务区域','text',true)}${area('experience','照料经验')}${field('service_radius_m','服务半径（米）','number',true)}${select('fee_pref','费用偏好',[['both','有偿无偿均可'],['free','无偿'],['paid','有偿']])}${field('address_tag','公开位置标签（不含门牌号）')}<button>保存服务偏好</button></form><button type="button" id="reload-helper">重新加载偏好</button>
    <h2>可用时间</h2><div id="availability-list"></div><form id="availability-form">${field('start_at','开始时间','datetime-local',true)}${field('end_at','结束时间','datetime-local',true)}<button>添加可用时间</button></form>`);
  f.elements.service_radius_m.min='1';f.elements.service_radius_m.step='1';f.elements.experience.required=true;f.elements.address_tag.maxLength=50;
  const af=box.querySelector('#availability-form');
  async function times(){const rows=await all('/helpers/me/availability');box.querySelector('#availability-list').innerHTML=rows.length?rows.map(w=>`<div class="time-entry">${escape(new Date(w.start_at).toLocaleString())} — ${escape(new Date(w.end_at).toLocaleString())}<button type="button" data-remove-time="${w.id}">删除时段</button></div>`).join(''):'<p>尚未添加可用时间。</p>';}
  async function load(){
    try {const h=await api('/helpers/me');hasProfile=true;populate(f,h);for(const name of ['service_types','supported_species'])for(const input of f.querySelectorAll(`[name="${name}"]`))input.checked=h[name].includes(input.value);await times();notice(box,'');}
    catch(e){if(e.status===404){hasProfile=false;notice(box,'请先保存服务偏好，再添加可用时间。');}else throw e;}
  }
  f.onsubmit=e=>{e.preventDefault();run(box,async()=>{
    const body=values(f);for(const name of ['service_types','supported_species']){body[name]=[...f.querySelectorAll(`[name="${name}"]:checked`)].map(i=>i.value);if(!body[name].length)throw Error('请至少选择一种服务类型和一种宠物类型。');}
    body.service_radius_m=Number(body.service_radius_m);body.address_tag=body.address_tag.trim()||null;
    await api('/helpers/me',{method:'PUT',body});hasProfile=true;await times();notice(box,'服务偏好已保存');
  });};
  af.onsubmit=e=>{e.preventDefault();run(box,async()=>{
    if(!hasProfile)throw Error('请先保存服务偏好。');const data=values(af);const start=new Date(data.start_at),end=new Date(data.end_at);if(end<=start)throw Error('结束时间必须晚于开始时间。');
    await api('/helpers/me/availability',{method:'POST',body:{start_at:start.toISOString(),end_at:end.toISOString()}});af.reset();await times();notice(box,'可用时间已添加');
  });};
  box.addEventListener('click',e=>{const b=e.target.closest('[data-remove-time]');if(b)run(box,async()=>{await api('/helpers/me/availability/'+b.dataset.removeTime,{method:'DELETE'});await times();notice(box,'时段已删除');});});
  box.querySelector('#reload-helper').onclick=()=>run(box,load);run(box,load);
}
