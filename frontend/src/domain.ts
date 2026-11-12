export type Kind='home_visit'|'dog_walking'|'errand_buy';
export const kinds:Record<Kind,string>={home_visit:'上门代看',dog_walking:'上门遛狗',errand_buy:'用品代买'};
export interface Pet {id:string;name:string;species:'cat'|'dog';birth_date:string;breed?:string;temperament?:string;precautions?:string;supplies_location?:string;care_instructions?:string}
export interface Item {item_key:string;position:number;content:string;completion_condition:string;required:boolean;pet_id?:string;product_name?:string;quantity?:number;unit?:string}
export interface Draft {pet_ids:string[];service_type:Kind;fee_type:'free'|'paid';window_start:string;window_end:string;expected_duration_minutes:number;location:string;budget:string;handover_notes:string;emergency_contact:string;requirements:string;precautions:string;raw_text:string;checklist_items:Item[]}
export interface RequestRow extends Partial<Draft>{id:string;version:number;status:string;service_type:Kind}
export const blank=():Draft=>({pet_ids:[],service_type:'home_visit',fee_type:'free',window_start:'',window_end:'',expected_duration_minutes:30,location:'',budget:'0.00',handover_notes:'',emergency_contact:'',requirements:'',precautions:'',raw_text:'',checklist_items:[{item_key:'care_1',position:1,content:'',completion_condition:'',required:true}]});
export function fixedItems(kind:Kind):Item[]{return (kind==='dog_walking'?['pickup','departure','return']:kind==='errand_buy'?['purchase','delivery']:['care_1']).map((key,i)=>({item_key:key,position:i+1,content:({pickup:'接狗',departure:'出发',return:'送回',purchase:'购买指定商品',delivery:'交付核对'} as Record<string,string>)[key]||'',completion_condition:'',required:true}));}
export function beijing(value:string){return /([zZ]|[+-]\d\d:\d\d)$/.test(value)?value:value+':00+08:00';}
export function validate(d:Draft,pets:Pet[]):string[]{const e:string[]=[];
 if(!d.pet_ids.length)e.push('请选择至少一只宠物');
 if(d.pet_ids.some(id=>!pets.some(p=>p.id===id&&(d.service_type!=='dog_walking'||p.species==='dog'))))e.push('所选宠物无效，遛狗只能选择犬类');
 const start=Date.parse(beijing(d.window_start)),end=Date.parse(beijing(d.window_end));
 if(!Number.isFinite(start)||!Number.isFinite(end)||!Number.isInteger(d.expected_duration_minutes)||d.expected_duration_minutes<1||end-start<d.expected_duration_minutes*60000)e.push('请填写能覆盖服务时长的有效时间窗口');
 for(const [k,label] of [['location','地点'],['handover_notes','交接方式'],['emergency_contact','异常联系人']] as const)if(!d[k].trim())e.push('请填写'+label);
 if(!/^\d{1,8}(\.\d{1,2})?$/.test(d.budget)||d.fee_type==='paid'&&Number(d.budget)<=0||d.fee_type==='free'&&Number(d.budget)!==0)e.push('服务费须为有效金额，无偿为0，有偿大于0');
 if(!d.checklist_items.length||d.checklist_items.some(i=>!i.content.trim()||!i.completion_condition.trim()))e.push('每项清单须填写内容与完成条件');
 if(d.service_type==='errand_buy'&&d.checklist_items.some(i=>i.item_key==='purchase'&&(!i.product_name?.trim()||!Number.isInteger(i.quantity)||i.quantity!<1||!i.unit?.trim())))e.push('请填写商品名称、正整数数量与单位');
 return e;}
export function payload(d:Draft):Draft{return {...structuredClone(d),window_start:beijing(d.window_start),window_end:beijing(d.window_end),budget:Number(d.budget).toFixed(2),checklist_items:d.checklist_items.map((i,n)=>({...i,position:n+1}))};}
