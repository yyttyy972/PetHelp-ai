<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
type Kind = 'home_visit'|'dog_walking'|'errand_buy';
const labels: Record<Kind,string> = {home_visit:'上门代看',dog_walking:'上门遛狗',errand_buy:'用品代买'};
const page=ref('发布需求'),stage=ref(0),message=ref(''),confirmed=ref(false),selected=ref(false);
const form=reactive({service_type:'home_visit' as Kind,raw_text:'',pet:'年糕',start:'',end:'',duration:30,location:'',handover:'',contact:'',fee:'free',budget:0,precautions:'',supplies:'',care:'',route:'',behavior:'',product:'',quantity:1,unit:'袋',goodsBudget:0});
const tasks=ref<{id:number;type:Kind;start:string;status:string}[]>([]);
const checks=ref<boolean[]>([]);
const checklist=computed(()=>form.service_type==='home_visit'?form.care.split('\n').filter(x=>x.trim()):form.service_type==='dog_walking'?['接狗：核对牵引与交接','出发：记录时间与路线','送回：确认安全交接']:[`购买：${form.product} ${form.quantity}${form.unit}，商品预算 ${form.goodsBudget} 元`,'交付：核对商品与购买凭证']);
function changeType(){form.pet=form.service_type==='dog_walking'?'豆豆':'年糕';stage.value=0;confirmed.value=false;message.value='';}
function review(){message.value='';if(!form.start||!form.end||!form.location.trim()||!form.handover.trim()||!form.contact.trim()){message.value='请补齐时间、地点、交接方式和异常联系人。';return;}
if(new Date(form.end).getTime()-new Date(form.start).getTime()<form.duration*60000){message.value='时间窗口必须覆盖预计服务时长。';return;}
if(form.fee==='paid'&&form.budget<=0){message.value='有偿服务须填写大于 0 的服务报酬。';return;}
if(form.service_type==='home_visit'&&(!form.care.trim()||!form.supplies.trim())){message.value='请填写用品位置及清单；喂食须由你明确份量。';return;}
if(form.service_type==='dog_walking'&&(!form.route.trim()||!form.behavior.trim())){message.value='请补充路线及行为注意事项。';return;}
if(form.service_type==='errand_buy'&&(!form.product.trim()||!form.unit.trim()||form.goodsBudget<=0)){message.value='请补充具体商品、单位与商品预算。';return;}
stage.value=1;confirmed.value=false;}
function publish(){if(!confirmed.value)return;tasks.value.unshift({id:Date.now(),type:form.service_type,start:form.start,status:'pending_match'});stage.value=2;selected.value=false;}
function demo(){form.raw_text='明天帮我照顾宠物';message.value='模拟补问：请明确日期与起止时间、具体要求和费用方式。此按钮不调用 AI，也不会猜测喂食份量。';}
function reset(){stage.value=0;selected.value=false;checks.value=[];message.value='';}
</script>

<template>
 <div class="layout">
  <aside><a class="brand" href="#" @click.prevent="page='发布需求'">邻宠帮<span>PetHelp / 社区互助</span></a><nav><button v-for="tab in ['发布需求','社区大厅','我的任务','基础档案']" :class="{active:page===tab}" @click="page=tab">{{tab}}</button></nav><p class="aside-note">小小的托付<br>有记录的安心</p><small>第 9 周 · A 董韵曦</small></aside>
  <main><header><span>邻里之间，让照料更安心</span><b>演示社区 · 小林</b></header><div class="banner">模拟数据模式 · 不连接真实 AI、预约或结算。刷新后演示记录清空。</div>
  <section v-if="page==='发布需求'">
   <div class="heading"><div><p class="eyebrow">CARE, WITH CLARITY</p><h1>给毛孩子，一份清晰的托付</h1><p>说明需求、确认清单，再找一位合适的邻居。</p></div><span class="pet-mark">爪</span></div>
   <ol class="steps"><li :class="{current:stage===0}">01 填写需求</li><li :class="{current:stage===1}">02 检查草稿</li><li :class="{current:stage>=2}">03 推荐与任务</li></ol>
   <form v-if="stage===0" @submit.prevent="review">
    <div class="types"><button type="button" v-for="(name,key) in labels" :class="{chosen:form.service_type===key}" @click="form.service_type=key;changeType()">{{name}}<small>{{key==='home_visit'?'熟悉的家，细致照料':key==='dog_walking'?'牵好每一步，安心送回':'买对用品，核对交付'}}</small></button></div>
    <article><h2>先说说，你需要什么帮助？</h2><label>自然语言需求<textarea v-model="form.raw_text" placeholder="例如：周五晚上帮年糕喂食、换水，别开阳台门。"/></label><button type="button" class="secondary" @click="demo">查看模拟补问</button><p class="hint">也可以直接手动填写。AI 草稿须经你确认；未提供的份量不自动补全。</p></article>
    <article><h2>服务安排</h2><div class="grid"><label>宠物<select v-model="form.pet"><option v-if="form.service_type!=='dog_walking'">年糕</option><option>豆豆</option></select></label><label>预计时长（分钟）<input type="number" min="1" step="1" required v-model.number="form.duration"></label><label>可开始时间（北京时间）<input type="datetime-local" required v-model="form.start"></label><label>最晚结束时间（北京时间）<input type="datetime-local" required v-model="form.end"></label><label>服务／交付地点<input required v-model="form.location" placeholder="仅参与者可见，不展示到大厅"></label><label>异常联系人<input required v-model="form.contact" placeholder="姓名及联系方式"></label></div><label>交接方式<input required v-model="form.handover" placeholder="说明如何交接宠物、钥匙或商品"></label></article>
    <article><h2>{{labels[form.service_type]}}清单</h2><template v-if="form.service_type==='home_visit'"><label>用品位置<input required v-model="form.supplies"></label><label>逐项照料要求（每行一项，含完成条件）<textarea required v-model="form.care" placeholder="请明确喂食份量、换水和清洁要求，不填写药物建议。"/></label></template><template v-else-if="form.service_type==='dog_walking'"><label>路线与牵引要求<input required v-model="form.route"></label><label>性格及行为注意事项<textarea required v-model="form.behavior"/></label><p class="hint">固定检查点：接狗 → 出发 → 送回</p></template><div v-else class="grid"><label>商品名称、规格及替代规则<input required v-model="form.product"></label><label>数量<input required type="number" min="1" step="1" v-model.number="form.quantity"></label><label>单位<input required v-model="form.unit"></label><label>商品预算上限（元）<input required type="number" min="0.01" step="0.01" v-model.number="form.goodsBudget"></label></div><label>禁止事项与注意事项<textarea v-model="form.precautions" placeholder="例如：不打开阳台门；缺货或超预算先联系宠主。"/></label></article>
    <article><h2>费用约定</h2><div class="grid"><label>服务费用方式<select v-model="form.fee"><option value="free">无偿互助</option><option value="paid">有偿服务</option></select></label><label v-if="form.fee==='paid'">服务报酬（元）<input type="number" min="0.01" step="0.01" required v-model.number="form.budget"></label></div><p class="hint">代买商品费用与服务报酬分开记录；仅演示模拟结算。</p></article><p role="alert" class="message">{{message}}</p><button class="primary">检查并生成手动草稿 →</button>
   </form>
   <article v-else-if="stage===1"><h2>请核对这份照料草稿</h2><p>{{labels[form.service_type]}} · {{form.pet}} · {{form.duration}} 分钟</p><p>{{form.start.replace('T',' ')}} 至 {{form.end.replace('T',' ')}}（北京时间）</p><p>地点：{{form.location}} · 交接：{{form.handover}}</p><p>异常联系人：{{form.contact}}</p><p>费用：{{form.fee==='free'?'无偿互助':form.budget+' 元服务报酬'}}</p><p v-if="form.service_type==='home_visit'">用品位置：{{form.supplies}}</p><p v-if="form.service_type==='dog_walking'">路线：{{form.route}}；行为说明：{{form.behavior}}</p><ul><li v-for="item in checklist">{{item}}</li></ul><p>注意事项：{{form.precautions||'未填写'}}</p><label class="inline"><input type="checkbox" v-model="confirmed">我已核对时间、清单与费用；喂食等要求由本人提供。</label><div class="actions"><button class="secondary" @click="stage=0">返回修改</button><button class="primary" :disabled="!confirmed" @click="publish">确认模拟发布</button></div></article>
   <template v-else><article><p class="eyebrow">{{stage===2?'待匹配 · 模拟候选':'流程预览 · 非真实业务状态'}}</p><h2>{{stage===2?'找到愿意搭把手的邻居':'从交接到核验，每一步有记录'}}</h2><template v-if="stage===2"><h3>{{form.pet==='豆豆'?'小林':'建国'}} · 演示帮手</h3><p>同一社区 · 时间覆盖（预设样例） · 距离约 200 米（估计）</p><p>养宠经验：本人自述；身份核验：演示已核验；历史评价：暂无足够记录。</p><p class="hint">候选仅为固定模拟数据，不代表 D 的匹配计算结果。身份核验不保证照料能力。</p><button class="primary" @click="selected=true">模拟邀请</button><p v-if="selected">已模拟邀请。正式预约需后端检查时间冲突并由双方确认同一版本。</p><button v-if="selected" class="secondary" @click="stage=3">打开后续流程预览</button></template><template v-else><p>待双方确认 → 已预约 → 服务中 → 待核验 → 已完成</p><label class="inline" v-for="(item,i) in checklist"><input type="checkbox" v-model="checks[i]">{{item}}</label><p>已标记 {{checks.filter(Boolean).length}} / {{checklist.length}} 项（仅本地预览）</p><p class="hint">照片不是自动完成依据，最终须宠主核验。重要修改须使原确认失效。</p><details><summary>异常处理入口示意</summary><p>无法进入、宠物拒绝配合、商品缺货或超预算：保留原记录 → 联系宠主 → 确认后续安排。不得直接变更为已完成。</p></details></template></article><button class="secondary" @click="reset">返回新建需求</button></template>
  </section>
  <section v-else-if="page==='基础档案'"><h1>基础档案 · 示例</h1><div class="grid"><article><h2>年糕</h2><p>英短猫 · 2 岁 · 宠主小林</p><p>性格谨慎；照料说明以宠主确认为准。</p></article><article><h2>豆豆</h2><p>柯基犬 · 宠主建国</p><p>遛狗仅可选择犬类档案。</p></article></div><p>第九周展示占位档案，第十周接入 B 的档案接口。</p></section>
  <section v-else><h1>{{page}}</h1><p class="hint">{{page==='社区大厅'?'公开投影：仅展示类型、时间、状态，不展示门牌、交接信息与联系人。':'本次会话内创建的模拟需求。'}}</p><article v-if="!tasks.length"><h2>还没有模拟需求</h2><p>先完成一份发布表单，再来查看。</p><button class="primary" @click="page='发布需求'">去发布需求</button></article><article v-for="task in tasks" :key="task.id"><h2>{{labels[task.type]}}</h2><p>{{task.start.replace('T',' ')}}（北京时间） · 待匹配</p><small>模拟需求 #{{task.id}}</small></article></section>
  <footer>邻宠帮 · 单次社区互助 / 第九周交互原型</footer></main>
 </div>
</template>
