<script setup lang="ts">
import {ref,onMounted} from 'vue';
import type {Api} from './api';
const props=defineProps<{api:Api}>();
const emit=defineEmits<{open:[id:string]}>();
const role=ref('all'),rows=ref<{id:string;status:string;scheduled_start:string;agreed_fee:string}[]>([]),cursor=ref<string|null>(null),busy=ref(false),error=ref(''),loaded=ref(false);
async function load(more=false){if(busy.value)return;busy.value=true;error.value='';try{const data=await props.api.call<{items:typeof rows.value;next_cursor:string|null}>(`/bookings?role=${role.value}&limit=20${more&&cursor.value?'&cursor='+encodeURIComponent(cursor.value):''}`);rows.value=more?[...rows.value,...data.items]:data.items;cursor.value=data.next_cursor;loaded.value=true;}catch(e){error.value=e instanceof Error?e.message:'加载失败';}finally{busy.value=false}}
onMounted(()=>load());
</script>
<template><article><h2>我的预约</h2><fieldset :disabled="busy"><label>预约角色<select v-model="role" @change="rows=[];loaded=false;load()"><option value="all">全部</option><option value="owner">我作为宠主</option><option value="helper">我承接的预约</option></select></label><button @click="load()">刷新预约列表</button><p role="alert" v-if="error">{{error}}</p><p v-if="busy">正在加载预约…</p><p v-if="loaded&&!rows.length">暂无预约</p><article v-for="row in rows" :key="row.id"><p>{{row.scheduled_start}} · {{row.status}} · 服务报酬 {{row.agreed_fee}} 元</p><small>{{row.id}}</small><button @click="emit('open',row.id)">查看预约详情</button></article><button v-if="cursor" @click="load(true)">加载更多预约</button></fieldset></article></template>
