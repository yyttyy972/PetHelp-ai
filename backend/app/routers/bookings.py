from datetime import timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import Field, AwareDatetime
from app.schemas import Model, Publish
from app.routers.api import db, me, one, own, role, insert, update, clean, demand_view, Error, page, media_ref

router = APIRouter(prefix='/api/v0')

class BookingInput(Publish):
    helper_id: UUID
    scheduled_start: AwareDatetime
    scheduled_end: AwareDatetime
    agreed_fee: Decimal = Field(ge=0, max_digits=10, decimal_places=2)

class Withdrawal(Model):
    reason: str = Field(min_length=1)

class RecordInput(Model):
    checklist_item_id: UUID
    kind: Literal['item_completed','pickup','departure','return','purchase','delivery']
    occurred_at: AwareDatetime
    note: str | None = None
    photo_urls: list[str] = Field(default_factory=list)
    actual_cost: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)

def now(c):
    return c.execute('SELECT clock_timestamp() AS time').fetchone()['time']

def log(c,r,b,u,op,old,payload=None):
    insert(c,'TaskEvent',dict(request_id=r['id'],booking_id=b['id'],actor_id=u['id'],event_type=op,operation=op,from_status=old,to_status=r['status'],request_version=r['version'],payload=payload or {}))

def transition(c,r,b,u,status,op,**values):
    old=r['status']
    b=update(c,'Booking',b['id'],dict(status=status,**values))
    r=update(c,'ServiceRequest',r['id'],{'status':status})
    log(c,r,b,u,op,old)
    return r,b

def cancel(c,r,b,u,reason):
    old=r['status']
    b=update(c,'Booking',b['id'],dict(status='cancelled',cancel_reason=reason))
    r=update(c,'ServiceRequest',r['id'],{'status':'pending_match'})
    log(c,r,b,u,'booking_cancelled',old,{'reason':reason})
    return r,b

def locked(c,id,u):
    ref=one(c,'Booking',id)
    r=one(c,'ServiceRequest',ref['request_id'],True)
    h=one(c,'HelperProfile',ref['helper_id'],True)
    b=one(c,'Booking',id,True)
    if u['id'] not in (b['owner_id'],h['user_id']):raise Error(403,'forbidden')
    return r,b,h

def version(r,b,v):
    if v!=r['version'] or b['request_version']!=r['version']:raise Error(409,'version_conflict')

def result(r,b):
    return {**clean(b),'request_status':r['status']}

def eligible(c,r,h,start,end,fee):
    owner=one(c,'User',r['owner_id']); user=one(c,'User',h['user_id'])
    role(owner,'owner');role(user,'helper')
    if user['id']==owner['id'] or user['community_code']!=r['community_code']:raise Error(403,'forbidden')
    pets=c.execute('SELECT p.* FROM "RequestPet" rp JOIN "PetProfile" p ON p.id=rp.pet_id WHERE rp.request_id=%s AND rp.deleted_at IS NULL',(r['id'],)).fetchall()
    if not pets or any(p['deleted_at'] or p['owner_id']!=r['owner_id'] or p['species'] not in h['supported_species'] or (r['service_type']=='dog_walking' and p['species']!='dog') for p in pets):raise Error(422,'invalid_pet')
    if r['service_type'] not in h['service_types'] or h['fee_pref'] not in [r['fee_type'],'both']:raise Error(422,'invalid_profile')
    if (r['fee_type']=='free' and fee!=0) or (r['fee_type']=='paid' and fee<=0) or (r['service_type']!='errand_buy' and fee>r['budget']):raise Error(422,'invalid_request')
    if not r['window_start']<=start<end<=r['window_end'] or (end-start).total_seconds()<r['expected_duration_minutes']*60 or end<=now(c):raise Error(422,'invalid_window')
    if not c.execute('SELECT 1 FROM "Availability" WHERE helper_id=%s AND deleted_at IS NULL AND start_at<=%s AND end_at>=%s',(h['id'],start,end)).fetchone():raise Error(409,'time_conflict')
    if c.execute('''SELECT 1 FROM "Booking" WHERE helper_id=%s AND deleted_at IS NULL
        AND status NOT IN ('completed','cancelled')
        AND (status<>'pending_confirm' OR reserved_until>clock_timestamp())
        AND ((scheduled_start<%s AND scheduled_end>%s) OR (status IN ('in_service','exception') AND scheduled_end<clock_timestamp()))''',(h['id'],end,start)).fetchone():raise Error(409,'time_conflict')

@router.post('/requests/{id}/bookings',status_code=201)
def create(id:UUID,body:BookingInput,u=Depends(me),c=Depends(db)):
    r=one(c,'ServiceRequest',id,True)
    active=c.execute('SELECT * FROM "Booking" WHERE request_id=%s AND deleted_at IS NULL AND status<>\'cancelled\'',(id,)).fetchone()
    ids=sorted({body.helper_id}|({active['helper_id']} if active else set()))
    helpers={x:one(c,'HelperProfile',x,True) for x in ids}
    h=helpers[body.helper_id]
    if u['id'] not in [r['owner_id'],h['user_id']]:raise Error(403,'forbidden')
    if body.expected_version!=r['version']:raise Error(409,'version_conflict')
    if active and active['status']=='pending_confirm' and active['reserved_until']<=now(c):r,_=cancel(c,r,active,u,'confirmation_timeout')
    if r['status']!='pending_match':raise Error(409,'booking_exists')
    eligible(c,r,h,body.scheduled_start,body.scheduled_end,body.agreed_fee)
    snapshot=demand_view(c,r,one(c,'User',r['owner_id']))
    snapshot.pop('status',None)
    for item in snapshot['checklist_items']:item.pop('execution_status',None)
    b=insert(c,'Booking',dict(request_id=id,owner_id=r['owner_id'],helper_id=h['id'],request_version=r['version'],request_snapshot=snapshot,scheduled_start=body.scheduled_start,scheduled_end=body.scheduled_end,agreed_fee=body.agreed_fee,reserved_until=now(c)+timedelta(minutes=15)))
    r=update(c,'ServiceRequest',id,{'status':'pending_confirm'});log(c,r,b,u,'booking_created','pending_match')
    return result(r,b)

@router.post('/bookings/{id}/confirm')
def confirm(id:UUID,body:Publish,u=Depends(me),c=Depends(db)):
    r,b,h=locked(c,id,u)
    if b['status']=='pending_confirm' and b['reserved_until']<=now(c):
        r,b=cancel(c,r,b,u,'confirmation_timeout')
        c.commit()  # Persist expiry even though this confirmation is rejected.
        raise Error(409,'reservation_expired')
    version(r,b,body.expected_version)
    if b['status']=='reserved':return result(r,b)
    if b['status']!='pending_confirm':raise Error(409,'invalid_state')
    field='owner_confirmed_at' if u['id']==b['owner_id'] else 'helper_confirmed_at'
    if b[field] is None:
        b=update(c,'Booking',id,{field:now(c)});log(c,r,b,u,'confirmed',r['status'])
    if b['owner_confirmed_at'] and b['helper_confirmed_at']:r,b=transition(c,r,b,u,'reserved','reserved')
    return result(r,b)

@router.post('/bookings/{id}/withdraw')
def withdraw(id:UUID,body:Withdrawal,u=Depends(me),c=Depends(db)):
    r,b,h=locked(c,id,u)
    if b['status'] not in ['pending_confirm','reserved']:raise Error(409,'invalid_state')
    r,b=cancel(c,r,b,u,body.reason);return result(r,b)

@router.post('/bookings/{id}/start')
def start(id:UUID,body:Publish,u=Depends(me),c=Depends(db)):
    r,b,h=locked(c,id,u);version(r,b,body.expected_version)
    if u['id']!=h['user_id']:raise Error(403,'forbidden')
    if b['status']!='reserved' or not b['owner_confirmed_at'] or not b['helper_confirmed_at'] or not b['scheduled_start']<=now(c)<b['scheduled_end']:raise Error(409,'invalid_state')
    r,b=transition(c,r,b,u,'in_service','started');return result(r,b)

@router.post('/bookings/{id}/records',status_code=201)
def record(id:UUID,body:RecordInput,u=Depends(me),c=Depends(db)):
    r,b,h=locked(c,id,u)
    if u['id']!=h['user_id']:raise Error(403,'forbidden')
    version(r,b,r['version'])
    if b['status']!='in_service':raise Error(409,'invalid_state')
    item=one(c,'ChecklistItem',body.checklist_item_id,True)
    if item['request_id']!=r['id'] or item['request_version']!=b['request_version']:raise Error(422,'invalid_evidence')
    expected=item['item_key'] if item['item_key'] in ['pickup','departure','return','purchase','delivery'] else 'item_completed'
    allowed={'home_visit':['item_completed'],'dog_walking':['item_completed','pickup','departure','return'],'errand_buy':['item_completed','purchase','delivery']}[r['service_type']]
    if body.kind!=expected or body.kind not in allowed or not (body.note or body.photo_urls) or not b['scheduled_start']<=body.occurred_at<=now(c):raise Error(422,'invalid_evidence')
    for url in body.photo_urls:media_ref(url,u,'evidence')
    if body.kind=='purchase':
        if not body.photo_urls or body.actual_cost is None or body.actual_cost>r['budget']:raise Error(422,'invalid_evidence')
    elif body.actual_cost is not None:raise Error(422,'invalid_evidence')
    previous={'departure':'pickup','return':'departure','delivery':'purchase'}.get(body.kind)
    if previous:
        prev=c.execute('SELECT occurred_at FROM "ExecutionRecord" WHERE booking_id=%s AND kind=%s AND deleted_at IS NULL ORDER BY occurred_at DESC LIMIT 1',(id,previous)).fetchone()
        if not prev or body.occurred_at<prev['occurred_at']:raise Error(422,'invalid_evidence')
    e=insert(c,'ExecutionRecord',dict(booking_id=id,actor_id=u['id'],**body.model_dump()))
    update(c,'ChecklistItem',item['id'],{'execution_status':'completed'})
    if body.kind=='purchase':update(c,'Booking',id,{'actual_cost':body.actual_cost})
    log(c,r,b,u,'record_added',r['status'],{'record_id':str(e['id'])})
    return clean(e)

@router.get('/bookings/{id}/records')
def records(id:UUID,limit:int=Query(20,ge=1,le=100),cursor:str|None=None,u=Depends(me),c=Depends(db)):
    locked(c,id,u);rows,n=page(c,'ExecutionRecord','booking_id=%s',[id],limit,cursor)
    return {'items':clean(rows),'next_cursor':n}

def complete_check(c,r,b):
    items=c.execute('SELECT * FROM "ChecklistItem" WHERE request_id=%s AND request_version=%s',(r['id'],b['request_version'])).fetchall()
    for item in items:
        if not item['required'] or item['execution_status']=='completed':continue
        approval=c.execute('''SELECT 1 FROM "TaskEvent" WHERE request_id=%s AND booking_id=%s
            AND actor_id=%s AND request_version=%s AND event_type='checklist_waived'
            AND payload->>'checklist_item_id'=%s AND deleted_at IS NULL''',
            (r['id'],b['id'],b['owner_id'],b['request_version'],str(item['id']))).fetchone()
        if item['execution_status']!='waived' or not approval:raise Error(422,'checklist_incomplete')
    records=c.execute('SELECT * FROM "ExecutionRecord" WHERE booking_id=%s AND deleted_at IS NULL',(b['id'],)).fetchall()
    kinds={e['kind'] for e in records}
    required={'dog_walking':{'pickup','departure','return'},'errand_buy':{'purchase','delivery'}}.get(r['service_type'],set())
    if not required<=kinds:raise Error(422,'checklist_incomplete')
    if r['service_type']=='errand_buy' and (b['actual_cost'] is None or b['actual_cost']>r['budget'] or not any(e['kind']=='purchase' and e['photo_urls'] for e in records)):raise Error(422,'invalid_evidence')

@router.post('/bookings/{id}/submit')
def submit(id:UUID,body:Publish,u=Depends(me),c=Depends(db)):
    r,b,h=locked(c,id,u);version(r,b,body.expected_version)
    if u['id']!=h['user_id']:raise Error(403,'forbidden')
    if b['status']!='in_service':raise Error(409,'invalid_state')
    complete_check(c,r,b);r,b=transition(c,r,b,u,'pending_verify','submitted');return result(r,b)

@router.post('/bookings/{id}/verify')
def verify(id:UUID,body:Publish,u=Depends(me),c=Depends(db)):
    r,b,h=locked(c,id,u);own(b,u);version(r,b,body.expected_version)
    if b['status']!='completed':
        if b['status']!='pending_verify':raise Error(409,'invalid_state')
        complete_check(c,r,b)
        r,b=transition(c,r,b,u,'completed','completed',settlement_status='simulated_settled',settled_at=now(c))
    return {**result(r,b),'settlement_total':format(b['agreed_fee']+(b['actual_cost'] or Decimal('0.00')),'.2f')}


class CancelRequest(Publish):
    reason: str = Field(min_length=1)

@router.post('/requests/{id}/cancel')
def cancel_request(id:UUID,body:CancelRequest,u=Depends(me),c=Depends(db)):
    r=one(c,'ServiceRequest',id,True);own(r,u)
    if body.expected_version!=r['version']:raise Error(409,'version_conflict')
    if r['status'] not in ['draft','pending_match','pending_confirm','reserved']:raise Error(409,'invalid_state')
    old=r['status']
    active=c.execute('SELECT * FROM "Booking" WHERE request_id=%s AND deleted_at IS NULL AND status<>\'cancelled\'',(id,)).fetchone()
    if active:
        one(c,'HelperProfile',active['helper_id'],True)
        one(c,'Booking',active['id'],True)
        update(c,'Booking',active['id'],dict(status='cancelled',cancel_reason=body.reason))
    r=update(c,'ServiceRequest',id,{'status':'cancelled'})
    insert(c,'TaskEvent',dict(request_id=id,booking_id=active['id'] if active else None,actor_id=u['id'],event_type='request_cancelled',operation='cancel_request',from_status=old,to_status='cancelled',request_version=r['version'],payload={'reason':body.reason}))
    return demand_view(c,r,u)
