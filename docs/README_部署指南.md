# 邻宠帮 - 本地一键部署指南

本指南用于在全新的环境中启动“邻宠帮”项目。

## 1. 环境准备
请确保电脑已安装以下软件：
- **Python** (推荐 3.10 或以上版本)
- **Node.js** (推荐 18.0 或以上版本)
- **PostgreSQL** (推荐 15 或以上版本)

## 2. 数据库配置
1. 打开 pgAdmin，新建数据库 `pethelp_db`。
2. 在 Query Tool 中依次执行 `backend/db/schema.sql` 和 `backend/db/seed.sql`。

## 3. 后端启动
1. 打开终端，进入后端目录：
   ```bash
   cd backend
安装后端依赖包：

bash
pip install -r requirements.txt
配置环境变量：打开 backend/app/config.py，将 DATABASE_URL 中的密码改为本地数据库密码。

启动后端服务：

bash
uvicorn app.main:app --reload
健康检查验证：终端打印 Application startup complete. 及定时任务启动日志即表示成功。可访问 http://127.0.0.1:8000/health 验证，返回 {"status":"ok"} 则正常。

## 4. 前端启动
新开一个终端，进入前端目录：

bash
cd frontend
安装前端依赖：

bash
npm install
启动前端服务：

bash
npm run dev
验证：浏览器打开 http://localhost:5173 能看到登录页面即成功。

## 5. 部署验证结果
经实际测试，在全新环境下按照上述步骤安装依赖并配置 `config.py` 后，后端服务成功启动。终端打印 `Application startup complete.` 且定时任务调度器正常挂载，无任何报错。
<img width="593" height="269" alt="image" src="https://github.com/user-attachments/assets/c2f5b5d0-9e8a-4313-93a5-8638e00fa1ab" />

<img width="893" height="136" alt="image" src="https://github.com/user-attachments/assets/e9840b52-4fd9-42dc-b892-01bdb3bad3be" />
