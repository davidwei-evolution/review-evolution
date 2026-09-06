# 使用与维护

所有命令在核心目录运行。`python -B scripts/experience.py --profile <私人目录> <子命令>`
可覆盖默认安装绑定，路径仅在本机配置保存，不随核心发布。S1/S2 经验均不进入核心。

首次安装：`--profile <新目录> init` 后执行 `bind <新目录>` 设置本机绑定
（不再需要手工构造 installation.json；也可完全不绑定，每次显式 --profile）。

1. 新建：`--profile <新目录> init`，只接受不存在的目录，生成随机 profile_id。
2. 回查：`query --component s1 --scope work --module documents`。不确定场景时先 query，
   查阅输出中有效偏好和待审项；不要把候选当作长期规则。关键词用空格分隔时为 AND 检索；
   `--fuzzy` 提供相似度兜底（近似匹配，不做语义等价承诺）。
3. 记录：按 [Schema](record-schema.md) 准备 JSON，先确认归属/证据后
   `add <JSON文件路径>`（也支持 `add -` 从 stdin 读 UTF-8 JSON）。
   record_id 用 UUID hex；重复相同记录不重复写入；相同 ID 不同内容报冲突。
4. 修订与停用：新记录带 supersedes 指向旧 ID，且只允许同 component 之间。
   confirmed 新修订让旧记录显示 superseded；state=retired 且带 supersedes 的条目是
   “停用标记”，旧记录显示 retired；同目标的 confirmed 新修订优先于 retired 标记
   （恢复即新增同目标的 confirmed 修订）。历史原件保留。普通记录不会自动生成偏好积分；
   仅 S1 偏好事件使用既有 plan-a-v1 政策。S2/S3 不计分，不套用积分门槛；
   S2 查询不返回有效或待确认的积分偏好项。
5. 导出/导入：[数据包协议](pack-format.md)。导出先运行 `plan-export` 预览：依赖补全会双向
   闭合（引用/被替代记录向后，替代/停用/决定事实向前），跨 scope/module 扩展必须确认
   plan_id 后 `export` 才写包；`plan-import` 预览会列出偏好/积分/状态与待确认的实际变化。
   同一用户多端建议复用同一 profile_id（后续包可直导），但**安装时不需要设置身份**：
   profile_id 不同时，用 `plan-import --merge-into-current` 预览并入当前档案，
   你确认一次后 `import --merge-into-current --trust-source "<原因>"` 单事务并入；
   首次确认会记住该来源（trusted-sources 查看，trusted-sources-remove 移除），
   后续同来源包不再重复问“是否本人”，但每次仍先预览变化。
6. 故障：写入事务在私人根 `.wb-state/transactions/`。未完成事务会阻止后续正常读取/写入；
   `recover <事务ID>` 仅恢复没有独立新修改的内容，不删除用户记录。核心更新回滚和数据恢复分开。

S1/S2 记录与 S1 事件的合计上限为 4000 个文件、64 MiB，总量内每个文件不超过 4 MiB。
add/add-event 及导入预览、提交前检查最终容量；超限拒绝提交，原记录、revision 和积分不变。
恰好达到上限仍可读，重复相同内容不增加占用。容量不包含 S3、历史归档和事务备份，
也不代表磁盘空闲空间检查。接近上限时使用独立档案分流，不自动删除历史或拆断引用链。
若旧版本已造成超限，先保留完整备份并审查恢复方案；本次升级不自动修复或删除既有数据。

大档案查询仍逐次读取并校验内容，查询前后对比全文摘要，不建立持久缓存或修改私人数据。
路径安全检查复用同一次 lstat 返回的属性，减少重复系统调用，仍检查每个父目录和文件的
链接/重解析点/硬链接；外部修改不依赖 revision、文件大小或时间戳才能发现。性能随设备、
路径深度、数据体积和偏好关系变化；4000 个文件是容量上限，不是固定响应时间承诺。

个人总览与一致性审计（均为只读，不写入、不离开本机）：

- `overview [--scope <范围>]`：在私人 profile 内实时生成个人经验总览——有效偏好、已确认
  S1、S2 记录、待归类记录、跨域对照与锚点。不维护常驻“总览主文件”，避免双数据源。
- `consistency-check [--scope <范围>]`：输出 pending 偏好、cross_domain 跨域对照、
  uncategorized 待归类记录与 anchors/missing_anchors 审计；query 结果同样包含
  cross_domain（同主题 work/personal 相反条目并排，供你复核，不自动处理）。

待归类与归位（S1/S2 普通记录）：归属不清时 module 写 `uncategorized`（category 可标
“待归类”）、state=candidate；确认归位后写一条新的 confirmed 修订（supersedes 旧记录，
scope/module/category 按归位结果填写），旧记录保留 superseded 审计痕迹，不重写旧文件。
classify 事件只用于偏好事件归位计分，不套用到普通记录。锚点（可选）：S1 文本或 evidence
可写 `锚点：scope/preference_id`，供 overview/consistency-check 校验目标是否存在。

S3 迭代日志存入私人根 `s3-private/`，使用 `log-s3 <JSON文件路径>`（也支持 `-` stdin），查询用 `query-s3 --task-id <任务ID>`
或 `query-s3 --text <关键词>`，也可 `--status observation|distilled|in-core` 筛选。
基础内容包含 task_id、text、evidence，只记录当前实际事实；写入凭据/账户秘密不属于复盘
所需内容。S3 私人日志不进入 S1/S2 经验包。
S3 蒸馏状态（可选）：observation=原始观察；distilled=已提炼为可复用方法（需 review_reference）；
in-core=已进入核心公共内容（需 review_reference 指向 CORE/CHANGELOG/审核记录）。
module/category 为可选辅助字段，便于按迭代主题归类。

S2 效果记录（防复发证据）：先用 S2 记录沉淀经验，之后每次真实机会出现时用
`observe-s2 <JSON文件路径>`（也支持 `-` stdin）登记 outcome（task_id/lesson_id/opportunity/recalled/applied/recurred/
evidence，必须指向已存在的 s2 记录）。`s2-metrics [--lesson <id>]` 按不同 task_id 汇总
机会、召回、采用与再犯次数，同一任务不重复计数。`avoided_candidate` 只是候选标记，
需要你确认真实跨任务/会话后才可描述为“已避免”；计数不自动证明因果。outcome 属私人
档案，不进入 S1/S2 经验包，也不占用 S1/S2 容量预算。
S2 查询返回的每条记录带 `reuse_notice` 与 `environment_review`：后者把记录 environment
与本机可离线获取的标准键（os/platform/python_version）比对，输出 mismatched_keys 与
unverifiable_keys；只对这些标准键自动判断，其余环境因素仍需人工核对。

更新账本（仅提醒，不自动联网）：`updates-status` 查看 repo/生态渠道上次检查时间与是否到期；
`updates-mark <JSON文件路径>`（也支持 `-` stdin）记录一次由用户发起/授权的人工检查结果
（channel=repo|ecosystem、checked_at、summary，可带 version/repo_status/new_items）。
`reminders_enabled=false` 可关闭提醒；`min_interval_days` 默认 21 天为 AI 默认值（非用户规则，
可改）。账本只在私人 profile；是否真正联网检查由用户逐次授权。
更新检查协议与账本 schema 见 [更新检查协议](update-brief.md)（schema 2）。
`updates-check --dry-run` 生成本地简报骨架（不联网）；用户请求真实版本检查时运行
`scripts/release_update.py check --online`，不要求用户安装 Git 或手工输入命令。
固定源、失败状态与非技术用户引导见 [更新协议](update-brief.md)。

候选晋升建议：`query` 的 promotion_suggestions 只读提示“重复观察”或“与已有偏好文本吻合”的
S1 记录，供你决定是否补 add-event；它不自动计分、不把候选当规则。推荐仅取当前有效状态
为 candidate/confirmed 且匹配 scope/module 的记录，排除停用、被替代记录和停用标记。

query 的 text 筛选同时作用于原始事件与有效偏好；task-id 查询以原始 events 为“本次新增”，
related_preferences 仅为历史聚合关联。general 保留跨场景适用，其余范围按条件筛选。
cross_domain 是显式的跨域对照，允许展示关联的另一范围，不能当作自动扩大适用范围。

偏好事件 source 应区分独立来源（建议 `<客户端>:<任务或会话标识>` 粒度）。同一来源对同一
偏好重复表达会按事件 ID 去重，不计新增分数；单端可走的快速通道是 `explicit` +
`confirmed_by` 事件，登记即生效为 user-explicit，不需要积分晋级。积分晋级面向多端独立来源
累计，单端预期见 [偏好政策兼容说明](preference-plan-a.md)。

S1 精准度抽样：真实任务后可用 `observe-s1 <JSON文件路径>`（也支持 `-` stdin）登记本次是否命中已有偏好（preference_id）
以及是否减少追问（fewer_followups）；新观察必须使用 schema 2 的 opportunity/recalled/applied/hit，
见 record-schema.md。`s1-metrics [--scope <范围>] [--preference-id <ID>]`
汇总；只计数、不自证因果。跨环境验收流程见 [客户端/跨环境验收](client-acceptance.md)。
S1 旧观察没有 hit 时保持未知；S1/S2 同任务矛盾观察单列 conflict_tasks 并排除成功统计。
S2 区分采用后再犯与未采用再犯；只有至少两个实际采用任务、无再犯与未决矛盾，才提供已避免候选。
S3、s1-outcomes、s2-outcomes 各自实行 4000 文件/4 MiB 单文件/64 MiB 总量预算，提交前检查。
已有超限历史先备份并独立处理，本版不会自动删减；预算不含其他目录或磁盘剩余空间。

## 对话生命周期（场景识别与默认收尾写入）

技能本身是提示与离线工具，不能强制宿主触发；以下流程由 Agent 在对话开始/结束时按提示执行，
执行受限时如实说明，不把“已提示”说成“已强制”。

- 开始（场景识别与回查）：收到任务、准备给实质方案前，先判断本次场景：scope 取
  work/personal/general，module/category 按实际内容自由归类；然后用
  `query --component s1 [--scope <范围>] [--module <场景>]` 只读回查有效偏好与相关记录。
  同主题若在 work 与 personal 存在相反条目按现状分别呈现，不自动合并。场景判断不清时先
  用 general 或关键词（含 --fuzzy）检索；命中 S2 候选时在收尾按 observe-s2 登记现场，
  不直接宣称已避免。
- 结束（默认写入）：每个实质对话或长对话收尾，默认按 [记录模板](record-schema.md) 把本次
  新增事实写入：S1/S2 用 add（含证据与 task_id），偏好要求用 add-event，S3 用 log-s3；
  没有新事实只注明“复核无变化”，用户明确要求不写入（如“本次对话不写入复盘”）时跳过。
  写完后可在最终答复简短说明“新增/无变化/写入受限”，不机械输出长复盘。
- 边界：自动回查与收尾依赖宿主执行，不创建后台任务；写入前仍按证据与范围区分，历史与
  候选不自动成为规则，跨客户端导入需按 pack 协议预览确认。

场景分类与整合：module/category 是自由标签，由 AI 按对话实际内容自行评估填写，不维护
人工受控词表，可随使用自然演化。`scene-census [--threshold <N>]` 在场景标签数量达到阈值
（默认 8，AI 默认值可改）时自行复盘：输出标签变体/相似标签及其证据量，附建议的统一样式
与归并方向（advisory，不改写历史记录）。经你确认后，后续新记录/偏好采用建议标签，
旧记录保留原标签并按需引用。

旧版资料保存在私人 `legacy/` 和独立完整备份。`legacy-search <关键词>` 返回来源行号，
标记 legacy-unclassified；旧命令、授权或偏好不能直接当现行规则。明确归属后可新建 S1/S2
记录并引用旧来源，不能为方便导出而把混合文档整体归为 S1/S2。

运行记录与程序变更分别验证：数据用 status/query 和导入预览；核心用 manifest、格式校验和
测试。只读回查/导出使用前后快照校验，不创建锁文件，不改变经验、profile revision 或积分；
读取期间发生变动时拒绝给出混合结果，重新查询即可。写入/导入仍持有事务锁。
S3 查询的前后快照还覆盖 s3-private 中的 JSON 文件集合及内容，即使外部修改未增加 revision，
也会检测前后差异。该检查不提供抵抗瞬时修改后原样恢复的强事务隔离保证。

当前只有本机离线验证，不保证所有客户端沙箱可直接写入私人目录；写入遇系统权限限制时走
宿主批准，不修改全局批准列表来绕过。旧受保护 bridge 迁移时被停用，本版不依赖持久特权入口。
