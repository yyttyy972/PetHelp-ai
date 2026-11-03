# 上门代看（home_visit）AI 字段设计

## 默认宠物范围

默认照看宠主档案中的全部相关宠物，不要求用户逐只选择宠物。只有用户提到特殊情况时，才在具体照料事项中指定某只宠物。例如：“家里的猫都喂一次粮，小橘需要额外喂药。”

## AI 需求字段

| 字段名 | 含义 | 数据类型 | 是否必填 | 缺失或补问规则 |
|---|---|---|---|---|
| `service_type` | 服务类型，固定为 `home_visit` | 字符串 | 是 | 默认识别为上门代看；无法确认时通过 `questions[]` 确认 |
| `care_items` | 上门代看的照料事项列表 | 数组 | 是 | 没有照料事项时，必须通过 `questions[]` 询问 |
| `supplies_location` | 猫粮、药品等用品的位置 | 字符串 | 否 | 提到喂食、用药等需要用品但未说明位置时，可以追问 |
| `service_time` | 期望的上门服务时间范围；AI 中间字段 | 字符串 | AI 草稿阶段可暂时为空；最终创建前必填 | 没有具体时间，或仅说“晚上”“尽快”等模糊时间时，必须通过 `questions[]` 询问具体时间范围 |
| `location` | 上门服务地点 | 字符串 | 是 | 缺失时通过 `questions[]` 询问 |
| `precautions` | 注意事项和禁止事项 | 字符串 | 否 | 可以为空 |
| `handover_notes` | 交接方式和入户交接说明 | 字符串 | 视最终创建请求而定 | 若用户资料或前端未提供，需由前端或后端补齐 |
| `emergency_contact` | 异常情况联系人及联系方式 | 字符串 | 视最终创建请求而定 | 若用户资料或前端未提供，需由前端或后端补齐 |
| `fee_type` | 服务费用类型，如 `free` 或 `paid` | 字符串 | 视最终创建请求而定 | 若用户资料或前端未提供，需由前端或后端补齐 |
| `budget` | 服务预算或费用上限 | 数字 | 视最终创建请求而定 | 若用户资料或前端未提供，需由前端或后端补齐 |
| `questions[]` | AI 补问列表 | 字符串数组 | 否 | 仅列出仍影响创建需求的必要问题 |

### `care_items` 子项

`care_items` 为数组，每项包含：

| 字段名 | 含义 | 数据类型 | 缺失时处理 |
|---|---|---|---|
| `content` | 照料事项，例如“喂猫粮” | 字符串 | 事项必须有明确内容；缺失时通过 `questions[]` 询问 |
| `frequency` | 次数或频率 | 字符串 | 未说明时，可通过 `questions[]` 补问或根据用户明确语义保留为空 |
| `target_pet` | 特殊情况下指定的宠物；普通事项为 `null` | 字符串或 `null` | 默认 `null`，不要求逐只选择宠物 |
| `special_note` | 额外要求 | 字符串或 `null` | 没有额外要求时为 `null` |

`target_pet` 仅用于清单文本中的特殊宠物说明，第一版不新增数据库字段。

## 补问规则

- 没有照料事项时，必须通过 `questions[]` 询问。
- 没有具体服务时间时，必须通过 `questions[]` 询问。
- 用户只说“晚上”“尽快”等模糊时间时，必须继续询问具体时间范围。
- 用户提到喂食、用药等需要用品的事项，但没有说明用品位置时，可以追问 `supplies_location`。
- `precautions` 可以为空。
- `emergency_contact`、`handover_notes`、`fee_type`、`budget` 如果已有用户资料或前端页面提供，AI 不重复询问；如果最终创建需求仍缺失，必须说明需要前端或后端补齐。

## AI 需求草稿与最终创建请求

AI 输出的是需求草稿，不等于最终 `ServiceRequest` 创建请求。`service_time` 在 AI 解析阶段可以暂时为空，但最终创建前必须转换为具体的 `window_start` 和 `window_end`。`emergency_contact`、`handover_notes`、`fee_type`、`budget` 等字段可以由前端页面、用户资料或平台默认值补齐；补齐后才能提交最终创建请求。

## AI 字段到后端字段映射

| AI 字段或输入 | 后端字段 | 映射说明 |
|---|---|---|
| `service_type` | `ServiceRequest.service_type` | 直接映射服务类型 `home_visit` |
| `service_time` | `ServiceRequest.window_start` + `ServiceRequest.window_end` | 具体时间范围转换后映射；模糊时间必须先补问 |
| `location` | `ServiceRequest.location` | 映射上门服务地点 |
| `budget` | `ServiceRequest.budget` | 映射预算；若最终创建仍缺失，由前端或后端补齐 |
| `precautions` | `ServiceRequest.precautions` | 映射注意事项，可为空 |
| `handover_notes` | `ServiceRequest.handover_notes` | 映射交接说明；可由前端或用户资料补齐 |
| `emergency_contact` | `ServiceRequest.emergency_contact` | 映射异常联系人；可由前端或用户资料补齐 |
| `fee_type` | `ServiceRequest.fee_type` | 映射费用类型；可由前端或平台默认值补齐 |
| `care_items[].content` | `ChecklistItem.content` | 直接作为照料事项文本 |
| `care_items[].frequency` 和 `special_note` | `ChecklistItem.content` | 拼接到清单文本中，形成频率和额外要求说明 |
| `care_items[].target_pet` | `ChecklistItem.content` | 拼接为特殊宠物说明；第一版不新增数据库字段 |
| 用户原始需求 | `ServiceRequest.raw_text` | 保存用户提交的原始自然语言需求 |

`supplies_location` 属于 AI 字段。若用品位置需要进入清单，应由 AI 拼接到相关 `ChecklistItem.content`；本设计不新增后端数据库字段。

## JSON 示例一：普通情况

用户输入：

> 家里的猫都喂一次粮、换一次水，明天下午上门，地点是我家。

AI 需求草稿：

```json
{
  "service_type": "home_visit",
  "care_items": [
    {
      "content": "喂猫粮",
      "frequency": "1次",
      "target_pet": null,
      "special_note": null
    },
    {
      "content": "换水",
      "frequency": "1次",
      "target_pet": null,
      "special_note": null
    }
  ],
  "supplies_location": null,
  "service_time": "明天下午（示例：14:00-17:00）",
  "location": "我家",
  "precautions": null,
  "handover_notes": null,
  "emergency_contact": null,
  "fee_type": null,
  "budget": null,
  "questions": []
}
```

## JSON 示例二：特殊宠物情况

用户输入：

> 家里的猫都喂一次粮，但小橘需要额外喂药。明天晚上来我家。

AI 需求草稿：

```json
{
  "service_type": "home_visit",
  "care_items": [
    {
      "content": "喂猫粮",
      "frequency": "1次",
      "target_pet": null,
      "special_note": null
    },
    {
      "content": "喂药",
      "frequency": "额外1次",
      "target_pet": "小橘",
      "special_note": "按宠主提供的用药说明执行"
    }
  ],
  "supplies_location": null,
  "service_time": "明天晚上",
  "location": "我家",
  "precautions": null,
  "handover_notes": null,
  "emergency_contact": null,
  "fee_type": null,
  "budget": null,
  "questions": [
    "明天晚上具体的上门时间范围是什么？",
    "猫粮和药品放在哪里？"
  ]
}
```

## 待后端确认

- `service_time` 的自然语言时间范围如何按 `reference_time`、`timezone` 转换为 `window_start` 和 `window_end`，以及默认时长或时间窗口规则。
- `care_items[].frequency`、`special_note`、`target_pet` 拼接进 `ChecklistItem.content` 时的统一文本格式。
- 默认照看宠主档案中全部相关宠物时，后端如何通过 `pet_id`（当前创建接口要求单个 `pet_id`）表达该范围；是否由后端根据宠物档案展开清单。
- `expected_duration_minutes` 是后端创建接口必填字段，但本 AI 字段设计未单独提取；其来源需要由前端、用户资料或平台默认值确定。
- `supplies_location` 是否优先读取 `PetProfile.supplies_location`，以及在多宠物或不同用品位置时如何处理。

