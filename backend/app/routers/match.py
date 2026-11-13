from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import uuid
from datetime import datetime

# ⚠️ 这里根据 B 组的实际情况导入数据库 session 
# 一般在 db.py 或 dependencies.py 里，函数名可能是 get_db 或 get_session
from ..db import get_db 

router = APIRouter()

@router.post("/requests/{request_id}/match")
def match_helpers(request_id: uuid.UUID, db: Session = Depends(get_db)):
    # 1. 查需求
    req_row = db.execute(
        text('SELECT * FROM "ServiceRequest" WHERE id = :id'), 
        {"id": request_id}
    ).fetchone()
    
    if not req_row:
        raise HTTPException(status_code=404, detail="需求不存在")
    
    req = dict(req_row._mapping)
    
    # 2. 查该需求关联的宠物（支持多宠物，查 RequestPet 表）
    pets_rows = db.execute(
        text('''
            SELECT p.* FROM "PetProfile" p
            JOIN "RequestPet" rp ON p.id = rp.pet_id
            WHERE rp.request_id = :req_id
        '''), 
        {"req_id": request_id}
    ).fetchall()
    req_pet_species = [dict(p._mapping)['species'] for p in pets_rows]

    # 3. 查所有帮手档案及对应账号信息
    helpers_rows = db.execute(
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
        
        # --- 开始硬性过滤 ---

        # 规则 1：服务类型匹配 (PostgreSQL 数组转 Python list)
        if req['service_type'] not in h['service_types']:
            continue
            
        # 规则 2：宠物种类匹配
        # 检查需求的宠物是否都在帮手支持的范围内
        if not all(species in h['supported_species'] for species in req_pet_species):
            continue
            
        # 规则 3：费用匹配
        if req['fee_type'] == 'free' and h['fee_pref'] not in ['free', 'both']:
            continue
        if req['fee_type'] == 'paid' and h['fee_pref'] not in ['paid', 'both']:
            continue

        # 规则 4：时间包含 (查 Availability)
        # 逻辑：帮手必须有一条可用时间，完全覆盖需求的时间窗口
        avail_row = db.execute(
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
            continue # 没空，跳过

        # 规则 5：时间冲突 (查 Booking)
        # 逻辑：不能跟该帮手已有的且未取消/未完成的预约时间重叠
        # 占用状态：pending_confirm, reserved, in_service, pending_verify, exception
        conflict_row = db.execute(
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
            continue # 时间冲突，跳过

        # --- 过滤结束，活下来的就是候选人 ---
        
        reasons = []
        if h['verification_status'] == 'verified':
            reasons.append("信用良好")
            
        # 简单判断一下是不是同小区/同栋（这里用 address_tag 和 location 简单对比，不接地图API）
        # B 的测试数据里 location 是 "1栋门厅交接"，address_tag 是 "1栋"
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
            "reasons": reasons if reasons else ["符合基础要求"]
        })

    # 4. 排序（信用良好的排前面）
    candidates.sort(key=lambda x: x['verification_status'] == 'verified', reverse=True)

    # 5. 返回
    return {
        "request_id": str(request_id),
        "version": req['version'],
        "candidates": candidates
    }
