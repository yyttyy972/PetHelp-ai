from uuid import UUID
from fastapi import APIRouter,Depends,Query
from pydantic import Field
from app.schemas import Model
from app.routers.api import me,db,one,own,insert,clean,Error
from app.routers.bookings import locked
router=APIRouter(prefix='/api/v0')
class Message(Model):
    content:str=Field(min_length=1,max_length=2000)
    client_id:UUID
class Read(Model):
    through_seq:int=Field(ge=0)
class Review(Model):
    rating:int=Field(ge=1,le=5)
    comment:str=Field(default='',max_length=2000)

@router.get('/conversations')
def conversations(limit:int=Query(20,ge=1,le=100),cursor:UUID|None=None,u=Depends(me),c=Depends(db)):
    rows=c.execute('''SELECT b.id,b.status,b.scheduled_start,
      CASE WHEN b.owner_id=%s THEN hu.display_name ELSE ou.display_name END AS display_name,
      (SELECT count(*) FROM "ChatMessage" m WHERE m.booking_id=b.id AND m.sender_id<>%s AND m.read_at IS NULL AND m.deleted_at IS NULL) AS unread
      FROM "Booking" b JOIN "HelperProfile" h ON h.id=b.helper_id
      JOIN "User" hu ON hu.id=h.user_id JOIN "User" ou ON ou.id=b.owner_id
      WHERE b.deleted_at IS NULL AND (b.owner_id=%s OR h.user_id=%s)
      AND (%s::uuid IS NULL OR b.id>%s) ORDER BY b.id LIMIT %s''',
      (u['id'],u['id'],u['id'],u['id'],cursor,cursor,limit+1)).fetchall()
    return {'items':clean(rows[:limit]),'next_cursor':str(rows[limit-1]['id']) if len(rows)>limit else None}

@router.get('/bookings/{id}/messages')
def messages(id:UUID,after:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100),u=Depends(me),c=Depends(db)):
    locked(c,id,u)
    rows=c.execute('SELECT * FROM "ChatMessage" WHERE booking_id=%s AND seq>%s AND deleted_at IS NULL ORDER BY seq LIMIT %s',(id,after,limit+1)).fetchall()
    return {'items':clean(rows[:limit]),'has_more':len(rows)>limit}

@router.post('/bookings/{id}/messages',status_code=201)
def send(id:UUID,body:Message,u=Depends(me),c=Depends(db)):
    locked(c,id,u)
    old=c.execute('SELECT * FROM "ChatMessage" WHERE sender_id=%s AND client_id=%s',(u['id'],body.client_id)).fetchone()
    if old:
        if old['booking_id']!=id or old['content']!=body.content:raise Error(409,'idempotency_conflict')
        return clean(old)
    return clean(insert(c,'ChatMessage',dict(booking_id=id,sender_id=u['id'],**body.model_dump())))

@router.post('/bookings/{id}/messages/read')
def read(id:UUID,body:Read,u=Depends(me),c=Depends(db)):
    locked(c,id,u)
    c.execute('UPDATE "ChatMessage" SET read_at=COALESCE(read_at,now()) WHERE booking_id=%s AND sender_id<>%s AND seq<=%s',(id,u['id'],body.through_seq))
    return {'status':'ok'}

@router.post('/bookings/{id}/review',status_code=201)
def review(id:UUID,body:Review,u=Depends(me),c=Depends(db)):
    r,b,h=locked(c,id,u);own(b,u)
    if b['status']!='completed':raise Error(409,'invalid_state')
    old=c.execute('SELECT * FROM "Review" WHERE booking_id=%s AND reviewer_id=%s',(id,u['id'])).fetchone()
    if old:
        if old['rating']!=body.rating or old['comment']!=body.comment:raise Error(409,'review_exists','此预约已评价，不能重复修改。')
        return clean(old)
    return clean(insert(c,'Review',dict(booking_id=id,reviewer_id=u['id'],reviewee_id=h['user_id'],**body.model_dump())))

@router.get('/helpers/{id}/reviews')
def reviews(id:UUID,limit:int=Query(20,ge=1,le=100),cursor:UUID|None=None,u=Depends(me),c=Depends(db)):
    h=one(c,'HelperProfile',id)
    rows=c.execute('SELECT id,rating,comment,created_at FROM "Review" WHERE reviewee_id=%s AND deleted_at IS NULL AND (%s::uuid IS NULL OR id>%s) ORDER BY id LIMIT %s',(h['user_id'],cursor,cursor,limit+1)).fetchall()
    stats=c.execute('SELECT count(*) AS count,avg(rating) AS average FROM "Review" WHERE reviewee_id=%s AND deleted_at IS NULL',(h['user_id'],)).fetchone()
    return {'items':clean(rows[:limit]),'next_cursor':str(rows[limit-1]['id']) if len(rows)>limit else None,**clean(stats)}
