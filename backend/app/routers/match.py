from uuid import UUID
from fastapi import APIRouter, Depends
from app.schemas import Publish
from app.routers.api import db, me, one, Error

router=APIRouter(prefix='/api/v0')

@router.post('/requests/{request_id}/match')
def match_helpers(request_id: UUID, body: Publish, user=Depends(me), conn=Depends(db)):
    req=one(conn,'ServiceRequest',request_id,True)
    if req['version']!=body.expected_version:raise Error(409,'version_conflict')
    if req['status']!='pending_match':raise Error(409,'invalid_state')
    user_community=user['community_code']
    if req['community_code']!=user_community:raise Error(403,'forbidden')
    cur=conn.cursor()
    # 5. 查出需求关联的宠物
    cur.execute('''
        SELECT p.species FROM "PetProfile" p
        JOIN "RequestPet" rp ON p.id = rp.pet_id
        WHERE rp.request_id = %s AND rp.deleted_at IS NULL AND p.deleted_at IS NULL
    ''', (request_id,))
    req_pet_species = [row['species'] for row in cur.fetchall()]

    # 6. 查出所有符合条件的帮手
    cur.execute('''
        SELECT h.*, u.display_name, u.avatar_url 
        FROM "HelperProfile" h
        JOIN "User" u ON h.user_id = u.id
        WHERE h.deleted_at IS NULL AND u.deleted_at IS NULL AND u.community_code = %s AND u.id <> %s AND 'helper'=ANY(u.roles)
    ''', (user_community, req['owner_id']))
    helpers = cur.fetchall()

    candidates = []

    for h in helpers:
        # --- 硬性过滤 ---
        if req['service_type'] not in h['service_types']: continue
        if not all(species in h['supported_species'] for species in req_pet_species): continue
        if req['fee_type'] == 'free' and h['fee_pref'] not in ['free', 'both']: continue
        if req['fee_type'] == 'paid' and h['fee_pref'] not in ['paid', 'both']: continue

        # D 原有服务/宠物/费用过滤及评分保持不变；时间规则单独修正。
        cur.execute('SELECT start_at,end_at FROM "Availability" WHERE deleted_at IS NULL AND helper_id=%s AND start_at<%s AND end_at>%s',
                    (h['id'],req['window_end'],req['window_start']))
        available=cur.fetchall()
        cur.execute("""SELECT scheduled_start,scheduled_end,status FROM "Booking"
            WHERE deleted_at IS NULL AND helper_id=%s AND status NOT IN ('completed','cancelled')
            AND (status<>'pending_confirm' OR reserved_until>clock_timestamp())""",(h['id'],))
        occupied=cur.fetchall()
        current=conn.execute('SELECT clock_timestamp() AS time').fetchone()['time']
        if any(b['status'] in ['in_service','exception'] and b['scheduled_end']<current for b in occupied):continue
        if not has_slot(req,available,occupied,current):continue

        # --- 评分与排序 ---
        score = 0
        reasons = []

        if h['verification_status'] == 'verified':
            score += 100
            reasons.append("身份已核验")
        if h['fee_pref'] == req['fee_type']:
            score += 50
            reasons.append("费用偏好完美匹配")
        if h.get('address_tag') and h.get('address_tag') in req.get('location', ''):
            score += 30
            reasons.append("同栋优先")
        if h.get('experience'):
            score += len(h['experience']) // 10
            reasons.append("已填写经验自述")

        candidates.append({
            "helper_id": str(h['id']),
            "display_name": h['display_name'],
            "avatar_url": h.get('avatar_url'),
            "verification_status": h['verification_status'],
            "fee_pref": h['fee_pref'],
            "service_radius_m": h['service_radius_m'],
            "address_tag": h.get('address_tag'),
            "reasons": reasons,
            "_score": score
        })

    # 按分数降序排序
    candidates.sort(key=lambda x: x['_score'], reverse=True)

    for c in candidates:
        del c['_score']

    return {
        "request_id": str(request_id),
        "version": req['version'],
        "candidates": candidates
    }


def has_slot(req, available, occupied, current):
    """Each candidate interval stays inside one Availability, matching booking eligibility."""
    duration=req['expected_duration_minutes']*60
    busy=sorted((b['scheduled_start'],b['scheduled_end']) for b in occupied)
    for a in available:
        left=max(req['window_start'],a['start_at'])
        right=min(req['window_end'],a['end_at'])
        for begin,end in busy:
            if end<=left:continue
            if begin>=right:break
            stop=min(begin,right)
            if (stop-left).total_seconds()>=duration and stop>current:return True
            left=max(left,end)
            if left>=right:break
        if (right-left).total_seconds()>=duration and right>current:return True
    return False
