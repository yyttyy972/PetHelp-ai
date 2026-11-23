from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from app.db import connection
from psycopg.rows import dict_row


def check_timeouts():
    print(f"[{datetime.now()}] [Info] 开始执行服务超时检查...")

    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            now_utc = datetime.now(timezone.utc)

            # 严格获取 in_service 且 scheduled_end < 当前时间的订单
            cur.execute('''
                SELECT 
                    b.id as booking_id, b.request_id, b.status as booking_status, b.scheduled_end,
                    r.id as req_id, r.version as req_version,
                    h.id as helper_id
                FROM "Booking" b
                JOIN "ServiceRequest" r ON b.request_id = r.id
                JOIN "HelperProfile" h ON b.helper_id = h.id
                WHERE b.status = 'in_service' 
                  AND b.scheduled_end < %s
                FOR UPDATE OF r, h, b
            ''', (now_utc,))
            timeout_bookings = cur.fetchall()

            for row in timeout_bookings:
                try:
                    print(f"  -> [Info] 发现真实超时订单: {row['booking_id']}，准备上报异常...")

                    # 1. 插入 ExceptionRecord 异常记录
                    cur.execute('''
                        INSERT INTO "ExceptionRecord" 
                        (booking_id, reported_by, reason_code, description, resume_status, status)
                        VALUES (%s, NULL, 'service_timeout', '帮手超时未提交核验', 'in_service', 'open')
                        RETURNING id
                    ''', (row['booking_id'],))
                    exception_id = cur.fetchone()['id']

                    # 2. 修改预约状态为 exception
                    cur.execute('''
                        UPDATE "Booking" SET status = 'exception' WHERE id = %s
                    ''', (row['booking_id'],))

                    # 3. 修改需求状态为 exception
                    cur.execute('''
                        UPDATE "ServiceRequest" SET status = 'exception' WHERE id = %s
                    ''', (row['request_id'],))

                    # 4. 插入异常提醒事件 (exception_reminder) 到 TaskEvent
                    cur.execute('''
                        INSERT INTO "TaskEvent" 
                        (request_id, booking_id, actor_id, event_type, from_status, to_status, request_version, payload, operation)
                        VALUES (%s, %s, NULL, 'exception_reminder', 'in_service', 'exception', %s, %s, 'timeout_reminder')
                    ''', (row['request_id'], row['booking_id'], row['req_version'],
                          '{"exception_id": "' + str(exception_id) + '", "reason_code": "service_timeout"}'))

                    print(f"  -> [Info] 成功拦截并记录异常: {row['booking_id']}")
                except Exception as e:
                    print(f"  -> [Error] 上报异常失败: {e}")

            conn.commit()
    print(f"[{datetime.now()}] [Info] 定时检查执行完毕。")


scheduler = BackgroundScheduler()


def start_scheduler():
    scheduler.add_job(check_timeouts, 'interval', minutes=1)
    scheduler.start()
    print("[Info] 定时任务调度器已启动，每 1 分钟检查一次。")
