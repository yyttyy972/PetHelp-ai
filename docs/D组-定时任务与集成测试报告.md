<img width="1797" height="445" alt="image" src="https://github.com/user-attachments/assets/0c8418ec-ba07-4313-9aca-15b14bacf731" /># D组 第12周 系统测试报告

## 1. 定时超时检查程序
- **功能说明**：系统后台每隔 1 分钟自动扫描数据库，发现“帮手预约超时未开始”的订单，自动将其状态改为取消，并释放相应需求。
- **代码文件**：`backend/app/cron_tasks.py`
- **验证过程**：在数据库中手动插入一条超时的预约记录（`scheduled_start` 设为 2 小时前，状态为 `reserved`）。
- **验证结果**：程序随主服务启动，持续稳定运行。定时任务成功捕获该异常订单，打印出拦截日志，证明后台自动巡检逻辑正常生效。

### 运行日志截图
*(第一张图：程序启动与定时任务稳定运行)*
<img width="865" height="314" alt="image" src="https://github.com/user-attachments/assets/e32c7391-dbc3-4fa1-a91a-5d675cd5a436" />

*(第二张图：成功拦截超时订单)*
<img width="428" height="148" alt="image" src="https://github.com/user-attachments/assets/32553772-6e69-481c-bf8b-43679d08d6fe" />


## 2. 对接 B 组异常处理模块（PR #7）
- **对接说明**：已按照 B 组要求，将 `cron_tasks.py` 的定时扫描逻辑与 `report_exception` 事务函数对接。扫描时会按规范持锁（需求→帮手→预约），触发系统异常上报（`u=None`），并生成提醒事件。
- **验证结果**：重新构造超时测试数据后，定时任务成功捕获并调用了异常上报函数，系统状态流转正常。
<img width="988" height="211" alt="image" src="https://github.com/user-attachments/assets/9573579d-6970-4af2-a2a5-dcb0ec4d0e63" />


## 3. 对接 B 组异常处理模块最终验证
- **对接说明**：已将 `cron_tasks.py` 的定时扫描逻辑严格修改为 `in_service` 且 `scheduled_end <= 当前时间`，并在调用 B 组 `report_exception` 时传入了完整的 Booking 数据。
- **验证结果**：定时任务成功捕获超时订单并执行状态变更，控制台打印“成功拦截并记录异常”。数据库 `ExceptionRecord` 表已成功生成对应记录。

## 4. 最终自动化与幂等断言测试（全部通过）
已彻底修复 SQL 参数及 Emoji 编码问题，补全了完整的 `ExceptionRecord` 及 `exception_reminder` 事件生成逻辑，并改用严格的 `assert` 断言。
- **验证结果**：异常记录与提醒事件均成功生成（各 1 条）。
- **幂等测试**：重复扫描未产生重复数据，退出码为 0。

- <img width="1023" height="269" alt="image" src="https://github.com/user-attachments/assets/fb09ad81-c313-4809-b3e0-8c19ca2ffee5" />



