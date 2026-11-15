from fastapi import APIRouter, HTTPException, Header
from psycopg.rows import dict_row
from uuid import UUID
import jwt
from app.db import connection
from app.config import JWT_SECRET

router = APIRouter()

@router.post("/requests/{request_id}/match")
def match_helpers(request_id: UUID, authorization: str = Header(None)):
    # 1. 登录鉴权 (自己解码 JWT)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证Token")
    
    token_str = authorization.split(" ")[1]
    try:
        # 使用 B 组 config 里的密钥进行解码
        payload = jwt.decode(token_str, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub") # 获取当前登录用户的ID
    except Exception as e:
        raise HTTPException(status_code=401, detail="Token无效或已过期")

    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            
            # 2. 查当前用户，获取他的 community_code (用于社区过滤)
            cur.execute('SELECT community_code FROM "User" WHERE id = %s', (user_id,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=401, detail="用户不存在")
            user_community = user['community_code']

            # 3. 查需求并校验状态
            cur.execute('SELECT * FROM "ServiceRequest" WHERE id = %s', (request_id,))
            req = cur.fetchone()
            
            if not req:
                raise HTTPException(status_code=404, detail="需求不存在")
            if req['status'] != 'pending_match':
                raise HTTPException(status_code=409, detail="需求不在待匹配状态")
            
            # 4. 社区过滤校验
            if req['community_code'] != user_community:
                raise HTTPException(status_code=403, detail="无权匹配其他社区的需求")

            # 5. 查出需求关联的宠物
            cur.execute('''
                SELECT p.species FROM "PetProfile" p
                JOIN "RequestPet" rp ON p.id = rp.pet_id
                WHERE rp.request_id = %s
            ''', (request_id,))
            req_pet_species = [row['species'] for row in cur.fetchall()]

            # 6. 查出所有符合条件的帮手
            cur.execute('''
                SELECT h.*, u.display_name, u.avatar_url 
                FROM "HelperProfile" h
                JOIN "User" u ON h.user_id = u.id
                WHERE h.deleted_at IS NULL AND u.community_code = %s
            ''', (user_community,))
            helpers = cur.fetchall()

            candidates = []

            for h in helpers:
                # --- 硬性过滤 ---
                if req['service_type'] not in h['service_types']: continue
                if not all(species in h['supported_species'] for species in req_pet_species): continue
                if req['fee_type'] == 'free' and h['fee_pref'] not in ['free', 'both']: continue
                if req['fee_type'] == 'paid' and h['fee_pref'] not in ['paid', 'both']: continue

                # 时间包含
                cur.execute('''
                    SELECT 1 FROM "Availability"
                    WHERE helper_id = %s AND start_at <= %s AND end_at >= %s LIMIT 1
                ''', (h['id'], req['window_start'], req['window_end']))
                if not cur.fetchone(): continue 

                # 时间冲突
                cur.execute('''
                    SELECT 1 FROM "Booking"
                    WHERE helper_id = %s AND status NOT IN ('completed', 'cancelled')
                      AND scheduled_start < %s AND scheduled_end > %s LIMIT 1
                ''', (h['id'], req['window_end'], req['window_start']))
                if cur.fetchone(): continue 

                # --- 评分与排序 ---
                score = 0
                reasons = []

                if h['verification_status'] == 'verified':
                    score += 100
                    reasons.append("信用良好")
                if h['fee_pref'] == req['fee_type']:
                    score += 50
                    reasons.append("费用偏好完美匹配")
                if h.get('address_tag') and h.get('address_tag') in req.get('location', ''):
                    score += 30
                    reasons.append("同栋优先")
                if h.get('experience'):
                    score += len(h['experience']) // 10 
                    reasons.append("经验丰富")

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
