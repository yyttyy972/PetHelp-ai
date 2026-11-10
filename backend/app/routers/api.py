import json, io, hashlib
from uuid import UUID, uuid4
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, UploadFile, File, Form, Query
from fastapi.responses import Response, FileResponse
from psycopg import sql
from psycopg.types.json import Jsonb
import jwt
from PIL import Image, UnidentifiedImageError
from app import schemas as S
from app.db import connection
from app.config import COMMUNITY, JWT_SECRET, MEDIA_ROOT
from app.core.security import hash_password, verify_password, token

router=APIRouter(prefix="/api/v0")
class Error(Exception):
    def __init__(self,status,code,message=None): self.status=status; self.code=code; self.message=message or code

def clean(x):
    if isinstance(x,dict): return {k:clean(v) for k,v in x.items() if k not in {"deleted_at","password_hash"}}
    if isinstance(x,(list,tuple)): return [clean(v) for v in x]
    if isinstance(x,Decimal): return format(x,".2f")
    if isinstance(x,datetime): return x.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    if isinstance(x,UUID): return str(x)
    if hasattr(x,"isoformat"): return x.isoformat()
    return x

def db(request:Request):
    yield request.state.db

def one(c,t,id,lock=False):
    row=c.execute(sql.SQL('SELECT * FROM {} WHERE id=%s AND deleted_at IS NULL'+(' FOR UPDATE' if lock else '')).format(sql.Identifier(t)),(id,)).fetchone()
    if not row: raise Error(404,"not_found")
    return row

def insert(c,t,data):
    data={k:(Jsonb(v) if isinstance(v,dict) else v) for k,v in data.items()}
    return c.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING *').format(sql.Identifier(t),sql.SQL(',').join(map(sql.Identifier,data)),sql.SQL(',').join(sql.SQL('%s::'+{'roles':'role_type[]','service_types':'service_type[]','supported_species':'pet_species[]'}[k]) if k in {'roles','service_types','supported_species'} else sql.Placeholder() for k in data)),list(data.values())).fetchone()

def update(c,t,id,data):
    data={**data,"updated_at":datetime.now(timezone.utc)}
    return c.execute(sql.SQL('UPDATE {} SET {} WHERE id=%s RETURNING *').format(sql.Identifier(t),sql.SQL(',').join(sql.SQL('{}=%s'+('::'+{'roles':'role_type[]','service_types':'service_type[]','supported_species':'pet_species[]'}[k] if k in {'roles','service_types','supported_species'} else '')).format(sql.Identifier(k)) for k in data)),[*data.values(),id]).fetchone()

def me(request:Request,c=Depends(db)):
    try:
        scheme,value=request.headers.get("authorization","").split(" ",1)
        if scheme.lower()!="bearer": raise ValueError()
        id=UUID(jwt.decode(value,JWT_SECRET,algorithms=["HS256"],options={"require":["exp","sub"]})["sub"])
        return one(c,"User",id)
    except (ValueError,jwt.PyJWTError,Error): raise Error(401,"unauthorized")

def own(row,u,field="owner_id"):
    if row[field]!=u['id']: raise Error(403,"forbidden")
def role(u,r):
    if r not in u['roles']: raise Error(403,"forbidden")
def user_view(u): return clean({k:u[k] for k in ['id','display_name','roles','community_code','avatar_url','address','verification_status']})
def media_ref(url,u,purpose):
    if url is None:return
    prefix=f"/api/v0/media/{u['id']}/{purpose}/"
    if not url.startswith(prefix) or '..' in url or not (MEDIA_ROOT/url.removeprefix('/api/v0/media/')).is_file(): raise Error(422,"invalid_media")
def helper(c,u,lock=False):
    h=c.execute('SELECT * FROM "HelperProfile" WHERE user_id=%s AND deleted_at IS NULL'+(' FOR UPDATE' if lock else ''),(u['id'],)).fetchone()
    if not h: raise Error(404,"not_found")
    return h

def page(c,t,where,params,limit,cursor):
    if cursor:
        try:cursor=UUID(cursor)
        except ValueError:raise Error(422,"validation_error")
        where+=' AND id>%s';params=[*params,cursor]
    rows=c.execute(sql.SQL('SELECT * FROM {} WHERE deleted_at IS NULL AND '+where+' ORDER BY id LIMIT %s').format(sql.Identifier(t)),[*params,limit+1]).fetchall()
    return rows[:limit],str(rows[limit-1]['id']) if len(rows)>limit else None

@router.post('/auth/register',status_code=201)
def register(body:S.Register,c=Depends(db)):
    d=body.model_dump();d['account']=d['account'].strip().lower();d['roles']=list(dict.fromkeys(d['roles']))
    if d['avatar_url']:raise Error(422,"invalid_media","Upload avatar after registration")
    d['password_hash']=hash_password(d.pop('password'));d['community_code']=COMMUNITY
    return user_view(insert(c,'User',d))
@router.post('/auth/login')
def login(body:S.Login,c=Depends(db)):
    u=c.execute('SELECT * FROM "User" WHERE account=%s AND deleted_at IS NULL',(body.account.strip().lower(),)).fetchone()
    if not u or not verify_password(body.password,u['password_hash']):raise Error(401,'invalid_credentials')
    return dict(access_token=token(u['id']),token_type='bearer',expires_in=3600)
@router.get('/users/me')
def profile(u=Depends(me)):return user_view(u)
@router.patch('/users/me')
def profile_patch(body:S.UserPatch,u=Depends(me),c=Depends(db)):
    one(c,'User',u['id'],True);d=body.model_dump(exclude_unset=True)
    if any(d.get(k)==None for k in ('display_name','roles') if k in d):raise Error(422,'validation_error')
    if 'roles' in d:
        d['roles']=list(dict.fromkeys(d['roles']))
        if ('owner' not in d['roles'] and c.execute('SELECT 1 FROM "PetProfile" WHERE owner_id=%s AND deleted_at IS NULL',(u['id'],)).fetchone()) or ('helper' not in d['roles'] and c.execute('SELECT 1 FROM "HelperProfile" WHERE user_id=%s AND deleted_at IS NULL',(u['id'],)).fetchone()):raise Error(409,'role_in_use')
    if 'avatar_url' in d:media_ref(d['avatar_url'],u,'avatar')
    return user_view(update(c,'User',u['id'],d))
@router.post('/pets',status_code=201)
def pet_create(body:S.Pet,u=Depends(me),c=Depends(db)):
    role(u,'owner');media_ref(body.photo_url,u,'pet')
    return clean(insert(c,'PetProfile',dict(owner_id=u['id'],**body.model_dump())))
@router.get('/pets')
def pets(limit:int=Query(20,ge=1,le=100),cursor:str|None=None,u=Depends(me),c=Depends(db)):
    rows,n=page(c,'PetProfile','owner_id=%s',[u['id']],limit,cursor);return dict(items=clean(rows),next_cursor=n)
@router.patch('/pets/{id}')
def pet_patch(id:UUID,body:dict,u=Depends(me),c=Depends(db)):
    p=one(c,'PetProfile',id,True);own(p,u)
    if not set(body)<=set(S.Pet.model_fields):raise Error(422,'validation_error')
    data=S.Pet.model_validate({**{k:p[k] for k in S.Pet.model_fields},**body}).model_dump()
    media_ref(data['photo_url'],u,'pet')
    if data['species']!=p['species'] and c.execute('SELECT 1 FROM "RequestPet" rp JOIN "ServiceRequest" r ON r.id=rp.request_id WHERE rp.pet_id=%s AND r.deleted_at IS NULL',(id,)).fetchone():raise Error(409,'resource_in_use')
    return clean(update(c,'PetProfile',id,data))
@router.delete('/pets/{id}',status_code=204)
def pet_delete(id:UUID,u=Depends(me),c=Depends(db)):
    p=one(c,'PetProfile',id,True);own(p,u)
    if c.execute('SELECT 1 FROM "RequestPet" rp JOIN "ServiceRequest" r ON r.id=rp.request_id WHERE rp.pet_id=%s AND r.deleted_at IS NULL',(id,)).fetchone():raise Error(409,'resource_in_use')
    update(c,'PetProfile',id,{'deleted_at':datetime.now(timezone.utc)});return Response(status_code=204)
@router.put('/helpers/me')
def helper_put(body:S.Helper,u=Depends(me),c=Depends(db)):
    role(u,'helper');one(c,'User',u['id'],True)
    if body.verification_status is not None and body.verification_status!=u['verification_status']:raise Error(403,'verification_read_only')
    d=body.model_dump(exclude_unset=True);d['verification_status']=u['verification_status']
    for k in ['service_types','supported_species']:d[k]=list(dict.fromkeys(d[k]))
    if d.get('fee_pref','both') is None:raise Error(422,'validation_error')
    if body.address_tag and any(x in body.address_tag for x in ['室','单元','门牌']):raise Error(422,'invalid_profile')
    old=c.execute('SELECT * FROM "HelperProfile" WHERE user_id=%s AND deleted_at IS NULL FOR UPDATE',(u['id'],)).fetchone()
    return clean(update(c,'HelperProfile',old['id'],d) if old else insert(c,'HelperProfile',dict(user_id=u['id'],**d)))
@router.get('/helpers/{id}')
def helper_get(id:UUID,u=Depends(me),c=Depends(db)):
    h=clean(one(c,'HelperProfile',id));return {k:v for k,v in h.items() if k not in ['created_at','updated_at']}
@router.post('/helpers/me/availability',status_code=201)
def availability(body:S.Window,u=Depends(me),c=Depends(db)):
    h=helper(c,u,True);return clean(insert(c,'Availability',dict(helper_id=h['id'],**body.model_dump())))
@router.get('/helpers/me/availability')
def availability_list(limit:int=Query(20,ge=1,le=100),cursor:str|None=None,u=Depends(me),c=Depends(db)):
    h=helper(c,u);rows,n=page(c,'Availability','helper_id=%s',[h['id']],limit,cursor);return dict(items=clean(rows),next_cursor=n)
@router.delete('/availability/{id}',status_code=204)
@router.delete('/helpers/me/availability/{id}',status_code=204)
def availability_delete(id:UUID,u=Depends(me),c=Depends(db)):
    h=helper(c,u,True);a=one(c,'Availability',id,True)
    if a['helper_id']!=h['id']:raise Error(403,'forbidden')
    if c.execute('SELECT 1 FROM "Booking" WHERE helper_id=%s AND deleted_at IS NULL AND status NOT IN (\'cancelled\',\'completed\') AND scheduled_start<%s AND scheduled_end>%s',(h['id'],a['end_at'],a['start_at'])).fetchone():raise Error(409,'resource_in_use')
    update(c,'Availability',id,{'deleted_at':datetime.now(timezone.utc)});return Response(status_code=204)

PUBLIC='id service_type window_start window_end expected_duration_minutes budget fee_type version status community_code'.split()
def participant(c,r,u):
    return r['owner_id']==u['id'] or bool(c.execute('SELECT 1 FROM "Booking" b JOIN "HelperProfile" h ON h.id=b.helper_id WHERE b.request_id=%s AND h.user_id=%s AND b.deleted_at IS NULL AND b.status NOT IN (\'cancelled\',\'completed\')',(r['id'],u['id'])).fetchone())
def demand_view(c,r,u):
    if not participant(c,r,u):
        if r['status']!='pending_match':raise Error(404,'not_found')
        return clean({k:r[k] for k in PUBLIC})
    d=clean(r)
    d['pets']=clean(c.execute('SELECT p.* FROM "PetProfile" p JOIN "RequestPet" rp ON rp.pet_id=p.id WHERE rp.request_id=%s AND rp.deleted_at IS NULL ORDER BY p.id',(r['id'],)).fetchall())
    d['checklist_items']=clean(c.execute('SELECT * FROM "ChecklistItem" WHERE request_id=%s AND request_version=%s ORDER BY position',(r['id'],r['version'])).fetchall())
    return d

def event(c,r,u,op,old=None):
    insert(c,'TaskEvent',dict(request_id=r['id'],actor_id=u['id'],event_type=op,operation=op,from_status=old,to_status=r['status'],request_version=r['version']))
def check_pets(c,body,u):
    for id in sorted(body.pet_ids):
        p=one(c,'PetProfile',id,True);own(p,u)
        if body.service_type=='dog_walking' and p['species']!='dog':raise Error(422,'invalid_pet')
def checklist(c,r,items):
    for item in items:insert(c,'ChecklistItem',dict(request_id=r['id'],request_version=r['version'],**item.model_dump()))
@router.post('/requests',status_code=201)
def request_create(body:S.Demand,u=Depends(me),c=Depends(db)):
    role(u,'owner');check_pets(c,body,u)
    d=body.model_dump(exclude={'pet_ids','checklist_items'});r=insert(c,'ServiceRequest',dict(owner_id=u['id'],community_code=COMMUNITY,**d))
    for id in body.pet_ids:insert(c,'RequestPet',dict(request_id=r['id'],pet_id=id))
    checklist(c,r,body.checklist_items);event(c,r,u,'created');return demand_view(c,r,u)
@router.get('/requests')
def request_list(scope:str='mine',limit:int=Query(20,ge=1,le=100),cursor:str|None=None,u=Depends(me),c=Depends(db)):
    if scope not in ['mine','open']:raise Error(422,'validation_error')
    where,params=('owner_id=%s',[u['id']]) if scope=='mine' else ("status='pending_match' AND community_code=%s",[u['community_code']])
    rows,n=page(c,'ServiceRequest',where,params,limit,cursor)
    return dict(items=[clean({k:r[k] for k in PUBLIC}) if scope=='open' else demand_view(c,r,u) for r in rows],next_cursor=n)
@router.get('/requests/{id}')
def request_get(id:UUID,u=Depends(me),c=Depends(db)):return demand_view(c,one(c,'ServiceRequest',id),u)
@router.patch('/requests/{id}')
def request_patch(id:UUID,body:dict,u=Depends(me),c=Depends(db)):
    r=one(c,'ServiceRequest',id,True);own(r,u)
    if r['status'] not in ['draft','pending_match']:raise Error(409,'invalid_state')
    if body.get('expected_version')!=r['version']:raise Error(409,'version_conflict')
    allowed=set(S.Demand.model_fields)-{'pet_ids','service_type'}
    if not set(body)<=allowed|{'expected_version'}:raise Error(422,'validation_error')
    old=demand_view(c,r,u)
    data={k:r[k] for k in S.Demand.model_fields if k not in ['pet_ids','checklist_items']}
    data['pet_ids']=[p['id'] for p in old['pets']]
    data['checklist_items']=[{k:i[k] for k in S.Item.model_fields} for i in old['checklist_items']]
    data.update({k:v for k,v in body.items() if k!='expected_version'})
    validated=S.Demand.model_validate(data);check_pets(c,validated,u)
    r=update(c,'ServiceRequest',id,dict(**validated.model_dump(exclude={'pet_ids','checklist_items'}),version=r['version']+1))
    checklist(c,r,validated.checklist_items);event(c,r,u,'version_changed',r['status']);return demand_view(c,r,u)
@router.post('/requests/{id}/publish')
def publish(id:UUID,body:S.Publish,u=Depends(me),c=Depends(db)):
    r=one(c,'ServiceRequest',id,True);own(r,u)
    if r['version']!=body.expected_version:raise Error(409,'version_conflict')
    if r['status']!='draft':raise Error(409,'invalid_state')
    r=update(c,'ServiceRequest',id,{'status':'pending_match'});event(c,r,u,'published','draft');return demand_view(c,r,u)
@router.delete('/requests/{id}',status_code=204)
def request_delete(id:UUID,u=Depends(me),c=Depends(db)):
    r=one(c,'ServiceRequest',id,True);own(r,u)
    if r['status']!='draft':raise Error(409,'invalid_state')
    update(c,'ServiceRequest',id,{'deleted_at':datetime.now(timezone.utc)});event(c,r,u,'draft_deleted','draft');return Response(status_code=204)
@router.post('/ai/parse')
def ai_parse(body:dict,u=Depends(me)):raise Error(503,'ai_unavailable')

@router.post('/media',status_code=201)
def upload(file:UploadFile=File(...),purpose:str=Form(...),u=Depends(me)):
    if purpose not in ['avatar','pet']:raise Error(422,'invalid_media')
    data=file.file.read(5*1024*1024+1)
    if len(data)>5*1024*1024:raise Error(413,'file_too_large')
    try:
        im=Image.open(io.BytesIO(data));fmt=im.format
        if fmt not in ['JPEG','PNG','WEBP'] or im.width*im.height>20000000:raise ValueError()
        if file.content_type!={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}[fmt]:raise ValueError()
        im.verify();im=Image.open(io.BytesIO(data));im.load()
    except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError):raise Error(422,'invalid_media')
    rel=f"{u['id']}/{purpose}/{uuid4()}.png";path=MEDIA_ROOT/rel;path.parent.mkdir(parents=True,exist_ok=True)
    im.save(path,format='PNG')
    return {'url':'/api/v0/media/'+rel}
@router.get('/media/{relative_path:path}')
def media(relative_path:str,request:Request,c=Depends(db)):
    path=(MEDIA_ROOT/relative_path).resolve()
    if not path.is_relative_to(MEDIA_ROOT) or not path.is_file():raise Error(404,'not_found')
    parts=relative_path.split('/')
    if len(parts)!=3 or parts[1] not in ['avatar','pet']:raise Error(404,'not_found')
    url='/api/v0/media/'+relative_path
    if parts[1]=='avatar' and c.execute('SELECT 1 FROM "User" WHERE avatar_url=%s AND deleted_at IS NULL',(url,)).fetchone():return FileResponse(path,media_type='image/png')
    u=me(request,c)
    if str(u['id'])==parts[0]:return FileResponse(path,media_type='image/png')
    rows=c.execute('SELECT r.* FROM "ServiceRequest" r JOIN "RequestPet" rp ON rp.request_id=r.id JOIN "PetProfile" p ON p.id=rp.pet_id WHERE p.photo_url=%s AND r.deleted_at IS NULL',(url,)).fetchall()
    if not any(participant(c,r,u) for r in rows):raise Error(403,'forbidden')
    return FileResponse(path,media_type='image/png')
