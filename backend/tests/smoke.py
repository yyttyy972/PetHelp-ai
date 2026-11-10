import os, uuid, io
import httpx
from PIL import Image
base=os.getenv('BASE_URL','http://127.0.0.1:8000')
c=httpx.Client(base_url=base,timeout=30)
def req(method,path,status=200,**kw):
    r=c.request(method,'/api/v0'+path,**kw)
    assert r.status_code==status,(method,path,r.status_code,r.text)
    return r.json() if r.content else None
assert c.get('/health').json()=={'status':'ok'}
account='test_'+uuid.uuid4().hex[:12]
user=req('POST','/auth/register',201,json=dict(account=account,password='TestPassword2026!',display_name='多宠测试',roles=['owner','helper']))
assert user['verification_status']=='unverified'
t=req('POST','/auth/login',json=dict(account=account,password='TestPassword2026!'))
c.headers['Authorization']='Bearer '+t['access_token']
req('PATCH','/users/me',403,json={'verification_status':'verified'})
pets=[]
for name in ['测试豆豆','测试团团']:
    pets.append(req('POST','/pets',201,json=dict(name=name,species='dog',birth_date='2024-01-01')))
body=dict(pet_ids=[p['id'] for p in pets],service_type='dog_walking',fee_type='paid',window_start='2026-11-10T02:00:00Z',window_end='2026-11-10T04:00:00Z',expected_duration_minutes=30,location='测试社区门厅',budget='30.00',handover_notes='到门厅联系',emergency_contact='测试联系人',checklist_items=[dict(item_key=k,pet_id=pets[0]['id'] if i==1 else None,position=i,content=k,completion_condition='记录时间') for i,k in enumerate(['pickup','departure','return'],1)])
key={'Idempotency-Key':str(uuid.uuid4())}
r=req('POST','/requests',201,json=body,headers=key)
assert req('POST','/requests',201,json=body,headers=key)['id']==r['id']
req('POST','/requests',409,json={**body,'budget':'40.00'},headers=key)
assert len(r['pets'])==2 and r['checklist_items'][0]['pet_id']==pets[0]['id']
r=req('PATCH','/requests/'+r['id'],json={'expected_version':1,'precautions':'全程牵绳'})
assert r['version']==2
req('PATCH','/requests/'+r['id'],409,json={'expected_version':1,'budget':'20.00'})
r=req('POST','/requests/'+r['id']+'/publish',json={'expected_version':2})
assert r['status']=='pending_match'
req('DELETE','/requests/'+r['id'],409)
assert len(req('GET','/requests/'+r['id'])['pets'])==2
hall=req('GET','/requests?scope=open&limit=100')['items']
assert all(set(x)==set('id service_type window_start window_end expected_duration_minutes budget fee_type version status community_code'.split()) for x in hall)
req('POST','/ai/parse',503,json={'text':'帮忙遛狗'})
buf=io.BytesIO();Image.new('RGB',(4,4),'blue').save(buf,format='PNG')
url=req('POST','/media',201,data={'purpose':'pet'},files={'file':('pet.png',buf.getvalue(),'image/png')})['url']
req('PATCH','/pets/'+pets[0]['id'],json={'photo_url':url})
assert c.get(url).status_code==200
other=httpx.Client(base_url=base,timeout=30)
assert other.get(url).status_code==401
print('PASS health/register/login/multi-pet/create/publish/version/idempotency/hall/media/privacy/AI-stub')
helper=req('PUT','/helpers/me',json=dict(service_types=['dog_walking'],service_area='社区内',experience='两年养狗经验',supported_species=['dog'],service_radius_m=500))
assert helper['verification_status']=='unverified' and helper['fee_pref']=='both'
a=req('POST','/helpers/me/availability',201,json=dict(start_at='2026-11-10T01:00:00Z',end_at='2026-11-10T09:00:00Z'))
req('DELETE','/helpers/me/availability/'+a['id'],204)
req('POST','/helpers/me/availability',422,json=dict(start_at='2026-11-10T01:00:00',end_at='2026-11-10T09:00:00'))
draft=req('POST','/requests',201,json=body)
req('DELETE','/requests/'+draft['id'],204)
req('GET','/requests/'+draft['id'],404)
req('DELETE','/pets/'+pets[0]['id'],409)
req('POST','/media',422,data={'purpose':'pet'},files={'file':('fake.png',b'not-an-image','image/png')})
bad={**body,'checklist_items':[{**i,'pet_id':str(uuid.uuid4())} for i in body['checklist_items']]}
req('POST','/requests',422,json=bad)
second='privacy_'+uuid.uuid4().hex[:12]
other.post('/api/v0/auth/register',json=dict(account=second,password='TestPassword2026!',display_name='另一位居民',roles=['owner']))
ot=other.post('/api/v0/auth/login',json=dict(account=second,password='TestPassword2026!')).json()
other.headers['Authorization']='Bearer '+ot['access_token']
assert 'pets' not in other.get('/api/v0/requests/'+r['id']).json()
assert other.get(url).status_code==403
assert other.patch('/api/v0/pets/'+pets[0]['id'],json={'name':'越权修改'}).status_code==403
print('PASS helper/availability/timezone/draft-delete/reference-protection/media-validation/foreign-pet/privacy')
