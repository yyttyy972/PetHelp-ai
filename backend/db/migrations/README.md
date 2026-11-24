# 增量迁移

初次建库先执行既有 schema.sql；已有数据库不要重建或重复执行 schema.sql。

启用申请接单模块前，在 backend 目录连接目标数据库执行：

```powershell
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/001_task_applications.sql
psql "$env:DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/002_messages.sql
```

此命令要求本机已安装 psql 且 DATABASE_URL 已配置。执行后重启后端。迁移新增 TaskApplication 表及索引，不清空或改写旧表数据；相同迁移可重复执行。SQL 使用事务，失败时不会部分创建。

本次申请模块仅保存申请方案；接受申请由原 bookings.create 执行资格、费用和冲突校验。申请本身不占用服务时间。需要回退应用时先停用申请路由，保留申请历史表；不要直接删除已有历史数据。
