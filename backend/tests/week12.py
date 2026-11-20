import os, uuid
from datetime import datetime, timedelta, timezone
os.environ.setdefault('JWT_SECRET','week12-local-test-secret-at-least-32-characters')
from fastapi.testclient import TestClient
from app.main import app
from app.db import connection

def run():
 with TestClient(app) as c:
  def call(method,path,token=None,expected=200,key=None,**kwargs):
   headers={'Authorization':'Bearer '+token} if token else {}
   if method!='GET':headers['Idempotency-Key']=key or str(uuid.uuid4())
   res=c.request(method,'/api/v0'+path,headers=headers,**kwargs)
   assert res.status_code==expected,(path,res.status_code,res.text)
   return res.json()
  owner=call('POST','/auth/login',json={'account':'xiaolin','password':'NeighborPet2026!'})['access_token']
  helper=call('POST','/auth/login',json={'account':'jianguo','password':'NeighborPet2026!'})['access_token']
  account='w12-'+uuid.uuid4().hex[:16]
  call('POST','/auth/register',expected=201,json={'account':account,'password':'Week12Test2026!','display_name':'访客','roles':['owner']})
  stranger=call('POST','/auth/login',json={'account':account,'password':'Week12Test2026!'})['access_token']
  pet=call('POST','/pets',owner,201,json={'name':'异常测试犬','species':'dog','birth_date':'2024-01-01'})['id']
  now=datetime.now(timezone.utc); start=now-timedelta(minutes=2);end=now+timedelta(minutes=40)
  call('POST','/helpers/me/availability',helper,201,json={'start_at':(now-timedelta(days=1)).isoformat(),'end_at':(now+timedelta(days=1)).isoformat()})
  body=dict(pet_ids=[pet],service_type='home_visit',fee_type='paid',window_start=(now-timedelta(minutes=5)).isoformat(),window_end=(now+timedelta(hours=3)).isoformat(),expected_duration_minutes=10,location='测试门厅',budget='30.00',handover_notes='联系宠主',emergency_contact='测试联系人',checklist_items=[dict(item_key=k,position=i,content=k,completion_condition='记录照料') for i,k in enumerate(['feed_food','change_water'],1)])
  def booking():
   r=call('POST','/requests',owner,201,json=body)
   call('POST','/requests/'+r['id']+'/publish',owner,json={'expected_version':1})
   b=call('POST','/requests/'+r['id']+'/bookings',owner,201,json=dict(expected_version=1,helper_id='00000000-0000-4000-8000-000000000012',scheduled_start=start.isoformat(),scheduled_end=end.isoformat(),agreed_fee='10.00'))
   for who in [owner,helper]:call('POST','/bookings/'+b['id']+'/confirm',who,json={'expected_version':1})
   return r,b
  r,b=booking();bid=b['id']
  key=str(uuid.uuid4()); report={'expected_version':1,'reason_code':'cannot_enter','description':'门锁无法开启'}
  x=call('POST','/bookings/'+bid+'/exceptions',helper,201,key=key,json=report)
  assert call('POST','/bookings/'+bid+'/exceptions',helper,201,key=key,json=report)==x
  call('POST','/bookings/'+bid+'/exceptions',helper,409,json=report)
  call('GET','/bookings/'+bid+'/exceptions',stranger,403)
  call('GET','/requests/'+r['id']+'/events',stranger,403)
  call('POST','/exceptions/'+x['id']+'/resolve',helper,403,json={'expected_version':1,'decision':'resume','resolution':'已开门'})
  call('POST','/exceptions/'+x['id']+'/notes',owner,json={'note':'正在开门'})
  assert call('POST','/exceptions/'+x['id']+'/resolve',owner,json={'expected_version':1,'decision':'resume','resolution':'已开门'})['request_status']=='reserved'
  call('POST','/bookings/'+bid+'/start',helper,json={'expected_version':1})
  call('POST','/bookings/'+bid+'/records',helper,201,json={'checklist_item_id':r['checklist_items'][0]['id'],'kind':'item_completed','occurred_at':datetime.now(timezone.utc).isoformat(),'note':'已喂粮'})
  x=call('POST','/bookings/'+bid+'/exceptions',helper,201,json={'expected_version':1,'reason_code':'pet_hiding','description':'宠物躲藏，待宠主安排'})
  call('POST','/bookings/'+bid+'/submit',helper,409,json={'expected_version':1})
  changed=[{k:i[k] for k in ['item_key','position','content','completion_condition','required']} for i in r['checklist_items']]
  changed[0]['content']='修改已完成内容'
  call('POST','/exceptions/'+x['id']+'/resolve',owner,422,json={'expected_version':1,'decision':'resume','resolution':'变更','approved_change':{'checklist_items':changed}})
  approved={'expected_version':1,'decision':'resume','resolution':'同意免除换水','approved_change':{'waive_item_keys':['change_water']}}
  key=str(uuid.uuid4())
  a=call('POST','/exceptions/'+x['id']+'/resolve',owner,key=key,json=approved)
  assert a['request_version']==2 and a['status']=='open'
  assert call('POST','/exceptions/'+x['id']+'/resolve',owner,key=key,json=approved)==a
  call('POST','/exceptions/'+x['id']+'/resolve',owner,409,key=key,json={**approved,'resolution':'different'})
  call('POST','/bookings/'+bid+'/confirm',helper,409,json={'expected_version':1})
  call('POST','/bookings/'+bid+'/confirm',helper,json={'expected_version':2})
  detail=call('GET','/bookings/'+bid,helper)
  assert [i['execution_status'] for i in detail['checklist_items']]==['completed','waived']
  call('POST','/bookings/'+bid+'/submit',helper,json={'expected_version':2})
  x=call('POST','/bookings/'+bid+'/exceptions',owner,201,json={'expected_version':2,'reason_code':'verification_dispute','description':'请确认记录'})
  call('POST','/exceptions/'+x['id']+'/resolve',owner,json={'expected_version':2,'decision':'resume','resolution':'已核对'})
  result=call('POST','/bookings/'+bid+'/verify',owner,json={'expected_version':2})
  assert result['settlement_total']=='10.00'
  assert call('POST','/bookings/'+bid+'/verify',owner,json={'expected_version':2})==result
  events=call('GET','/requests/'+r['id']+'/events?limit=100',helper)['items']
  assert events and all(e['event_type']!='idempotency_result' for e in events)
  print('PASS exception permissions, notes, resume, version approval, preserved evidence, waived audit, dispute, settlement, replay')
  r,b=booking();bid=b['id']
  call('POST','/bookings/'+bid+'/start',helper,json={'expected_version':1})
  with connection() as db:
   db.execute('UPDATE "Booking" SET scheduled_start=clock_timestamp()-interval \'30 minutes\',scheduled_end=clock_timestamp()-interval \'1 minute\' WHERE id=%s',(bid,))
   db.execute('UPDATE "ServiceRequest" SET window_start=clock_timestamp()-interval \'1 hour\' WHERE id=%s',(r['id'],))
  x=call('POST','/bookings/'+bid+'/exceptions',helper,201,json={'expected_version':1,'reason_code':'service_timeout','description':'服务已超时'})
  call('POST','/exceptions/'+x['id']+'/resolve',owner,409,json={'expected_version':1,'decision':'resume','resolution':'继续'})
  competing=call('POST','/requests',owner,201,json=body)
  call('POST','/requests/'+competing['id']+'/publish',owner,json={'expected_version':1})
  # Existing overdue exception blocks normal creation, so seed a competing reservation
  # through a separate DB transaction to exercise resolution's conflict recheck.
  from app.routers.api import insert
  with connection() as db:
   blocked=insert(db,'Booking',dict(request_id=competing['id'],owner_id='00000000-0000-4000-8000-000000000001',helper_id='00000000-0000-4000-8000-000000000012',request_version=1,request_snapshot={},scheduled_start=now+timedelta(minutes=60),scheduled_end=now+timedelta(minutes=80),agreed_fee='10.00',reserved_until=now+timedelta(minutes=15)))
   db.execute('UPDATE "ServiceRequest" SET status=%s WHERE id=%s',('pending_confirm',competing['id']))
  denied={'expected_version':1,'decision':'resume','resolution':'延期冲突测试','approved_change':{'scheduled_end':(now+timedelta(minutes=90)).isoformat()}}
  call('POST','/exceptions/'+x['id']+'/resolve',owner,409,json=denied)
  assert call('GET','/requests/'+r['id'],owner)['version']==1
  call('POST','/bookings/'+str(blocked['id'])+'/withdraw',helper,json={'reason':'释放测试占用'})
  extended=(now+timedelta(minutes=90)).isoformat()
  call('POST','/exceptions/'+x['id']+'/resolve',owner,json={'expected_version':1,'decision':'resume','resolution':'批准延长','approved_change':{'scheduled_end':extended}})
  call('POST','/bookings/'+bid+'/confirm',helper,json={'expected_version':2})
  x=call('POST','/bookings/'+bid+'/exceptions',helper,201,json={'expected_version':2,'reason_code':'other','description':'宠主决定结束'})
  closed=call('POST','/exceptions/'+x['id']+'/resolve',owner,json={'expected_version':2,'decision':'end','resolution':'提前终止'})
  assert closed['request_status']=='cancelled'
  detail=call('GET','/bookings/'+bid,owner)
  assert detail['settlement_status']=='unsettled' and detail['agreed_fee']=='10.00'
  print('PASS timeout requires approved extension and reconfirmation; termination preserves fees without settlement')

  body['service_type']='errand_buy'
  body['checklist_items']=[dict(item_key=k,position=i,content=k,completion_condition='记录凭证') for i,k in enumerate(['purchase','delivery'],1)]
  r,b=booking();bid=b['id']
  call('POST','/bookings/'+bid+'/start',helper,json={'expected_version':1})
  x=call('POST','/bookings/'+bid+'/exceptions',helper,201,json={'expected_version':1,'reason_code':'over_budget','description':'商品需40元','proposed_change':{'budget':'45.00'}})
  assert call('GET','/requests/'+r['id'],owner)['budget']=='30.00'
  call('POST','/exceptions/'+x['id']+'/resolve',owner,json={'expected_version':1,'decision':'resume','resolution':'同意预算','approved_change':{'budget':'45.00'}})
  call('POST','/bookings/'+bid+'/confirm',helper,json={'expected_version':2})
  import io
  from PIL import Image
  buf=io.BytesIO();Image.new('RGB',(8,8),'white').save(buf,format='PNG')
  url=call('POST','/media',helper,201,data={'purpose':'evidence'},files={'file':('receipt.png',buf.getvalue(),'image/png')})['url']
  detail=call('GET','/bookings/'+bid,helper)
  for item in detail['checklist_items']:
   evidence={'checklist_item_id':item['id'],'kind':item['item_key'],'occurred_at':datetime.now(timezone.utc).isoformat(),'note':'测试交付'}
   if item['item_key']=='purchase':evidence.update(photo_urls=[url],actual_cost='40.00')
   call('POST','/bookings/'+bid+'/records',helper,201,json=evidence)
  call('POST','/bookings/'+bid+'/submit',helper,json={'expected_version':2})
  assert call('POST','/bookings/'+bid+'/verify',owner,json={'expected_version':2})['settlement_total']=='50.00'
  print('PASS over-budget proposal does not mutate budget; approval and helper confirmation enable purchase and settlement')


if __name__=='__main__':run()
