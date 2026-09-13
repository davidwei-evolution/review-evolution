# 私人记录 Schema 1

> 当前策略：按任务回查，默认最多3条/3000字符；简单问答跳过，同一任务复用，新事实或任务变化再查。公开与开发版均退出日常效果登记；observe-s1/s2命令只返回退役提示，旧schema与内部兼容函数仅服务历史数据/回归，不能作为日常执行流程。无新增安静结束。


## S2 可选分类（v0.16.0-beta.1 起）

分类字段须同时提供，且只用于 S2：

- s2_type：runtime（运行工具）、reasoning（推理核验）、execution（执行交付）、interaction（用户互动）。
- s2_applicability：current-user（本档案对应用户）、task-environment（特定任务/环境）、reusable-method（待结合现场复核的可复用方法）。
- s2_context：非空字符串，说明具体适用条件、限制及用户互动背景；不以该字段替代原有 evidence/environment。

interaction 必须为 current-user；“可复用”仍是私人方法，不代表公共许可或跨用户授权。
字段全部缺省的旧记录保留原样，查询视图显示 unclassified，不自动补写或计分。

query/recall 支持 --s2-type，指定后只查 S2；与 --component s1 同用报错。
s2-classification-preview 只读列出有效/候选的未分类记录与证据（默认20条，可 --limit 1..100）。
Agent 阅读后给出具体分类理由，用户确认前不修改旧记录。确认后以 add 新增带 supersedes 的修订：
原 ID/证据/效果引用保留，新修订有新 ID；候选不能仅因为分类确认就升级为 confirmed。
预览 plan_id 仅是预览内容摘要，不是自动迁移授权，也不是 add 的事务提交参数。

含分类字段的导出包使用 core_api=2；新版本仍接受 API 1 旧包。旧核心因 API 2 明确拒绝导入。
本地数据根 schema 仍为1；旧核心可能忽略新字段，因此写入分类后的档案不得直接降级给旧核心使用。
导出包拒绝保护不等于全面降级防护；需要回退时使用对应旧核心与其原备份。完整备份仍遵守相同核心摘要恢复。

本分类不是事实/经历/方法三类记忆的替代，而是 S2 内部按问题领域细分。

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
必须标明待验证）。**例外（2026-09-13）**：`state=retired` 的 S2 **停用标记**只是维护动作
（用于合并去重、撤销旧条目，本身不参与召回也不计分），**不再要求**这四项——停用原因直接写在
`text` 里即可，避免为了过校验而编造因果。正常 S2 记录（candidate/confirmed）要求不变。
跨客户端导入保留来源状态，回查明确提醒验证当前环境，不承诺错误不复发。

S2 记录完整合成示例（所有值均为合成，使用时替换为真实依据；state 为 confirmed 时再补
confirmed_by 原话或核验引用）：

```json
{"id":"22222222222222222222222222222222","component":"s2","module":"release","scope":"general","category":"upgrade","state":"candidate","text":"跨版本升级因未知新组件停止时，先完成可读迁移审查，再用 --reviewed-manifest 精确放行，不改动校验代码。","task_id":"example-task","created_at":"2026-01-01T00:00:00Z","evidence":["合成示例，不是真实观察"],"s2_type":"execution","s2_applicability":"task-environment","s2_context":"仅在候选来源经官方 digest 核验、审查覆盖全部新增文件时适用","environment":{"os":"nt","platform":"win32","host":"QwenWork","python_version":"3.14.7"},"cause":"旧门禁白名单不含新组件且更新器无合规续行参数","prevention":"迁移审查后使用 --reviewed-manifest 提供逐文件哈希与依据","counter_signal":"候选来源未验签、审查遗漏新增文件或需删除旧文件时，停止并拒绝安装"}
```

说明：S2 在通用必填（id/component/module/scope/category/state/text/task_id/created_at/
evidence）之外，另须 cause/prevention/counter_signal 字符串与 environment 版本键值表；
s2_type/s2_applicability/s2_context 三者须同时出现，取值语义见本文件首节。
query 对 S2 记录返回 `environment_review`：自动比对 environment 与本机标准离线键
（os/platform/python_version），给出 mismatched_keys/unverifiable_keys；只对标准键自动判断，
其他环境因素仍需人工核对。

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
v0.20.3：分类 candidate 仅在目标也是 candidate 且正文、证据、原因、预防、反例与环境均未变化时停用目标；允许更正场景分类。其它候选修订保留为候选，不隐藏原件、不自动确认。读取旧档案同样按此视图计算，不改原字节。部分导出补齐此类状态依赖并确认范围扩展。

## text 怎么写才搜得到：用“未来会怎么问”的词（2026-09-12，D3）

回查是**词面匹配**（严格匹配；整次零命中时命令会自动放宽一次为中文二元字组／英文词的重叠匹配），
**不是语义理解**。因此 `text` 要按“**未来我会怎么问这件事**”来写，而不是按当时的场景代号、内部
隐语或临时说法写。

- 反例（当时看得懂，未来搜不到）：`zip 里多了个目录`、`那个锁的问题`、`方案 A 的做法`；
- 正例（未来会这么问）：`安装/打包时校验包内顶层目录与 SKILL.md name 一致`、
  `档案写入偶发瞬时锁占用时先等待片刻再重试`、`改核心后先 reseal 再跑全量回归`；
- 具体做法：写完 `text` 后自问“一周后我想起这件事，会输入哪 2–3 个词？”——把那几个词**写进 text**；
- 检索侧配套：`recall`/`query` 先用 2–3 个短词；严格无命中时会自动放宽一次（结果标
  `text_match=relaxed`，相关性须自行核对），仍未命中就按 `diagnosis.modules` 换词重试一次；
- 边界：这只提高**词面命中率**，不等于语义检索；也不能为了好搜而夸大或改写事实，
  事实仍以 `evidence` 为准，`text` 只是便于检索的表述。