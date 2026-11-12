import type {Pet,RequestRow,Draft} from './domain';
export class ApiError extends Error {constructor(public code:string,message:string,public status=0){super(message)}}
export class Api {
 token='';
 constructor(public base='http://127.0.0.1:8000/api/v0'){}
 async call<T>(path:string,method='GET',body?:unknown,key?:string):Promise<T>{
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),15000);
  try{const r=await fetch(this.base.replace(/\/$/,'')+path,{method,signal:controller.signal,headers:{...(body!==undefined?{'Content-Type':'application/json'}:{}),...(this.token?{Authorization:`Bearer ${this.token}`} :{}),...(key?{'Idempotency-Key':key}:{})},body:body===undefined?undefined:JSON.stringify(body)});
   if(r.status===204)return undefined as T;
   const data=await r.json().catch(()=>null);
   if(!r.ok){if(r.status===401)this.token='';throw new ApiError(data?.code||'http_error',data?.message||`请求失败（${r.status}）`,r.status)}
   if(data===null)throw new ApiError('invalid_response','服务返回了无效数据');return data as T;
  }catch(e){if(e instanceof ApiError)throw e;throw new ApiError('network_error','连接失败或超时，请检查后端地址和服务；输入仍保留。')}finally{clearTimeout(timer)}
 }
 pets(){return this.call<{items:Pet[];next_cursor:string|null}>('/pets?limit=100')}
 requests(scope:string,cursor:string|null){return this.call<{items:RequestRow[];next_cursor:string|null}>(`/requests?scope=${scope}&limit=20${cursor?'&cursor='+encodeURIComponent(cursor):''}`)}
 create(d:Draft,key:string){return this.call<RequestRow>('/requests','POST',d,key)}
 publish(r:RequestRow,key:string){return this.call<RequestRow>(`/requests/${r.id}/publish`,'POST',{expected_version:r.version},key)}
}
