from fastapi import APIRouter, HTTPException
from sqlalchemy import text
import uuid
from app.db import connection

router = APIRouter()

@router.post("/requests/{request_id}/match")
def match_helpers(request_id: uuid.UUID):
    # 使用 B 组的 connection 获取游标
    with connection() as conn:
        # 1. 查需求
        req_row = conn.execute(
            text('SELECT * FROM "ServiceRequest" WHERE id = :id'), 
            {"id": request_id}
        ).fetchone()
        
        if not req_row:
            raise HTTPException(status_code=404, detail="需求不存在")
        
        req = dict(req_row._mapping)
        
        # 2. 查该需求关联的宠物
        pets_rows = conn.execute(
            text('''
                SELECT p.* FROM "PetProfile" p
                JOIN "RequestPet" rp ON p.id = rp.pet_id
                WHERE rp.request_id = :req_id
            '''), 
            {"req_id": request_id}
        ).fetchall()
        req_pet_species = [dict(p._mapping)['species'] for p in pets_rows]

        # 3. 查所有帮手档案
        helpers_rows = conn.execute(
            text('''
                SELECT h.*, u.display_name, u.avatar_url 
                FROM "HelperProfile" h
                JOIN "User" u ON h.user_id = u.id
                WHERE h.deleted_at IS NULL
            ''')
        ).fetchall()

        candidates = []

        for h_row in helpers_rows:
            h = dict(h_row._mapping)
            
            # 规则 1：服务类型匹配
            if req['service_type'] not in h['service_types']:
                continue
                
            # 规则 2：宠物种类匹配
            if not all(species in h['supported_species'] for species in req_pet_species):
                continue
                
            # 规则 3：费用匹配
            if req['fee_type'] == 'free' and h['fee_pref'] not in ['free', 'both']:
                continue
            if req['fee_type'] == 'paid' and h['fee_pref'] not in ['paid', 'both']:
                continue

            # 规则 4：时间包含
            avail_row = conn.execute(
                text('''
                    SELECT 1 FROM "Availability"
                    WHERE helper_id = :helper_id 
                      AND start_at <= :req_start 
                      AND end_at >= :req_end
                    LIMIT 1
                '''),
                {
                    "helper_id": h['id'], 
                    "req_start": req['window_start'], 
                    "req_end": req['window_end']
                }
            ).fetchone()
            
            if not avail_row:
                continue 

            # 规则 5：时间冲突
            conflict_row = conn.execute(
                text('''
                    SELECT 1 FROM "Booking"
                    WHERE helper_id = :helper_id 
                      AND status NOT IN ('completed', 'cancelled')
                      AND scheduled_start < :req_end 
                      AND scheduled_end > :req_start
                    LIMIT 1
                '''),
                {
                    "helper_id": h['id'], 
                    "req_start": req['window_start'], 
                    "req_end": req['window_end']
                }
            ).fetchone()
            
            if conflict_row:
                continue 

            reasons = ["符合基础要求"]
            if h['verification_status'] == 'verified':
                reasons.append("信用良好")
                
            if h.get('address_tag') and h.get('address_tag') in req.get('location', ''):
                reasons.append("同栋优先")
                
            candidates.append({
                "helper_id": str(h['id']),
                "display_name": h['display_name'],
                "avatar_url": h.get('avatar_url'),
                "verification_status": h['verification_status'],
                "fee_pref": h['fee_pref'],
                "service_radius_m": h['service_radius_m'],
                "address_tag": h.get('address_tag'),
                "reasons": reasons
            })

        candidates.sort(key=lambda x: x['verification_status'] == 'verified', reverse=True)

        return {
            "request_id": str(request_id),
            "version": req['version'],
            "candidates": candidates
        }
