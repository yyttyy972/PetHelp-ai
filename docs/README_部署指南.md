# 邻宠帮 - 本地一键部署指南

本指南用于在全新的环境中启动“邻宠帮”项目。

## 1. 环境准备
在开始之前，请确保您的电脑已安装以下软件：
- **Python** (推荐 3.10 或以上版本)
- **Node.js** (推荐 18.0 或以上版本)
- **PostgreSQL** (推荐 15 或以上版本)

## 2. 数据库配置
1. 打开 pgAdmin，新建一个数据库，命名为 `pethelp_db`。
2. 在 `pethelp_db` 中打开 Query Tool，依次执行以下脚本：
   - 复制 `backend/db/schema.sql` 的全部内容并运行（建表）。
   - 复制 `backend/db/seed.sql` 的全部内容并运行（导入测试数据）。

## 3. 后端启动
1. 打开终端，进入后端目录：
   ```bash
   cd backend


## 4. 部署验证结果
经实际测试，在全新环境下按照上述步骤安装依赖并配置 `config.py` 后，后端服务成功启动。终端打印 `Application startup complete.` 且定时任务调度器正常挂载，无任何报错。
<img width="593" height="269" alt="image" src="https://github.com/user-attachments/assets/c2f5b5d0-9e8a-4313-93a5-8638e00fa1ab" />

<img width="893" height="136" alt="image" src="https://github.com/user-attachments/assets/e9840b52-4fd9-42dc-b892-01bdb3bad3be" />
