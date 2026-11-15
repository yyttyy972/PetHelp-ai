# 邻宠帮 AI 解析评估标准校准 v1

## 1. 校准范围

本报告基于以下现有材料进行离线分析：

- `docs/backend-contract/api-v0.2.md`
- `docs/week9/prompt-v0.md`
- `docs/week9/ai-parse-schema.json`
- `docs/week10/ai-parse-evaluation-dataset-v1.json`
- `docs/week10/ai-parse-evaluation-results-v1.json`
- `docs/week10/ai-parse-failure-analysis-v1.md`
- `tests/batch_test_parser.py`

本次不修改 Prompt、Schema、parser、评估器或 45 条原始数据，也不重新调用模型。

## 2. 争议标注核对

### 2.1 HV-14：禁止喂食应归入 precautions

**判断：人工标注应修正。**

Prompt 已明确：`precautions` 用于“宠物行为特点、禁止事项及其他安全注意事项”。“不要喂食”是明确的禁止事项，应进入 `draft.precautions`。模型输出 `precautions="不要喂食"` 符合现有定义，不是编造或字段污染。

建议修正：

- `expected_field_values.precautions`：由 `null` 改为能表达“不要喂食”的文本。
- checklist 仍只包含换水和清理猫砂，不生成喂食项。
- `question_topics_not_to_ask` 继续包含 `food_portion`。

现有评估器把预算追问中的“多少”命中 `food_portion`，属于话题检测误判，不应据此判 HV-14 失败。

### 2.2 HV-08：未明确服务时长时应为 null 并追问

**判断：人工标注应修正。**

用户给出了 10:00–11:00 的可服务窗口，但没有说明实际执行需要多久。`window_start/window_end` 表示时间窗口，`expected_duration_minutes` 表示预计执行时长，两者不是同一概念。Prompt 也明确规定时长缺失时填 `null` 并补问，不能用窗口长度推断。

建议修正：

- `expected_field_values.expected_duration_minutes`：由 `60` 改为 `null`。
- `required_question_topics`：增加 `duration`。
- 保留 10:00–11:00 的 window，不因时长未知而清空已明确的窗口。

模型本次将时长设为 `null` 并追问“预计需要多少分钟”，符合现有契约与 Prompt。

### 2.3 HV-15：现有字段不支持周期性服务

**判断：当前 draft 只能表达单次需求，不能直接表达“连续多天、每天一次”。**

API v0.2 的 ServiceRequest 只有一组 `window_start/window_end`，没有 recurrence、日期数组或重复规则字段。不能把下周一至周三合并为一个跨三天连续窗口，也不能任意选择其中一天。

在现有字段下，合理草稿行为是：

- `window_start=null`、`window_end=null`。
- 在 `questions` 中确认拆分方式、具体服务日期及每天的起止时间。
- 用户已经明确“每次20分钟”，因此 `expected_duration_minutes=20` 可以保留；它是明确的单次执行时长，不是从窗口猜测。
- 不生成多个 ServiceRequest，也不在 AI parse 阶段自动拆单。

建议修正：

- `expected_field_values.expected_duration_minutes`：由 `null` 改为 `20`。
- 保留 `recurring_schedule_scope` 和 `time_window` 两类必问主题。
- 将“需要确认如何拆分为单次需求”写入 annotation note 和验收标准。

仍需后端 B 确认产品策略：周期需求最终由用户手动创建多条、由前端拆单，还是未来扩展 recurrence 模型。在 B 明确前，AI 只能返回不可直接发布的单次草稿并追问。

### 2.4 EB-03：input.pet_ids 应作为已选择宠物传入

**判断：数据集标注本身有契约依据，但当前本地 runner 没有传递完整输入语义。**

API v0.2 明确 `/ai/parse` 输入包含可选 `pet_ids`。数据集的 `input.pet_ids` 表示调用方已经选择的宠物，不应被等同为“仅供名称匹配的全部宠物档案”。因此在真实 API 语义下，EB-03 预期年糕 UUID 出现在 draft.pet_ids 是合理的。

当前 runner 只调用：

```python
parse_request(text, reference_time, timezone, pets=fixture_only_pet_profiles)
```

它没有传入 `input.pet_ids`；而现有 `parse_request()` 也没有 selected pet_ids 参数。模型只看到“帮我买东西”和一份可用宠物档案，输出空 pet_ids 并追问关联宠物具有合理性。

校准建议：

- 不修改 EB-03 的目标 pet_id。
- 在修复 runner/adapter 前，将 EB-03 标记为“输入上下文未完整传递”，不计入模型准确率。
- 后续接口应明确区分：`pet_ids` 是已选择宠物；`pets` 是用于 UUID/名称解析的档案上下文。
- 已选择 pet_ids 必须原样进入候选 draft；模型不能因为文本未出现宠物名字而丢弃它们。

## 3. 应修正的人工标注

| case_id | 当前标注 | 建议标注 | 依据 |
|---|---|---|---|
| HV-14 | `precautions=null` | `precautions` 表达“不要喂食” | Prompt 将禁止事项定义为 precautions |
| HV-08 | `expected_duration_minutes=60`，无 duration 追问 | 时长为 `null`，增加 `duration` 必问主题 | 时间窗口长度不能推导执行时长 |
| HV-15 | `expected_duration_minutes=null` | 保留用户明确提供的每次 20 分钟；窗口仍为 null | 明确信息可保留，周期窗口不可编造 |
| EB-03 | 预期关联年糕，但 runner 未传 input.pet_ids | 保留预期；在 runner 修复前排除模型计分 | `/ai/parse` 契约明确接收 pet_ids |

除此之外，同义文本、标点和 UUID 数组顺序不应通过修改人工语义标注来逐字迎合模型，应由评估逻辑处理。

## 4. 现有评估器问题

### 4.1 字符串字段使用完全相等

`_check_fields()` 当前直接执行 `actual_value == expected_value`，导致以下等价表达失败：

- “门禁远程开”与“门禁远程开启”。
- “宠主”与上下文明确指向宠主的“我/用户”。
- 中文句号、分号、空格差异。
- 表达顺序不同但事实相同。

改进方案：

1. 对自然语言字段做 Unicode NFKC、首尾空白、连续空白和无意义句末标点规范化。
2. `raw_text` 不做规范化，继续要求逐字一致。
3. 枚举、数字、时间、UUID、null 继续严格相等。
4. 对 `location`、联系方式等事实字段采用规范化后精确或结构化比较，不能做模糊语义放宽。
5. 对 requirements、precautions、handover_notes 使用“事实单元覆盖”而不是整句相等，并分别检查不应出现的事实。

### 4.2 pet_ids 依赖数组顺序

Schema 已要求 `uniqueItems=true`，业务语义是宠物集合。当前精确数组比较会把 HV-06 的相同 UUID、不同顺序判为失败。

改进方案：

- 比较前先分别检查类型、UUID 格式和无重复。
- 正确性使用集合相等判断。
- 如果未来业务规定展示顺序，再单独记录 order warning，不与宠物选择正确性混为一谈。

### 4.3 checklist 匹配过度依赖单一字面关键词

当前 `_check_checklist()` 要求 item_key、pet_id 完全相同，并要求每个 `content_keywords` 是 content 的直接子串。它无法识别：

- “送至”与“送到”。
- “交还宠物”与“送回旺财”。
- “更换饮用水”与“换水”。
- 时长写在 return 而非 departure，但整体流程仍完整。

改进方案应分两层。

#### 固定结构严格检查

- 所有项：`position` 连续且从 1 开始，`required` 类型正确，`pet_id` 为 null 或属于 draft.pet_ids。
- dog_walking：前三项必须严格为 pickup、departure、return，顺序不可放宽。
- errand_buy：前两项必须严格为 purchase、delivery；purchase 三个商品字段必须存在，delivery.pet_id 必须为 null。
- home_visit：在后端确认 canonical item_key 词表后严格检查；确认前，自定义同义 key 应进入 review，而不是直接算业务错误。
- product_name、quantity、unit、UUID、position 等机器字段严格比较，不做语言近似。

#### 自然语言事实覆盖检查

- 标注不再只提供单个字符串关键词，而应支持同义词组或事实断言，例如 `any_of:["送到","送至"]`。
- 对数量、剂量、地点、禁令等关键事实保留严格检查：30克不能被20克通过，社区东门不能被西门通过。
- 允许关键事实分布在 content 与 completion_condition 的合理位置；是否允许跨 checklist 项覆盖应由具体规则限定。
- 模糊语义匹配只用于措辞，不得掩盖商品、宠物、数量、时间、地点和安全要求的真实遗漏。

### 4.4 questions 主题匹配关键词过宽

`food_portion` 包含通用词“多少”，使“预算金额是多少”误命中喂食份量；`recurring_schedule_scope` 的词表又无法识别“下周一至周三是指哪些日期”的实际追问。

改进方案：

- 使用主题短语或词组共现，而不是任一单词命中。
- food_portion 要求“喂/猫粮/狗粮/份量”等上下文与“多少/克/勺”共同出现。
- budget 要求“预算/金额/费用上限”等预算上下文。
- recurring_schedule_scope 覆盖“日期范围、拆分、每天、分别创建、哪一天”等表达。
- 同时检查 required topics 与 forbidden topics；不能只检查是否出现某个宽泛词。

## 5. 需要修改的 Prompt 规则

以下是后续建议，本次不直接修改 Prompt：

1. 明确“不要喂食、不要开门、禁止接触其他动物”等禁止事项进入 `precautions`。
2. 明确“服务窗口长度不等于预计执行时长”；未给时长时必须为 null 并追问。
3. 明确周期需求当前不能由一个 draft 表达：窗口为 null，追问拆分方式和每次时间；用户已明确的每次时长可以保留。
4. 明确调用方已选择的 pet_ids 优先于文本名称匹配；pets 档案只提供解析上下文，不能改变已选集合。
5. 明确 purchase 的 product_name、quantity、unit 无论是否已知都必须输出；未知值为 null 并追问。
6. 在 B 确认后增加 home_visit canonical item_key 表，避免 feed_food/feeding/feed_cat_food 等漂移。
7. 加入 requirements、precautions、checklist 的字段归位正反例，避免相同事项重复进入多个字段。

## 6. 需要与后端 B 确认的字段约定

| 议题 | 当前证据 | 需要确认 |
|---|---|---|
| 周期性服务 | ServiceRequest 只有单一 window，无 recurrence 字段 | 是前端拆成多条请求、用户逐条创建，还是未来扩展周期模型 |
| 周期需求中的明确时长 | 用户可明确“每次20分钟”，Schema 可容纳正整数 | 在窗口未确定但每次时长明确时，是否允许保留 duration=20 |
| `/ai/parse` 的 pet_ids | API v0.2 明确为可选输入 | 它是否始终表示已选择宠物，以及 parser 本地接口如何接收该字段 |
| pets 档案上下文 | 当前只存在本地 parser 的 `pets` 参数 | 传全部宠物还是仅传候选宠物；不得与 selected pet_ids 混用 |
| home_visit item_key | 契约只说按明确照料要求填写，未列 canonical key | 是否正式固定 feed_food、change_water、clean_litter、give_medicine 等词表 |
| precautions 边界 | Prompt 已包含行为特点、禁止事项、安全事项 | 是否所有明确禁令都进入 precautions，即使同时影响 checklist |
| requirements 边界 | Prompt 仅明确“补充执行要求”，遛狗路线放此处 | 上门照料步骤是否只进 checklist，何时允许 requirements 重复摘要 |

在这些约定确认前，评估器应把相关案例标为 `needs_review`，不应强行计入模型失败或通过。

## 7. 修改后的测试验收标准

### 7.1 分层验收

1. **Schema 硬门槛**
   - Draft 2020-12 校验必须通过。
   - required 字段缺失、类型错误、非法 UUID、quantity=0 等直接失败。

2. **确定性机器字段**
   - service_type、fee_type、数字、时间、null 状态严格比较。
   - raw_text 必须逐字等于输入 text。
   - pet_ids 按集合比较，同时独立检查 UUID、唯一性和是否来自允许输入。

3. **业务不变量**
   - end 晚于 start，duration 不超过窗口。
   - checklist.pet_id 非空时属于 draft.pet_ids。
   - dog_walking 与 errand_buy 固定 key 和顺序严格校验。
   - 不得推断未提供的时间、金额、数量、宠物或联系方式。

4. **自然语言字段**
   - 先做最小规范化，再比较事实覆盖。
   - 同义改写和无意义标点不失败。
   - 关键事实值错误或遗漏仍失败。

5. **追问完整性**
   - 缺失必填信息必须出现对应主题追问。
   - 已明确信息不得重复追问。
   - 使用上下文相关主题判定，不用“多少”等单一宽泛词。

### 7.2 结果状态

- `passed`：Schema、机器字段、业务不变量、关键事实和追问均满足。
- `failed`：存在明确业务错误、真实信息遗漏、错误推断或必要追问缺失。
- `error`：API、JSON 解析或 Schema 校验失败。
- `needs_review`：后端字段约定未确认，或仅靠自动规则无法可靠判断语义等价。

### 7.3 不得因校准而放宽的内容

- 不允许把错误宠物、错误时间、错误地点、错误金额或错误数量视为同义表达。
- 不允许忽略 required 字段、固定 checklist key/顺序和跨字段成员关系。
- 不允许用语义相似度掩盖否定词差异，例如“喂食”与“不要喂食”。
- 不允许将缺少追问但恰好输出 null 的案例判为通过。
- 不允许为了提高通过率删除 Schema 校验或业务不变量校验。

## 8. 建议实施顺序

1. 先由 B 确认周期、selected pet_ids、home_visit item_key 和字段边界。
2. 修正 HV-14、HV-08、HV-15 标注，并标记 EB-03 的 runner 上下文前提。
3. 改造评估器的集合比较、字符串规范化、checklist 分层校验和 questions 主题规则。
4. 按确认结果补充 Prompt 规则。
5. 使用保存的 actual_output 离线重评估；只有 Prompt 或模型行为发生变化时才重新调用 API。
