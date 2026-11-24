import {api, hasToken, setToken} from './api.js';
import '../css/auth.css';
import {initProfiles} from './profiles.js';
import {initRequests} from './requests.js';
import {initMatch} from './match.js';
import {initApplications} from './applications.js';
import {initCommunity} from './community.js';

let user = null;
let busy = false;
const app = document.querySelector('.app');
const panel = document.createElement('dialog');
panel.className = 'auth-panel';
panel.setAttribute('aria-labelledby', 'auth-title');
panel.innerHTML = `<h1 id="auth-title">欢迎来到邻宠帮</h1>
  <form id="auth-form">
    <label>账号<input name="account" autocomplete="username" maxlength="100" required></label>
    <label>密码<input name="password" type="password" autocomplete="current-password" maxlength="128" required></label>
    <fieldset id="register-fields" hidden disabled><legend>注册资料</legend>
      <label>昵称<input name="display_name" maxlength="60" required></label>
      <label>身份<select name="roles"><option value="owner">宠主</option><option value="helper">帮手</option><option value="both">宠主和帮手</option></select></label>
    </fieldset>
    <p id="auth-status" role="status" aria-live="polite"></p>
    <button type="submit" id="auth-submit">登录</button>
    <button type="button" id="auth-toggle">没有账号？注册</button>
    <button type="button" id="auth-retry" hidden>重试连接</button>
  </form>`;
document.body.append(panel);
const form = panel.querySelector('form');
const status = panel.querySelector('#auth-status');
const fields = panel.querySelector('#register-fields');
const submit = panel.querySelector('#auth-submit');
const toggle = panel.querySelector('#auth-toggle');
const retry = panel.querySelector('#auth-retry');
let registering = false;
function show(message = '') {
  app.inert = true;
  if (!panel.open) panel.showModal();
  status.textContent = message;
}
function mode(register) {
  registering = register; fields.hidden = fields.disabled = !register;
  submit.textContent = register ? '注册并登录' : '登录';
  toggle.textContent = register ? '已有账号？登录' : '没有账号？注册';
  form.elements.password.minLength = register ? 8 : 1;
  form.elements.password.autocomplete = register ? 'new-password' : 'current-password';
}
function applyIdentity() {
  if (!user) return;
  if (!user.roles.includes(app.dataset.role)) setRole(user.roles[0]);
  for (const button of app.querySelectorAll('[data-role-choice]')) {
    button.disabled = !user.roles.includes(button.dataset.roleChoice);
  }
  app.querySelector('.profile-card h2').textContent = user.display_name;
  const label = app.querySelector('#profile-label');
  label.textContent = app.dataset.role === 'helper'
    ? (user.verification_status === 'verified' ? '已核验帮手' : '帮手（未核验）') : '宠主档案';
  app.querySelector('.profile-card .rating').hidden = true;
}
async function restore() {
  show('正在验证登录状态…');
  try {
    user = await api('/users/me');
    applyIdentity(); app.inert = false; panel.close();
    initProfiles(user, updated => {user = updated; applyIdentity();});
    initRequests(user);
    initMatch(user);
    initApplications(user);
    initCommunity(user);
    form.elements.password.value = ''; retry.hidden = true;
  } catch (error) {
    show(error.message); retry.hidden = !hasToken();
  }
}
function logout() {
  setToken(''); user = null;
  localStorage.removeItem('neighbor-pet-help-draft');
  // Clear prototype state as well as identity so the next account sees no local messages/drafts.
  location.replace(location.pathname + '?signed_out=1');
}
panel.addEventListener('cancel', event => event.preventDefault());
toggle.addEventListener('click', () => {mode(!registering); status.textContent = '';});
retry.addEventListener('click', restore);
window.addEventListener('auth-expired', () => {
  user = null; show('登录已失效，请重新登录');
});
form.addEventListener('submit', async event => {
  event.preventDefault(); if (busy) return;
  busy = true; submit.disabled = toggle.disabled = true; retry.hidden = true;
  status.textContent = registering ? '正在注册…' : '正在登录…';
  const account = form.elements.account.value.trim();
  const password = form.elements.password.value;
  try {
    if (registering) {
      const role = form.elements.roles.value;
      await api('/auth/register', {method:'POST', authenticated:false, body:{account,password,
        display_name:form.elements.display_name.value.trim(),roles:role === 'both' ? ['owner','helper'] : [role]}});
      mode(false); // Registration succeeded: login retries must not register the account again.
    }
    const result = await api('/auth/login', {method:'POST',authenticated:false,body:{account,password}});
    setToken(result.access_token);
    localStorage.removeItem('neighbor-pet-help-draft');
    location.replace(location.pathname);
  } catch (error) {status.textContent = error.message;}
  finally {busy = false; submit.disabled = toggle.disabled = false;}
});
app.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!user || (button?.dataset.roleChoice && !user.roles.includes(button.dataset.roleChoice))) {
    event.preventDefault(); event.stopImmediatePropagation(); return;
  }
}, true);
app.addEventListener('click', () => queueMicrotask(applyIdentity));
window.addEventListener('hashchange', applyIdentity);
const logoutButton = [...app.querySelectorAll('[data-screen="settings"] button')].find(b => b.textContent === '退出登录');
logoutButton.removeAttribute('aria-disabled');
logoutButton.addEventListener('click', logout);
mode(false);
if (hasToken()) restore(); else show();
