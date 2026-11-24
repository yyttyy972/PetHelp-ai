"""Applications reserve nothing until the owner accepts via the booking workflow."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import Field
from app.schemas import Publish
from app.routers.api import db, me, one, own, role, helper, insert, update, clean, page, Error
from app.routers.bookings import BookingInput, create as create_booking, eligible, result

router = APIRouter(prefix='/api/v0')

class ApplicationInput(BookingInput):
    # Identity comes from the authenticated account, never from client-supplied helper_id.
    helper_id: UUID | None = None
    note: str = Field(default='', max_length=2000)

def view(c, application, request=None):
    request = request or one(c, 'ServiceRequest', application['request_id'])
    h = one(c, 'HelperProfile', application['helper_id'])
    u = one(c, 'User', h['user_id'])
    data = clean(application)
    data.update(display_name=u['display_name'], request_status=request['status'],
                current_version=request['version'], service_type=request['service_type'])
    data['actionable'] = (application['status']=='pending'
                          and request['status']=='pending_match'
                          and application['request_version']==request['version'])
    return data

def application_locked(c, id):
    ref = one(c, 'TaskApplication', id)
    request = one(c, 'ServiceRequest', ref['request_id'], True)
    h = one(c, 'HelperProfile', ref['helper_id'], True)
    application = one(c, 'TaskApplication', id, True)
    return request, h, application

@router.post('/requests/{id}/applications', status_code=201)
def apply(id:UUID, body:ApplicationInput, u=Depends(me), c=Depends(db)):
    role(u, 'helper')
    r = one(c, 'ServiceRequest', id, True)
    h = helper(c, u, True)
    if body.helper_id is not None and body.helper_id != h['id']:
        raise Error(403, 'forbidden')
    if r['version'] != body.expected_version: raise Error(409, 'version_conflict')
    if r['status'] != 'pending_match': raise Error(409, 'invalid_state')
    eligible(c, r, h, body.scheduled_start, body.scheduled_end, body.agreed_fee)
    old = c.execute('''SELECT * FROM "TaskApplication" WHERE request_id=%s
        AND helper_id=%s AND request_version=%s AND status='pending' AND deleted_at IS NULL''',
        (id, h['id'], r['version'])).fetchone()
    if old:
        if any(old[k]!=getattr(body,k) for k in ['note','scheduled_start','scheduled_end','agreed_fee']):
            raise Error(409, 'application_exists', '已有待处理申请；修改方案请先撤回。')
        return view(c, old, r)
    a = insert(c, 'TaskApplication', dict(request_id=id, helper_id=h['id'],
        request_version=r['version'], note=body.note, scheduled_start=body.scheduled_start,
        scheduled_end=body.scheduled_end, agreed_fee=body.agreed_fee))
    return view(c, a, r)

@router.get('/requests/{id}/applications')
def for_request(id:UUID, limit:int=Query(20,ge=1,le=100), cursor:str|None=None,
                u=Depends(me), c=Depends(db)):
    r=one(c,'ServiceRequest',id); own(r,u)
    rows, nxt=page(c,'TaskApplication','request_id=%s',[id],limit,cursor)
    return {'items':[view(c,a,r) for a in rows], 'next_cursor':nxt}

@router.get('/applications')
def mine(limit:int=Query(20,ge=1,le=100), cursor:str|None=None, u=Depends(me),c=Depends(db)):
    role(u,'helper')
    rows,nxt=page(c,'TaskApplication',
        'helper_id IN (SELECT id FROM "HelperProfile" WHERE user_id=%s)',[u['id']],limit,cursor)
    return {'items':[view(c,a) for a in rows], 'next_cursor':nxt}

@router.post('/applications/{id}/accept')
def accept(id:UUID,body:Publish,u=Depends(me),c=Depends(db)):
    r,h,a=application_locked(c,id); own(r,u)
    if a['status']=='accepted': return result(r,one(c,'Booking',a['booking_id']))
    if a['status']!='pending': raise Error(409,'invalid_state')
    if r['version']!=body.expected_version or a['request_version']!=r['version']:
        raise Error(409,'version_conflict')
    booking=create_booking(r['id'],BookingInput(expected_version=body.expected_version,
        helper_id=h['id'],scheduled_start=a['scheduled_start'],scheduled_end=a['scheduled_end'],
        agreed_fee=a['agreed_fee']),u,c)
    update(c,'TaskApplication',id,{'status':'accepted','booking_id':UUID(booking['id'])})
    c.execute('''UPDATE "TaskApplication" SET status='rejected',updated_at=now()
        WHERE request_id=%s AND id<>%s AND status='pending' AND deleted_at IS NULL''',(r['id'],id))
    return booking

@router.post('/applications/{id}/reject')
def reject(id:UUID,u=Depends(me),c=Depends(db)):
    r,h,a=application_locked(c,id);own(r,u)
    if a['status']=='rejected':return view(c,a,r)
    if a['status']!='pending':raise Error(409,'invalid_state')
    return view(c,update(c,'TaskApplication',id,{'status':'rejected'}),r)

@router.post('/applications/{id}/withdraw')
def withdraw(id:UUID,u=Depends(me),c=Depends(db)):
    r,h,a=application_locked(c,id);own(h,u,'user_id')
    if a['status']=='withdrawn':return view(c,a,r)
    if a['status']!='pending':raise Error(409,'invalid_state')
    return view(c,update(c,'TaskApplication',id,{'status':'withdrawn'}),r)
