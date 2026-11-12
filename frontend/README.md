# 邻宠帮前端 · A 第九周

Vue 3 + TypeScript + Vite。使用内存模拟数据，无需数据库、API key 或后端。

## 运行

安装 Node.js 22 或 24，在 frontend 目录运行：

```sh
npm ci
npm run dev
```

打开终端输出的本地地址（通常为 http://127.0.0.1:5173）。

```sh
npm run build
npm run preview
```

build 先执行 TypeScript/Vue 类型检查，再输出 dist。移动端布局断点 760px。

## 结构

- src/App.vue：三类发布表单、核对、模拟列表、候选与流程预览。
- src/style.css：桌面及窄屏布局、可见焦点样式。
- src/main.ts：应用入口。
- ../docs/week9/A-页面流程与联调.md：流程图、字段差异、协作事项、验收步骤。

仅第九周原型：没有真实登录、AI 推理、匹配、上传、预约或结算；按钮明确区分模拟操作。档案为只读样例，任务仅保留当前会话。后续以服务端状态为准，不可将本地预览状态用于生产。无偿服务按零服务费理解，代买商品预算独立处理。
