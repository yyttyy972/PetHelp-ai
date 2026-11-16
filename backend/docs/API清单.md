# 邻宠帮 API 清单 v0.2 草稿

已按冻结契约同步第 10 周实现口径（12 表、多宠物）；本次补回身份核验、头像与地址、服务半径、费用双轨、禁止事项、原始需求及宠物照片字段，并同步候选卡与权限投影，既有状态与事务设计不变。第 9 周第一轮，仅定义契约，不代表已实现，供 A/C/D 与成员 B 对齐。技术栈 FastAPI + PostgreSQL；限一个社区、猫狗、单次单帮手服务、模拟结算。

## 公共约定与字段来源

前缀 `/api/v0`，`/health` 除外；JSON 字段蛇形小写，UUID 使用字符串，金额使用两位小数字符串，时间使用带时区 ISO 8601，返回 UTC `Z`，无时区时间拒绝。登录后使用 Bearer token，身份由服务端解析，禁止客户端提交 actor_id、owner_id、状态、结算状态等受控字段。详情字段见数据字典，同名字段直接来自同名表；密码输入 `password` 只生成 User.password_hash，不存明文。

列表请求 `limit(1..100，默认20),cursor`，响应 `{items:[],next_cursor:null|string}`；详情为对象，创建返回 201，查询与动作返回 200，软删除返回 204；第 10 周实现基础档案、需求与上传，后续接口见下方实施范围。错误始终 `{ "code": "version_conflict", "message": "需求版本已变化，请重新确认" }`，不返回框架默认 detail。

以下简写是明确字段集合：U=User 的 id,display_name,roles,community_code,avatar_url,address,verification_status；P=PetProfile 除 deleted_at 的全部字段；H=HelperProfile 除 deleted_at 的全部字段（含 service_radius_m,fee_pref,verification_status,address_tag）；R=ServiceRequest 除 deleted_at 的全部字段（含 fee_type,precautions,raw_text），加 pets 名单及当前版本 checklist_items；B=Booking 除 deleted_at 的全部字段；E=ExecutionRecord 除 deleted_at 的全部字段；X=ExceptionRecord 除 deleted_at 的全部字段。password_hash 永不返回；User.address、location、交接说明、异常联系人、PetProfile.photo_url、执行照片 URL、precautions 与 raw_text 仅宠主与当前预约帮手可见，本人始终可读自己的资料，历史预约帮手仅能读取自身预约快照与记录，不取得当前个人地址或宠物照片。avatar_url、verification_status 以及帮手 address_tag、fee_pref、service_radius_m 可公开展示，address_tag 不得包含门牌；大厅 R 投影仅 id,service_type,window_start,window_end,expected_duration_minutes,budget,fee_type,version,status,community_code，不暴露原始需求、禁止事项与照片。预约快照、事件 payload 和幂等响应重放均执行同一权限投影，不能绕过限制。

## REST 接口

表内字段均为必填，标记 `?` 为可选；更新只接收列出的白名单字段，字典中的系统字段不可通过通用 PATCH 写入。

|方法、路径|请求字段|响应字段及来源|特有错误|实现状态（第10/11周）|
|---|---|---|---|---|
|GET /health|无|`{"status":"ok"}`，不依赖数据库|503 service_unavailable（进程不可用）|已实现|
|POST /auth/register|account,password,display_name,roles,avatar_url?,address?|U（含 avatar_url、verification_status，社区由配置赋值，核验默认 unverified）|409 account_exists|已实现|
|POST /auth/login|account,password|access_token,token_type,expires_in（认证派生）|401 invalid_credentials|已实现|
|GET /users/me|无|U|401 unauthorized|已实现|
|PATCH /users/me|display_name?,roles?,avatar_url?,address?|U；verification_status 只读|409 role_in_use|已实现|
|POST /pets|name,species,breed?,birth_date,temperament?,precautions?,supplies_location?,care_instructions?,photo_url?|P|422 invalid_pet|已实现|
|GET /pets|分页|P 列表，仅本人|—|已实现|
|PATCH /pets/{id}|上述宠物字段的可选项，含 photo_url?|P；不自动改变已有需求快照|403 forbidden|已实现|
|DELETE /pets/{id}|无|204|409 resource_in_use|已实现|
|PUT /helpers/me|service_types,service_area,experience,supported_species,service_radius_m,fee_pref?,verification_status?,address_tag?|H；fee_pref 首次缺省 both，核验值继承 User|422 invalid_profile；403 verification_read_only|已实现|
|GET /helpers/{id}|无|H，隐藏审计字段|404 not_found|已实现|
|POST /helpers/me/availability|start_at,end_at|Availability 全字段（不含 deleted_at）|422 invalid_window|已实现|
|GET /helpers/me/availability|分页|Availability 列表|—|已实现|
|DELETE /availability/{id}|无|204|409 resource_in_use|已实现|
|POST /requests|pet_ids:[uuid]（至少一项）,service_type,fee_type,window_start,window_end,expected_duration_minutes,location,budget,handover_notes,emergency_contact,requirements?,precautions?,raw_text?,checklist_items|R，初始 draft/version=1|422 invalid_request|已实现|
|GET /requests|scope=mine或open,分页|本人 R 或大厅投影|—|已实现|
|GET /requests/{id}|无|按权限投影 R|404 not_found|已实现|
|PATCH /requests/{id}|expected_version，创建字段的可选项，含 fee_type?,precautions?,raw_text?（宠物名单/service_type 不可变）|R，重要修改 version+1|409 invalid_state/version_conflict|已实现|
|POST /requests/{id}/publish|expected_version|R|422 incomplete_request|已实现|
|POST /requests/{id}/match|expected_version|request_id,version,candidates[{helper_id,avatar_url,verification_status,fee_pref,service_radius_m,address_tag,reasons}]，候选卡字段来源见下文，不持久化排名|503 matching_unavailable|已实现（第11周接入D模块）|
|POST /requests/{id}/bookings|expected_version,helper_id,scheduled_start,scheduled_end,agreed_fee|B；宠主邀请或 helper_id=本人申请|409 time_conflict/booking_exists|第11周已实现|
|POST /bookings/{id}/confirm|expected_version|B，双方分别确认同一版本|409 reservation_expired/version_conflict|第11周已实现|
|POST /bookings/{id}/withdraw|reason|B（cancelled），需求重新 pending_match|409 invalid_state|第11周已实现|
|POST /requests/{id}/cancel|expected_version,reason|R（cancelled）|409 invalid_state/version_conflict；403 forbidden|第11周已实现|
|POST /bookings/{id}/start|expected_version|B 与 request_status|409 invalid_state/version_conflict|第11周已实现|
|POST /bookings/{id}/records|checklist_item_id,kind,occurred_at,note?,photo_urls?,actual_cost?|E；更新对应清单执行状态|422 invalid_evidence|第11周已实现|
|GET /bookings/{id}/records|分页|E 列表|403 forbidden|第11周已实现|
|POST /bookings/{id}/submit|expected_version|B 与 request_status=pending_verify|422 checklist_incomplete|第11周已实现|
|POST /bookings/{id}/verify|expected_version|B 与 request_status=completed，模拟结算结果|409 invalid_state|第11周已实现|
|POST /bookings/{id}/exceptions|reason_code,description,proposed_change?|X 与 request_status=exception|409 invalid_state|未实现，后续周次|
|POST /exceptions/{id}/notes|note|TaskEvent 全字段，payload.note 保存追加沟通内容|409 invalid_state|未实现，后续周次|
|POST /exceptions/{id}/resolve|resolution,decision=resume或end,approved_change?|X 与 request_status|409 invalid_state/version_conflict|未实现，后续周次|
|POST /bookings/{id}/reviews|rating,comment?|Review 字段（不含 deleted_at），双方由预约推导|409 already_reviewed|未实现，后续周次|
|GET /requests/{id}/events|分页|TaskEvent 全字段|403 forbidden|未实现，后续周次|
|POST /media|multipart file，purpose=avatar或pet|{url}，本地 /api/v0/media/ 相对 URL；JPEG/PNG/WebP，最大5 MiB，校验实际解码类型|413 file_too_large；422 invalid_media|已实现|
|DELETE /requests/{id}|无|仅 draft，204 软删除，已发布拒绝|409 invalid_state|已实现|
|GET /media/{relative_path}|无|二进制文件：头像可公开，宠物照片按宠主与当前预约帮手授权，执行凭证按关联预约参与者授权；第10周受控读取|404 not_found|已实现|
|POST /ai/parse|text,reference_time,timezone,pet_ids?|draft{需求创建字段},questions[]，AI 建议不落库|503 ai_unavailable|503 留桩|

checklist_items 的每项为 `item_key,pet_id?,position,content,completion_condition,required,product_name?,quantity?,unit?`，服务端生成 id、request_version 与 execution_status；遛狗必须包含 pickup/departure/return 三个 item_key，代买包含 purchase/delivery，代看按明确照料要求填写，缺少份量须追问而非猜测。kind 为 item_completed/pickup/departure/return/purchase/delivery，必须与服务类型及清单项兼容。

候选卡 avatar_url 来自 HelperProfile.user_id 对应的 User，verification_status、fee_pref、service_radius_m、address_tag 来自 HelperProfile，其中核验值与 User 同步；reasons 由匹配模块说明费用兼容和范围满足依据，可引用上述字段，不得把身份核验表述为服务能力或可靠性保证。fee_type=free 匹配 free/both，paid 匹配 paid/both，半径为匹配硬约束且预约时重检；free 要求 agreed_fee=0，paid 要求 agreed_fee>0，无偿代买仍独立记录商品预算和 actual_cost，费用不兼容返回 422 invalid_request，范围不满足返回 422 invalid_profile。

PUT /helpers/me 中 verification_status 作为可选核验值回传字段，只允许与服务端 User.verification_status 一致，试图改写返回 403 verification_read_only，省略时继承服务端值；fee_pref 省略时创建取 both、更新保留原值，address_tag 省略时更新保留、显式 null 清空。身份核验已定为演示 verified、新注册 unverified，不开放自助认证。照片与头像 URL 仅引用本地已授权资源，上传逻辑限本周受控图片；AI draft 对应新增 fee_type、precautions、raw_text，raw_text 保留用户原话，fee_type 未明确时追问，AI 输出仍须用户确认后经创建接口落库。新增需求字段纳入版本快照及重要修改规则，不改变状态转换。

所有写操作支持 `Idempotency-Key`（UUID），确认完成必须提供；同一预约、同一操作、同一键重放返回既有结果，不重复事件和结算，键相同而规范化请求摘要不同返回 409 idempotency_conflict，已 completed 的 verify 使用新键也只返回既有完成结果。需求业务修改与 TaskEvent 同事务，事件记录键、摘要及响应快照，创建记录也在对应预约锁内处理。

公共错误：400 invalid_request，401 unauthorized，403 forbidden，404 not_found，409 invalid_state/version_conflict/time_conflict/idempotency_conflict，422 validation_error，501 not_implemented，503 service_unavailable；未知异常返回 500 internal_error，不泄露 SQL 或文件路径。

## 跨成员边界及待确认项

A/C/D 对齐时确认各成员所负责模块、预留有效期（暂定 15 分钟）、确认后允许的重要修改范围、异常结束是否允许部分费用（本稿仅记录实际费用，异常终止不自动模拟结算）、评价可见范围（暂定参与者）、多宠物名单创建后不可变。小林的年糕用于代看与代买，建国的柯基用于遛狗需求，小林可兼任该次帮手，禁止自己接自己的需求。

AI 适配器输入自然语言与上下文，输出建议字段和追问；规则匹配适配器输入需求版本与候选档案/时间窗口，输出 helper_id 和可解释 reasons；两者不得写状态，推荐不占用时间，预约建立时由后端重新校验。本周不实现 AI、匹配算法、真实支付或前端。

## 第 10 周实施范围

实现 health、注册登录、用户、宠物、帮手、可用时间、需求 CRUD、publish 与媒体；AI 返回 503 ai_unavailable，匹配及预约后续接口未实现（404），由 C/D 后续接入。DELETE /availability/{id} 保留冻结路径，同时提供 DELETE /helpers/me/availability/{id} 别名。POST /requests 创建 draft，publish 才进入 pending_match；PATCH 仅 draft/pending_match，所有重要修改复制完整清单新版本。checklist_items.pet_id 可空，非空必须属于 pet_ids；R.pets 为本需求宠物档案列表，非参与者仅返回大厅投影。

身份核验已定：演示账号 verified，新注册 unverified，自证返回 403 verification_read_only。所有写请求可携带 UUID Idempotency-Key；需求事件使用 TaskEvent 同事务持久化，非需求操作无可关联 request_id，使用本地文件幂等缓存，重启保留，但数据库提交与缓存写入之间崩溃存在重复执行窗口，不新增核心表；该限制必须在联调时知悉。

实现补充：图片上传仅 purpose=avatar/pet，响应 201；请求字节上限5 MiB，解码限制2000万像素，重新编码 PNG，未绑定头像仅上传者可读，绑定后头像公开；非头像图片仅上传者与相关当前预约帮手可读。register 暂不接受非空 avatar_url，注册后上传并 PATCH 绑定。无有效预约的其他用户只看到大厅投影。宠物 species 在被未删除需求引用时禁止修改；角色在档案仍引用时禁止移除。幂等重放须身份仍有效，键作用域为调用者+方法+路径；请求 JSON 规范化计算哈希，multipart 按原始请求字节计算哈希。

运行约束：单进程单 worker 串行处理业务请求，/health 独立；不提供高并发部署保证。CORS_ORIGINS 默认允许 localhost:5173 与 127.0.0.1:5173，可配置 A 的开发地址。DELETE /helpers/me/availability/{id} 是已实现别名；业务响应全部按统一错误格式。

## 第11周增量（2026-11-16）

已接入 D 的 match 路由，POST /requests/{id}/match 接收 expected_version，排除宠主本人、已删除用户和档案，统一错误格式；保留 D 原有服务类型、宠物类型、费用兼容硬过滤及排序权重；时间规则调整为单条 Availability 与需求窗口交集扣除有效预约占用后，存在连续空闲段不短于 expected_duration_minutes，不拼接多条 Availability，已过期待确认预约不占用候选时间，超时未结束的执行或异常预约仍阻止接单，核验文案仅表示“身份已核验”，不作信用保证。当前无可靠距离数据，service_radius_m 仅展示，不宣称已验证实际距离。

预约、确认、撤回、开始、逐项记录、提交、核验均已实现，confirm/verify 必须携带 UUID Idempotency-Key；全部预约写请求的幂等结果写入 TaskEvent，与业务同事务提交。helper_id 始终是 HelperProfile.id，“本人申请”指该档案 user_id 为当前账号。创建预约为201，其余动作为200；records POST为201、GET为分页。预约响应为 Booking 字段加 request_status，verify 另返回 settlement_total（agreed_fee+actual_cost，空实际费用按0）。

确认超时使用数据库 clock_timestamp，取消预约并重新开放需求后返回409 reservation_expired，超时清理会提交，不因错误响应回滚。重要修改允许 pending_confirm/reserved，先取消原预约并重新开放，再复制清单新版本；旧预约保留历史确认时间但状态 cancelled，因此确认失效。

POST /media 的 purpose 新增 evidence，格式大小限制不变，关联执行记录后仅该预约双方可读取，上传者可读自己尚未绑定的文件。购买凭证必须是真实上传资源、actual_cost 必填且不超过预算；其余记录不接受 actual_cost。遛狗和代买分别验证前序节点及时间顺序。

必需项 waived 仅接受同预约、同版本、宠主 actor_id 的 checklist_waived 事件，payload.checklist_item_id 指向该项；本周不开放批准豁免入口，后续异常模块须按此审计约定生成事件，不能仅直接修改状态。异常处理和评价本周仍未实现。之前“预约均未实现”等第10周范围描述仅为历史记录，以本节和表格状态列为准。

POST /requests/{id}/cancel 已实现：仅宠主可在 draft/pending_match/pending_confirm/reserved 调用，请求 expected_version、非空 reason，成功 200 返回 R；需求直接 cancelled，关联有效预约同时 cancelled，不重新开放。版本不符或服务已开始返回409，非宠主403。confirm/verify 缺少 Idempotency-Key 返回422 validation_error，此约束由中间件强制执行，其他写操作支持按键重放。


## 第11周预约查询补充
- GET /api/v0/bookings：登录必需，role=owner/helper/all（默认all），limit=1..100（默认20）、cursor；200 返回 {items,next_cursor}，仅包含当前账号作为宠主或帮手参与的未软删除预约，包含 cancelled/completed 历史记录；按 UUID 升序游标分页，双角色 all 不重复。owner 指预约宠主，不区分邀请或帮手申请。
- GET /api/v0/bookings/{id}：仅该预约宠主或帮手可读，200 返回预约字段及 request_status、checklist_items；清单按预约 request_version 查询，包含执行状态，重要修改后不会混入新版清单。
- 两个接口均返回 id（预约编号）、request_id、request_version、owner_id、helper_id、owner_confirmed_at、helper_confirmed_at、scheduled_start/end、agreed_fee、actual_cost、settlement_status、status、reserved_until 等 Booking 字段，排除 request_snapshot 和 deleted_at；列表不带清单，详情带清单。确认时间为空表示该方未确认，预约 cancelled 时历史确认不代表仍有效；status 是预约状态，request_status 是当前需求状态。
- 错误统一 {code,message}：未登录401 unauthorized，非参与者详情403 forbidden，不存在或已软删除详情404 not_found，非法UUID/role/limit/cursor为422 validation_error；GET 无需 Idempotency-Key。不增加数据库字段。
