# 私人记录 Schema 1

S1 示例（所有值均为合成样例，使用时替换为真实依据）：

```json
{"id":"11111111111111111111111111111111","component":"s1","module":"documents","scope":"work","category":"writing","state":"candidate","text":"可能偏好先给结论","task_id":"example-task","created_at":"2026-01-01T00:00:00Z","evidence":["合成示例，不是用户要求"]}
```

必填 id/component/module/scope/category/state/text/task_id/created_at/evidence。
id 为 32 位小写 hex；component 为 s1/s2；scope 为 work/personal/general；state 为
candidate/confirmed/retired。confirmed 还须 confirmed_by 原话或核验引用。
日期、来源和证据应真实；格式可校验不代表证据语义真实。可选 supersedes 是旧记录 ID。
新记录 ID 可用 `python -c "import uuid; print(uuid.uuid4().hex)"` 生成。

修订与停用协议：supersedes 只能指向同 component 的记录。confirmed 新修订使旧记录显示
superseded；state=retired 且带 supersedes 的条目是“停用标记”（自身需要 supersedes），
旧记录显示 retired；同目标的 confirmed 新修订优先于 retired 标记，恢复用同目标
confirmed 新修订表达。跨 component 的替代/停用一律拒绝。

S2 另须 cause/prevention/counter_signal（字符串）和 environment（版本键值表；未知可为空但
必须标明待验证）。跨客户端导入保留来源状态，回查明确提醒验证当前环境，不承诺错误不复发。
query 对 S2 记录返回 `environment_review`：自动比对 environment 与本机标准离线键
（os/platform/python_version），给出 mismatched_keys/unverifiable_keys；只对标准键自动判断，
其他环境因素仍需人工核对。

JSON 以 UTF-8 文件传入各写命令（`add`/`add-event`/`log-s3`/`observe-s1`/`observe-s2`/
`updates-mark`），也支持用 `-` 从 stdin 读取，避免临时文件与终端编码问题。
偏好事件 source 建议取 `<客户端>:<任务或会话标识>` 粒度：同一来源对同一偏好重复表达会被
事件 ID 去重，不计新增分数；explicit + confirmed_by 是单端直接生效的通道。

S2 效果 outcome（observe-s2）私有 JSON：

```json
{"schema":1,"task_id":"真实任务标识","lesson_id":"<对应S2记录ID>","opportunity":true,
 "recalled":true,"applied":true,"recurred":false,
 "evidence":"本次真实观察或可核验引用","created_at":"2026-09-06T00:00:00Z"}
```

约束：lesson_id 必须已存在于 s2/records；无 opportunity 时 recalled/applied/recurred 必须
为 false；applied 需要 recalled；recurred 可以发生在未召回/未采用时。s2-metrics 只按不同 task_id 计数，
`avoided_candidate` 需用户确认真实跨任务/会话后才可表述为“已避免”。

积分仅适用于 S1。S1 记录与计分事件是不同对象。旧事件 ID、依据与分值政策保留，不由普通 add 自动计分。
新偏好事件可用 `add-event <JSON文件路径>`（或 `-` stdin）登记，明确要求需要 confirmed_by；
候选支持不等于用户批准。
偏好事件的可选 component 只能为 s1；旧事件省略该字段时按 S1 处理，不重写历史 ID。
偏好事件可带可选 task_id（字符串），便于 `query --task-id` 按任务返回真实新增事件，
不影响事件 ID 与积分。
S2/S3 不通过 add-event 计分，也不适用积分门槛；S2 保留证据与验证状态，S3 保留变更审核依据。
决定事件必须包含 target/basis，依赖缺失时拒绝保存；有效状态由评分引擎重算。

add-event 只接受一个对象，不接受 events 数组。完整合成示例：

```json
{"policy":"plan-a-v1","preference_id":"brief","scope":"work","module":"documents","text":"先写结论","source":"synthetic:task-1","evidence":"合成原话","device":"synthetic","date":"2026-09-06","kind":"explicit","confirmed_by":"合成确认，实际使用必须换成真实依据"}
```

kind 为 support/explicit/difference/exception/replace/decision/classify/promote。
事件 ID 保持 source/preference_id/scope/kind 身份规则；同 ID 异内容是冲突，不得换 source 骗取新分。
promote 在通用必填字段外需要非空 basis（query 待确认偏好的证据 ID 数组）和真实 confirmed_by；
score 达 10 且没有其他待解冲突后可用 add-event 登记。不得把建议晋级自动视为用户同意。
导入预览展示来源文本与证据状态；evidence_present/confirmation_claim_present 仅表示字段存在，
authenticity=not-verified、reference_resolution=not-checked 不因引用格式正确而自动改成 verified。

S1 新效果观察用 schema 2；保留 schema 1 原件只读，不将旧 preference_id 自动换算为 hit：

```json
{"schema":2,"task_id":"synthetic-task","scope":"work","preference_id":"brief","opportunity":true,"recalled":true,"applied":true,"hit":false,"fewer_followups":false,"evidence":"合成：采用后未满足本次需求","created_at":"2026-09-06T00:00:00Z"}
```

目标 preference_id 必须在对应 scope 或 general 中存在；hit 需要 applied，applied 需要 recalled，
recalled 需要 opportunity。未关联偏好可省略 preference_id，但 hit 必须为 false。
同任务、同目标出现矛盾状态时进入 conflict_tasks，不将其计为成功；旧 hit 未知计入 unknown_hit_tasks。

仅原件是事实源；不手工维护常驻“总览主文件”。需要总览时运行 `overview [--scope <范围>]`
在私人 profile 内实时生成只读视图；一致性审计用 `consistency-check`。只读导出/查询/审计
不会晋级、不改变 revision。归属不清的 S1/S2 记录先写 module=uncategorized（category 可标
“待归类”）+ state=candidate，归位用新的 confirmed 修订（supersedes 旧记录）留痕。
