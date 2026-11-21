# 第12周 C组：AI 解析评估与 Prompt v3 交付说明

## 1. 本周交付内容

- `app/ai/prompt-v3.md`：需求解析 Prompt v3。
- `app/ai/parser.py`：解析器切换为加载 Prompt v3。
- `scripts/run_ai_parse_evaluation.py`：45 条真实模型评估脚本。
- `tests/test_ai_parse_evaluation.py`：评估器离线回归测试。
- `docs/week12/ai-parse-evaluation-dataset-v1.1.json`：三类服务各 15 条，共 45 条评估数据。
- `docs/week12/baseline/ai-parse-evaluation-results-prompt-v2-rechecked.json`：Prompt v2 复核基线。
- `docs/week12/ai-parse-evaluation-results-week12-v1.json`：Prompt v3 最终完整评估结果。

解析接口及数据库行为未改变；AI 解析仍只生成草稿，不写业务状态。

## 2. 评估方法

评估采用“确定性硬校验 + AI 语义裁判”的混合方式：

- 严格校验 Schema、宠物 ID、服务类型、费用类型、时间窗口、时长、预算、原始文本、清单键、宠物关联、数量和单位。
- 语义评估交接说明、需求、注意事项、地点、商品名称、清单内容、完成条件、追问覆盖和禁止推断。
- 接受同义词、合理简称、语序和标点差异，例如“安全送回/送回”和“门禁远程开启/门禁远程开”。
- AI 裁判无法可靠判断时返回 `needs_review`，不会强行判定通过或失败。
- `required_question_topics` 表示最低必问集合，不是追问白名单。

数据集已同步当前通用决定：普通喂食份量不是必问信息；主人主动提供时记录，未提供时不得猜测，但不必追问。

## 3. Prompt v3 共性修正

本轮根据真实评估结果修正以下共性问题：

1. 用户给出的预计时长超过明确时间窗口时，保留时间窗口，将时长设为 `null` 并追问，不擅自修改时间或时长。
2. 遛狗始终生成 `pickup`、`departure`、`return` 三项；目标犬只不确定时使用 `pet_id=null` 并追问。
3. 代买始终以 `purchase`、`delivery` 开头；共享商品只生成一条 `purchase`，不按宠物重复购买。
4. 每条 `purchase` 必须包含 `product_name`、`quantity`、`unit`；缺失信息填 `null` 并追问，不省略字段、不猜测。

## 4. 最终评估结果

最终运行时间：2026-11-21。模型：项目当前配置的 `deepseek-chat`。

| 服务类型 | 通过 | 失败 | 错误 | 总数 |
| --- | ---: | ---: | ---: | ---: |
| 上门代看 | 11 | 4 | 0 | 15 |
| 遛狗 | 14 | 1 | 0 | 15 |
| 代买 | 14 | 1 | 0 | 15 |
| 合计 | 39 | 6 | 0 | 45 |

- 总体通过率：`39 / 45 = 86.67%`。
- Schema 有效：`45 / 45`。
- `needs_review`：0。
- 语义裁判异常：0。

Prompt v2 复核基线为 23 条通过、6 条失败、2 条错误、14 条待复核。两版评估器口径不同，不能只依据数字做严格统计推断；但 v3 最终批次已消除运行错误和 Schema 错误，并显著减少需要人工处理的简单语义差异。

## 5. 已知未通过样例

- `HV-02`：两只宠物的共同换水、清理猫砂被拆成逐宠物事项。当前决定暂不调整此行为。
- `HV-04`：模糊时间被转换成了具体时间窗口。
- `HV-09`：遗漏门禁交接信息，且未追问用品位置。
- `HV-12`：未追问必要的交接方式和紧急联系人，并将完成条件细化为“吃完”。
- `DW-07`：记录了犬只紧张，但遗漏主动避让大型犬的执行要求。
- `EB-13`：预计时长没有按标注保留为 `null`。

这些问题均有明确样例和判定依据，不影响解析器运行或 Schema 安全，可作为下一轮 Prompt 优化输入。

## 6. 验证命令

在 `backend` 目录执行：

```powershell
.\.venv\Scripts\python.exe -m py_compile app\ai\parser.py scripts\run_ai_parse_evaluation.py
.\.venv\Scripts\python.exe -m unittest tests.test_ai_parse_evaluation -q
.\.venv\Scripts\python.exe .\scripts\run_ai_parse_evaluation.py
```

定向复测可重复提供 `--case-id`：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_ai_parse_evaluation.py --case-id EB-03 --case-id EB-09
```

完整评估会调用真实模型并产生 API 用量；离线测试使用 mock，不调用真实模型。

本机交付验证结果：

- Python 编译检查通过。
- `tests.test_ai_parse_evaluation` 共 7 项，全部通过。
- 最终结果文件校验通过：45 条、39 条通过、0 个运行错误。

## 7. 交付结论

Prompt v3、混合评估器、45 条数据集、v2 基线和 v3 最终结果已形成可复现闭环。最终批次 45 条均成功通过 Schema，三类服务均有覆盖，失败样例已记录。
