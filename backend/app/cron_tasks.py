from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from app.db import connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def check_timeouts():
    print(f"[{datetime.now()}] [Info] 开始执行服务超时检查...")

    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            now_utc = datetime.now(timezone.utc)

            # 只找处于 in_service 且超时的订单
            cur.execute('''
                SELECT b.id, b.request_id, b.helper_id 
                FROM "Booking" b
                WHERE b.status = 'in_service' 
                  AND b.scheduled_end <= %s
                FOR UPDATE OF b
            ''', (now_utc,))
            timeouts = cur.fetchall()

            for b in timeouts:
                try:
                    print(f"  -> [Info] 发现超时订单: {b['id']}，执行状态变更...")
                    # 直接修改预约状态为异常
                    cur.execute('''
                        UPDATE "Booking" SET status = 'exception' WHERE id = %s
                    ''', (b['id'],))
                    # 修改需求状态为异常
                    cur.execute('''
                        UPDATE "ServiceRequest" SET status = 'exception' WHERE id = %s
                    ''', (b['request_id'],))

                    # 插入异常记录
                    cur.execute('''
                        INSERT INTO "ExceptionRecord" 
                        (booking_id, reason_code, description, resume_status, status)
                        VALUES (%s, 'service_timeout', '帮手超时未提交核验', 'in_service', 'open')
                    ''', (b['id'],))

                    print(f"  -> [Info] 成功拦截并记录异常: {b['id']}")
                except Exception as e:
                    print(f"  -> [Error] 处理失败: {e}")

            conn.commit()
    print(f"[{datetime.now()}] [Info] 定时检查执行完毕。")


scheduler = BackgroundScheduler()


def start_scheduler():
    scheduler.add_job(check_timeouts, 'interval', minutes=1)
    scheduler.start()
    print("[Info] 定时任务调度器已启动，每 1 分钟检查一次。")
