from decimal import Decimal
from psycopg.types.json import Jsonb
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import Field, AwareDatetime
from app.schemas import Model, Publish, Demand, Item
from app.routers.api import db, me, one, own, clean, insert, update, page, demand_view, checklist, Error
from app.routers.bookings import locked, now, version, transition, log, eligible

router = APIRouter(prefix='/api/v0')

class Change(Model):
    budget: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    precautions: str | None = None
    requirements: str | None = None
    window_end: AwareDatetime | None = None
    scheduled_end: AwareDatetime | None = None
    checklist_items: list[Item] | None = Field(None, min_length=1)
    waive_item_keys: list[str] = Field(default_factory=list)

class Report(Publish):
    reason_code: Literal['cannot_enter','pet_hiding','service_timeout','over_budget','out_of_stock','verification_dispute','other']
    description: str = Field(min_length=1)
    proposed_change: Change | None = None

class Note(Model):
    note: str = Field(min_length=1)

class Resolve(Publish):
    resolution: str = Field(min_length=1)
    decision: Literal['resume','end']
    approved_change: Change | None = None

def view(x,r):
    return {**clean(x), 'request_status': r['status'], 'request_version': r['version']}

def lock_exception(c,id,u):
    ref=one(c,'ExceptionRecord',id)
    r,b,h=locked(c,ref['booking_id'],u)
    x=one(c,'ExceptionRecord',id,True)
    if x['status']!='open' or b['status']!='exception':raise Error(409,'invalid_state')
    return r,b,h,x

def report_exception(c,r,b,u,reason,description,proposed=None):
    # D's scheduler may call with u=None after acquiring request/helper/booking locks.
    if b['status'] not in ['reserved','in_service','pending_verify']:raise Error(409,'invalid_state')
    if reason=='service_timeout' and (b['status']!='in_service' or b['scheduled_end']>now(c)):raise Error(409,'invalid_state')
    if reason=='verification_dispute' and (b['status']!='pending_verify' or not u or u['id']!=b['owner_id']):raise Error(403,'forbidden')
    actor=u or {'id':None}
    x=insert(c,'ExceptionRecord',dict(booking_id=b['id'],reported_by=actor['id'],reason_code=reason,description=description,resume_status=b['status'],proposed_change=proposed))
    r,b=transition(c,r,b,actor,'exception','exception_reported',)
    log(c,r,b,actor,'exception_reminder',r['status'],{'exception_id':str(x['id']),'reason_code':reason})
    return view(x,r)

@router.post('/bookings/{id}/exceptions',status_code=201)
def report(id:UUID,body:Report,u=Depends(me),c=Depends(db)):
    r,b,h=locked(c,id,u);version(r,b,body.expected_version)
    return report_exception(c,r,b,u,body.reason_code,body.description,body.proposed_change.model_dump(mode='json',exclude_unset=True) if body.proposed_change else None)

@router.get('/bookings/{id}/exceptions')
def history(id:UUID,limit:int=Query(20,ge=1,le=100),cursor:str|None=None,u=Depends(me),c=Depends(db)):
    locked(c,id,u)
    rows,n=page(c,'ExceptionRecord','booking_id=%s',[id],limit,cursor)
    return {'items':clean(rows),'next_cursor':n}

@router.post('/exceptions/{id}/notes')
def notes(id:UUID,body:Note,u=Depends(me),c=Depends(db)):
    r,b,h,x=lock_exception(c,id,u)
    return clean(insert(c,'TaskEvent',dict(request_id=r['id'],booking_id=b['id'],actor_id=u['id'],event_type='exception_note',operation='exception_note',from_status=r['status'],to_status=r['status'],request_version=r['version'],payload={'exception_id':str(id),'note':body.note})))

def finish(c,r,b,x,u,resolution,status):
    x=update(c,'ExceptionRecord',x['id'],dict(status='resolved',resolution=resolution,resolved_by=u['id'],resolved_at=now(c)))
    r,b=transition(c,r,b,u,status,'exception_resolved')
    return view(x,r)

@router.post('/exceptions/{id}/resolve')
def resolve(id:UUID,body:Resolve,u=Depends(me),c=Depends(db)):
    r,b,h,x=lock_exception(c,id,u);own(b,u);version(r,b,body.expected_version)
    if body.decision=='end':
        if body.approved_change is not None:raise Error(422,'invalid_change')
        update(c,'Booking',b['id'],{'cancel_reason':body.resolution})
        return finish(c,r,b,x,u,body.resolution,'cancelled')
    if x['approved_change'] is not None:raise Error(409,'confirmation_pending')
    change=body.approved_change.model_dump(exclude_unset=True) if body.approved_change else {}
    if not change:
        if x['resume_status'] in ['reserved','in_service'] and b['scheduled_end']<=now(c):raise Error(409,'schedule_extension_required')
        return finish(c,r,b,x,u,body.resolution,x['resume_status'])
    if any(change.get(k) is None for k in ['budget','window_end','scheduled_end','checklist_items'] if k in change):raise Error(422,'invalid_change')
    current=demand_view(c,r,u)
    old_items=current['checklist_items']
    data={k:r[k] for k in Demand.model_fields if k not in ['pet_ids','checklist_items']}
    data['pet_ids']=[p['id'] for p in current['pets']]
    data['checklist_items']=[{k:i[k] for k in Item.model_fields} for i in old_items]
    data.update({k:v for k,v in change.items() if k in Demand.model_fields})
    validated=Demand.model_validate(data)
    items={i.item_key:i for i in validated.checklist_items}
    # Evidence-bearing and completed items are immutable across versions.
    protected={row['item_key'] for row in c.execute('SELECT DISTINCT i.item_key FROM "ExecutionRecord" e JOIN "ChecklistItem" i ON i.id=e.checklist_item_id WHERE e.booking_id=%s AND e.deleted_at IS NULL',(b['id'],)).fetchall()}
    for old in old_items:
        if old['execution_status'] in ['completed','waived'] or old['item_key'] in protected:
            if old['item_key'] not in items or clean(items[old['item_key']].model_dump())!={k:old[k] for k in Item.model_fields}:raise Error(422,'executed_item_immutable')
    waived=set(change.get('waive_item_keys',[]))
    if not waived<=items.keys() or waived & protected:raise Error(422,'invalid_change')
    end=change.get('scheduled_end',b['scheduled_end'])
    if end<b['scheduled_end']:raise Error(422,'invalid_window')
    candidate={**r,**validated.model_dump(exclude={'pet_ids','checklist_items'})}
    if end!=b['scheduled_end'] or candidate['window_end']!=r['window_end'] or x['resume_status'] in ['reserved','in_service']:
        eligible(c,candidate,h,b['scheduled_start'],end,b['agreed_fee'],exclude_booking_id=b['id'])
    if b['actual_cost'] is not None and validated.budget<b['actual_cost']:raise Error(422,'invalid_change')
    r=update(c,'ServiceRequest',r['id'],dict(**validated.model_dump(exclude={'pet_ids','checklist_items'}),version=r['version']+1))
    checklist(c,r,validated.checklist_items)
    old_status={i['item_key']:i['execution_status'] for i in old_items}
    for item in c.execute('SELECT * FROM "ChecklistItem" WHERE request_id=%s AND request_version=%s',(r['id'],r['version'])).fetchall():
        status='waived' if item['item_key'] in waived else old_status.get(item['item_key'],'pending')
        if status in ['completed','waived']:
            update(c,'ChecklistItem',item['id'],{'execution_status':status})
        if status=='waived':log(c,r,b,u,'checklist_waived','exception',{'checklist_item_id':str(item['id'])})
    snapshot=demand_view(c,r,u);snapshot.pop('status',None)
    for item in snapshot['checklist_items']:item.pop('execution_status',None)
    b=update(c,'Booking',b['id'],dict(request_version=r['version'],request_snapshot=Jsonb(snapshot),scheduled_end=end,owner_confirmed_at=now(c),helper_confirmed_at=None))
    approved=body.approved_change.model_dump(mode='json',exclude_unset=True)
    approved['resolution']=body.resolution
    x=update(c,'ExceptionRecord',id,{'approved_change':Jsonb(approved)})
    log(c,r,b,u,'exception_change_approved','exception',{'exception_id':str(id)})
    return view(x,r)

def confirm_change(c,r,b,h,u,expected_version):
    version(r,b,expected_version)
    x=c.execute('SELECT * FROM "ExceptionRecord" WHERE booking_id=%s AND status=\'open\' AND deleted_at IS NULL FOR UPDATE',(b['id'],)).fetchone()
    if not x or x['approved_change'] is None or not b['owner_confirmed_at']:raise Error(409,'invalid_state')
    if u['id']!=h['user_id']:raise Error(403,'forbidden')
    if x['resume_status'] in ['reserved','in_service']:
        eligible(c,r,h,b['scheduled_start'],b['scheduled_end'],b['agreed_fee'],exclude_booking_id=b['id'])
    b=update(c,'Booking',b['id'],{'helper_confirmed_at':now(c)})
    log(c,r,b,u,'exception_change_confirmed','exception',{'exception_id':str(x['id'])})
    finish(c,r,b,x,{'id':b['owner_id']},x['approved_change']['resolution'],x['resume_status'])
    return {**clean(one(c,'Booking',b['id'])),'request_status':x['resume_status']}

@router.get('/requests/{id}/events')
def events(id:UUID,limit:int=Query(20,ge=1,le=100),cursor:str|None=None,u=Depends(me),c=Depends(db)):
    r=one(c,'ServiceRequest',id)
    where="request_id=%s AND event_type<>'idempotency_result'";params=[id]
    if r['owner_id']!=u['id']:
        b=c.execute('SELECT b.id FROM "Booking" b JOIN "HelperProfile" h ON h.id=b.helper_id WHERE b.request_id=%s AND h.user_id=%s AND b.deleted_at IS NULL ORDER BY b.created_at DESC LIMIT 1',(id,u['id'])).fetchone()
        if not b:raise Error(403,'forbidden')
        where+=' AND booking_id=%s';params.append(b['id'])
    rows,n=page(c,'TaskEvent',where,params,limit,cursor)
    return {'items':clean(rows),'next_cursor':n}
