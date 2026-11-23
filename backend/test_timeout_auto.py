import requests
from datetime import datetime, timezone, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import connection
from app.cron_tasks import check_timeouts

def run_test():
    print("--- 开始自动化测试 ---")
    
    # 1. 造一个真实的超时需求与预约
    with connection() as conn:
        with conn.cursor() as cur:
            req_id = '99999999-9999-9999-9999-999999999999'
            b_id = '88888888-8888-8888-8888-888888888888'
            
            # 清理可能残留的测试数据
            cur.execute('DELETE FROM "ExceptionRecord" WHERE booking_id = %s', (b_id,))
            cur.execute('DELETE FROM "TaskEvent" WHERE request_id = %s', (req_id,))
            cur.execute('DELETE FROM "Booking" WHERE id = %s', (b_id,))
            cur.execute('DELETE FROM "ServiceRequest" WHERE id = %s', (req_id,))

            # 插入全新的测试需求
            cur.execute('''
                INSERT INTO "ServiceRequest" (id, owner_id, service_type, community_code, window_start, window_end, expected_duration_minutes, location, budget, fee_type, handover_notes, emergency_contact, status, version)
                VALUES (%s, '00000000-0000-4000-8000-000000000001', 'home_visit', 'linchong-001', NOW(), NOW(), 60, '1栋', 30, 'paid', 'test', '123', 'in_service', 1)
            ''', (req_id,))

            # 插入一个真实的超时预约
            cur.execute('''
                INSERT INTO "Booking" (id, request_id, owner_id, helper_id, request_version, request_snapshot, scheduled_start, scheduled_end, reserved_until, status, agreed_fee)
                VALUES (%s, %s, '00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000012', 1, '{}'::jsonb, NOW() - INTERVAL '3 hours', NOW() - INTERVAL '1 hour', NOW() - INTERVAL '3 hours', 'in_service', 30.00)
            ''', (b_id, req_id))
            conn.commit()

    # 2. 调用定时任务（模拟一次扫描）
    check_timeouts()

    # 3. 验证异常是否入库
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM "ExceptionRecord" WHERE booking_id = %s', (b_id,))
            exception = cur.fetchone()
            if exception:
                print("✅ 验证通过：异常记录已成功生成！")
                print(f"  异常ID: {exception[0]}, 原因: service_timeout")
            else:
                print("❌ 验证失败：没有找到对应的异常记录！")
            
            # 4. 幂等测试：再跑一次定时任务，不应该报错或生成新记录
            print("--- 开始幂等测试 ---")
            check_timeouts()
            
            cur.execute('SELECT COUNT(*) FROM "ExceptionRecord" WHERE booking_id = %s', (b_id,))
            count = cur.fetchone()[0]
            if count == 1:
                print("✅ 幂等测试通过：重复扫描没有产生重复的异常记录！")
            else:
                print(f"❌ 幂等测试失败：产生了 {count} 条异常记录！")

if __name__ == "__main__":
    run_test()
