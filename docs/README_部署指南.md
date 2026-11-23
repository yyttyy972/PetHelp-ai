# 邻宠帮：本地部署与联调指南

本指南用于在一台新电脑上启动邻宠帮的 PostgreSQL、FastAPI 后端和 Vue 前端。命令以 Windows PowerShell 为主；请在项目根目录开始操作。

## 1. 环境准备

请先安装 Git、Python 3.10+、Node.js 18+（包含 npm）和 PostgreSQL 15+。

```powershell
git --version
python --version
node --version
npm --version
psql --version
```

拉取最新代码：

```powershell
git clone https://github.com/yyttyy972/PetHelp-ai.git
cd PetHelp-ai
git checkout main
git pull origin main
```

如果已经克隆仓库，只需进入仓库后执行最后两行。

## 2. 初始化 PostgreSQL

以下示例使用数据库名 `pethelp_db` 和默认端口 `5432`。请将用户、密码、主机或端口替换为本机实际配置。

在项目根目录执行：

```powershell
createdb -U postgres pethelp_db
psql -U postgres -d pethelp_db -v ON_ERROR_STOP=1 -f backend/db/schema.sql
psql -U postgres -d pethelp_db -v ON_ERROR_STOP=1 -f backend/db/seed.sql
```

也可以在 pgAdmin 中新建 `pethelp_db`，然后依次执行 `backend/db/schema.sql` 和 `backend/db/seed.sql`。不要把数据库密码提交到 GitHub。

## 3. 安装并配置后端

进入后端目录，创建虚拟环境并安装业务依赖和 AI 依赖：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
```

### 3.1 配置环境变量

项目通过环境变量读取数据库和密钥，不需要、也不应修改 `backend/app/config.py`。在准备启动后端的同一个 PowerShell 窗口中执行：

```powershell
$env:DATABASE_URL = "postgresql://postgres:<数据库密码>@127.0.0.1:5432/pethelp_db"
$env:JWT_SECRET = "<至少32个字符的随机字符串>"
$env:CORS_ORIGINS = "http://127.0.0.1:5173"
$env:AI_API_KEY = "<DeepSeek API Key>"
$env:AI_BASE_URL = "https://api.deepseek.com"
$env:AI_MODEL = "deepseek-chat"
$env:AI_TIMEOUT = "30"
```

- 请把尖括号占位内容替换为真实值。
- `AI_API_KEY` 未配置时，普通业务接口仍可运行，但真实 AI 解析会进入安全回退。
- 本地开发未显式设置 `JWT_SECRET` 时项目可以自动生成并持久化；联调和部署建议显式设置。
- 不要提交 API Key、数据库密码、JWT Secret 或包含这些内容的 `.env` 文件。

### 3.2 启动后端

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

保持该终端运行。看到 `Application startup complete.` 和定时任务启动日志后，访问：

- 健康检查：http://127.0.0.1:8000/health
- 接口文档：http://127.0.0.1:8000/docs
- API 根地址：http://127.0.0.1:8000/api/v0

健康检查应返回：

```json
{"status":"ok"}
```

## 4. 安装并启动前端

新开一个 PowerShell 窗口，从项目根目录进入前端目录：

```powershell
cd frontend
npm ci
npm run dev -- --port 5173
```

浏览器访问 http://127.0.0.1:5173。在“连接设置”中选择连接后端，API 地址填写：

```text
http://127.0.0.1:8000/api/v0
```

测试账号：

- 小林：`xiaolin`
- 建国：`jianguo`
- 两个账号的演示密码：`NeighborPet2026!`

## 5. 最小联调检查

1. 打开 http://127.0.0.1:8000/health，确认返回 `{"status":"ok"}`。
2. 打开 http://127.0.0.1:8000/docs，确认接口文档可访问。
3. 打开 http://127.0.0.1:5173，切换到后端模式并使用测试账号登录。
4. 查询社区大厅，确认能够读取演示需求。
5. 发布一条未来时间的需求，确认草稿保存、发布和列表查询正常。
6. 配置 `AI_API_KEY` 后调用 AI 解析，确认返回 `draft` 和 `questions`。
7. 运行定时超时自动化测试，确认异常记录、提醒事件和幂等检查通过：

```powershell
cd backend
.\.venv\Scripts\python.exe test_timeout_auto.py
```

涉及时间匹配时请新建未来需求；种子数据中的原服务日期可能已经过期。

## 6. 常见问题

### 数据库连接失败

确认 PostgreSQL 已启动，并检查 `DATABASE_URL` 的用户名、密码、端口和数据库名。

### 浏览器提示跨域错误

确认后端启动终端中包含：

```powershell
$env:CORS_ORIGINS = "http://127.0.0.1:5173"
```

修改环境变量后需要重启后端。

### AI 接口进入回退

确认已经在后端启动终端配置 `AI_API_KEY`、`AI_BASE_URL` 和 `AI_MODEL`，然后重启后端。真实密钥不得提交到仓库。

### 前端无法启动

确认已经安装 Node.js 18 或以上版本，并在 `frontend` 目录执行 `npm ci`。

## 7. 验收分工说明

- 后端、定时超时任务、异常提醒事件和自动化测试已完成独立验证。
- 前端代码位于 `frontend/`，已合并到 `main`。
- 最终汇报前由 A 在安装了 Node.js 的环境中完成一次前后端联合演示。
