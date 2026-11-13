# 邻宠帮 · D组匹配与验证说明

## 一、 匹配规则说明

### 1. 匹配硬性过滤（一票否决制）
所有规则均基于B组接口文档第2节的表结构字段，按以下顺序逐项校验，任意一项不满足则直接过滤。

| 序号 | 规则名称 | 校验字段 | 判断逻辑 |
| :--- | :--- | :--- | :--- |
| 1 | 社区一致性 | `User.community_code` | 帮手与需求方的社区代码必须相同 |
| 2 | 角色匹配 | `HelperProfile.service_types` | 需求 `service_type` 必须存在于帮手 `service_types` 数组中 |
| 3 | 宠物种类匹配 | `HelperProfile.supported_species` | 若服务为 `home_visit` 或 `dog_walking`，需求 `PetProfile.species` 必须在帮手支持范围内 |
| 4 | 费用偏好兼容 | `HelperProfile.fee_pref` & `ServiceRequest.fee_type` | `fee_type=free` 需帮手偏好为 `free` 或 `both`；`fee_type=paid` 需帮手偏好为 `paid` 或 `both` |
| 5 | 时间包含 | `Availability.start_at/end_at` | 需求 `window_start` 和 `window_end` 必须完整落在帮手某条可用时间记录内 |
| 6 | 时间冲突（防并发） | `Booking.scheduled_start/scheduled_end` | 需求时间段不能与帮手已有占用状态的预约重叠 |
| 7 | 服务范围（首版简化） | `HelperProfile.service_radius_m` | 首版暂不接地图API，通过 `address_tag` 与需求 `location` 是否同小区/同栋进行过滤 |

**时间冲突判断公式：**
- 冲突条件：`新任务开始 < 已有任务结束 AND 新任务结束 > 已有任务开始`
- 占用状态包含：`pending_confirm`（未过期）、`reserved`、`in_service`、`pending_verify`、`exception`
- 不占用状态：`completed`、`cancelled`

### 2. 推荐排序规则（软约束）
通过硬性过滤的候选人，按以下优先级降序排列，并作为 `reasons` 字段返回给前端A展示：

| 优先级 | 排序维度 | 具体规则 |
| :--- | :--- | :--- |
| 1 | 信用度 | `verification_status` 为 `verified` 的排在 `unverified` 前面 |
| 2 | 地理就近 | `address_tag` 与需求 `location` 匹配度更高（如同栋楼）的优先 |
| 3 | 经验丰富度 | `HelperProfile.experience` 字段内容更丰富的优先（按字符串长度初步排序） |
| 4 | 费用偏好精确匹配 | `fee_pref` 精确匹配需求 `fee_type` 的优先于 `both` |

### 3. 匹配接口返回结构（对齐B组API清单）
`POST /api/v0/requests/{id}/match` 返回候选列表，每个候选包含以下字段供A组前端展示：
- `helper_id`：帮手UUID
- `display_name`：帮手名称
- `avatar_url`：头像URL
- `verification_status`：核验状态
- `fee_pref`：费用偏好
- `service_radius_m`：服务范围
- `address_tag`：小区内位置标签
- `reasons`：匹配理由数组（如 `["同小区", "支持犬类", "时间匹配", "信用良好"]`）

### 4. D组对B组待决定事项的建议（请B确认）
| 事项编号 | 事项 | D组建议 | 理由 |
| :--- | :--- | :--- | :--- |
| 事项1 | 身份核验怎么通过 | 首版演示数据直接置为 `verified`，不开发复杂核验流程 | A组候选卡需要展示信用标识，匹配排序也依赖此字段 |
| 事项4 | 预留有效期 | 15分钟合理，但计算时间冲突时必须把 `pending_confirm` 算作占用状态 | 防止一个帮手被两人同时锁定，产生并发抢单问题 |

---

## 二、 测试用例与Mock数据

### 1. 测试用例清单

| 用例编号 | 测试场景 | 输入数据简述 | 预期匹配结果 | 触发规则 |
| :--- | :--- | :--- | :--- | :--- |
| TC-01 | 完美匹配（正常流） | 需求：遛狗，10:00-11:00，2栋，paid。<br>帮手A：支持狗，同小区2栋，可用09:00-12:00，`fee_pref=both`。 | 匹配成功，排第1 | 全部满足 |
| TC-02 | 时间冲突（防重单） | 需求：代看，10:30-11:30。<br>帮手B：可用09:00-12:00，但已有 `reserved` 订单10:00-11:00。 | 匹配失败 | 规则6 |
| TC-03 | 宠物种类不符 | 需求：代看猫。<br>帮手C：`supported_species` 仅含狗。 | 匹配失败 | 规则3 |
| TC-04 | 费用偏好不符 | 需求：遛狗，`fee_type=paid`。<br>帮手D：`fee_pref=free`。 | 匹配失败 | 规则4 |
| TC-05 | 可用时间不含需求 | 需求：10:00-11:00。<br>帮手E：可用时间仅14:00-16:00。 | 匹配失败 | 规则5 |
| TC-06 | 服务类型不符 | 需求：`dog_walking`。<br>帮手F：`service_types` 仅含 `home_visit`。 | 匹配失败 | 规则2 |
| TC-07 | 多候选排序验证 | 需求：遛狗，10:00-11:00，2栋。<br>帮手G：`verified`，同栋，经验丰富。<br>帮手H：`unverified`，同小区不同栋，经验少。 | 匹配成功，G排在H前面 | 排序规则 |

### 2. Mock 数据（供A组第9周前端演示使用）

**需求数据（request_demo）：**

```json
{
  "id": "req-001-uuid",
  "service_type": "dog_walking",
  "window_start": "2026-11-10T10:00:00Z",
  "window_end": "2026-11-10T11:00:00Z",
  "expected_duration_minutes": 60,
  "location": "阳光小区2栋",
  "fee_type": "paid",
  "budget": "20.00",
  "community_code": "SUNSHINE_01"
}
