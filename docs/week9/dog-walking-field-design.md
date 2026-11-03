# 上门遛狗（dog_walking）AI 字段设计

## 产品规则与宠物范围

- `service_type` 固定为 `dog_walking`，已与后端枚举对齐。
- 每次任务固定生成 `pickup`、`departure`、`return` 三个清单节点，顺序不变。
- 默认全程使用牵引绳并处理宠物排泄物，不就这两项向用户补问。
- 行为特点优先读取 `PetProfile.temperament`、`precautions`、`care_instructions`，结合用户明确提供的信息；均无信息时可以简单询问。
- 宠主档案只有一只狗时自动确定目标；有多只狗且目标未明确时必须询问本次遛哪只或哪几只。
- `target_dogs` 为狗名字组成的字符串数组；需要数量时通过 `target_dogs.length` 计算，不单独保存 `dog_count`。名字须解析到宠主所属、物种为 dog 的档案，重名需消歧。
- 路线可选；服务时间和遛狗时长必须明确。喂水、喂食等附加任务只在用户明确提出时生成，不替代三个固定节点。

## AI 字段

草稿阶段尚未获取的值可以为 `null`，未确定目标时 `target_dogs` 为 `[]`；标为最终必填的字段未补齐前不能创建需求。

| 字段名 | 含义 | 数据类型 | 必填与补问规则 |
|---|---|---|---|
| `service_type` | 服务类型 | 字符串 | 固定为 `dog_walking` |
| `target_dogs` | 本次遛狗对象 | 字符串数组 | 最终必须明确；一只狗自动选定，多只狗未指定则必须补问 |
| `service_time` | 服务开始时间或时间范围，AI 中间字段 | 字符串或 null | 缺失或模糊必须补问，最终转换为具体窗口 |
| `duration_minutes` | 遛狗时长，分钟 | 正整数或 null | 缺失必须补问；映射后不得超过服务窗口分钟数 |
| `route_note` | 路线或活动范围 | 字符串或 null | 可选追问，不阻塞需求草稿 |
| `behavior_notes` | 档案或用户提供的行为特点 | 字符串或 null | 两者均缺失时可以简单询问；不自行编造 |
| `precautions` | 其他注意事项 | 字符串或 null | 可空 |
| `handover_notes` | 接送交接说明 | 字符串或 null | 已有资料或页面提供则不重复问；最终创建必填 |
| `location` | 接送或执行地点 | 字符串或 null | 资料或页面可提供；最终创建必填 |
| `fee_type` | `free` 或 `paid` | 字符串或 null | 资料或页面可提供；最终创建必填 |
| `budget` | 服务费上限 | 数字或 null | 资料或页面可提供；最终创建必填且不小于 0 |
| `questions[]` | 必要及可选补问 | 字符串数组 | 无待问问题时为 `[]`；可选问题不阻塞草稿 |
| `care_items` | 固定节点及用户明确要求的附加任务 | 对象数组 | 至少包含下述三个节点 |

## care_items

每项包含 `item_key`（字符串）、`content`（字符串）、`special_note`（字符串或 null）。`special_note` 为 AI 内部字段，最终拼接到相关 `ChecklistItem.content`，不新增数据库字段。

| item_key | content 要求 |
|---|---|
| `pickup` | 接到狗并确认牵引装备 |
| `departure` | 出发并执行遛狗；包含全程使用牵引绳、处理宠物排泄物、遛狗时长，以及已提供的路线要求和行为注意事项 |
| `return` | 安全送回并完成交接 |

时长未明确的草稿可以注明“时长待确认”，但必须补问并在最终创建前更新清单，不把占位文本作为已确认要求。

## 补问规则

- `service_time` 缺失，或仅“明天下午”“晚上”“尽快”等无法转换为具体时间窗口时，必须补问。
- `duration_minutes` 缺失时必须补问。
- 档案有多只狗而 `target_dogs` 未明确时，必须询问目标，不默认全选。
- 档案和输入均没有行为特点时，可以简单询问；有信息则不重复询问。
- `route_note` 缺失可以可选追问，不阻塞需求草稿。
- 不补问是否使用牵引绳、是否处理排泄物，不默认添加喂水或喂食。
- `handover_notes`、`location`、`fee_type`、`budget` 等后端必填字段未由资料或页面提供时，必须由前端或后端在最终创建前补齐，不能将缺失值直接提交。

## AI 草稿与最终创建请求

本文件的 JSON 是 AI 内部需求草稿，不是 `POST /requests` 请求体，也不是直接照搬的 `POST /ai/parse` 响应；后者约定为 `draft{需求创建字段}, questions[]`，需经适配层转换。

转换时间时使用解析请求的 `reference_time` 和 `timezone`，不臆造日期或时间。明确开始时间和时长后才能形成具体窗口；窗口结束晚于开始，`expected_duration_minutes` 必须大于 0 且不超过窗口分钟数。涉及接送交接的窗口边界见待后端确认。

最终创建还必须提供 `emergency_contact`（可从资料或页面补齐），以及后端要求的 `pet_id` 和完整 `checklist_items`。按固定顺序生成 `position`，补齐明确的 `completion_condition`、`required`；后端生成 id、request_version、execution_status。非代买任务的 `product_name`、`quantity`、`unit` 均不使用并保持全空。未补齐必填项或存在未解决的多狗映射时，不直接创建需求。

## AI 字段到后端字段映射

| AI 字段或输入 | 后端字段 | 说明 |
|---|---|---|
| `service_type` | `ServiceRequest.service_type` | `dog_walking` 已在后端枚举中 |
| `target_dogs` | 无同名数据库字段 | 单只狗经档案解析得到 `ServiceRequest.pet_id`；多只狗映射待确认 |
| `service_time` | `ServiceRequest.window_start` + `ServiceRequest.window_end` | 转换为带时区具体时间窗口 |
| `duration_minutes` | `ServiceRequest.expected_duration_minutes` | 正整数且不超过窗口分钟数 |
| `location` | `ServiceRequest.location` | 最终必填 |
| `budget` | `ServiceRequest.budget` | 最终必填，非负服务费上限 |
| `precautions` 和 `behavior_notes` | `ServiceRequest.precautions`，或相关 `ChecklistItem.content` | 保留注意事项；已知行为特点也写入 departure 文本 |
| `route_note` | 相关 `ChecklistItem.content` | 有要求时写入 departure 文本，无新增字段 |
| `handover_notes` | `ServiceRequest.handover_notes` | 最终必填 |
| `fee_type` | `ServiceRequest.fee_type` | `free` / `paid` |
| `care_items` | `ChecklistItem` | 转换为 `checklist_items` 并补齐后端必填属性 |
| `care_items[].item_key` | `ChecklistItem.item_key` | 固定包含 pickup/departure/return |
| `care_items[].content` | `ChecklistItem.content` | 非空清单文本 |
| `care_items[].special_note` | 拼接到 `ChecklistItem.content` | AI 内部字段，不新增列 |
| 用户原始输入 | `ServiceRequest.raw_text` | 保留原始文本 |
| `questions[]` | 无数据库字段 | AI 解析接口补问列表，不落库为新列 |

## JSON 示例一：单只狗

用户输入：“明晚七点帮我遛旺财半小时，在小区里走。它见到大狗会害怕。”

假设档案仅有一只狗旺财。下列为尚未补齐资料和页面字段的 AI 草稿：

```json
{
  "service_type": "dog_walking",
  "target_dogs": ["旺财"],
  "service_time": "明晚19:00开始，持续30分钟",
  "duration_minutes": 30,
  "route_note": "在小区里走",
  "behavior_notes": "见到大狗会害怕",
  "precautions": null,
  "handover_notes": null,
  "location": null,
  "fee_type": null,
  "budget": null,
  "questions": [],
  "care_items": [
    {
      "item_key": "pickup",
      "content": "接到旺财并确认牵引装备",
      "special_note": null
    },
    {
      "item_key": "departure",
      "content": "出发并遛狗30分钟；全程使用牵引绳，处理宠物排泄物；在小区里走；旺财见到大狗会害怕",
      "special_note": null
    },
    {
      "item_key": "return",
      "content": "将旺财安全送回并完成交接",
      "special_note": null
    }
  ]
}
```

`questions` 为空仅代表当前没有 AI 补问，不代表已满足最终创建的全部必填要求。

## JSON 示例二：多只狗

用户输入：“明天下午帮我遛旺财和豆豆四十分钟。”

假设档案确认旺财和豆豆均为宠主的狗，但没有行为特点信息。目标已明确，不重复问遛哪只；具体时间必须补问：

```json
{
  "service_type": "dog_walking",
  "target_dogs": ["旺财", "豆豆"],
  "service_time": "明天下午",
  "duration_minutes": 40,
  "route_note": null,
  "behavior_notes": null,
  "precautions": null,
  "handover_notes": null,
  "location": null,
  "fee_type": null,
  "budget": null,
  "questions": [
    "明天下午希望几点开始，具体服务时间范围是什么？",
    "旺财和豆豆有什么需要注意的行为特点吗？",
    "对路线或活动范围有要求吗？（可选）"
  ],
  "care_items": [
    {
      "item_key": "pickup",
      "content": "接到旺财和豆豆并确认牵引装备",
      "special_note": null
    },
    {
      "item_key": "departure",
      "content": "出发并遛狗40分钟；全程使用牵引绳，处理宠物排泄物",
      "special_note": null
    },
    {
      "item_key": "return",
      "content": "将旺财和豆豆安全送回并完成交接",
      "special_note": null
    }
  ]
}
```

## 后端兼容性检查

依据此前上传的《邻宠帮 · 接口对齐文档 v0（完整版）》：`dog_walking` 枚举、三个固定 item_key、dog 物种限制及以上目标字段均已有定义。预算非负、时长为正且不超过窗口、必填请求属性与清单属性按原契约校验。行为档案字段使用已有 `PetProfile` 属性；AI 扩展信息通过现有文本字段表达，不新增数据库字段，也不修改后端文档。

## 待后端确认

- **真实冲突：多狗任务与单个 pet_id。** 后端 `ServiceRequest.pet_id` 为必填 UUID，明确单次服务对应一只宠物；本产品允许 `target_dogs` 包含多只狗。目前没有合法的一对多映射。需协商支持方式；本设计不自行新增字段、不擅自拆单、不任意选一只狗作为全部狗的代表。多狗示例仅为 AI 草稿，问题解决前不能直接创建单个需求。
- **时间转换边界待明确。** 已知开始时间和遛狗时长后，接狗、送回交接是否包含在服务窗口和 `expected_duration_minutes` 中，需要确认；仍须遵守时长不超过窗口的既有约束，不自行扩展或缩短用户时间。

其余字段映射未发现名称或类型冲突。AI 草稿转换为最终创建请求时仍需补齐上述既有必填字段，此为适配要求，不是新增数据库设计。
