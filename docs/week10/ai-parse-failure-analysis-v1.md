# 邻宠帮 AI Parse 失败分析 v1

## 1. 分析范围与结论

- 数据来源：`ai-parse-evaluation-dataset-v1.json` 与 `ai-parse-evaluation-results-v1.json`。
- 本报告为离线分析，未调用 DeepSeek API。
- 共 45 条：10 条 `passed`、33 条 `failed`、2 条 `error`。
- 43 条实际输出通过 JSON Schema；`EB-02`、`EB-09` 因 `purchase` 缺少必填字段而未通过 Schema。
- 原始通过率 `10/45` 不能直接视为模型真实准确率。29 条案例含 checklist 字面匹配失败，22 条含字段精确比较失败，其中大量是同义表达、标点、数组顺序或信息放置差异。
- 45 条中没有发现 service_type 识别错误，也没有确认模型凭空编造时间、金额、宠物 UUID 或联系方式。

失败类型会重叠。例如一个案例可以同时存在字段归位错误和测试程序误判。

## 2. 失败原因分类

### 2.1 AI 确实理解或字段映射错误

| case_id | 实际表现 | 人工预期 |
|---|---|---|
| HV-01、HV-02、HV-04、HV-06、HV-08、HV-12、HV-13、HV-14 | 将已在 checklist 表达的照料事项重复写入 `requirements`；HV-14 还把“不要喂食”写入 `precautions` | 上门代看的具体照料事项主要进入 checklist；这些案例的 `requirements` 应为 `null`，HV-14 的 `precautions` 标注也为 `null` |
| DW-01 | “全程牵引”进入 `precautions`，未与路线一起进入 `requirements` | `requirements` 同时包含小区路线和全程牵引要求；`precautions` 表达怕大狗和主动避让 |
| DW-04 | “两个都要牵好”进入 `precautions` | 牵引要求应进入 `requirements`；人工标注的 `precautions` 为 `null` |
| DW-07 | `precautions` 只保留“看到大型犬会紧张”，避让动作只出现在 `requirements` | `precautions` 应完整体现紧张、保持距离和主动避开 |
| DW-13 | 将“只遛豆豆，不遛旺财”写入 `precautions` | 通过 `pet_ids=[豆豆]` 表达选择即可，`precautions` 为 `null` |

这些案例大多没有误解用户意图，主要问题是跨字段归位不稳定。

### 2.2 AI 遗漏必要字段

| case_id | 实际表现 | 人工预期 |
|---|---|---|
| EB-02 | `purchase` 有购买内容，但完全未输出 `product_name`、`quantity`、`unit` | 三个字段必须存在；本例应为猫粮、1、袋 |
| EB-09 | `purchase` 有冻干零食及数量描述，但完全未输出 `product_name`、`quantity`、`unit` | 三个字段必须存在；共同商品的 `pet_id` 可为 `null` |
| DW-08 | 喝水任务使用 `item_key="water"` | 人工标注约定为 `give_water` |

`DW-08` 的信息没有丢失，但结构化键名没有遵循标注约定；`EB-02`、`EB-09` 是会阻断 Schema 的真实遗漏。

### 2.3 AI 追问不充分

| case_id | 实际表现 | 人工预期 |
|---|---|---|
| HV-07 | 追问预算和用药说明，但未追问交接方式 | 还需追问 `handover` |
| HV-09 | 只追问预算，未询问猫粮存放位置 | 还需追问 `supplies_location` |
| EB-06 | 只追问送达地点 | 还需追问交接方式 `handover` |

以下两项不应计入真实追问不足：

- `HV-14` 实际没有追问喂食份量；评估器因预算问题中的“多少”命中 `food_portion` 宽泛关键词而误判。
- `HV-15` 已询问“下周一至周三”日期范围和每天晚上的起止时间，只是没有命中 `recurring_schedule_scope` 的有限关键词。

### 2.4 AI 自行编造信息

未发现可以确认的编造案例。模型新增的 `requirements`、`precautions` 或 completion condition 基本都能追溯到用户原文或固定流程。

需要注意的边界行为：

- `DW-05` 在宠物未选择时仍生成通用 pickup/departure/return 描述，但这是遛狗 Schema 要求的固定流程，不属于凭空生成用户事实。
- `HV-08` 将时长保持为 `null` 并追问，反而比人工标注直接期望 60 分钟更符合“不猜测时长”的规则。

### 2.5 测试程序过于严格或标注存在争议

#### Checklist 字面匹配

涉及 29 个案例、63 个 expected checklist 项。评估器同时要求 `item_key`、`pet_id` 和 `content_keywords` 字面匹配，导致大量语义正确输出失败。

- home_visit：模型使用 `feed_cat_food`、`feeding`、`medication`、`water_refill`、`clean_litter_box` 等语义键，而标注要求 `feed_food`、`give_medicine`、`change_water`、`clean_litter`。
- dog_walking：三项的 `pickup/departure/return` 顺序和 pet_id 通常正确，但“接到旺财”与“接走宠物”、“送回旺财”与“交还宠物”等同义表达不能通过关键词检查。
- 有些时长写在 `return` 而非 `departure`，仍被判 checklist 失败。
- `EB-01` 的“送至春和社区东门”未命中“送到社区东门”，属于明显误判。

#### 字段精确比较

涉及 22 个案例。常见误判包括：

- `门禁由宠主远程开启` 与 `门禁由用户远程开启`。
- `门禁远程开启` 与 `门禁远程开`。
- `在社区东门当面交付` 与 `在东门当面交付`。
- `交接时当面给宠主` 与 `交接时当面给我`。
- `precautions` 仅相差句号。
- `HV-06` 的 `pet_ids` 内容相同但顺序不同。
- `DW-15` 用 UUID 指代宠物，人工标注在文本字段中使用名字；Prompt 又要求正式输出只使用 UUID，标注与 Prompt 存在张力。

#### 数据集或接口上下文争议

- `HV-08`：用户只给出 10:00–11:00 服务窗口，没有给出预计执行时长。模型输出 `null` 并追问；人工预期为 60。按“不猜测时长”规则，模型更合理。
- `HV-15`：用户明确“每次20分钟”，模型保留 20 并追问日期范围和每天起止时间；人工预期将 duration 设为 `null`。是否因单次 draft 无法表达周期而清空每次时长，需要重新明确标注政策。
- `EB-03`：文本只说“帮我买东西”，没有提及年糕。批量程序只把宠物档案传给 `pets`，没有把数据集的 `input.pet_ids` 作为已选择宠物传给 parser。模型输出空 `pet_ids` 并追问关联宠物是合理的；人工预期自动关联唯一 fixture，存在上下文定义不一致。

### 2.6 Schema 验证失败

| case_id | 实际表现 | Schema/人工预期 |
|---|---|---|
| EB-02 | `purchase` 缺少 `product_name`、`quantity`、`unit` | 三个字段仍为 required；应分别输出猫粮、1、袋 |
| EB-09 | `purchase` 缺少 `product_name`、`quantity`、`unit` | 三个字段仍为 required；应输出冻干零食、1、包；共同商品 `pet_id=null` |

这两条的自然语言内容基本正确，但结构化输出不完整，因此 parser 按设计拒绝返回成功结果。

## 3. 按服务类型逐条分析

### 3.1 home_visit（14 Failed，0 Error）

| case_id | 主要分类 | 实际输出表现 | 人工预期/结论 |
|---|---|---|---|
| HV-01 | 字段归位；测试过严 | 照料事项重复进入 requirements；`feed_cat_food` 未匹配 `feed_food`；交接说明为同义改写 | requirements 为 null；checklist 语义实际完整 |
| HV-02 | 字段归位；测试过严 | 事项重复进入 requirements；两条喂食项使用带编号的自定义 key | requirements 为 null；实际分别关联两只猫，语义正确 |
| HV-03 | 测试过严 | “远程开/远程开启”及自定义 item_key 被判失败 | 时间、预算和喂食份量追问均正确 |
| HV-04 | 字段归位；测试过严 | 喂食刻度重复进入 requirements；自定义 item_key | requirements 为 null；时长追问正确 |
| HV-05 | 测试过严 | 仅交接说明同义改写失败 | 模糊时间和照料事项均有追问 |
| HV-06 | 字段归位；测试过严 | pet_ids 仅顺序不同；用药说明重复进入 requirements；使用 `medication/water_refill` | 实际宠物关联和药量均正确 |
| HV-07 | 追问不足；键名漂移 | 追问预算、药名和药量，但没问交接；`medication` 未匹配 `give_medicine` | 应补问 handover |
| HV-08 | 标注争议；键名漂移 | 时长为 null 并追问；任务关联正确但 key 不同 | 人工预期 60 分钟可能违反“不猜测时长” |
| HV-09 | 追问不足；键名漂移 | 未追问猫粮位置；使用 `feeding` | 应补问 supplies_location |
| HV-10 | 测试过严 | precautions 仅多句号；“更换饮用水”未命中字面“换水” | 实际语义正确 |
| HV-12 | 字段归位；键名漂移 | 喂食量重复进入 requirements；`feed_cat_food` | 应仅在 checklist 表达；交接和紧急联系人追问正确 |
| HV-13 | 字段归位；键名漂移 | 喂食要求重复进入 requirements | 时长冲突追问正确，未保留矛盾时长 |
| HV-14 | 评估器误判；字段归位 | 没有追问喂食份量；“不要喂食”进入 precautions | `food_portion` 失败由“预算金额是多少”误命中；照料 checklist 正确 |
| HV-15 | 标注争议；评估关键词不足 | 保留每次20分钟，追问日期范围和每天起止时间 | 是否应清空 duration 有争议；实际已有周期范围追问 |

### 3.2 dog_walking（15 Failed，0 Error）

| case_id | 主要分类 | 实际输出表现 | 人工预期/结论 |
|---|---|---|---|
| DW-01 | 字段归位；测试过严 | 路线与安全信息均保留，但“全程牵引”放入 precautions；checklist 使用同义措辞 | 信息完整，主要是字段边界和字面匹配问题 |
| DW-02 | 测试过严 | 三个固定 key、顺序和 pet_id 正确；未逐字出现标注关键词 | 模糊时间追问正确 |
| DW-03 | 测试过严 | 三个固定项语义正确 | 时长追问正确 |
| DW-04 | 字段归位；测试过严 | 牵引要求进入 precautions；时长写在 return | 应进入 requirements；其余语义正确 |
| DW-05 | 测试过严 | 生成通用固定流程，字面不匹配 | pet_ids 为空并追问宠物、交接等缺失信息，行为合理 |
| DW-06 | 测试过严 | 三个固定项均正确，以“宠物”替代名字 | 语义正确 |
| DW-07 | 字段信息拆分；测试过严 | 避让要求在 requirements，紧张特点在 precautions | 合并看信息完整，但 precautions 不够完整 |
| DW-08 | 键名漂移；测试过严 | 喝水项使用 `water`，其余三项正确 | 应统一为 `give_water` |
| DW-09 | 测试过严 | 三个固定项语义正确 | fee_type 和预算均正确追问 |
| DW-10 | 测试过严 | 三个固定项语义正确 | 地点、交接、紧急联系人均正确追问 |
| DW-11 | 测试过严 | 三个固定项语义正确 | 正确识别30分钟窗口与60分钟时长冲突并追问 |
| DW-12 | 测试过严 | 三个固定项语义正确，时长在 return | fee_type 明确后未重复追问，符合预期 |
| DW-13 | 字段归位；测试过严 | 正确只选择豆豆，但把排除旺财写入 precautions | precautions 应为 null；核心选择正确 |
| DW-14 | 测试过严 | precautions 仅为同义改写和标点差异；三项语义正确 | 安全要求完整保留 |
| DW-15 | 标注/Prompt 张力；测试过严 | precautions 用 UUID 区分宠物；三项共同事项正确 | Prompt 禁止正式输出宠物名字，模型行为有依据 |

### 3.3 errand_buy（4 Failed，2 Error）

| case_id | 主要分类 | 实际输出表现 | 人工预期/结论 |
|---|---|---|---|
| EB-01 | 测试过严 | “送至春和社区东门”未命中“送到社区东门”；交接说明为简称 | 商品、规格、数量、预算和交付语义均正确 |
| EB-02 | Schema 失败；字段遗漏 | purchase 未输出三个商品字段 | required 字段必须存在 |
| EB-03 | 输入上下文/标注争议 | 文本未提宠物，模型 pet_ids=[] 并追问关联宠物；三个商品字段均为 null | 标注预期自动关联唯一 fixture，但 runner 没传“已选 pet_id”语义 |
| EB-06 | 追问不足 | 只问送达地点 | 还应追问 handover |
| EB-09 | Schema 失败；字段遗漏 | purchase 未输出三个商品字段 | required 字段必须存在；共同商品 pet_id=null 正确 |
| EB-11 | 测试过严 | “当面给我”与“当面给宠主”精确比较失败 | fee_type 追问正确；核心语义一致 |

## 4. 出现频率最高的 5 个问题

1. **Checklist 字面匹配或 item_key 不统一：29 个案例、63 个标注项。** 这是当前失败数最大的来源，包含大量语义正确但措辞不同的输出。
2. **字段采用精确字符串/数组比较：22 个案例。** handover_notes、requirements、precautions、pet_ids 顺序和标点尤其明显。
3. **信息字段归位不稳定：至少 12 个案例。** 主要是照料事项重复进入 requirements，以及路线、牵引、安全信息在 requirements/precautions 之间漂移。
4. **必要追问遗漏：3 个明确案例。** `HV-07`、`HV-09`、`EB-06`。
5. **purchase required 字段遗漏导致 Schema 失败：2 个案例。** `EB-02`、`EB-09`。


