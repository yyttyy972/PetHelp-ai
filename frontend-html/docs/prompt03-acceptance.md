# Prompt 03 基础档案验收

日期：2026-11-24。分支：feature/html-integration。

## 交付范围

- 个人资料：真实昵称、常用地址、头像上传和保存；宠主和帮手均可进入。
- 宠物：列表分页读取、新增、编辑、删除；出生日期、性格、注意事项、用品位置、照料说明和照片。图片通过带 Token 的请求读取。
- 帮手：三类服务、支持宠物类型、服务区域、经验、半径、费用偏好、公开位置标签。
- 时间：新增、查询、删除；浏览器本地日期时间转成带时区的 ISO 时间提交。
- 沿用暖色、圆角及原页面导航；替换相应页面的演示资料。单一地址通过个人资料维护，不伪造多地址存储。

## 文件与接口

- backend/app/routers/api.py：新增 GET /helpers/me，位于 /helpers/{id} 前，按当前登录用户查档案，要求 helper 角色；不存在返回 404，不接受其他用户 ID。
- frontend-html/js/profiles.js、css/profiles.css：基础档案页面。
- js/api.js：FormData 上传、鉴权图片读取、中文错误提示。上传不自动生成幂等键，防止把不同文件识别成同一 JSON 请求。
- js/auth.js、index.html：登录后初始化真实档案、头像和个人资料入口；个人资料不再强制切换到帮手。
- tests/profiles-live.mjs、package 配置：可重复运行的真实浏览器测试。

复用 PATCH /users/me；GET/POST/PATCH/DELETE /pets；POST /media、GET /media/{path}；PUT /helpers/me；GET/POST /helpers/me/availability；DELETE /helpers/me/availability/{id}。无数据库结构变更。

## 验证

`npm run test:profiles` 对专用测试账号验证通过：个人资料刷新持久化；宠物照片上传显示、新增、编辑、刷新、删除；帮手偏好及时间段刷新持久化、时段删除；另一账号宠物列表隔离、越权修改返回 403；帮手本人档案未建立返回 404，未登录返回 401；伪装 PNG 的无效文件被后端拒绝，前端保留输入。无浏览器 pageerror。

`npm run build` 通过。390px 手机视口页面无横向溢出，已查看宠物页截图。测试运行会留下专用账号及部分测试档案；不删除原有演示数据。

## 已知边界

尚未接入真实任务发布、匹配、预约、消息；首页仍含原型演示内容。没有服务评价/健康证等无后端依据的个人资料展示。头像上传和保存已实现，但本轮自动测试重点覆盖宠物图片；尚未做所有图片大小边界和断网恢复测试。删除已被需求引用的宠物、已被预约占用的时段以原后端约束为准。

下一步：Prompt 04，真实 AI 解析、草稿编辑、必填检查及需求发布。
