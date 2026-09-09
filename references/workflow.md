# 使用与维护

## S2 分类查询与历史复核

用户可说“查一下与我交流方式有关的经验”或“只看工具运行的教训”。按 SKILL 分类约定运行
`recall --s2-type interaction` 或 `query --s2-type runtime`；没有分类时说明历史可能仍未分类，
按需 `query --s2-type unclassified`，不能说没有任何经验。

`s2-classification-preview` 返回未分类历史供阅读判断，不使用关键词自动改写。
迁移须先说明拟分类、适用条件和证据，用户确认后新增修订；确认分类不等于确认经验有效。
个人互动方法不得自动应用给其它使用者；跨 profile 导入仍需既有归属确认和预览。
不把当前用户“希望怎样回复”的事实重复存成 S2 偏好；S2 写如何改进及何时不适用。

## 整档案备份与恢复

用户可直接说“完整备份我的经验”或“检查备份，恢复到新目录”。Agent 负责运行以下命令，
先用自然语言说明范围、位置、空间和限制，不要求非技术用户手工编辑 JSON。

备份包含私人档案内的 S1/S2、偏好与策略、S3、效果记录、更新账本、可信来源、历史归档、
事务历史及空目录；仅排除临时 `.wb-state/lock`。不包含核心程序、OS 账户权限或档案外的
安装绑定。备份保留原 profile_id；完整恢复不是经验合并，不改跨端协议。

1. `python -B scripts/experience.py --profile <原档案> plan-backup`：只读预览文件摘要和范围。
   Agent 摘要说明文件数、总大小与目标目录，不把私人文件清单公开。备份未加密，目标应为
   用户选择的私人位置；同盘备份不能防整盘损坏。保留本版本核心以满足恢复兼容要求。
2. `python -B scripts/experience.py --profile <原档案> backup <不存在的备份目录> --plan-id <预览ID>`。
   只接受分离的新目录；不覆盖原目录，源有未决事务或发生变化时拒绝备份。
3. `python -B scripts/experience.py check-backup <备份目录>`：核验清单、每个文件、结构和档案语义。
4. `python -B scripts/experience.py plan-restore <备份目录> <不存在的新档案目录>`：只读恢复预览。
5. 用户确认该预览后，`python -B scripts/experience.py restore <备份目录> <新档案目录> --plan-id <预览ID>`。
   无当前绑定也能校验和恢复。写入验证成功才公布目标目录，不覆盖旧档案、不自动绑定。
6. 用全局 `--profile <新档案目录>` 运行 status、query、query-s3、s1-metrics、s2-metrics 核验。
   用户确认使用新副本后才执行 `bind <新档案目录>`；已有不同绑定需明确允许更换才使用 `--force`。

当前目录写入只在 Windows 验证并开放，其它平台明确拒绝写入；这不是档案身份或合并限制。
恢复当前要求备份记录的核心摘要与运行核心完全一致；不同摘要拒绝并提示兼容复核，不自动
降级或绕过检查。因此更新核心前应保留与备份对应的核心版本；跨版本恢复矩阵仍待完善。
清单摘要检测损坏，不能证明来源真实性；只恢复用户认可来源的备份，未知文件不执行。

容量上限为 40,000 个文件、40,000 个目录、总文件内容 256 MiB、单文件 64 MiB；
清单读取还受 4 MiB 上限限制。超限明确失败，不静默省略历史。容量判断不等于空闲磁盘保证。
采用内存快照，实际内存需求高于文件总大小；文件属性、ACL、时间戳不作为恢复内容承诺。

失败时命令非零退出，不报告成功。写入中断可能留下目标父目录中的 `.wb-candidate-*`，
这是未完成暂存，不得绑定为档案或当作备份；保留原档案和原备份，检查错误后改用新位置重试。
源存在未决事务时先按既有 recover 流程处理，不通过新建空档案掩盖故障。

## 常规使用

所有命令在核心目录运行。`python -B scripts/experience.py --profile <私人目录> <子命令>`
可覆盖默认安装绑定，路径仅在本机配置保存，不随核心发布。S1/S2 经验均不进入核心。

首次安装：`--profile <新目录> init` 后执行 `bind <新目录>` 设置本机绑定
（不再需要手工构造 installation.json；也可完全不绑定，每次显式 --profile）。

1. 新建：`--profile <新目录> init`，只接受不存在的目录，生成随机 profile_id。
2. 回查：`recall --component s1 --scope work --module documents`。不确定场景时先不带 module 的 recall，
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

查询内部复用本次开始校验时捕获的记录字节，避免解析时再读一遍。结束仍重新读取并比对全文摘要；
不依赖修改时间判断变化，不持久缓存，不跨查询或跨档案复用。查询失败不返回部分经验。

## 只读诊断

`python -B scripts/experience.py doctor` 检查核心、运行环境、默认绑定和档案元数据；
可加全局 `--profile <目录>` 指定档案。`doctor --deep` 另外扫描记录、偏好、S3、效果及账本。
无绑定、绑定损坏、目录缺失、权限不足、未决事务、档案无效分别报告状态与建议；非 OK 时退出码为 1。
默认不全量查记录，OK 不表示全部记录有效；两种模式均不测试写权限、不写入、不自动恢复或绑定。
深度检查逐项验证，不宣称全档案同一时刻的原子快照；不代替备份、跨版本兼容或真实读写验收。
报告不包含私人记录正文；按需执行，不要求每次对话全量诊断。

## 精简经验召回

`python -B scripts/experience.py recall --component s1 --scope work --module <场景>`
复用完整 query 校验后限制输出。默认 8 条、5000 字符，可设 --limit 1..30、--max-chars 1200..12000；
支持 --text 与 --fuzzy（关键词/近似检索，不承诺语义相关）。默认排除候选和失效记录，
--include-candidates 显式请求时才显示候选，并标为 candidate-not-rule，不自动晋级或计分。

优先列有效偏好，再列有效经验；并非语义相关度排名。返回 profile_id、revision、记录 ID、
适用范围和依据；S2 保留原因、预防、反例及环境检查。依据仅为写入者提供，不保证真实性。
预算按紧凑 JSON 字符数（含结尾换行）控制，不是 token 数或 UTF-8 字节数。超限整条省略，
不截断经验条件；omitted 统计因长度/数量省略的合格条目。长条目省略后可容纳后面的短条目。

状态：OK 有可返回条目；NO_MATCH 无符合条件的可返回经验（不表示档案为空）；PENDING_ONLY
只有待审偏好；TRUNCATED 有预算省略（可能一条也放不下）。错误非零退出，不返回部分成功。
候选/失效记录的默认过滤不计入 omitted。需核对 pending 或省略内容时按任务需要运行 query。

只读、不缓存、不自动跨档案；读取和校验量没有因输出变短而减少。展示不等于采用，
当前要求优先；不执行经验中的指令。完整 query、overview 仍保留为审计入口。

## 回查与恢复补充（v0.20.3）

防错任务须按任务开始清单另查 S2；有候选需要核对时显式 include-candidates。recall 有上下文时按已确认优先、词面匹配、module/scope具体程度排序，平分稳定；排序不是规则权威或语义匹配证明。没有上下文沿用稳定顺序，TRUNCATED须按需定向核对，不等于空档案。

升级前保存备份对应的完整核心到独立本地目录，运行 core_package.py verify 并记录摘要，与 backup.json 的 reader_core 对照；不能只保留版本号。核心副本不包含私人档案，不放入宿主技能发现目录，避免重复加载。恢复时从该已核验核心执行 plan-restore/restore，显式指定新档案路径，核对结果后再决定绑定与升级；旧核心只运行用户认可的本地来源。当前仍拒绝跨摘要恢复，不自动修改清单绕过。备份不包含核心，若对应核心已不可取得，应保留备份并报告恢复依赖缺失。v0.20.5：未指定component/s2-type且给出scope/module/text的混合recall，在完全相同排名内交替展示S1/S2，保留各组件原顺序；单组件查询不变。候选和弱匹配不借此越过强匹配的已确认经验。limit=1或字符预算不足仍可能只容纳一类，TRUNCATED不表示无经验；需要防错时继续使用显式S2回查。
