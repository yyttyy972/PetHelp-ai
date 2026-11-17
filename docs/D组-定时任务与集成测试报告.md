# D组 第12周 系统测试报告

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
