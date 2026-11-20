from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from app.db import connection
from psycopg.rows import dict_row
from app.routers.exceptions import report_exception

def check_timeouts():
    print(f"[{datetime.now()}] [Info] 开始执行定时超时检查...")
    
    with connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            now_utc = datetime.now(timezone.utc)
            
            # 按照 B 哥要求的顺序：需求 -> 帮手 -> 预约，进行持锁查询
            cur.execute('''
                SELECT 
                    b.id as booking_id, b.request_id, b.helper_id, b.status as booking_status,
                    r.id as req_id, r.version as req_version,
                    h.id as helper_id, h.user_id as helper_user_id
                FROM "Booking" b
                JOIN "ServiceRequest" r ON b.request_id = r.id
                JOIN "HelperProfile" h ON b.helper_id = h.id
                WHERE b.status = 'reserved' 
                  AND b.scheduled_start + interval '30 minutes' < %s
                FOR UPDATE OF r, h, b
            ''', (now_utc,))
            timeout_bookings = cur.fetchall()
            
            for row in timeout_bookings:
                try:
                    print(f"  -> [Info] 发现超时订单: {row['booking_id']}，准备上报异常...")
                    
                    r_dict = {"id": row['req_id'], "version": row['req_version'], "status": "reserved"}
                    b_dict = {"id": row['booking_id'], "status": row['booking_status']}
                    
                    report_exception(
                        c=cur,
                        r=r_dict,
                        b=b_dict,
                        u=None,
                        reason='service_timeout',
                        description='帮手超时未开始服务'
                    )
                    print(f"  -> [Info] 成功拦截并上报异常: {row['booking_id']}")
                except Exception as e:
                    print(f"  -> [Error] 上报异常失败 {row['booking_id']}: {e}")
            
            conn.commit()
    print(f"[{datetime.now()}] [Info] 定时检查执行完毕。")

scheduler = BackgroundScheduler()

def start_scheduler():
    scheduler.add_job(check_timeouts, 'interval', minutes=1)
    scheduler.start()
    print("[Info] 定时任务调度器已启动，每 1 分钟检查一次。")
