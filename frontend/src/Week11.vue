<script setup lang="ts">
import { ref, computed } from 'vue';
const step=ref(0), role=ref('owner'), owner=ref(false), helper=ref(false), consent=ref(false), note=ref(''), error=ref('');
const items=ref([{content:'按宠主约定份量喂食',condition:'记录实际喂食情况',done:false},{content:'更换饮水',condition:'清洗水碗并加入新鲜饮水',done:false}]);
const records=ref<{content:string;note:string;time:string}[]>([]);
const names=['推荐邻居','预约确认','已预约','服务执行','宠主核验','已完成'];
const complete=computed(()=>items.value.every(i=>i.done));
function confirm(){if(!consent.value)return;if(role.value==='owner')owner.value=true;else helper.value=true;consent.value=false;if(owner.value&&helper.value)step.value=2;}
function record(index:number){error.value='';if(!note.value.trim()){error.value='请填写实际完成情况后保存。';return;}const item=items.value[index];if(!item||item.done)return;records.value.push({content:item.content,note:note.value.trim(),time:new Date().toLocaleString('zh-CN')});item.done=true;note.value='';}
function reset(){step.value=0;owner.value=false;helper.value=false;consent.value=false;records.value=[];items.value.forEach(i=>i.done=false);note.value='';error.value='';}
</script>
<template>
<section aria-label="第十一周流程演示">
 <h1>从托付到完成</h1><p class="banner">第十一周交互演示 · 固定模拟需求，刷新即清空；角色切换仅用于演示。</p>
 <p>上门代看 · 年糕 · 30 分钟 · 无偿互助</p>
 <ol class="steps" style="flex-wrap:wrap"><li v-for="(name,i) in names" :key="name" :class="{current:step===i}">{{name}}</li></ol>
 <label>当前演示角色<select v-model="role"><option value="owner">宠主小林</option><option value="helper">帮手建国</option></select></label>
 <article v-if="step===0"><h2>推荐邻居：建国</h2><p>同社区 · 可服务上门代看 · 时间匹配（模拟）</p><details><summary>查看帮手详情与推荐依据</summary><p>养猫经验为本人自述。暂无足够历史评价；实际候选以匹配接口为准。</p><p>服务清单：喂食、换水。服务报酬：0 元。</p></details><button class="primary" :disabled="role!=='owner'" @click="step=1">邀请并核对预约</button></article>
 <article v-if="step===1"><h2>双方确认同一份约定 · 版本 1</h2><ul><li v-for="item in items" :key="item.content">{{item.content}}；完成条件：{{item.condition}}</li></ul><p>宠主：{{owner?'已确认':'待确认'}} · 帮手：{{helper?'已确认':'待确认'}}</p><label class="inline"><input type="checkbox" v-model="consent">我已核对服务清单及费用</label><button :disabled="!consent || (role==='owner'?owner:helper)" @click="confirm">确认约定</button><p class="hint">切换另一角色完成双向确认；正式预约由后端校验版本及确认期限。</p><button @click="reset">撤回演示预约</button></article>
 <article v-if="step===2"><h2>双方已确认</h2><p>正式服务仅允许帮手在预约时间内开始。</p><button class="primary" :disabled="role!=='helper'" @click="step=3">模拟进入服务时间并开始</button></article>
 <article v-if="step===3"><h2>照料清单</h2><label>本次完成情况<textarea v-model="note" placeholder="写下实际执行情况，异常情况请先联系宠主"/></label><p role="alert">{{error}}</p><div v-for="(item,i) in items" :key="item.content"><p>{{item.content}} · {{item.condition}}</p><button :disabled="role!=='helper'||item.done" @click="record(i)">{{item.done?'已保存记录':'保存此项完成记录'}}</button></div><p>已完成 {{items.filter(i=>i.done).length}} / {{items.length}} 项</p><button class="primary" :disabled="role!=='helper'||!complete" @click="step=4;consent=false">提交宠主核验</button></article>
 <article v-if="records.length"><h2>执行记录</h2><ul><li v-for="(record,i) in records" :key="i">{{record.time}} · {{record.content}}<p>{{record.note}}</p></li></ul></article>
 <article v-if="step===4"><h2>等待宠主核验</h2><p>请逐项核对实际执行记录；存在疑问时先联系帮手。</p><label class="inline"><input type="checkbox" v-model="consent">我已核对全部记录，确认服务完成</label><button class="primary" :disabled="role!=='owner'||!consent" @click="step=5">确认完成</button></article>
 <article v-if="step===5"><h2>服务已完成</h2><p>模拟结算：0 元。未发生真实付款。</p><button @click="reset">重新演示</button></article>
</section>
</template>
