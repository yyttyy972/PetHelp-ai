# 邻宠帮业务规则知识库

整理平台当前版本的服务、预约、执行及匹配规则，用于 AI 规则问答与业务解释。

规则以当前后端实现和已确认的业务契约为依据。
对于文档与代码不一致的情况，单独标记，避免将历史规则或尚未实现的功能作为当前平台能力进行回答。

## 规则状态说明

- 已实现：当前代码已有对应功能。
- 部分实现：部分流程已实现，仍有功能缺失。
- 未实现：当前版本尚未提供对应功能。
- 待确认：跨组业务口径尚未最终确认。

## 服务类型

### BR-SVC-001

- rule_id: `BR-SVC-001`
- title: 代看服务（home_visit）的基本要求
- content: `home_visit` 按当前需求版本的清单逐项记录照料结果；执行记录类型为 `item_completed`。记录必须提供文字说明或照片，但照片存在本身不能自动证明照料正确。提交完成时，所有必需清单项必须为 `completed`，或为有宠主同版本审计事件支持的 `waived`。
- conditions: `ServiceRequest.service_type = home_visit`；`Booking.status = in_service` 时可新增执行记录；提交时核验 `Booking.request_version` 对应的清单。
- implementation_status: 部分实现（逐项记录和提交核验已实现；本周没有宠主批准 `waived` 的入口）
- source_file: `backend/docs/状态转换表.md`；`backend/app/routers/bookings.py`；`backend/docs/第11周自检记录.md`
- source_section: “服务类型核验”；`record()`、`complete_check()`；“限制”

### BR-SVC-002

- rule_id: `BR-SVC-002`
- title: 遛狗服务（dog_walking）的基本要求
- content: `dog_walking` 的关联宠物必须全部为犬类；当前版本清单及执行证据必须包含 `pickup`、`departure`、`return`，并按接狗→出发→送回的时间顺序记录。每条记录必须提供文字说明或照片。
- conditions: `ServiceRequest.service_type = dog_walking`；新增记录仅限帮手且 `Booking.status = in_service`；记录属于当前预约版本，`occurred_at` 不早于预约开始且不晚于数据库当前时间。
- implementation_status: 已实现
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`backend/app/routers/bookings.py`
- source_section: “服务类型核验”；“checklist_items 与 kind 约定”；`eligible()`、`record()`、`complete_check()`

### BR-SVC-003

- rule_id: `BR-SVC-003`
- title: 代买服务（errand_buy）的基本要求
- content: `errand_buy` 必须记录 `purchase` 和 `delivery`。购买记录必须有照片凭证及 `actual_cost`，实际商品费用不得超过 `ServiceRequest.budget`；交付时间不得早于购买时间。商品实际费用与服务报酬 `Booking.agreed_fee` 分开记录，完成核验时模拟结算合计为二者之和，不调用真实支付系统。
- conditions: `ServiceRequest.service_type = errand_buy`；新增记录仅限帮手且 `Booking.status = in_service`；非 `purchase` 记录不得填写 `actual_cost`。
- implementation_status: 已实现
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`backend/app/routers/bookings.py`；`backend/docs/第11周自检记录.md`
- source_section: “服务类型核验”；“候选卡与费用约定”；`record()`、`complete_check()`、`verify()`；“本地 PostgreSQL 与 FastAPI TestClient 实测通过”

## 预约生命周期

### BR-BOOK-001

- rule_id: `BR-BOOK-001`
- title: 建立预约与双方确认
- content: `pending_match` 的 `ServiceRequest` 可由宠主邀请帮手，或由该帮手本人申请，建立一个 `pending_confirm` 的 `Booking`；发起预约不等于确认。预约保存需求当前版本快照并预留 15 分钟。宠主和帮手须分别确认同一 `ServiceRequest.version`；第一方确认只写入自己的确认时间，双方均确认后，`Booking` 与 `ServiceRequest` 才进入 `reserved`。
- conditions: 建立时 `expected_version` 等于需求当前版本、无有效预约，且帮手、宠物、费用、窗口、可用时间和冲突检查通过；确认时预约未过期且 `Booking.request_version = ServiceRequest.version = expected_version`。
- implementation_status: 已实现
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`backend/app/routers/bookings.py`
- source_section: 状态转换表 `pending_match → pending_confirm → reserved`；REST 接口 `/requests/{id}/bookings`、`/bookings/{id}/confirm`；`create()`、`confirm()`

### BR-BOOK-002

- rule_id: `BR-BOOK-002`
- title: 预约确认超时
- content: 当 `Booking.status = pending_confirm` 且 `reserved_until` 不晚于数据库当前时间时，该 `Booking` 置为 `cancelled`，原因记为 `confirmation_timeout`，对应 `ServiceRequest` 回到 `pending_match`，释放预留。此处取消的是预约，不是终止整个需求。
- conditions: 超时判断使用数据库 `clock_timestamp()`；当前代码在确认该预约或为该需求再次建立预约时惰性处理。
- implementation_status: 部分实现（数据库时间、持久化取消和惰性检查已实现；文档所述后端定时扫描及提醒/通知未实现）
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`backend/app/routers/bookings.py`
- source_section: 状态转换表“确认超时”；“超时任务”；API 清单“确认超时”；`create()`、`confirm()`、`cancel()`

### BR-BOOK-003

- rule_id: `BR-BOOK-003`
- title: 宠主主动取消整个需求
- content: 宠主取消整个 `ServiceRequest` 时，需求进入终态 `cancelled`；若存在有效 `Booking`，该预约也同步进入 `cancelled`。该操作不会把需求重新开放为 `pending_match`。
- conditions: 仅宠主可操作；需求状态仅限 `draft`、`pending_match`、`pending_confirm`、`reserved`；必须提交当前 `expected_version` 和非空原因；服务开始后拒绝取消。
- implementation_status: 已实现
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`backend/app/routers/bookings.py`
- source_section: 状态转换表“宠主取消整个需求”；REST 接口及实现补充 `/requests/{id}/cancel`；`cancel_request()`

### BR-BOOK-004

- rule_id: `BR-BOOK-004`
- title: 帮手撤回或宠主撤回当前预约
- content: 服务开始前撤回当前预约时，只将 `Booking` 置为 `cancelled` 并记录原因；对应 `ServiceRequest` 回到 `pending_match`，可重新匹配。该操作不同于宠主取消整个需求。
- conditions: 操作者必须是预约宠主或预约帮手；`Booking.status` 仅限 `pending_confirm` 或 `reserved`；必须提供非空原因。
- implementation_status: 已实现
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`backend/app/routers/bookings.py`；`backend/docs/第11周自检记录.md`
- source_section: 状态转换表“帮手服务开始前退出或宠主撤回预约”；REST 接口 `/bookings/{id}/withdraw`；`withdraw()`、`cancel()`；“回归通过”

### BR-BOOK-005

- rule_id: `BR-BOOK-005`
- title: 重要需求修改
- content: 宠主修改重要内容时，`ServiceRequest.version` 加一并复制完整清单。若需求在 `pending_match`，旧推荐失效但仍保持 `pending_match`；若处于 `pending_confirm` 或 `reserved`，旧 `Booking` 必须先置为 `cancelled`，需求回到 `pending_match`，旧确认不再有效，之后须重新匹配并由双方确认。`in_service` 或 `pending_verify` 不允许直接 PATCH，须走异常流程。
- conditions: 重要字段包含当前 API 允许修改的需求内容，并明确包括 `fee_type`、`precautions`、`raw_text`；宠物名单和 `service_type` 不可通过该 PATCH 改变；须校验 `expected_version`。
- implementation_status: 部分实现（开始服务前的重要修改和版本失效已实现；进行中/待核验阶段所需的异常处理接口尚未实现）
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`backend/docs/第11周自检记录.md`
- source_section: 状态转换表“宠主重要修改”及“重要修改在 in_service/pending_verify”；REST 接口 `PATCH /requests/{id}` 与第 11 周实现补充；“回归通过”

### BR-BOOK-006

- rule_id: `BR-BOOK-006`
- title: 服务开始
- content: 只有预约帮手可以显式开始服务；成功后 `Booking` 与 `ServiceRequest` 同步由 `reserved` 进入 `in_service`，并记录开始事件。
- conditions: 双方确认时间均已存在；`Booking.request_version`、`ServiceRequest.version` 与 `expected_version` 一致；数据库当前时间满足 `scheduled_start <= now < scheduled_end`。
- implementation_status: 已实现
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`backend/app/routers/bookings.py`
- source_section: 状态转换表 `reserved → in_service`；REST 接口 `/bookings/{id}/start`；`start()`

## 执行、完成与核验

### BR-EXEC-001

- rule_id: `BR-EXEC-001`
- title: 执行记录的通用要求
- content: 只有预约帮手能为 `in_service` 的 `Booking` 新增 `ExecutionRecord`。记录必须对应该预约需求版本的清单项，`kind` 必须同时符合清单项 `item_key` 和服务类型，并至少提供 `note` 或 `photo_urls`；成功后将对应清单项标为 `completed` 并写入事件。宠主和该帮手可分页读取本预约记录。
- conditions: `Booking.status = in_service`；需求版本与预约版本一致；`occurred_at` 位于 `scheduled_start` 与数据库当前时间之间；照片引用须通过媒体权限校验。
- implementation_status: 已实现
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`backend/app/routers/bookings.py`
- source_section: 状态转换表“提交逐项执行证据”；REST 接口 `/bookings/{id}/records`；`record()`、`records()`

### BR-EXEC-002

- rule_id: `BR-EXEC-002`
- title: 帮手提交服务完成
- content: 帮手申请完成前，当前预约版本的所有必需清单项必须为 `completed`，或为经宠主批准并有对应同版本 `checklist_waived` 审计事件的 `waived`；此外遛狗必须具备三阶段记录，代买必须具备购买凭证、预算内实际费用和交付记录。通过后 `Booking` 与 `ServiceRequest` 进入 `pending_verify`。
- conditions: 仅预约帮手可操作；`Booking.status = in_service`；版本一致且提交 `expected_version`。
- implementation_status: 部分实现（完成校验和状态转换已实现；本周没有批准 `waived` 的入口）
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`backend/app/routers/bookings.py`；`backend/docs/第11周自检记录.md`
- source_section: 状态转换表 `in_service → pending_verify`；REST 接口 `/bookings/{id}/submit`；`complete_check()`、`submit()`；“限制”

### BR-EXEC-003

- rule_id: `BR-EXEC-003`
- title: 宠主完成核验与模拟结算
- content: 宠主在 `pending_verify` 状态重新核验清单和服务类型证据，通过后将 `Booking` 与 `ServiceRequest` 置为终态 `completed`，写入一次完成结果并进行一次模拟结算。重复核验已完成预约时返回既有结果，不重复结算或写完成事件；结算合计为 `agreed_fee + actual_cost`，缺省实际费用按零计算。
- conditions: 仅宠主可操作；预约版本、需求当前版本和 `expected_version` 一致；首次核验前 `Booking.status = pending_verify`；接口要求 UUID `Idempotency-Key`。
- implementation_status: 已实现
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`backend/app/routers/bookings.py`；`backend/docs/第11周自检记录.md`
- source_section: 状态转换表 `pending_verify → completed` 及“重复 verify”；REST 接口和第 11 周补充 `/bookings/{id}/verify`；`verify()`；“本地 PostgreSQL 与 FastAPI TestClient 实测通过”

## 匹配条件与推荐理由

### BR-MATCH-001

- rule_id: `BR-MATCH-001`
- title: 匹配调用边界
- content: 只有 `pending_match` 的 `ServiceRequest` 可查询候选；调用需携带当前 `expected_version`，且调用者社区须与需求社区一致。匹配只返回候选和解释，不持久化排名、不占用时间，也不改变 `ServiceRequest` 或创建 `Booking`；建立预约时后端重新校验资格和冲突。
- conditions: `ServiceRequest.status = pending_match`；`expected_version = ServiceRequest.version`；`user.community_code = ServiceRequest.community_code`。
- implementation_status: 已实现
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`backend/app/routers/match.py`
- source_section: 状态转换表“查询候选”；REST 接口 `/requests/{id}/match` 及“AI 与匹配适配器”；`match_helpers()`

### BR-MATCH-002

- rule_id: `BR-MATCH-002`
- title: 候选帮手的基础硬过滤
- content: 候选必须是同社区、未删除且拥有 helper 角色的其他用户，不能是需求宠主本人；需求服务类型须在 `HelperProfile.service_types` 中，需求关联的所有宠物 species 须在 `supported_species` 中，且费用偏好须兼容（`free` 匹配 `free/both`，`paid` 匹配 `paid/both`）。
- conditions: 对每个候选逐项检查，任一条件不满足即过滤；预约建立时还会重检，并额外保证遛狗宠物为 dog。
- implementation_status: 已实现（存在文档冲突：D 组说明把宠物种类过滤限定于 `home_visit`/`dog_walking`，当前 `match.py` 对三类服务都检查所有关联宠物）
- source_file: `docs/D组-匹配规则与测试说明.md`；`backend/docs/API清单.md`；`backend/app/routers/match.py`；`backend/app/routers/bookings.py`
- source_section: “匹配硬性过滤”；API 第 11 周匹配补充；`match_helpers()`；`eligible()`

### BR-MATCH-003

- rule_id: `BR-MATCH-003`
- title: 候选可用时间必须存在连续空闲段
- content: 当前实现不是要求整个需求窗口完整包含在一条可用时间内，而是在某一条 `Availability` 与需求窗口的交集中扣除有效预约占用；剩余任一连续空闲段达到 `expected_duration_minutes` 且结束时间晚于数据库当前时间，即满足匹配。不拼接多条可用时间。
- conditions: 逐条检查 `Availability`；空闲段长度不少于 `ServiceRequest.expected_duration_minutes`；已结束的时间段不作为可用候选段。
- implementation_status: 已实现（存在文档冲突：D 组规则 5 要求整个需求窗口落在某条 Availability 内；第 11 周代码、自检和 API 补充采用“窗口交集内存在足够长连续空闲段”）
- source_file: `docs/D组-匹配规则与测试说明.md`；`backend/docs/API清单.md`；`backend/docs/第11周自检记录.md`；`backend/app/routers/match.py`
- source_section: “匹配硬性过滤-时间包含”与 TC-08；API 第 11 周匹配补充；“新增回归通过”；`has_slot()`

### BR-MATCH-004

- rule_id: `BR-MATCH-004`
- title: 候选时间冲突与占用状态
- content: `completed`、`cancelled` 不占用帮手时间；未过期的 `pending_confirm` 以及 `reserved`、`in_service`、`pending_verify`、`exception` 均占用时间。区间冲突采用半开边界：新开始 < 已有结束且新结束 > 已有开始；已过期的待确认预约不再占用。存在已超过 `scheduled_end` 仍为 `in_service` 或 `exception` 的预约时，当前帮手不得继续接单。
- conditions: 检查同一 `HelperProfile.id` 的未删除预约；匹配查询用于推荐过滤，预约创建时在事务中再次检查。
- implementation_status: 已实现
- source_file: `docs/D组-匹配规则与测试说明.md`；`backend/docs/API清单.md`；`backend/app/routers/match.py`；`backend/app/routers/bookings.py`
- source_section: “时间冲突判断公式”；API 第 11 周匹配补充；`match_helpers()`、`has_slot()`；`eligible()`

### BR-MATCH-005

- rule_id: `BR-MATCH-005`
- title: 服务半径和位置标签不作为当前硬过滤
- content: 当前没有可靠距离数据，`service_radius_m` 只展示，不表示已经验证实际距离；`address_tag` 仅在其文本出现在需求 `location` 时用于加分和生成“同楼优先”理由，不作为候选硬过滤。
- conditions: 候选通过其他硬过滤后才参与位置加分；当前实现未调用地图或距离 API，也未在预约建立时重检实际半径。
- implementation_status: 已实现（当前不进行实际距离硬过滤；service_radius_m仅展示，address_tag仅用于软加分）
- source_file: `docs/D组-匹配规则与测试说明.md`；`backend/docs/API清单.md`；`backend/docs/第11周自检记录.md`；`backend/app/routers/match.py`；`backend/app/routers/bookings.py`
- source_section: “匹配硬性过滤-服务范围”；API“候选卡与费用约定”及“第 11 周匹配补充”；“限制”；`match_helpers()`；`eligible()`

### BR-MATCH-006

- rule_id: `BR-MATCH-006`
- title: 推荐排序权重
- content: 当前代码按总分降序返回候选：身份已核验加 100 分，费用偏好与需求精确一致加 50 分，`address_tag` 出现在需求 `location` 中加 30 分，填写了经验则按经验字符串长度整除 10 加分。代码使用总分而非 D 组文档所列的逐级优先比较。
- conditions: 仅对通过全部硬过滤的候选计分；同分时保持数据库返回的原相对顺序，代码未定义额外的稳定业务排序键。
- implementation_status: 已实现（存在文档冲突：D 组排序优先级为身份→地理→经验→费用；当前代码权重使费用精确匹配通常优先于地理，经验长度也可能改变跨维度结果）
- source_file: `docs/D组-匹配规则与测试说明.md`；`backend/docs/第11周自检记录.md`；`backend/app/routers/match.py`
- source_section: “推荐排序规则（软约束）”；“保留原有服务/宠物/费用过滤与排序权重”；`match_helpers()` 的评分与排序

### BR-MATCH-007

- rule_id: `BR-MATCH-007`
- title: 推荐理由的生成与表述边界
- content: 当前代码只在对应加分条件成立时返回理由：`身份已核验`、`费用偏好完美匹配`、`同楼优先`、`已填写经验自述`。身份核验只能陈述核验状态，不能表述为服务能力、信用或可靠性保证；`service_radius_m` 虽随候选卡展示，但当前不能生成“实际距离已满足”的结论。
- conditions: `reasons` 由匹配模块根据候选字段生成；不满足加分条件时不添加对应理由；推荐理由不得改变状态或替代预约时的服务端重检。
- implementation_status: 已实现（存在文档差异：D 组示例包含“支持犬类”“时间匹配”“信用良好”，当前代码不生成前两项，且 API 明确禁止把身份核验写成信用保证）
- source_file: `docs/D组-匹配规则与测试说明.md`；`backend/docs/API清单.md`；`backend/app/routers/match.py`
- source_section: “匹配接口返回结构”与 reasons 示例；API“候选卡字段来源”和第 11 周匹配补充；`match_helpers()` 的 `reasons`

## 待确认事项

### BR-PENDING-001

- rule_id: `BR-PENDING-001`
- title: 预留有效期仍带有契约待确认标记
- content: 当前状态表和代码均使用 15 分钟预约预留，但 API 清单仍把“预留有效期（暂定 15 分钟）”列为 A/C/D 对齐待确认事项。因此第一版知识库按当前实现回答 15 分钟，同时保留契约尚待最终确认的提示。
- conditions: 适用于新建 `pending_confirm` Booking 的 `reserved_until` 计算。
- implementation_status: 待确认（当前代码已按 15 分钟实现，但跨组契约文字仍标为暂定）
- source_file: `backend/docs/状态转换表.md`；`backend/docs/API清单.md`；`docs/D组-匹配规则与测试说明.md`；`backend/app/routers/bookings.py`
- source_section: 状态转换表“15 分钟预留”；API“A/C/D 对齐时确认”；D 组“待决定事项”；`create()`
