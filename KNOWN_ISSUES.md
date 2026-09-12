# 已知问题（KNOWN_ISSUES）

本文件是**随核心发布、面向用户**的已知缺陷清单。状态取 `open`（未修）/ `fixed`（已修）。
编号与维护者本地审计记录（不随包发布、不代表用户环境）一致：D 为缺陷，E 为产品级观察，
M 为宿主/平台限制类观察。
只登记**已确认**的问题；未经复现的推测不列入。
**覆盖范围**：本表自 v0.22.1-beta.1 起建档，只登记该版本之后发现并处理的缺陷；更早版本
（v0.9–v0.21.x）的缺陷已在各自修复版本关闭，见 `CHANGELOG.md`。发布前按 `references/release-check.md`
的闭环要求逐条 triage 缺陷类 S3 记录，结论保存在维护者本地清账记录中（不随包发布）。

## open

| 编号 | 问题 | 影响面 | 计划 |
|---|---|---|---|
| M1 | 手机端（鸿蒙 7.0 钉钉内嵌千问 / WorkBuddy）受宿主**对话级沙箱**限制：技能与经验只在安装它的那个对话内可见，换一个对话既看不到技能、也读不到同一份经验档案；技能可见性还有一层"会话启动时定稿的能力清单"，运行期不刷新 | 移动端跨对话调用与经验累积 | **小范围验证成功，但不保证完整支持所有移动端**（非本技能可自行绕过的配置问题）：宿主提供应用级共享技能目录与账户级经验存储后再评估；在此之前只按"单对话内可用"表述，不写"已支持移动端" |

## fixed

| 编号 | 问题 | 修复版本与内容 |
|---|---|---|
| D1 | 档案中存在**带冗余 `component` 字段的偏好事件**时，`plan-export` / 导出 100% 失败，且只报 `ERROR: 'id'` | **v0.22.1-beta.1**：① 导出侧不再假设事件存在 `id` 字段；② 写入侧新增事件字段白名单，schema 之外的字段在写入前剥离，并在结果中报告 `dropped_fields`；③ 新增回归 `tests/test_export_robustness.py`（含冗余字段的导出多组合、导出→导入往返与幂等、剥离与拒绝边界） |
| D7 | 文档自报的回归项数与实际不一致，且没有用户可见的已知问题清单 | **v0.22.1-beta.1**：README 不再自报项数（以 `references/compatibility-matrix.md` 为单一来源）；建立本文件 |
| D9 | 宿主提供账号变量时，若用户按提示 `init` 了新档案，该作用域**读不到旧经验且不报错** | **v0.22.2-beta.1**：`bind` / `bind --client/--account` 在"绑到空档案且本机还有其它非空档案"时返回 `notice`，给出改绑原档案或先做合并的指引；`install.md` 补充说明 |
| D3 | `plan-import` / `import` 不支持 `.zip` 形式经验包，且非包路径报 `WinError 3` 误导 | **v0.22.2-beta.1**：导入端支持 `.zip`（逐条目校验后解到临时目录，单层包装目录自动拆开）；非包路径给出"这看起来不是经验包"的明确错误 |
| D2 | 部分宿主会在技能目录写入簿记文件（如 `_user_meta.json`），使核心校验判定"多出文件" | **v0.22.2-beta.1**：**默认仍严格**；报错分为"宿主簿记文件"与"未知文件（按篡改）"两类；前者可用 `--allow-host-files` 显式放行（`core_package verify` / `doctor` / `intro` 均支持）；`install.md` 写明核心目录应独占 |
| D6 | 文档中的 observe 字段清单与代码校验不完全一致；校验失败时报错不列出缺哪个字段 | **v0.22.2-beta.1**：`observe-s1` / `observe-s2` 校验失败时列出缺失字段名；SKILL.md 不再内嵌字段清单，改为指向 `references/record-schema.md`（单一来源） |
| E1 | 召回为词面匹配：中文未分词 + 空格为 AND，"自然语言长查询"系统性 `NO_MATCH` | **v0.22.3-beta.1**：新增两段匹配——严格词面无命中时自动做一次**重叠匹配**（中文二元字组 + 英文词，命中比例 ≥ 0.6，按重叠度排序），结果标 `text_match=relaxed` 并提示核对相关性；`NO_MATCH` 的 diagnosis 增加可用 `modules` 与"换词一次"的重试指引。放宽不改变记录状态、不计分 |
| E2 | "技能被加载 → 开工回查 → 命中 → 采用"四个环节都没有强制保证 | **v0.22.3-beta.1**：新增 [宿主集成说明](references/host-integration.md)（独占目录、成对注入账号变量、会话启动提示、触发词、宿主不应做的事、4 步自检）；SKILL.md 与 workflow.md 写入"开工协议"（短词检索 → 自动放宽一次 → 按 modules 换词重试一次后继续任务） |
| D4 | 测试夹具未覆盖真实数据形态（当年 217 项全绿仍漏掉 D1） | **v0.22.4-beta.1**：新增 `tests/test_release_readiness.py` 的"真实形态档案"夹具（混合状态 + 已分类 S2 + 旧写法事件 + 被替代记录）并做**单字段冗余注入**模糊测试：记录层注入后导出不崩、事件层注入一律被剥离 |
| D5 | 测试与核心清单纯绑定，却没有开发态 reseal 入口（一次未 reseal 会产生几十条假失败） | **v0.22.4-beta.1**：新增 `core_package.py reseal [--version]`（重算清单并自校验，拒绝私人/状态路径写入核心）；workflow.md 与 release-check.md 写明"改核心 → reseal → 跑测试"三步，并把 `Core content mismatch` 定性为"未 reseal"而非代码损坏 |
| D8 | 用低于内容格式的核心导出的包声明 `core_api=1`，含分类字段时导入端才拒绝 | **v0.22.4-beta.1**：导出端本已按内容自动判定 `core_api`（有分类即 2），本次补**回归护栏**（有分类必须声明 2、无分类仍为 1、伪造 1 的包被拒）；导入端报错改为可行动文案（指明"由较旧核心导出，请用匹配内容的核心重新导出"）；compatibility-matrix 记录该坑 |
| D11 | 测试夹具继承安装态身份，导致公开发布身份的构建必然有 1 项回归失败 | **v0.22.4-beta.1**：在 v0.22.3 上**未能复现**（把核心改成公开发布身份 `review-evolution` 后 254/254 通过，判断已被中途改动修掉）；补**护栏**：断言两种身份都在允许表内，且公开身份的载荷能通过内容门禁 |
| E3 | 缺陷类经验记录不会阻塞发版（记录与发布流程未闭环） | **v0.22.4-beta.1**：新增只读命令 `experience.py release-review`（列出 S3 中缺陷类条目与 `not_in_core` 计数）；release-check.md 增加"已知问题与经验闭环检查"：发布前每条缺陷类 S3 必须对上 KNOWN_ISSUES 的 fixed 或显式挂起并写理由，结论进 release note |
| D10 | `updates-status` 的 `up_to_date` 在**本机版本领先发布线**时输出 false，易被读成"有更新待装" | **v0.22.4-beta.1**：新增版本关系三态 `relation = equal / local-ahead / behind`（`_version_key`/`_version_ahead`，可比较 `x.y.z-beta.n`）；`up_to_date` 改为"等于或领先"，`local-ahead` 附带"无需更新、以发布页为准"的 `next_step` |
| P10 | 候选经验默认不被召回，导致"记了却搜不到" | **v0.22.5-beta.1**：采用**兜底式**——默认仍只召回**已确认**经验；**当没有任何已确认命中时**，才把候选作为兜底返回，并整体标注 `candidate_fallback=true` 与"未确认候选，仅供参考、不是规则、不计分"的说明。同时新增批量确认入口 `plan-confirm-candidates` / `confirm-candidates`（预览 → 确认 plan_id → 单事务写入；每条候选生成新的 confirmed 修订并 `supersedes` 原候选，历史保留）。**没有**把候选并入默认结果。**v0.22.6-beta.1** 补上闭环：`candidate-status` 可见候选计数，收尾按 A/B/C 条件不定时提醒"过一遍"（90 天冷却、可关闭、绝不自动确认），并把"用户原话明确的要求"改为直接记 confirmed 以减少便签产生 |
| D12 | 候选清单与计数按记录文件的**原始 `state`** 判断，会把已被替代/停用的记录再次列为"待确认"——候选复核时把已确认过的条目又问了一遍，并因此多写了重复记录 | **v0.22.6-beta.1**：`candidate_confirm_plan` / `candidate_counts` 改用**有效状态**（effective 计算），并补回归；同时停用由此产生的重复确认修订，使同一主题只保留一条生效偏好 |
| D13 | 公开候选（`build_public.py --s3 exclude`）产出后**没有跑自身的测试**：275 项中 16 项失败，按发布规则该候选当时不可发布 | **v0.22.6-beta.1**：① 测试加 `optional_s3_enabled()` 守卫，公开版缺席可选模块时**显式跳过**而不是报错；② `intro` 能力清单断言改为"核心项必须存在、开发期项仅开发版要求"；③ `build_public.py` 增加**构建自测门禁**——候选产出后自动跑自带全量测试，失败即中止产出（`--skip-tests` 仅开发用） |
| D14 | 宿主在「上传/注册」路径**改写已装文件**（实测：`SKILL.md` 的 `description: >` 变 `description: |`、注入 `install_method: upload`）→ 与清单摘要不符 → **升级第一步即被拒**（`Target core invalid`），而报错只给一行 detail | **v0.22.7-beta.1（2026-09-12）**：① `core_package verify` 与更新器的"目标核心无效"报错**追加可行动指引**（备份被改写文件 → 用同版本原包复原 → 重新 verify；**不要改 CORE.json**）；② 新增**只读**诊断 `core_package.py diff --root <目录> [--reference <同版本原包>]`，逐文件列出差异并分类（`representation-only` / `frontmatter-only` / `body-differs` / `binary-or-non-utf8`）；③ `install.md` 与 `host-integration.md` 写明处置与"注册路径会改写、updater 路径不会"；**不提供**自动放行——被改写的字节仍按篡改处理 |
| D15 | `release_update.py check` 把"**本机**核心失效"与"发布信息失效"混成同一个 `VALIDATION_ERROR`（"本机或发布信息未通过校验"），真实运行中曾被引导去**反复联网重试/换镜像** | **v0.22.7-beta.1（2026-09-12）**：本机核心自身校验失败现在返回 **`LOCAL_CORE_INVALID`**，message 明说"这是本机问题、与发布源无关、不要反复联网重试"，并给出 `verify` / `diff` 的具体命令与 `next_step`；非零退出码一并纳入 |
| D16 | 从含可选 S3 的开发包切到公开包时**静默能力回退**：`runtime-policy` 变为 `edition=public`、`s3_available=false`，而 `install` 只回 `UPDATED`，用户不知道自己少了一块功能 | **v0.22.7-beta.1（2026-09-12）**：`install_plan` / `install` 结果新增 `edition`、`s3_available` 与 `capability_change`（检测到 `s3_available` 由 true→false 时给出"本候选未附带 S3 模块、旧 S3 只读保留"的说明并追加进 `message`）；`doctor` 输出 `optional_modules` |
| D17 | v0.22.7 的报错/诊断本身有三处毛病（真机反馈 N1–N3）：`Target core invalid` 的**处置指引重复输出两遍**；`diff` 的 frontmatter 键名把**被压平的整段中文**当成键名；`LOCAL_CORE_INVALID` 仍带 `releases_page` 与 `cross_check=true`，与"不要反复联网重试"**自相矛盾** | **v0.22.8-beta.1（2026-09-12）**：① 追加指引前先判重（`HOST_REWRITE_HINT not in message`）；② 键名解析限定 `^[A-Za-z_][A-Za-z0-9_-]*:`，其余按值处理；③ `LOCAL_CORE_INVALID` 改为 `cross_check=false` + `cross_check_reason`，不再附发布页 |
| D18 | D17 的 ② **只修了一半**（真机复测发现）：`facts.frontmatter_keys` 干净了，但 `keys_added`/`keys_removed` 仍走旧宽松解析（`line.split(':',1)[0].strip()`），`.strip()` 抹掉了缩进判断 → `keys_added` 里仍出现 **355 字符的中文整段**被当成"键名"（`keys_removed` 出现 `onboarding`/`tags` 之类的碎片） | **v0.22.9-beta.1（2026-09-12）**：抽出统一过滤器 `_key_names()`，`frontmatter_keys`、`keys_added`、`keys_removed` 三处共用（行首 `^[A-Za-z_][A-Za-z0-9_-]*:`，不做 `.strip()`）；新增回归覆盖"压平成一行"的宿主改写。`kind`/`note` 判定原本不受影响 |
| D19 | **首次自我介绍里出现技术词**（真机反馈）：模型念出了 `recall/query`、`add/add-event`、`doctor`，以及 `S1/S2/S3` 这类内部代号——面向非技术用户不该出现 | **v0.22.9-beta.1（2026-09-12）**：① `intro` 的能力卡片不再输出 `commands`（内部命令名只用于判断该发行形态有没有这项能力）；② 卡片的 `ability`/`example`/`advice` 全部改写成人话；③ `description` 去掉 S1/S2/S3 代号；④ `intro` 新增 `composition.plain_language` 约束（列明禁止项 + 正反例）；⑤ `SKILL.md`（含**公开版模板**）新增"零技术词"硬规则；⑥ 新增两条回归（卡片字段零技术词、description 不含 S1/S2/S3） |

## 平台限制（已声明，非缺陷）

| 项目 | 状态 | 说明 |
|---|---|---|
| 备份 / 恢复（目录发布） | **仅 Windows** | 非 Windows 会被明确拒绝（`Directory publication currently validated on Windows only`）；这是设计上的限制，不是缺陷。其它平台仍可使用记录、查询、召回、导出 |
| macOS / Linux 的普通功能 | **未验证** | 代码按跨平台写（写锁 `fcntl` 分支、数据目录 darwin/XDG 分支），但从未在真机跑过；**不宣称支持** |
| Claude Code 等其它宿主客户端 | **未验证** | 技能目录与加载机制随客户端而异，须按各自官方文档核验；未实测不得写"支持" |
| 手机端跨对话共享 | **未打通**（小范围验证成功，不保证完整支持所有移动端） | 对话级沙箱，见 M1；不因单次安装成功推断跨对话可用 |

用三平台 CI 只能验证**代码层**跨平台；宿主加载/触发、授权弹窗、真实对话效果必须真机验证。
