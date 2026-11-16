import os,uuid
from datetime import datetime,timedelta,timezone
os.environ.setdefault('JWT_SECRET','week11-local-test-secret-at-least-32-characters')
from fastapi.testclient import TestClient
from app.main import app

def run():
 with TestClient(app) as c:
  def call(method,path,expected=200,token=None,**kw):
   headers={'Authorization':'Bearer '+token} if token else {}
   if method!='GET':headers['Idempotency-Key']=str(uuid.uuid4())
   headers.update(kw.pop('headers',{}))
   r=c.request(method,'/api/v0'+path,headers=headers,**kw)
   assert r.status_code==expected,(path,r.status_code,r.text)
   return r.json() if r.content else None
  owner=call('POST','/auth/login',json={'account':'xiaolin','password':'NeighborPet2026!'})['access_token']
  helper=call('POST','/auth/login',json={'account':'jianguo','password':'NeighborPet2026!'})['access_token']
  hid='00000000-0000-4000-8000-000000000012'
  pet=call('POST','/pets',201,owner,json={'name':'week11-dog','species':'dog','birth_date':'2024-01-01'})['id']
  now=datetime.now(timezone.utc); start=now-timedelta(seconds=30);end=now+timedelta(minutes=40)
  call('POST','/helpers/me/availability',201,helper,json={'start_at':(now-timedelta(days=1)).isoformat(),'end_at':(now+timedelta(days=1)).isoformat()})
  for service,keys in [('home_visit',['feed_food']),('dog_walking',['pickup','departure','return']),('errand_buy',['purchase','delivery'])]:
   body=dict(pet_ids=[pet],service_type=service,fee_type='paid',window_start=(now-timedelta(minutes=1)).isoformat(),window_end=(now+timedelta(hours=1)).isoformat(),expected_duration_minutes=10,location='测试门厅',budget='30.00',handover_notes='联系宠主',emergency_contact='测试联系人',checklist_items=[dict(item_key=k,position=i,content=k,completion_condition='记录证据') for i,k in enumerate(keys,1)])
   r=call('POST','/requests',201,owner,json=body);rid=r['id']
   call('POST',f'/requests/{rid}/publish',token=owner,json={'expected_version':1})
   match=call('POST',f'/requests/{rid}/match',token=owner,json={'expected_version':1})
   assert all(x['helper_id']!='00000000-0000-4000-8000-000000000011' for x in match['candidates'])
   b=call('POST',f'/requests/{rid}/bookings',201,owner,json=dict(expected_version=1,helper_id=hid,scheduled_start=start.isoformat(),scheduled_end=end.isoformat(),agreed_fee='10.00'));bid=b['id']
   missing=c.post('/api/v0/bookings/'+bid+'/confirm',headers={'Authorization':'Bearer '+owner},json={'expected_version':1})
   assert missing.status_code==422 and missing.json()['code']=='validation_error'
   first=call('POST',f'/bookings/{bid}/confirm',token=owner,json={'expected_version':1});assert first['status']=='pending_confirm'
   second=call('POST',f'/bookings/{bid}/confirm',token=helper,json={'expected_version':1});assert second['status']=='reserved'
   call('POST',f'/bookings/{bid}/start',token=helper,json={'expected_version':1})
   call('POST',f'/bookings/{bid}/submit',422,helper,json={'expected_version':1})
   for item in r['checklist_items']:
    kind=item['item_key'] if service!='home_visit' else 'item_completed'
    d=dict(checklist_item_id=item['id'],kind=kind,occurred_at=datetime.now(timezone.utc).isoformat(),note='测试执行证据')
    if kind=='purchase':
     import io
     from PIL import Image
     buf=io.BytesIO();Image.new('RGB',(8,8),'white').save(buf,format='PNG')
     url=call('POST','/media',201,helper,data={'purpose':'evidence'},files={'file':('receipt.png',buf.getvalue(),'image/png')})['url']
     d.update(photo_urls=[url],actual_cost='12.50')
    call('POST',f'/bookings/{bid}/records',201,helper,json=d)
   call('POST',f'/bookings/{bid}/submit',token=helper,json={'expected_version':1})
   missing=c.post('/api/v0/bookings/'+bid+'/verify',headers={'Authorization':'Bearer '+owner},json={'expected_version':1})
   assert missing.status_code==422 and missing.json()['code']=='validation_error'
   k={'Idempotency-Key':str(uuid.uuid4())}
   v=call('POST',f'/bookings/{bid}/verify',token=owner,headers=k,json={'expected_version':1})
   assert v['settlement_total']==('22.50' if service=='errand_buy' else '10.00')
   assert call('POST',f'/bookings/{bid}/verify',token=owner,headers=k,json={'expected_version':1})==v
   assert call('POST',f'/bookings/{bid}/verify',token=owner,json={'expected_version':1})==v
   print('PASS',service,'booking-confirm-start-record-submit-verify-replay')
  def new_request():
   r=call('POST','/requests',201,owner,json=body)
   call('POST','/requests/'+r['id']+'/publish',token=owner,json={'expected_version':1})
   return r
  def book(r):
   return call('POST','/requests/'+r['id']+'/bookings',201,owner,json=dict(expected_version=1,helper_id=hid,scheduled_start=start.isoformat(),scheduled_end=end.isoformat(),agreed_fee='10.00'))
  r=new_request();b=book(r)
  r2=new_request()
  call('POST','/requests/'+r2['id']+'/bookings',409,owner,json=dict(expected_version=1,helper_id=hid,scheduled_start=start.isoformat(),scheduled_end=end.isoformat(),agreed_fee='10.00'))
  changed=call('PATCH','/requests/'+r['id'],token=owner,json={'expected_version':1,'precautions':'新禁止事项'})
  assert changed['version']==2 and changed['status']=='pending_match'
  call('POST','/bookings/'+b['id']+'/confirm',409,helper,json={'expected_version':1})
  b=book(r2)
  withdrawn=call('POST','/bookings/'+b['id']+'/withdraw',token=helper,json={'reason':'临时有事'})
  assert withdrawn['status']=='cancelled' and withdrawn['request_status']=='pending_match'
  r=new_request();b=book(r)
  from app.db import connection
  with connection() as db:
   db.execute('UPDATE "Booking" SET reserved_until=clock_timestamp()-interval \'1 minute\' WHERE id=%s',(b['id'],))
  call('POST','/bookings/'+b['id']+'/confirm',409,helper,json={'expected_version':1})
  assert call('GET','/requests/'+r['id'],token=owner)['status']=='pending_match'
  from concurrent.futures import ThreadPoolExecutor
  from threading import Barrier
  from app.routers.bookings import create,BookingInput
  from app.routers.api import one,Error
  barrier=Barrier(2);rs=[new_request(),new_request()]
  def concurrent_attempt(r):
   with connection() as db:
    u=one(db,'User',uuid.UUID('00000000-0000-4000-8000-000000000001'))
    barrier.wait(timeout=10)
    try:
     return create(uuid.UUID(r['id']),BookingInput(expected_version=1,helper_id=hid,scheduled_start=start,scheduled_end=end,agreed_fee='10.00'),u,db)['id']
    except Error as e:
     db.rollback();return e.code
  with ThreadPoolExecutor(max_workers=2) as pool:
   outcomes=list(pool.map(concurrent_attempt,rs))
  assert outcomes.count('time_conflict')==1,outcomes
  winning=next(x for x in outcomes if x!='time_conflict')
  call('POST','/bookings/'+winning+'/withdraw',token=helper,json={'reason':'并发测试清理'})
  print('PASS version-invalidation/withdraw/expiry/conflict/independent-transaction-concurrency')
  for stage in ['draft','pending_match','pending_confirm','reserved']:
   x=call('POST','/requests',201,owner,json=body)
   active=None
   if stage!='draft':call('POST','/requests/'+x['id']+'/publish',token=owner,json={'expected_version':1})
   if stage in ['pending_confirm','reserved']:active=book(x)
   if stage=='reserved':
    for who in [owner,helper]:call('POST','/bookings/'+active['id']+'/confirm',token=who,json={'expected_version':1})
   call('POST','/requests/'+x['id']+'/cancel',403,helper,json={'expected_version':1,'reason':'越权'})
   ck={'Idempotency-Key':str(uuid.uuid4())}
   cancelled=call('POST','/requests/'+x['id']+'/cancel',token=owner,headers=ck,json={'expected_version':1,'reason':'行程取消'})
   assert cancelled['status']=='cancelled'
   assert call('POST','/requests/'+x['id']+'/cancel',token=owner,headers=ck,json={'expected_version':1,'reason':'行程取消'})==cancelled
   if active:
    with connection() as db:assert db.execute('SELECT status FROM "Booking" WHERE id=%s',(active['id'],)).fetchone()['status']=='cancelled'
  from app.routers.match import has_slot
  t=now.replace(hour=10,minute=0,second=0,microsecond=0)+timedelta(days=2)
  req={'window_start':t,'window_end':t+timedelta(hours=2),'expected_duration_minutes':60}
  avail=[{'start_at':t+timedelta(hours=1),'end_at':t+timedelta(hours=2)}]
  assert has_slot(req,avail,[],now)
  assert not has_slot(req,avail,[{'scheduled_start':t+timedelta(minutes=90),'scheduled_end':t+timedelta(minutes=100)}],now)
  assert has_slot(req,[{'start_at':t,'end_at':t+timedelta(hours=2)}],[{'scheduled_start':t,'scheduled_end':t+timedelta(hours=1)}],now)
  assert not has_slot(req,[{'start_at':t,'end_at':t+timedelta(minutes=30)},{'start_at':t+timedelta(minutes=30),'end_at':t+timedelta(hours=1)}],[],now)
  print('PASS missing-idempotency-key/cancel-four-states/authorization/cancel-replay/partial-window/free-gap')
if __name__=='__main__':run()
