const tokenKey = 'pethelp-html-token';
let token = sessionStorage.getItem(tokenKey) || '';
let generation = 0;
const pending = new Map();
export function setToken(value) {
  token = value; generation++; pending.clear();
  if (value) sessionStorage.setItem(tokenKey, value);
  else sessionStorage.removeItem(tokenKey);
}
export const hasToken = () => Boolean(token);
export class ApiError extends Error {
  constructor(message, status = 0, code = 'network_error') {
    super(message); this.status = status; this.code = code;
  }
}
export async function api(path, {method = 'GET', body, key, authenticated = true, blob = false, timeout = 15000} = {}) {
  const epoch = generation;
  const multipart = body instanceof FormData;
  const operation = multipart ? null : JSON.stringify([method, path, body]);
  const mutation = !['GET', 'HEAD'].includes(method);
  if (mutation && !multipart) {
    key ||= pending.get(operation) || crypto.randomUUID();
    pending.set(operation, key);
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch('/api/v0' + path, {
      method, signal: controller.signal,
      headers: {
        ...(body !== undefined && !multipart ? {'Content-Type': 'application/json'} : {}),
        ...(authenticated && token ? {Authorization: `Bearer ${token}`} : {}),
        ...(key ? {'Idempotency-Key': key} : {}),
      },
      body: multipart ? body : body === undefined ? undefined : JSON.stringify(body),
    });
    if (epoch !== generation) throw new ApiError('账号已切换，请重试。', 0, 'session_changed');
    const data = response.ok && blob ? await response.blob() : response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      if (response.status < 500) pending.delete(operation);
      if (response.status === 401 && authenticated) {
        setToken(''); window.dispatchEvent(new Event('auth-expired'));
      }
      const messages = {invalid_credentials:'账号或密码不正确', conflict:'账号已存在或操作冲突', validation_error:'请检查填写内容是否完整、格式是否正确', invalid_media:'图片无效，请选择有效的 JPG、PNG 或 WebP 图片', file_too_large:'图片不能超过 5MB', forbidden:'当前账号没有操作权限', service_unavailable:'后端或数据库暂不可用，请稍后重试'};
      throw new ApiError(messages[data?.code] || data?.message || `请求失败（${response.status}）`, response.status, data?.code);
    }
    if (response.status !== 204 && data === null) throw new ApiError('服务返回了无效数据');
    pending.delete(operation);
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('连接失败或超时，请检查后端后重试。');
  } finally { clearTimeout(timer); }
}
