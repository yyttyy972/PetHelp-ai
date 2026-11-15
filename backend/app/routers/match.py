from fastapi import APIRouter, HTTPException, Header
from psycopg.rows import dict_row
from uuid import UUID
import json

# 导入 B 组的数据库连接
from app.db import connection
# 导入 B 组的鉴权逻辑（假设 token 方法在 security 里）
from app.core.security import verify_token 

router = APIRouter()

@router.post("/requests/{request_id}/match")
def match_helpers(request_id: UUID, authorization: str = Header(None)):
    # 1. 登录鉴权 (拦截未登录)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.split(" ")[1]
    user_info = verify_token(token) # 假设 B 组写了这个函数，返回包含 user_id 和 community_code 的字典
    if not user_info:
         raise HTTPException(status_code=401, detail="Token无效")
    req_community = user_info.get('community_code')

    # 使用 B 组的 psycopg 连接
    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 2. 查需求并进行状态、版本校验
            cur.execute('SELECT * FROM "ServiceRequest" WHERE id = %s', (request_id,))
            req = cur.fetchone()
            
            if not req:
                raise HTTPException(status_code=404, detail="需求不存在")
            if req['status'] != 'pending_match':
                raise HTTPException(status_code=409, detail="需求状态不是待匹配状态")
            
            # （关于 expected_version 校验，如果没有通过入参传，这里默认跳过，如需入参请在函数头加 expected_version: int）
            
            # 3. 社区过滤（确保需求方社区和当前操作者社区一致）
            if req['community_code'] != req_community:
                raise HTTPException(status_code=403, detail="无权操作其他社区的需求")

            # 4. 查出需求关联的宠物
            cur.execute('''
                SELECT p.species FROM "PetProfile" p
                JOIN "RequestPet" rp ON p.id = rp.pet_id
                WHERE rp.request_id = %s
            ''', (request_id,))
            req_pet_species = [row['species'] for row in cur.fetchall()]

            # 5. 查出所有同社区的帮手（带出 User 的 display_name 和 address）
            cur.execute('''
                SELECT h.*, u.display_name, u.avatar_url, u.address 
                FROM "HelperProfile" h
                JOIN "User" u ON h.user_id = u.id
                WHERE h.deleted_at IS NULL AND u.community_code = %s
            ''', (req_community,))
            helpers = cur.fetchall()

            candidates = []

            for h in helpers:
                # --- 硬性过滤 ---
                # 服务类型
                if req['service_type'] not in h['service_types']:
                    continue
                # 宠物种类
                if not all(species in h['supported_species'] for species in req_pet_species):
                    continue
                # 费用偏好
                if req['fee_type'] == 'free' and h['fee_pref'] not in ['free', 'both']:
                    continue
                if req['fee_type'] == 'paid' and h['fee_pref'] not in ['paid', 'both']:
                    continue

                # 时间包含 (Availability)
                cur.execute('''
                    SELECT 1 FROM "Availability"
                    WHERE helper_id = %s AND start_at <= %s AND end_at >= %s LIMIT 1
                ''', (h['id'], req['window_start'], req['window_end']))
                if not cur.fetchone():
                    continue 

                # 时间冲突 (Booking)
                cur.execute('''
                    SELECT 1 FROM "Booking"
                    WHERE helper_id = %s AND status NOT IN ('completed', 'cancelled')
                      AND scheduled_start < %s AND scheduled_end > %s LIMIT 1
                ''', (h['id'], req['window_end'], req['window_start']))
                if cur.fetchone():
                    continue 

                # --- 加入候选人并生成打分依据 ---
                score = 0
                reasons = []

                # 评分点 1：信用度
                if h['verification_status'] == 'verified':
                    score += 100
                    reasons.append("信用良好")
                # 评分点 2：费用偏好精确匹配
                if h['fee_pref'] == req['fee_type']:
                    score += 50
                    reasons.append("费用偏好完美匹配")
                # 评分点 3：同栋
                if h.get('address_tag') and h.get('address_tag') in req.get('location', ''):
                    score += 30
                    reasons.append("同栋优先")
                # 评分点 4：经验
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
                    "_score": score # 隐藏字段用于排序
                })

            # 按分数降序排序
            candidates.sort(key=lambda x: x['_score'], reverse=True)

            # 移除内部的 _score 字段，返回给前端
            for c in candidates:
                del c['_score']

            return {
                "request_id": str(request_id),
                "version": req['version'],
                "candidates": candidates
            }
