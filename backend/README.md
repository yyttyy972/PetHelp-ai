# 邻宠帮第 10 周后端

Python 3.12、PostgreSQL 17；运行目录为 backend，配置从环境变量读取，数据库模式以 db/schema.sql 为准，接口清单见 docs/API清单.md，交互文档 /docs，机器接口 /openapi.json。

## 初始化与启动（PowerShell）

```powershell
cd C:\Users\Mini\Desktop\软件工程\backend
py -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
createdb -U postgres linchong
psql -U postgres -d linchong -v ON_ERROR_STOP=1 -f db/schema.sql
psql -U postgres -d linchong -v ON_ERROR_STOP=1 -f db/seed.sql
$env:DATABASE_URL = 'postgresql://postgres:你的密码@127.0.0.1:5432/linchong'
$env:JWT_SECRET = '替换为随机生成的至少32字符密钥，不要提交到仓库'
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

schema.sql 只在空库执行一次；seed.sql 使用固定 UUID 和 ON CONFLICT DO NOTHING，可重复执行，不清空已有业务数据。演示账号 xiaolin / jianguo，密码均为 NeighborPet2026!，仅限本地演示；两人均为 owner/helper、verified，新注册为 unverified。年糕归小林，豆豆与团团归建国，服务窗口为2026-11-09和2026-11-10 UTC，过期后仍可展示但应另建未来需求进行匹配演示；没有伪造照片或凭证 URL。

可配置 COMMUNITY_CODE（默认 linchong-001）、MEDIA_ROOT（默认 backend/storage）。JWT 一小时有效；密码采用随机盐 PBKDF2-SHA256 600000 轮；/health 不访问数据库，但启动必须提供 JWT_SECRET。

## 第 10 周流程

注册→登录取得 Bearer token→POST /pets 建两只狗→POST /requests 携带两个 pet_ids 与 pickup/departure/return 清单，获得 draft→POST /requests/{id}/publish 携带 expected_version=1→GET /requests/{id} 查看 pets 与清单→GET /requests?scope=open 查看精简大厅投影。日期必须带时区，金额使用两位小数字符串，客户端不得传 owner_id、status 或自证核验。

执行验证脚本：`.venv/Scripts/python.exe tests/smoke.py`，需启动服务并提供 BASE_URL（默认 http://127.0.0.1:8000）；脚本在测试库创建独立账号与需求，不用于生产库。

## 已知边界

只实现第10周基础档案、需求 CRUD/publish、受控图片上传；AI 返回503，匹配算法由D、结构化草稿由C提供，预约执行异常评价等后续接口尚未注册。没有前端，前端启动需A的项目。

需求写入的幂等结果使用 TaskEvent 同事务保存；其他操作因12表契约没有独立幂等表，使用本地文件缓存，数据库提交与文件写入之间存在崩溃窗口；部署只支持本地单实例，不宣称分布式严格一次。上传失败重试可能遗留未绑定文件，后续需清理策略。当前路由以 Pydantic 及服务逻辑校验输入，SQL模型定义在 db/schema.sql。尚无真实支付、通知或定位。

开发联调：CORS_ORIGINS 可配置逗号分隔的前端地址，默认 http://localhost:5173,http://127.0.0.1:5173；当前采用单 worker 串行事务，避免同步数据库锁阻塞事件循环，不用于高并发部署。
