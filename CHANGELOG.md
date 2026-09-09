# v0.21.5-beta.1（本地补丁，2026-09-09，旧基线受控 bootstrap 策略定稿）

- 用户确认 A 方案：允许“官方 digest 核验 + 逐次授权”后运行候选包自带更新器完成旧基线
  （<v0.21.2，如 v0.15.0-beta.1）升级；update-brief 新增“旧基线受控 bootstrap”流程，
  并把“不得执行包内脚本”改为“默认禁止、唯一受控例外”。
- compatibility-matrix“升级入口选择”更新：受控 bootstrap 为首选，备份+核心替换为兜底；
  release-check 增加发布前第二环境 bootstrap 验收为 P0 前置。
- 档案不丢失强制化：update-brief/兼容矩阵/release-check 均要求升级前备份并记录档案基线、
  升级后核验与续写、失败保留原档案并回滚核心；不以删除/重建经验目录作为恢复手段。
- 受控 bootstrap 档案保留验证通过（离线合成）：v0.15.0 旧核心写入合成档案（revision 3、
  records 2、effective_preferences 1）→ 候选包自带更新器升级为 v0.21.5 → 档案摘要不变、
  status 与升级前一致、新核心续写与查询成功；证据见
  001《github-upgrade-e2e-verify-2026-09-09\results-bootstrap》。
- 运行代码/测试与 v0.21.4 相同（纯文档/版本清单变更）；封签后回归 174/174；
  未发布、未生成安装 zip。

# v0.21.4-beta.1（本地补丁，2026-09-09）

- 真实联网验证发现并修复 `verify-remote-tag` 解码缺陷：GitHub Contents API 的 base64
  content 带换行，原实现 `b64decode(..., validate=True)` 直接拒绝，返回 VALIDATION_ERROR；
  改为先去空白再校验解码，并补“含换行 base64”回归样本。
- 真实联网验证记录（results-online）：check --online 正确识别远端最新 prerelease
  v0.21.0-beta.1（LOCAL_AHEAD）；--stable-only 返回 NO_ELIGIBLE_RELEASE；官方附件下载
  152,916 字节，SHA-256 与官方 digest `14960a63…5206` 一致。
- compatibility-matrix/README/CHANGELOG 版本字样同步至 v0.21.4-beta.1；封签后全量回归
  174/174 通过（58.705 s）；未发布、未生成安装 zip。

# v0.21.3-beta.1（本地补丁，2026-09-09，文档/版本清单）

- 完成 v0.15.0-beta.1 → v0.21.2-beta.1 本机端到端合成验证（离线，不触网）：
  * 旧 v0.15 自带更新器对 11 个新增组件 UPDATE_STOPPED（只列首个文件）——旧发布基线
    不能靠自带更新器完成跨版本升级；
  * v0.21.2 更新器用 --reviewed-manifest + 门禁身份表完成同一场景（identity_change
    wb-review-evolution→review-evolution、11 文件收据、UPDATED）；
  * 离线发布快照验证默认含预发布、--stable-only 与 cross_check 输出。
- compatibility-matrix 同步到当前版本并新增“升级入口选择”：v0.15.0-beta.1 基线走受控
  核心替换（沿用原档案），v0.21.2+ 支持 --reviewed-manifest 事务升级；不给旧更新器打补丁。
- update-brief 增加旧基线（版本早于 v0.21.2）升级注意与兼容矩阵入口。
- 运行脚本/测试逐文件哈希不变；v0.21.3 封签后全量回归 174/174 通过（59.098 s）。
  未发布、未生成安装 zip。

# v0.21.2-beta.1（本地补丁，2026-09-09）

- 来源：《wb-review-evolution-升级问题总结-20260908.md》——另一台电脑 0.15.0-beta.1 →
  v0.21.0-beta.1 的 GitHub Release 升级复盘；用户指示先修 GitHub/升级链路问题，其余入
  迭代计划；用户已定 GitHub 远端方向 C（后续发布修复版），本批仍不发布、不生成安装 zip。
- GitHub/升级链路修复：
  1) P2：`plan-install/install` 新增 `--reviewed-manifest` 合规放行通道——迁移审查收据
     （schema 1/component-review，含候选版本、逐文件 SHA-256、reviewed_by/reason）精确
     绑定新增文件；错误改为列出全部待审组件而非只报第一个；私人/状态路径即使“审查”也拒绝。
  2) P3：canonical_name 变化改为只在发布门禁身份表允许、lineage 不变的组合下放行，计划
     带 identity_change 审计字段；其余身份/schema 字段仍严格相等。
  3) P4：`plan-install/install` 的 --target 改为必填，校验错误带候选/目标实际路径，
     避免从暂存副本运行时把脚本所在目录误当目标。
  4) P5：update-brief 明确“可信镜像 + 官方 asset digest 一致”可作网络受限降级路径，
     校验锚点仍是官方 digest；不关闭证书校验。
  5) P1 复核：默认含预发布已在 v0.21.1 修复，本次无新增代码。
- 顺带落地已登记直接项：record-schema.md 增加 S2 完整 JSON 示例（含四类 s2_type 语义）；
  S1/S2 写入缺字段时报错列出全部缺失字段并指向 record-schema；`add --help` 说明只接受
  JSON 位置参数；read_payload 兼容 PowerShell BOM（utf-8-sig + BOM 字符剥离）；
  diagnostics.py 增加可直接运行的 CLI（--profile/--deep）与入口说明。
- 全量回归 174 项通过（release_update 专项 33 项；新增 8 项覆盖放行收据、身份审计、
  私有路径拒绝、BOM stdin、缺失字段清单与 diagnostics CLI）。

# v0.21.1-beta.1（本地补丁，2026-09-08）

- 修复 GitHub 更新链路三问题（来源：《upgrade-v0.15-to-v0.21-issues-report.md》真实第二
  环境升级复盘，另一 agent 于本机总结）：
  1) `check --online` 默认渠道同时比较正式发布与预发布（当前仓库只发布 beta，旧默认只查
     正式发布会长期误报“无更新”）；输出 channel、latest_release_type/release_type 与
     每版 assets（含附件 URL/大小）；新增 --stable-only；否定或错误结果带 cross_check
     发布页复核提示，Agent 不得据此断言“没有新版”。
  2) 新增 `download` 子命令：Python urllib 独立 TLS 通道，固定
     github.com/<repo>/releases/download/ 来源、重定向仅允许 GitHub CDN、默认 64 MiB
     上限、可选 SHA-256 校验；作为用户授权后首选下载通道，替代 PowerShell/curl 系统
     通道（schannel 环境问题），仍与更新安装分开授权。
  3) 新增 `verify-remote-tag` 只读预检：核验远端 tag 的 CORE.json 与本机候选一致，
     预防 v0.21.0-beta.1 曾出现的“附件已是新版、tag 提交仍是 0.15.0-beta.1”发布分叉；
     release-check.md 把 TAG_MATCH 设为发布前必做项，并说明 GitHub “Source code (zip)”
     来自 tag 提交树、官方以附件 zip 为准。
- README/SKILL/update-brief 同步默认含预发布、交叉复核与首选下载通道的协议；README
  安装说明提示优先 Release 附件。
- 版本升至 v0.21.1-beta.1（本地补丁，未发布、未生成安装 zip）；全量回归 166 项通过
  （含新增 10 项 release_update 测试）。

# v0.21.0-beta.1（2026-09-08 内测定版，发布前）

- 用户定版：本地版本与计划发布版本统一为 v0.21.0-beta.1；公开发布名 review-evolution、
  lineage wb-review-evolution（路线 A=公开发布名 review-evolution、本地开发名保持
  wb-review-evolution），release_ready 仍为 false，发布动作待内容审核
  与用户两次确认。
- 相对 v0.20.8-beta.1 无功能代码改动；156 项回归保持。

# v0.20.8-beta.1（本地补丁，2026-09-08）

- 复核并修订 S2 定义：明确包含“防错 + 如何更好与用户对话/解释/组织回复”的互动改进；
- SKILL/README 的 S1/S2/S3 首次出现处补充完整定义（S1=使用者经验与协作偏好；
  S2=AI 防错与互动改进；S3=技能自身迭代）；
- README 安装说明按公开发布名 review-evolution 校准（目录名须与包内 SKILL name 一致）；
- 无功能代码改动；156 项回归保持。

# v0.20.7-beta.1（本地补丁，2026-09-08）

- 发布前设计复盘与能力说明文档产出（001 归档）；SKILL.md description 与 README 增加
  定位、核心价值、当前能力与客观边界口径；明确当前为受控 Beta、Windows + Python 3.10+。
- 全局 AGENTS.md 新增“发布前设计复盘与能力描述同步”默认要求（迭代规划条目 014）。
- 无功能代码改动；156 项回归保持。

# v0.20.6-beta.1（本地补丁，2026-09-08）

- re-cli.ps1 增加 Python 3.10+ 最低版本校验：微软商店占位符与低于 3.10 的旧版本都会被
  拒绝并给出明确提示；`py -3` 选择分支使用同一校验。
- 新增回归：启动器脚本含版本校验助手文本。

# v0.20.5-beta.1（本地补丁，2026-09-08）

- C05：修复有上下文的混合recall同排名结果被S1占满的问题；S1/S2仅在同排名内交替，单组件查询、有效性顺序和完整条目预算保持。
- 新增回归：小预算S2覆盖、稳定只读、候选/弱匹配不插队、显式S2筛选。不是语义检索或真实效果证明。

# v0.20.4-beta.1（本地文档补丁，2026-09-08）

- C04：兼容矩阵区分基线缺少backup、当前功能、合成证据及真实待验。移除陈旧远端状态，明确API字段和降级/对应核心恢复路径。
- 运行代码未变；不放宽恢复校验，不宣称跨版本恢复已通过。

# v0.20.3-beta.1（本地补丁，2026-09-08）

- 修复分类候选隐藏confirmed及部分导出漏修订；共享分类状态判定，旧异常修订可读，不改原件。
- 补齐任务开始S2回查，统一介绍/更新/recall入口，明确同摘要恢复所需核心保留步骤。
- recall增加有上下文的确定性词面/场景排序；不新增语义检索或跨档案缓存。
- schema与包API规则不变；真实效果和第二客户端仍待验。

# 核心变更记录

## v0.20.2-beta.1 — 授权弹窗处理优先级与隐私边界提示（本地补丁，文档级）

- install.md/SKILL.md 明确授权弹窗的推荐处理顺序：命令前缀“始终允许”（如
  `python -B scripts/experience.py`）优先，其次“仅允许写入目录”，最后才逐次批准；
  并给出“是否进入项目视野”的判断标准，避免用户把私人目录误加为工作区/源目录。
- 无核心逻辑改动；版本升至 v0.20.2-beta.1，README 版本行同步。

## v0.20.1-beta.1 — 客户端写入授权引导（本地补丁，文档级）

- install.md 新增“客户端文件权限与‘授权一次’”：说明弹窗属客户端沙箱策略、数据只在本机；
  建议“始终允许”或加入可写路径（重开客户端生效）；不要把私人数据目录加为项目/工作区目录。
- SKILL.md 首次安装介绍补充 init/bind 触发授权弹窗时的引导话术与拒绝后的处理。
- 无核心逻辑改动；版本升至 v0.20.1-beta.1，README 版本行同步。

## v0.20.0-beta.1 — Python 必需运行时的受控安装引导与低频提醒（本地补丁）

- install.md 新增“Python 是默认必需运行时”：安装验收说明原因，提供官方路径
  （winget --source winget / python.org），经用户同意后才安装；默认推荐 3.12.x
  （要求 3.10+，已有 3.13/3.14 可直接使用），较大功能更新后评估是否调整推荐版本。
- 半安装状态补充低频提醒政策：不创建后台/定时提醒；只在用户主动询问、经验功能失败或
  大版本更新介绍时提及，同一客户端明确拒绝后不再主动催促。
- SKILL.md 首次安装介绍与 client-acceptance 验收表同步该协议。
- 版本升至 v0.20.0-beta.1；README 版本行按默认规则同步。

## v0.19.0-beta.1 — S2 分类迁移支持与历史迁移（本地补丁）

- effective_states 增加“候选分类修订替代未分类原件”语义：S2 分类迁移用新增
  candidate 修订 + supersedes 表达，旧记录显示 superseded、新修订保持原候选状态，
  不因分类确认升级有效性；普通候选 supersede 仍不隐藏旧记录。
- 新增回归 2 项（候选分类修订替代未分类原件；普通候选 supersede 语义保持）。
- 版本升至 v0.19.0-beta.1；README 版本行按默认规则同步。
- 本机 10 条未分类 S2（9 条旧 + v0.17 新增 1 条）按用户授权完成分类迁移，
  迁移收据见 001 目录。

## v0.18.0-beta.1 — 兼容/反馈/验收/诊断完善（本地补丁，四任务合批）

- 新增 `references/compatibility-matrix.md`：已发布 v0.15.0-beta.1 与本地主线的
  读/写/导入导出/备份恢复兼容与降级边界、升级路径与验收要求（条目 003-B5/009）；
  install.md 升级节增加入口。
- 新增 `references/feedback-template.md`：反馈与环境信息模板（unknown 字段约定与隐私
  边界；GitHub 原生 Issue 模板留发布轮）。
- client-acceptance.md 增补“验收证据绑定”与“效果口径”两节：验收项须绑定测试入口与
  真实环境证据；声称“更懂用户/减少追问”前须附 outcome 汇总或标注未测量（003/005）。
- doctor 按“版本/格式不兼容、容量超限、未决事务”给出更具体的下一步指引，不泄露异常
  原文（003 P1 诊断可用性）。
- release_gate REFS 白名单收录两个新参考文件；版本升至 v0.18.0-beta.1；
  README 版本行按默认规则同步。新增回归 3 项（医生细分 2 + 文档清单绑定 1）。

## v0.17.0-beta.1 — 安装体验与无 Python 运行环境（本地补丁）

- 新增 `scripts/re-cli.ps1`（自动发现可用 Python、排除微软商店占位符静默退出 49、
  统一 UTF-8 后调用 experience.py）与 `scripts/verify-core.ps1`（无 Python 时按
  CORE.json 做 SHA-256 等效完整性校验）。
- intro 默认只读探测本机绑定（bound-valid / needs-setup-or-repair / not-inspected），
  不读取记录正文；安装后 Agent 可据状态决定是否引导 init/bind。
- install.md 增补 Windows 运行环境发现（实际执行版本验证、py -3、宿主内置运行时、
  用户级目录、winget --source winget）、半安装状态与遗留步骤、zip 为唯一安装源、
  验证流程接入 doctor；installer-review-template 增补环境信息记录与 unknown 约定。
- 版本升至 v0.17.0-beta.1；README 正文文案与发布件同步仍按决定 C 暂缓，版本行经用户
  2026-09-07 明确要求即时对齐并设为默认同步规则（除非另行要求）。
- 新增回归：intro 默认绑定探测三态、PS1 辅助脚本 ASCII 约束与清单收录。

## v0.16.0-beta.1 — S2 分类与适用边界（本地）

- 可选四类 S2 类型及适用范围、上下文；旧记录保持未分类，S1/S3 不接受 S2 字段。
- query/recall 支持类型筛选，新增只读历史分类预览，不自动迁移或计分。
- 含分类字段的经验包标记 core_api=2；旧版拒绝导入，无分类包仍为 API 1。

## v0.15.7-beta.1 — 精简经验召回（本地补丁）

- 新增 recall，复用 query 校验，按条数和字符预算输出完整条目与依据；不建立持久缓存。
- 区分无匹配、只有待审项、预算省略和错误；默认不展示候选及失效经验。
- 任务入口和首次介绍同步；不改变评分、身份、格式和合并规则。

## v0.15.6-beta.1 — 只读诊断（本地补丁）

- 新增 doctor 与可选深度检查，区分绑定、目录、权限、事务与档案异常，提供下一步建议。
- 不自动修改、不检验写权限、不泄露私人记录正文；首次介绍同步该能力。

## v0.15.5-beta.1 — 整档案备份与恢复（本地）

- 新增计划、备份、校验、恢复预览及恢复到新目录命令，保留全部文件与空目录，排除临时写锁。
- 清单摘要、内容校验、容量边界、陈旧计划及失败不覆盖保护；不自动绑定，不改变跨端协议。
- 当前写入流程限已验证 Windows，恢复要求相同核心摘要；备份未加密，跨版本迁移另行评估。

## v0.15.4-beta.1 — 查询内部复用已校验内容（本地补丁）

- 解析复用查询开始时捕获的记录字节，减少一次重复读取；结束仍重新读取全文核验变化。
- 保留容量、重复 JSON 键、引用闭包与状态校验；无跨查询缓存，不改身份、数据格式及合并。
- 未对外发布；性能以具体档案实测为准。

## v0.15.3-beta.1 — 首次介绍补齐相关经验提醒

- intro 的经验查询能力事实加入有条件提醒、自然语言请求与使用建议，与上一版规则一致。
- 保留证据与适用性条件，不承诺每轮自动提醒；不新增检索算法，不改变数据或合并机制。
- 本地补丁，未对外发布。

## v0.15.2-beta.1 — 高度相关经验提醒（本地补丁）

- 修正任务开始清单禁止显式提醒的旧规则，增加证据、相关性、适用性与具体行动条件。
- 经验提醒不依赖习惯形成或积分晋级；保留当前要求优先、档案隔离与导入授权边界。
- 复用现有 query，仅更新提示规则，不宣称新增语义检索或已证明行为效果；未对外发布。

## v0.15.1-beta.1 — 本地发布状态文案修正

- 区分本地补丁、历史冻结状态与远端发布事实，避免以完整性标志推断发布状态。
- 仅修改说明与核心清单；程序、档案格式、身份及跨端合并规则保持原样。
- 此补丁未上传 GitHub。

## v0.15.0-beta.1 — 公开 Beta 候选冻结准备（当时未发布）

- 版本统一为 0.15.0-beta.1（tag 建议 v0.15.0-beta.1，显示 “Beta 1”）；release_ready 保持
  false，不宣称正式稳定版。
- release_gate 支持 0.x 预发布版本（0.y.z-beta.N），仍只允许 release_ready=false、
  继续阻断 v1.0.0/正式发布；新增门禁回归测试。
- 新增根 LICENSE（MIT，Copyright (c) 2026 davidwei-evolution）并纳入门禁允许列表。
- README 改为公开 Beta 版文案：能力/安装（非技术说明）/已知限制/许可与反馈；
  支持范围声明 Windows + Python 3.10+。
- release-check 文档口径校正：测试计数不再写死 “43+”，真实进程锁竞争从“待验”移入
  本机已验证；跨主机锁竞争保留为待真实执行。
- 消除自动扫描唯一命中：tests 的 Windows 绝对路径改为运行时拼接的合成输入。
- 可发现性内容更新（发布后 main，未改版本号）：SKILL.md description 与 README 增加
  检索标签（经验复盘/自我迭代/理解用户习惯/长期记忆等）与“适合这样用”典型需求示例；
  GitHub 仓库 description/topics 与 Release 文案同步完善（详见迭代规划 004）。

## v0.13.1 — 开发版，经验整合并入当前档案（确认式合并 + 可信来源）

- 新增“并入当前档案”合并模式：profile_id 不同的经验包不再只能拒绝，可用
  `plan-import --merge-into-current` 预览（来源/目标 id、新增记录、偏好积分与状态变化、
  冲突与 S2 环境提示），确认归属后 `import --merge-into-current --trust-source "<原因>"`
  以单一事务并入当前客户端档案；profile_id 相同的直导流程不变。
- 首次确认会把来源 profile_id 记入可信来源账本（private profile 的
  updates/trusted-sources.json）：新增 `trusted-sources` 查看与
  `trusted-sources-remove <来源ID>` 移除；后续同来源包不再重复问“是否本人”，每次仍先预览。
- 安装零身份负担：普通用户无需在安装时设置 profile_id；同用户多端复用同一 id 降级为
  可选高级优化（可免确认直导）。文档明确 profile_id 由 init 随机生成、仅属该用户，
  不复制他人 id；核心不含任何个人 id。
- 安全默认保留：未显式确认（--merge-into-current + 首次 --trust-source）仍拒绝不同
  profile 导入；冲突仍停摆不覆盖；不执行包内指令、不导入 S3/outcomes。
- 新增回归：不同 profile 默认拒绝、merge 预览未信任标记、无 trust 提交拒绝、首次
  信任并入、二次 unchanged、可信来源移除（64 → 65 项测试）。

## v0.13.0 — 开发版，当前能力驱动的首次介绍

- 新增离线只读 intro：核验当前核心、版本与 CLI 入口，按场景排序能力事实、自然语言请求示例和建议。
- 未绑定 profile 也可介绍；显式检查只返回配置状态，不暴露经验正文、不写首次使用标记。
- 安装对话主动交付，按用户语境重新组织说明；新建对话须宿主支持和明确授权，无法创建则当前交付。
- 核心缺失/篡改停止能力背书；介绍规则包含跳过、避免重复、无运行时降级以及模型触发与真实客户端验收边界。

## v0.12.1 — 开发版，大档案路径检查性能

- 路径安全检查每个节点仅执行一次 lstat，复用类型、重解析属性与硬链接计数，去掉重复元数据请求。
- 保留逐次全文摘要、schema/依赖校验和只读快照；不引入跨查询缓存，不改变 S1 积分或私人格式。
- 新增系统调用数量、链接属性/权限失败关闭、同大小且恢复时间戳的外部修改检测回归。
- 大档案使用同一合成档案比较优化前后完整查询结果与文件哈希；实测结果见工作区验收报告。

## v0.12.0 — 开发版，发布检查与受控更新

- 显式联网读取固定公开 Releases API，按 SemVer 比较，排除草稿/默认预发布并呈现逐版本变化。
- 区分无发布、无新版、版本体系不明、列表不完整与网络/校验失败，不以失败冒充无更新。
- 本地候选更新计划与事务替换绑定已确认标签、文件哈希、身份/数据格式，失败尝试回滚。
- 不下载、不自动安装或建立定时任务；非技术用户由 Agent 引导，优先宿主已有运行时。
- 发布比较、错误/分页、无 PATH 工具、隔离更新与回滚测试；真实新版仍需实际发布后验收。
## v0.11.0 — 开发版，复用与效果语义校准

- 统一查询与推荐范围，排除失效推荐；文本搜索返回有效偏好，任务关联聚合单独标识。
- S1 新观察 schema 2 明确命中，保留旧观察为未知；S2 支持未采用时再犯，矛盾观察不计成功。
- promote 事件绑定审阅证据，确认十分晋级为长期偏好，不增加积分；保留原事件身份规则。
- 导入预览增加正文/证据与定义差异，不把引用格式视为真实性认证。
- S3/效果观察增加独立容量检查；补偏好、统计、历史检索和真实进程锁竞争测试。
- 新事件/观察格式需兼容核心读取；旧原件与 S1 积分政策不变。
## v0.10.4 — 开发版，历史功能缺口补回（总览/一致性/归位/锚点/首装说明）

- query 结果新增 `cross_domain` 跨域对照输出（同主题 work/personal 相反偏好并排，
  只对照不自动处理）；按 --scope 过滤。
- 新增只读 `overview [--scope]`：私人 profile 内实时生成个人经验总览（有效偏好、
  已确认 S1、S2 记录、待归类记录、跨域对照、锚点）；不维护常驻总览文件。
- 新增只读 `consistency-check [--scope]`：输出 pending 偏好、cross_domain、
  uncategorized 待归类记录与 anchors/missing_anchors 审计，不改写任何记录/事件。
- 待归类与归位流程文档化（S1/S2 普通记录）：module=uncategorized + state=candidate
  暂存；归位用新的 confirmed 修订 supersedes 旧记录留痕，不重写旧文件；
  classify 事件仍只用于偏好事件。
- 锚点（可选）恢复：S1 文本/evidence 可写 `锚点：scope/preference_id`，
  overview/consistency-check 校验目标存在性与状态。
- 首次使用介绍补运行环境项：Python 3.10+、官方下载页 python.org、先征得同意；
  查询句式增加“查看个人经验总览”。
- 回归：新增 query 跨域输出、overview 只读总览、consistency-check 待归类+锚点审计
  3 项测试（61 → 64 项）；README/SKILL/workflow/record-schema 同步。
- 未实施（留待用户决策）：每轮全过程复盘记录结构、场景化指南/多客户端提示词模板入库。

## v0.10.3 — 开发版，外部客户端审计修复 + 对话生命周期恢复

- 新增 `bind <私人目录> [--force]`：原子写入 installation.json；绑定缺失时报可操作错误，
  不再裸抛 WinError 3；install.md 更新 init → bind → status 首装流程，无需手工构造 JSON。
- 写命令（add/add-event/log-s3/observe-s1/observe-s2/updates-mark）支持 `-` 从 stdin 读
  UTF-8 JSON；文档参数表述统一为“JSON 文件路径（或 -）”。
- 入口统一 reconfigure stdin/stdout/stderr 为 UTF-8（errors=replace），修复 Windows 管道/
  GBK 中文乱码；README 增补 Windows 已知问题说明。
- query/query-s3 支持空格分隔多关键词 AND 与 `--fuzzy` 相似度兜底（默认行为不变）。
- S2 查询输出 `environment_review`：自动比对 environment 与本机标准离线键
  （os/platform/python_version），给出 mismatched/unverifiable；其余环境因素仍人工核对。
- 偏好 source 语义与单端预期文档化：explicit + confirmed_by 单端即生效 user-explicit；
  同一来源重复表达按事件 ID 去重；积分晋级面向多端独立来源。
- 恢复“对话生命周期”提示层：任务开始场景识别回查 + 实质对话收尾默认沉淀
  （无新事实注明复核无变化；用户明确要求不写入时跳过）；task-start-checklist/workflow 同步。
- 清理：删除 preference_engine.ANCHOR_RE 死代码；safe_store 模块 docstring 不再描述已停用
  bridge 机制。
- 依据另一客户端 v0.10.1 实测报告逐条核对：57 项基线 + 新增 4 项回归 = 61 项通过。

## v0.10.2 — 开发版，首次安装介绍主动触发修复

- SKILL.md frontmatter description 增加中英触发说明：新客户端安装完成后首个相关会话，
  或用户询问“这个技能怎么用/自我介绍/你是做什么的”时，主动执行简短首次使用介绍。
- SKILL.md 新增“首次安装介绍（主动执行）”协议：触发条件、介绍骨架（一句话定位/S1-S2-S3/
  隐私边界/使用方式/如实说明）、边界；references/install.md 同步。
- 修复现象：安装完成后未按计划主动自我介绍（原描述与正文均缺少“主动”与触发词）。
- 源码与安装副本测试仍为 57 项；重新生成 v0.10.2 安装 zip 供另一台机器复验。

## v0.10.1 — 开发版，发布门禁身份配置

- release_gate 新增身份允许清单：开发版 (wb-review-evolution, wb-review-evolution) 与
  公开发布候选 (review-evolution, wb-review-evolution)。
- 公开候选身份可进入内容审核，但 publication_authorized 恒为 false；v1.0.0 /
  release_ready=true 仍不由本开发门禁放行（正式发布需另行确认策略与完整审核）。
- 新增 2 项回归：公开候选身份通过/未知身份拒绝、v1.0.0 仍被开发门禁阻断。
- 源码与安装副本测试增至 57 项。

## v0.10.0 — 开发版，S1 精准度抽样与跨环境验收流程

- 新增 S1 抽样观测：observe-s1 / s1-metrics（scope/module/preference_id/fewer_followups/
  evidence；只计数，不自证因果）。
- 新增 references/client-acceptance.md：本机已验证项与真实第二环境验收清单（安装、触发
  钩子、pack 往返、并发冲突），明确“真实跨端待验”。
- 源码与安装副本测试增至 55 项。

## v0.9.9 — 开发版，更新检查文档与本地简报骨架

- 新增 references/update-brief.md：更新检查协议（repo/ecosystem 渠道、账本 schema 2、
  不可信输入边界、决策流程），明确本技能代码不发起网络请求。
- 账本 schema 扩展至 2：repo/ecosystem 增加 latest_version/last_brief 等字段；
  updates-mark 支持记录 brief 与 latest_version；旧 schema 1/缺省账本自动归一。
- 新增 `updates-check --dry-run`：只生成本地简报骨架（当前核心版本、将检查项、
  上次摘要与 item 模板），不联网；未授权时不执行任何真实检索。
- release_gate 允许清单加入 update-brief.md；源码与安装副本测试增至 54 项。

## v0.9.8 — 开发版，场景整合复盘机制

- module/category 明确为 AI 按实际使用自由归类的标签，不引入人工维护的受控词表。
- 新增 `scene-census [--threshold <N>]`：场景标签达到阈值（默认 8，AI 默认值可改）时，
  自动复盘并输出合并方案——识别大小写/空格变体与相似标签，附证据量与建议统一样式；
  结果只读 advisory，不改写历史记录，经用户确认后用于后续归类。
- 源码与安装副本测试增至 52 项。

## v0.9.7 — 开发版，S3 蒸馏状态、候选晋升提示与更新账本

- S3 日志支持可选蒸馏状态与字段：status=observation/distilled/in-core，module/category，
  distilled/in-core 必须带 review_reference；`query-s3 --status` 可筛选。
- query 输出 `promotion_suggestions`（只读建议，不自动计分）：同一 S1 记录文本在 ≥2 个
  不同 task 重复出现，或与已有有效偏好文本一致/包含时提示，由用户确认后再 add-event。
- 新增更新账本：`updates-status` / `updates-mark`（私人 profile），记录 repo/生态渠道上次
  检查与是否到期；reminders_enabled 可关，min_interval_days 默认 21 天为 AI 默认值。
  只提醒不自动联网，联网检查仍需用户授权。
- 源码与安装副本测试增至 51 项。

## v0.9.6 — 开发版，S2 效果事实源、故障验收补强与旧入口清理

- 新增 S2 效果记录：`observe-s2` 登记真实机会结果（必须指向已存在 s2 记录；
  opportunity/recalled/applied/recurred 语义约束），`s2-metrics` 按不同 task_id 汇总
  机会/召回/采用/再犯；avoided_candidate 仅供候选，需用户确认真实跨任务/会话。
- 故障与恢复验收补强：新增多文件写入中途磁盘满回滚测试、journal 终态崩溃留下 prepared
  事务后 recover 恢复测试；release-check 增补跨平台/故障验收矩阵（本机已执行项与
  macOS/Linux、真实磁盘满/断电、独立进程竞争、第二客户端等仍待真实执行项）。
- 旧入口清理：SKILL.md 与兼容文档明确旧 v4.x 路径（troubleshooting/update-check/按场景
  records-lessons/self_maintain 等）已失效，统一指向 experience.py + 私人 profile，
  不回退旧目录写入；全局 AGENTS.md 的同步修订另案待用户授权。
- 源码测试增至 48 项（在 43 项基础上新增 S2 outcome、磁盘满回滚、崩溃恢复等回归）。

## v0.9.5 — 开发版，导出状态保持、预览与停用协议

- 部分导出改为“先预览后确认”：`plan-export` 展示原选择、自动补全的依赖、原因与实际条目；
  依赖补全会跨 scope/module 时，`export` 必须携带确认过的 `--plan-id` 才写包。
- 导出依赖闭包改为双向：向后保留被引用的证据/被替代记录，向前保留会改变有效状态的
  confirmed/retired 替代标记与 decision/classify 事件；导入端状态与源端一致，
  不会让已被替代/停用的记录复活。
- 停用协议正式化：state=retired 且 supersedes 旧记录的条目是“停用标记”，旧记录显示
  retired；同目标的 confirmed 新修订优先于 retired 标记（恢复以新确认修订表达）；
  跨 component 的修订/替代一律拒绝。
- 导入预览 `rule_changes`：列出将新增/变化的偏好（状态/层级/积分/待确认原因）、受影响
  记录的有效状态变化、staged 新增/移除；预览绑定 plan_id，导入前可见规则变化。
- `query --task-id/--text` 返回匹配的原始偏好事件清单（events 字段），不再只有空
  effective_preferences；S1 事件可选 task_id 便于按任务回查“本次新增”。
- 新增 A1/A2/A4/A5/A6 回归测试；仍为本地开发版，未发布。

## v0.9.4 — 开发版，S3 读取快照

- S3 查询前后快照包含 S3 JSON 文件内容和文件集合，发现读取期间外部增删改即拒绝返回。
- 保持只读、不创建写锁；S1/S2 导入计划与积分逻辑不变。

## v0.9.3 — 开发版，写入容量预检

- S1/S2 新增与 S1 事件新增、导入预览和提交前，检查最终文件数量、单文件及总字节上限。
- 使用现存文件实际大小与待提交序列化字节，重复导入不重复占用预算；超限不提交经验或修订号。
- 容量边界与失败后档案可读性回归验证；不改变数据 schema、原有经验或积分政策。

## v0.9.2 — 开发版，S1 积分边界

- 明确积分仅适用于 S1，覆盖 work/personal/general；S2/S3 按证据、验证与审核管理。
- S2 查询不运行偏好评分、不返回待确认积分项；拒绝显式归属非 S1 的偏好事件，包括导入路径。
- 兼容无 component 字段的历史 S1 事件，保留事件 ID、评分政策与既有数据。

## v0.9.1 — 开发版，P0 内容门禁

- 核心导出要求独立、绑定全部文件内容的隐私审核记录；缺失或过期审核直接阻断。
- 闭合路径清单与字段约束；扫描邮箱、绝对路径、常见凭据与私人运行元数据，结果只报告指纹。
- 私人内容与 S3 原件不进入核心；导出保持原始清单字节，不生成设备标识或构建时间。
- 审核通过不等于发布授权，也不承诺识别所有语义隐私；当前仍未公开发布。

## v0.9.0 — 开发版

- 一个核心源，独立私人 profile 与数据 schema 1；未发布，尚未定稿为 v1.0.0。
- S1/S2 记录与组件导入导出；不可变条目、依赖闭包、预览计划、去重与事务恢复。
- 核心按内容清单验证和导出；公共方法独立审核；不包含私人历史或设备标识。
- 旧 v4.x 属于历史版本体系，原始材料留私人档案，不改写历史编号。
- 本机验证不代替多操作系统/多客户端验收。
