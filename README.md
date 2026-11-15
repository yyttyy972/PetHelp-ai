# PetHelp-ai

邻宠帮：AI 需求理解与规则知识库。C 组第九、十周 AI 模块交付仓库。

## 核心代码

- `src/ai/parser.py`：需求解析逻辑
- `src/ai/schema.py`：结构化结果校验
- `src/ai/config.py`：模型与环境配置
- `tests/`：离线测试、手工场景测试与批量评估程序
- `validate_schema.py`：Schema 校验入口

## 文档与评估

- `docs/week9/`：需求字段设计、初版 Prompt 与 JSON Schema
- `docs/week10/prompt-v2.md`：第十周 Prompt
- `docs/week10/ai-parse-evaluation-dataset-v1.1.json`：45 条评估数据
- `docs/week10/ai-parse-evaluation-results-prompt-v2-judged.json`：Judge 复核结果
- `docs/week10/ai-parse-evaluation-calibration-v1.md`：评估标准校准
- `docs/week10/ai-parse-failure-analysis-v1.md`：失败案例分析
- `docs/week10/ai-parse-real-api-test.md`：三类场景真实接口测试记录

## 环境配置

1. 安装 Python 依赖：`python -m pip install -r requirements.txt`
2. 复制 `.env.example` 为本地 `.env`
3. 在本地 `.env` 中填写 `AI_API_KEY` 等配置

**不要提交 `.env`、API Key、数据库密码或访问 Token。**

## 后端联调说明

AI 模块已在本地独立后端入口完成真实接口调用验证。该入口尚未合并进 B 组标准后端启动入口；正式注册、字段映射及前端草稿交互需由 A、B 审核确认。
