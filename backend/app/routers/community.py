import json
from pathlib import Path
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,Query,UploadFile,File
from fastapi.responses import FileResponse,Response
from pydantic import Field
from app.schemas import Model
from app.routers.api import me,db,one,own,insert,clean,update,Error
from app.routers.bookings import locked
from app.config import MEDIA_ROOT
router=APIRouter(prefix='/api/v0')
class Message(Model):
    content:str|None=Field(default=None,max_length=2000)
    client_id:UUID
    kind:str='text'
    media_url:str|None=None
    latitude:float|None=Field(default=None,ge=-90,le=90)
    longitude:float|None=Field(default=None,ge=-180,le=180)
    accuracy_m:float|None=Field(default=None,ge=0,le=100000)
    location_label:str|None=Field(default=None,max_length=200)
class Read(Model):
    through_seq:int=Field(ge=0)
class Review(Model):
    rating:int=Field(ge=1,le=5)
    comment:str=Field(default='',max_length=2000)
class AddressBody(Model):
    label:str=Field(min_length=1,max_length=30)
    contact_name:str=Field(min_length=1,max_length=50)
    contact_phone:str=Field(min_length=3,max_length=30)
    address:str=Field(min_length=2,max_length=300)
    latitude:float|None=Field(default=None,ge=-90,le=90)
    longitude:float|None=Field(default=None,ge=-180,le=180)
    is_default:bool=False
class Signal(Model):
    call_id:UUID
    kind:str
    payload:dict=Field(default_factory=dict)

@router.get('/addresses')
def addresses(u=Depends(me),c=Depends(db)):
    rows=c.execute('SELECT * FROM "Address" WHERE user_id=%s AND deleted_at IS NULL ORDER BY is_default DESC,created_at',(u['id'],)).fetchall()
    return {'items':clean(rows)}

def save_address(c,u,body,id=None):
    data=body.model_dump()
    if data['is_default'] or not c.execute('SELECT 1 FROM "Address" WHERE user_id=%s AND deleted_at IS NULL AND (%s::uuid IS NULL OR id<>%s)',(u['id'],id,id)).fetchone():
        data['is_default']=True
        c.execute('UPDATE "Address" SET is_default=false,updated_at=now() WHERE user_id=%s AND deleted_at IS NULL',(u['id'],))
    if id:
        row=one(c,'Address',id,True)
        if row['user_id']!=u['id']:raise Error(403,'forbidden')
        return clean(update(c,'Address',id,data))
    return clean(insert(c,'Address',{'user_id':u['id'],**data}))

@router.post('/addresses',status_code=201)
def address_create(body:AddressBody,u=Depends(me),c=Depends(db)):return save_address(c,u,body)

@router.patch('/addresses/{id}')
def address_update(id:UUID,body:AddressBody,u=Depends(me),c=Depends(db)):return save_address(c,u,body,id)

@router.delete('/addresses/{id}',status_code=204)
def address_delete(id:UUID,u=Depends(me),c=Depends(db)):
    row=one(c,'Address',id,True)
    if row['user_id']!=u['id']:raise Error(403,'forbidden')
    update(c,'Address',id,{'deleted_at':c.execute('SELECT now() AS n').fetchone()['n'],'is_default':False})
    if row['is_default']:
        replacement=c.execute('SELECT id FROM "Address" WHERE user_id=%s AND deleted_at IS NULL ORDER BY created_at LIMIT 1',(u['id'],)).fetchone()
        if replacement:update(c,'Address',replacement['id'],{'is_default':True})
    return Response(status_code=204)

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
    if body.kind not in ['text','audio','location']:raise Error(422,'validation_error')
    if body.kind=='text' and not (body.content or '').strip():raise Error(422,'validation_error')
    if body.kind=='audio':
        prefix=f'/api/v0/bookings/{id}/chat-media/'
        if not body.media_url or not body.media_url.startswith(prefix) or '..' in body.media_url:raise Error(422,'invalid_media')
        filename=body.media_url.removeprefix(prefix)
        if not (MEDIA_ROOT/'chat'/str(id)/filename).is_file():raise Error(422,'invalid_media')
    if body.kind=='location' and (body.latitude is None or body.longitude is None):raise Error(422,'validation_error')
    old=c.execute('SELECT * FROM "ChatMessage" WHERE sender_id=%s AND client_id=%s',(u['id'],body.client_id)).fetchone()
    if old:
        if old['booking_id']!=id or old['kind']!=body.kind:raise Error(409,'idempotency_conflict')
        return clean(old)
    data=body.model_dump();data['content']=(data['content'] or '').strip() or None
    return clean(insert(c,'ChatMessage',dict(booking_id=id,sender_id=u['id'],**data)))

@router.post('/bookings/{id}/chat-media',status_code=201)
def chat_media_upload(id:UUID,file:UploadFile=File(...),u=Depends(me),c=Depends(db)):
    locked(c,id,u)
    allowed={'audio/webm':'.webm','audio/ogg':'.ogg','audio/mp4':'.m4a','audio/mpeg':'.mp3','audio/wav':'.wav'}
    content_type=(file.content_type or '').split(';',1)[0]
    if content_type not in allowed:raise Error(422,'invalid_media','仅支持 WebM、Ogg、M4A、MP3 或 WAV 语音。')
    data=file.file.read(10*1024*1024+1)
    if not data or len(data)>10*1024*1024:raise Error(413,'file_too_large','语音不能超过 10MB。')
    name=str(uuid4())+allowed[content_type]
    path=MEDIA_ROOT/'chat'/str(id)/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return {'url':f'/api/v0/bookings/{id}/chat-media/{name}'}

@router.get('/bookings/{id}/chat-media/{name}')
def chat_media(id:UUID,name:str,u=Depends(me),c=Depends(db)):
    locked(c,id,u)
    if Path(name).name!=name:raise Error(404,'not_found')
    path=MEDIA_ROOT/'chat'/str(id)/name
    if not path.is_file():raise Error(404,'not_found')
    media={'.webm':'audio/webm','.ogg':'audio/ogg','.m4a':'audio/mp4','.mp3':'audio/mpeg','.wav':'audio/wav'}.get(path.suffix.lower(),'application/octet-stream')
    return FileResponse(path,media_type=media)

@router.get('/bookings/{id}/signals')
def signals(id:UUID,after:int=Query(0,ge=0),call_id:UUID|None=None,u=Depends(me),c=Depends(db)):
    locked(c,id,u)
    rows=c.execute('SELECT * FROM "CallSignal" WHERE booking_id=%s AND seq>%s AND sender_id<>%s AND created_at>now()-interval \'2 minutes\' AND (%s::uuid IS NULL OR call_id=%s) ORDER BY seq LIMIT 200',(id,after,u['id'],call_id,call_id)).fetchall()
    return {'items':clean(rows)}

@router.post('/bookings/{id}/signals',status_code=201)
def signal(id:UUID,body:Signal,u=Depends(me),c=Depends(db)):
    locked(c,id,u)
    if body.kind not in ['offer','answer','ice','hangup'] or len(json.dumps(body.payload))>30000:raise Error(422,'validation_error')
    return clean(insert(c,'CallSignal',dict(booking_id=id,sender_id=u['id'],**body.model_dump())))

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
