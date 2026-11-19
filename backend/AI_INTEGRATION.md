# C1 AI Parser 集成说明

## 安装 AI 依赖

在 `backend` 目录执行：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
```

AI 依赖独立声明在 `requirements-ai.txt`，不修改后端原有的 `requirements.txt`。

## 环境变量

将 `.env.ai.example` 中的占位值复制到 `backend/.env`，并填写真实密钥：

```dotenv
AI_API_KEY=your_deepseek_api_key
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-chat
AI_TIMEOUT=30
```

不要提交 `backend/.env`、API Key、数据库密码或 JWT_SECRET。

后端原有的 `DATABASE_URL`、`JWT_SECRET` 等变量仍按 B 组现有方式配置。

## 正式启动

正式入口已经在 `app.main` 中注册 AI Router：

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`run_ai_integration.py` 是兼容的独立入口，直接导出同一个正式 FastAPI app，不会重复注册路由：

```powershell
.venv\Scripts\python.exe -m uvicorn run_ai_integration:app --host 127.0.0.1 --port 8000
```

## 测试 AI 接口

先登录获取 Bearer token，并准备属于当前用户的宠物 UUID。然后发送：

```powershell
$headers = @{ Authorization = "Bearer <access-token>" }
$body = @{
  text = "帮我照看宠物"
  reference_time = "2026-11-16T12:00:00+08:00"
  timezone = "Asia/Hong_Kong"
  pet_ids = @("<owned-pet-uuid>")
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v0/ai/parse `
  -Headers $headers `
  -ContentType application/json `
  -Body $body
```

`pet_ids` 可以省略；省略时服务端按空数组处理。接口只返回 `draft` 和 `questions`，不会创建 ServiceRequest 或写入业务数据库。
