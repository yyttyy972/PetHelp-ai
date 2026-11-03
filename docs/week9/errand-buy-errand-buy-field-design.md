# 宠物用品代买 AI 字段设计

## AI 字段

| 字段名 | 含义 | 数据类型 | 是否必填 | 缺失时的补问方式 |
|---|---|---|---|---|
| `service_type` | 服务类型；`errand_buy` 已与后端 `service_type` 枚举对齐 | 字符串 | 是 | “请确认您需要的是宠物用品代买服务吗？” |
| `product_name` | 要购买的宠物用品名称 | 字符串 | 仅 `service_type = errand_buy` 时必填 | “请问需要购买什么商品？” |
| `product_detail` | AI 内部商品细节，可包含品牌、种类、口味、规格、型号等信息 | 字符串 | 否 | 用户未提供时，可在 `questions[]` 中询问：“对品牌、种类、口味、规格或型号有要求吗？” |
| `quantity` | 购买数量 | 数字 | 仅 `service_type = errand_buy` 时必填 | “请问需要购买多少？” |
| `unit` | 数量单位，如袋、盒、件 | 字符串 | 仅 `service_type = errand_buy` 时必填 | “请问数量的单位是什么，例如袋、盒或件？” |
| `budget_max` | 可接受的最高预算，通常以人民币计 | 数字 | 是 | 后端 `ServiceRequest.budget` 为必填；用户未提供时，在 `questions[]` 中询问：“您的预算上限是多少？” |
| `delivery_location` | 商品交付地点 | 字符串 | 是 | “请问需要送到哪里？” |
| `delivery_time` | AI 中间字段，表示期望的送达时间或时间范围 | 字符串 | AI 解析阶段可暂时为空；最终创建 `ServiceRequest` 前必须转换为 `window_start` 和 `window_end` | 只说“尽快”等无法转换为具体时间范围的表达时，必须在 `questions[]` 中继续询问具体时间范围 |
| `precautions` | 购买或交付时需要特别注意的事项 | 字符串 | 否 | “还有需要特别注意的事项吗？” |

`product_detail` 是 AI 内部字段，不是数据库字段，不直接新增数据库列；最终可以由 AI 模块拼接到 `ChecklistItem.content` 的清单文本中。

在 `service_type = errand_buy` 的代买场景下，`product_name`、`quantity`、`unit` 必须同时存在；其他服务类型不使用这组三个商品字段。

## 补问列表

`questions[]` 定义为补问列表，与 `POST /ai/parse` 的返回字段保持一致：

- 用户没有提供 `product_detail` 时，可以提出相关可选补问；用户明确表示不需要或不在意时，可不再追问。
- 用户明确表示“不在意”“随便买”时，`questions[]` 为空数组。
- 用户不回答可选问题时，仍可继续提交，不阻塞代买请求。
- 用户未提供必填的 `budget_max` 时，必须加入补问，不能直接创建需求。
- `delivery_time` 无法转换为具体时间范围时，必须继续询问具体时间范围；在最终创建 `ServiceRequest` 前必须完成转换。

## AI 解析结果与最终创建请求的区别

AI 输出的是需求草稿，不等于最终的 `ServiceRequest` 创建请求。`fee_type`、`expected_duration_minutes`、`handover_notes`、`emergency_contact` 等字段可以来自前端页面、用户资料或平台默认值，后续由前端和后端补齐后，才能提交最终创建请求。

## AI 字段到后端字段映射

| AI 字段或输入 | 后端字段 | 映射说明 |
|---|---|---|
| `product_name` | `ChecklistItem.product_name` | 代买场景直接映射商品名称；仅 `errand_buy` 使用 |
| `quantity` | `ChecklistItem.quantity` | 代买场景直接映射购买数量；仅 `errand_buy` 使用 |
| `unit` | `ChecklistItem.unit` | 代买场景直接映射数量单位；仅 `errand_buy` 使用 |
| `product_detail` | 无直接数据库字段；内容进入 `ChecklistItem.content` | 将品牌、种类、口味、规格、型号等细节拼接到清单文本中 |
| `budget_max` | `ServiceRequest.budget` | 后端预算字段必填；缺失时必须通过 `questions[]` 补问 |
| `delivery_location` | `ServiceRequest.location` | 映射交付地点 |
| `delivery_time` | `ServiceRequest.window_start` + `ServiceRequest.window_end` | AI 解析阶段可暂时为空；最终创建前必须完成具体时间范围转换；“尽快”等无法转换的表达需先补问 |
| `precautions` | `ServiceRequest.precautions` | 映射注意事项 |
| 用户原始文本 | `ServiceRequest.raw_text` | 保存用户提交的原始输入 |

## JSON 示例

用户输入：

> 帮我买一袋猫粮，预算100元以内，送到社区东门。

示例输出（AI 需求草稿）：

```json
{
  "service_type": "errand_buy",
  "product_name": "猫粮",
  "product_detail": null,
  "quantity": 1,
  "unit": "袋",
  "budget_max": 100,
  "delivery_location": "社区东门",
  "delivery_time": null,
  "precautions": null,
  "questions": [
    "对品牌、种类、口味、规格或型号有要求吗？",
    "希望具体什么时候送达？"
  ]
}
```

如果用户回复“不在意”或“随便买”，则示例补问结果为：

```json
{
  "product_detail": null,
  "questions": []
}
```
