# Prompt 06：申请接单与选择帮手

日期：2026-11-24；分支 feature/html-integration。

## 交付

- backend/db/migrations/001_task_applications.sql：独立申请表、外键、金额/时间约束、待处理申请唯一索引。已在本机执行，未重建旧表。
- backend/app/routers/applications.py、app/main.py：申请、查询、接受、拒绝、撤回；记录需求版本及提议的时间和服务报酬。
- frontend-html/js/applications.js：大厅申请弹窗、宠主申请管理、帮手申请列表、预约列表/详情、双方确认及撤回。
- js/match.js、js/auth.js：入口和初始化；css/auth.css：申请说明输入样式。
- tests/applications-live.mjs、package.json：真实双账号及并发测试。

## 接口

- POST /requests/{id}/applications：expected_version、scheduled_start/end（带时区）、agreed_fee、note；按登录账号确定帮手，拒绝代他人申请。
- GET /requests/{id}/applications：仅需求宠主，limit/cursor 分页。
- GET /applications：当前帮手自己的申请，limit/cursor 分页。
- POST /applications/{id}/accept：宠主操作，携带 expected_version；接受后返回原 Booking 结构。
- POST /applications/{id}/reject：宠主拒绝；POST /applications/{id}/withdraw：申请人撤回。
- 预约展示与确认复用 GET /bookings、GET /bookings/{id}、POST /bookings/{id}/confirm、POST /bookings/{id}/withdraw。

所有接口需要登录 Token。申请时间和费用在提交及接受时分别校验；无偿报酬必须为0，商品预算不等于服务报酬。申请期间不锁定档期；接受时复用原预约事务和冲突校验。一个申请接受后其他待处理申请标记未选中；预约仍需双方确认。已接受申请重复接受返回同一预约，不能借重试重复创建。

## 真实测试

`npm run test:applications` 通过：两个帮手同时申请；相同申请重试返回原 ID；宠主浏览并选择帮手；另一申请自动未选中；重复接受返回同一预约；双方在页面核对清单后确认进入 reserved；撤回恢复需求 pending_match；无关人查看预约/申请及申请人冒充宠主接受均被403拒绝；并发接受返回一次200和一次409；需求版本更新后旧申请无法接受但允许本人撤回。浏览器无 pageerror。

测试创建专用账号及测试需求，保留在本机数据库，不用于生产环境。页面中出现申请列表加载提示时需等待完成再操作。

## 边界

本轮完成申请与预约确认，未完成新版 HTML 的开始服务、执行凭证、提交验收和异常处理页面，属于下一阶段 Prompt 07。数据库迁移必须先于新后端启动；新建数据库同样需要在 schema.sql 后执行该迁移。
