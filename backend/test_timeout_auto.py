import sys
import os
import traceback

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import connection
from app.cron_tasks import check_timeouts


def run_test():
    print("--- 开始自动化测试 ---")
    req_id = '99999999-9999-9999-9999-999999999999'
    b_id = '88888888-8888-8888-8888-888888888888'

    try:
        # 1. 造测试数据
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM "TaskEvent" WHERE request_id = %s', (req_id,))
                cur.execute('DELETE FROM "ExceptionRecord" WHERE booking_id = %s', (b_id,))
                cur.execute('DELETE FROM "Booking" WHERE id = %s', (b_id,))
                cur.execute('DELETE FROM "ServiceRequest" WHERE id = %s', (req_id,))

                cur.execute('''
                    INSERT INTO "ServiceRequest" (id, owner_id, service_type, community_code, window_start, window_end, expected_duration_minutes, location, budget, fee_type, handover_notes, emergency_contact, status, version)
                    VALUES (%s, '00000000-0000-4000-8000-000000000001', 'home_visit', 'linchong-001', NOW() - INTERVAL '3 hours', NOW() - INTERVAL '1 hour', 60, '1栋', 30, 'paid', 'test', '123', 'in_service', 1)
                ''', (req_id,))

                cur.execute('''
                    INSERT INTO "Booking" (id, request_id, owner_id, helper_id, request_version, request_snapshot, scheduled_start, scheduled_end, reserved_until, status, agreed_fee)
                    VALUES (%s, %s, '00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000012', 1, '{}'::jsonb, NOW() - INTERVAL '3 hours', NOW() - INTERVAL '1 hour', NOW() - INTERVAL '3 hours', 'in_service', 30.00)
                ''', (b_id, req_id))
                conn.commit()

        # 2. 调用定时任务
        check_timeouts()

        # 3. 验证数据
        with connection() as conn:
            with conn.cursor() as cur:
                # 修复取值方式
                cur.execute('SELECT COUNT(*) AS cnt FROM "ExceptionRecord" WHERE booking_id = %s', (b_id,))
                exception_count = cur.fetchone()['cnt']

                cur.execute(
                    'SELECT COUNT(*) AS cnt FROM "TaskEvent" WHERE request_id = %s AND event_type = \'exception_reminder\'',
                    (req_id,))
                event_count = cur.fetchone()['cnt']

                assert exception_count == 1, f"ExceptionRecord 数量错误，期望 1，实际 {exception_count}"
                assert event_count == 1, f"exception_reminder 数量错误，期望 1，实际 {event_count}"
                print("[Pass] 异常记录与提醒事件生成验证通过！")

                # 4. 幂等测试（重复扫描）
                check_timeouts()

                cur.execute('SELECT COUNT(*) AS cnt FROM "ExceptionRecord" WHERE booking_id = %s', (b_id,))
                exception_count_2 = cur.fetchone()['cnt']

                cur.execute(
                    'SELECT COUNT(*) AS cnt FROM "TaskEvent" WHERE request_id = %s AND event_type = \'exception_reminder\'',
                    (req_id,))
                event_count_2 = cur.fetchone()['cnt']

                assert exception_count_2 == 1, f"幂等测试失败，ExceptionRecord 变为了 {exception_count_2}"
                assert event_count_2 == 1, f"幂等测试失败，exception_reminder 变为了 {event_count_2}"
                print("[Pass] 幂等测试通过！")
                print("--- 所有测试全部通过 ---")

    except Exception as e:
        print("[Fail] 测试失败：")
        traceback.print_exc()
        sys.exit(1)  # 失败时返回非 0 退出码


if __name__ == "__main__":
    run_test()
