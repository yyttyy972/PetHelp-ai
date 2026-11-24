# Prompt 04：AI 解析与需求发布

2026-11-24，feature/html-integration。

## 修改内容

- js/requests.js：替换原发布表单及模拟提交监听；真实宠物选择、AI 解析/补问、人工编辑、逐宠清单、商品信息、后端草稿创建/修改/删除、正式发布、个人需求列表和恢复。
- js/request-domain.js：复用原 frontend/src/domain.ts 中不依赖 Vue 的业务校验和 AI 字段映射，移除 TypeScript 类型生成原生 JS；不是将新界面改成 Vue。
- js/auth.js：认证完成后初始化发布功能。
- js/api.js：允许 AI 单次请求45秒超时，普通接口仍15秒。
- tests/requests-live.mjs、package.json：真实接口与浏览器验收脚本。
- 本机 backend/.env：已配置用户提供的模型凭据；已确认被 gitignore 排除。凭据不写入本文、测试或前端。

复用接口：GET /pets；POST /ai/parse；POST/GET /requests；GET/PATCH/DELETE /requests/{id}；POST /requests/{id}/publish。后端业务字段与状态不改动。

## 行为说明

AI 返回仅为建议，不自动发布。信息缺失时展示补问，保留可编辑字段；本机暂存允许缺项，后端草稿按现有契约要求完整。已保存后宠物与服务类型锁定。PATCH/publish 使用当前 expected_version；版本冲突要求重新加载。成功发布后表单只读，首页宠主需求来自后端。

保留 dog_walking 的 pickup/departure/return、errand_buy 的 purchase/delivery；清单宠物必须属于选中名单。代买商品预算与服务报酬分开，不添加后端不存在的发布阶段报酬字段。

## 验收结果

- 真实模型接口返回 200，上门代看场景保留宠物 UUID，缺失信息返回8条补问（单次结果，不保证每次数量一致）。
- 浏览器真实 AI 解析、补问、缺项阻止保存及本机刷新恢复通过。
- 三类服务分别通过创建草稿、修改、刷新恢复和发布；发布状态为 pending_match。
- 外部会话更新版本后，旧版本保存冲突被提示，没有覆盖新版本。
- 无偿代买、商品预算50元的需求发布成功。
- 已发布表单按钮禁用；用户确认后才调用发布接口。
- 测试拦截注入 AI 502 验证失败时保留输入；该拦截只在测试中存在，不属于运行时回退。
- 无浏览器 pageerror；生产构建通过。

测试使用专用 html-request- 前缀账号，测试需求保留在本机数据库。尚未验收任务匹配、预约和消息功能；对应后续阶段。AI只完成有限真实样例测试，不代表全部自然语言场景正确。

下一步 Prompt 05：真实任务大厅、帮手匹配及匹配原因解释。
