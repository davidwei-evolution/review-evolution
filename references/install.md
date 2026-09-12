## v0.22 安装前：S3明确选择

安装时先告知：可选S3记录本skill安装/升级/运行问题，支持按需查询分类迁移；额外调用和内容会增加token及操作成本，不能伪报具体比例。让用户决定是否安装并加载。未明确选择时用基础版，不加载S3；选择后用官方含S3版，核验后运行s3-choice enable --confirmed。不以下载含S3包代替明确授权。
基础版无scripts/s3_optional.py；已有S3原件继续保留，完整备份仍包含它们。基础版用户需要读旧S3时可选择官方含S3版，不重建或丢弃档案。停用用s3-choice disable --confirmed，不删除文件；物理移除已安装模块不自动执行。
选择保存在本安装/客户端账号作用域的本机配置，不随经验包转移。公开版不提供开发模式选项，也不自动按S3修改核心。普通S1/S2功能无需S3。

# 安装、核心升级与私人数据

常规发布更新采用 [更新协议](update-brief.md) 的自然语言引导与 release_update.py
内容绑定计划/事务替换。检查、下载、更新分别处理授权；用户无需 Git 或命令行知识。
没有用户安装的 Python 时先检测宿主内置运行时；均没有时提供官方图形界面安装引导
（Windows 的具体探测与降级路径见下文两节）。

`release_ready` 与版本通道绑定（1.0-A）：**开发版（`0.x.y[-beta.n]`）必须 `release_ready=false`**，
表示尚未通过正式发布验收；**正式版（`X.Y.Z`，X≥1，无预发布后缀）必须 `release_ready=true`**，
且审核收据里要有 `stable_evidence`。Agent 应在安装前明确告知；用户已明确要求开发安装时可继续，
完整性校验失败则停止。手工复制不构成发布授权。
**`--allow-dev` 只在目标 `release_ready=false`（开发版 / 预发布候选）时才需要**：
**v1.0.0 及以后的正式版不需要该参数**，按普通升级流程处理。给开发版加 `--allow-dev` 时，
它**只是放行这道门禁、不是质量背书**——完整性校验、内容审核与两次人工确认都不因此放松；
`check` 的 stable 渠道也不会推荐它（要用默认渠道或 `--include-prerelease`）。新增文件时还需
`--reviewed-manifest`（见下文用 `emit-receipt-template` 生成骨架）。
v0.11.0 新增 promote 事件与 S1 outcome schema 2；这些数据应由 v0.11.0 或更新兼容核心读取。
旧原件不迁移、不覆盖；旧版可能拒绝新格式，不保证仅回退核心即可继续读取新增数据。

### Python 是默认必需运行时（先说明原因，同意后再安装）

经验的写入、回查（在对话中影响回复）、导出/导入、备份恢复与 doctor 都依赖本机 Python
运行 experience.py；没有 Python 时只能停留在“半安装状态”，无法读写私人经验档案。
因此安装验收把 Python 作为默认必需项，但安装动作本身必须经用户同意后才执行：

- 先探测宿主自带运行时与系统 Python（见下节）；都没有时向用户说明“为什么必须装”，
  并只提供官方路径（不推荐第三方镜像/捆绑安装器）：
  - 推荐（官方源、快捷）：`winget install --id Python.Python.3.12 --source winget
    --scope user`；
  - 备用（官方安装包）：https://www.python.org/downloads/windows/。
- 版本要求 Python 3.10+；默认推荐 3.12.x（生态兼容稳定）。已有 3.13/3.14 可直接使用；
  本技能发生较大功能更新后，应评估是否调整推荐版本。
- 预计下载/安装约 30–60 MB、1–3 分钟（视网络）；安装期间可继续阅读文档、不受影响；
  装完后通常需重开客户端，当前会话可用绝对路径继续。
- 用户拒绝安装：进入“半安装状态”（见下节），按低频提醒政策处理，不逐会话催促。

### Windows 运行环境发现（先验证再使用）

Windows 新机常见的 `python`/`python3` 只是微软商店占位程序（位于 WindowsApps），
在无交互子进程里会静默退出 49 且无输出；因此不要只探测路径是否存在，必须实际执行
版本命令验证。按以下顺序寻找可用解释器：

1. 执行 `python --version`：退出码 0 且输出 `Python 3.x.y` 才算可用；退出码 49、
   无输出或路径在 `WindowsApps` 下均视为占位符。
2. 官方启动器：`py -3 --version`（Python Launcher 自带版本）。
3. 宿主客户端内置运行时（如千问等客户端自带 Python 的绝对路径）。
4. 用户级安装目录：`%LOCALAPPDATA%\Programs\Python\Python3*\python.exe`。
5. 都没有时安装官方 Python。国内网络建议显式指定官方源，避免默认多源时 msstore
   源不可达导致整体失败：
   `winget install --id Python.Python.3.12 --source winget --scope user`
   （也可到 https://www.python.org/downloads/windows/ 下载官方安装包）。

安装后当前会话的 PATH 仍是旧快照：直接用新解释器的绝对路径调用即可；重开客户端后
才可直接输入 `python`。技能包内置 `scripts/re-cli.ps1` 自动完成以上探测并统一 UTF-8：

```text
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\re-cli.ps1 status
```

**一键安装入口（Windows，D1，2026-09-12）**：同一脚本支持按顺序完成整套安装，避免逐条命令
分别触发宿主确认：

```text
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\re-cli.ps1 -InstallAll
```

它会依次：① 校验核心完整性 → ② **先查本机既有绑定**（有则复用并跳过 init）→ ③ 无绑定时才
`init` + `bind` 默认档案 → ④ 跑 `doctor` 自检；每一步都输出一句白话说明在做什么，失败即停在
原状态、不继续写入。安装前先向用户说明这几步，再执行。
**诚实边界**：技能侧能做到的是把多条命令收敛为**一次调用**；**能否只弹一次授权取决于宿主是否
支持对该脚本／命令前缀一次授权**，技能无法决定宿主弹窗次数，也不得向用户承诺"一定只弹一次"。
macOS/Linux 暂无等价一键脚本（备份/恢复本身也仅 Windows 可用），按下方命令逐条执行。

### 半安装状态（暂不安装 Python）

Python 只用于经验数据（profile）命令与官方校验脚本；核心文档与技能文件本身可先安装。
没有 Python 时：

1. 照常把技能文件放入技能目录，是否已被宿主发现/加载须以当前客户端实际状态验证；完整性校验使用无 Python 入口：
   `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify-core.ps1`
   （与 `core_package.py verify` 同一 CORE.json 清单的 SHA-256 校验）。
2. 明确以下能力暂不可用：`init`/`bind`/`status`、首次介绍中的绑定状态核验、经验查询/
   写入/导入导出与自检。能做的只有读取文档与查看文件。
3. 把“遗留步骤：安装 Python 后补 init/bind/status”写入本客户端记忆或本机笔记，
   避免后续会话把“技能已在列表”误当“数据功能已就绪”。
4. 补做时重开客户端（PATH 已刷新），或按上一节绝对路径方式调用。
5. 拒绝后的低频提醒政策：不创建后台/定时提醒。默认只在以下时机顺带说明一次——
   ① 用户主动询问技能能力或使用方式；② 用户尝试查询/写入/导出等经验功能且失败；
   ③ 技能大版本更新后的首次介绍。同一客户端用户明确拒绝后不再主动催促；
   跨客户端不共享拒绝状态，新客户端首次介绍属正常说明而非催促。

不要因为技能目录已存在或校验通过就宣称“全部可用”；未完成绑定前只能介绍支持的能力，
不能说“没有经验”或“已记住什么”。

### 客户端文件权限与“授权一次”（Codex 等沙箱客户端）

### 核心目录必须独占（宿主注入文件）

少数宿主在「上传/添加技能」时会往技能根目录写入自己的簿记文件（例如 `_user_meta.json`，
通常只有 name/installedAt/source 三字段）。这类文件不是核心内容，但默认会让核心校验判定
"多出文件"：`doctor` / `intro` / 升级 / 备份的**核心校验**会失败，日常 status/recall/query/add
不受影响。处置：

- 保持核心目录独占是首选；能指定安装目录的宿主请让它把技能放在独立目录；
- 已知宿主/OS 簿记文件（`_user_meta.json`、`.DS_Store`、`Thumbs.db`、`desktop.ini`、`.idea/`、
  `.vscode/`）可显式放行一次：
  `python -B scripts/core_package.py verify --allow-host-files`，或
  `python -B scripts/experience.py doctor --allow-host-files`（`intro` 同样支持该开关）；
- **未知的额外文件一律仍然拒绝**，并明确按核心篡改处理——不因为"可能是宿主写的"就放行；
- 该开关只影响"文件集合"判定，不放松任何内容哈希校验。

### 目标核心被宿主改写导致升级被拒（U1，2026-09-12 真机实测）

**现象**：`check` / `plan-install` 报 `Core content mismatch: SKILL.md`（或
`Target core invalid at <技能目录>: Core content mismatch: SKILL.md`）。
**成因**：少数客户端在「上传/注册」路径会**改写已装文件**——实测把 `SKILL.md` 的 frontmatter
`description: >` 改成 `description: |`（折叠换行被压平），并注入 `install_method: upload` 之类的字段。
文件字节变了、`CORE.json` 里的摘要还是发布原值，于是完整性校验失败，**升级第一步就被挡住**。
（同一台机器上，走更新器事务替换路径**不会**发生这种改写——所以问题只在注册环节。）

**处置（顺序照做，不要跳步）**：

1. **只读诊断**，先看清到底差在哪：
   `python -B scripts/core_package.py diff --root <技能目录>`；若手边有同版本原包，加
   `--reference <原包目录>` 会直接给出结论：`representation-only`（仅行尾/BOM/空白）/
   `frontmatter-only`（正文一致、只差 frontmatter 表示法与字段）/ `body-differs`（正文也变了）。
2. **备份**被改写的那份文件（例如 `SKILL.md.bak-<日期>`）。
3. **用同版本原包里的同名文件复原**，然后重新 `verify` 到官方清单摘要。
4. **不要修改 `CORE.json` 去迁就**被改写的文件——那等于自己伪造清单，之后所有校验都失去意义。
5. 复原后重跑 `plan-install`。

**如果换了客户端仍会被改写**：把该客户端与注册路径记下来反馈；这是宿主行为，技能侧不会为它
自动放行，但报错会给出上面这条可行动路径。

部分客户端（如 Codex 桌面）默认只允许写入当前工作区；本技能私人档案位于用户数据目录，
首次写入（init/bind/add/导出等）可能弹出文件授权窗口。

- 弹窗属于客户端权限策略，不是技能要求联网或作者授权；私人数据只保存在本机、不上传。
- 处理弹窗的推荐顺序：
  ① 若客户端支持“命令/前缀始终允许”，对 `python -B scripts/experience.py` 一次授权，
     之后经验命令不再逐条弹窗（不扩大私人文件的可见性）；
  ② 若客户端区分“允许写入目录”与“工作区/源目录”，把私人数据目录加入前者；
  ③ 都不支持时，每次批准即可。
- 不要把私人数据目录加为“工作区/源目录”。判断标准：该目录是否出现在文件列表或项目
  搜索里——能看到就说明已进入项目视野，明文私人 JSON 可能被读取或随项目分享，应移除；
  看不到但允许写入，才是安全的“可写授权目录”。配置一般在新会话/重开客户端后生效。
- 其它客户端（千问、钉钉等）按各自权限规则执行；本技能不要求联系作者或经过作者授权。

核心 `wb-review-evolution` 和私人目录必须分开。Windows 默认数据基目录是当前用户
LOCALAPPDATA 下 review-evolution；macOS 为 Library/Application Support/review-evolution；
Linux 为 XDG_DATA_HOME/review-evolution。`installation.json` 只保存本机 profile_root，
不属于核心或经验包。也可完全不设置绑定，每次显式 --profile。

设置本机绑定（不再手工构造 JSON）：

```text
python -B scripts/experience.py --profile <新私人目录> init
python -B scripts/experience.py bind <新私人目录>
python -B scripts/experience.py status
```

`bind` 只接受已 init 且 profile.json 合法的目录；已存在其他绑定时需加 `--force`。
installation.json 位于默认数据基目录下，内容仅三个字段：schema（1）、core_series
（modular-1）、profile_root（绑定目录的绝对路径）；不进入核心或经验包。

**新装第一步（必做）：先查既有绑定，再决定是否新建档案。** 读同目录下的 `installation.json`
（Windows 默认 `%LOCALAPPDATA%\review-evolution\installation.json`；macOS
`~/Library/Application Support/review-evolution/installation.json`；Linux
`$XDG_DATA_HOME/review-evolution/installation.json`，即与 `data_home()` 同目录），或直接运行
`doctor` 看当前绑定。**已存在 `profile_root` → 复用该档案、跳过 init**，只跑 `status`/`doctor`
核对；**不存在 → 才**按下面的 `init` + `bind` 新建。禁止在已有绑定的机器上把新档案顶替进去
（`bind` 会拒绝覆盖，D9 也会对"绑到空档案"给出提醒；但顺序正确才不会走到那一步）。

新装：以 zip 为唯一安装源——若旁有同名解压目录，不要使用（无法证明未被改动），从 zip
重新解压安装。检查目标是否存在，独立验证核心（无 Python 时用 verify-core.ps1）；按上面
命令创建私人 profile 并绑定（暂不装 Python 则按“半安装状态”记录遗留步骤）；核对
core_package verify 与 experience status，并按需运行 `doctor` 只读自检；新会话确认技能
可见。安装后说明可以查询“本次新增经验”和“已经记住的经验”。安装验证通过后，按
SKILL.md“首次安装介绍（主动执行）”协议**主动**生成简短介绍（优先当前安装对话；若该对话
先于安装开始导致新技能未加载，直接读取当前核心并运行 `experience.py intro`，仍在本对话
完成介绍；新对话仅为可选路径）。介绍必须基于当前能力、给自然语言指令和建议，不照抄固定
模板。不要把程序可读说成已在当前会话重新加载。

Windows 注意：程序输出与 JSON 输入均为 UTF-8；旧 GBK 命令提示符下若显示乱码，改用
PowerShell/Windows Terminal 或 `chcp 65001`，数据本身不受影响。

中文环境（CP936/GBK）额外前置（U11，2026-09-12 实测）：PowerShell 5.1 在 CP936 下会把**含中文的
系统名称、计算机名与中文路径**显示成乱码（例如 `Microsoft Windows 11 רҵxx`），这不代表数据坏了。
做法：① 命令加 `python -X utf8`，或把输出**重定向到文件后用 UTF-8 读取**；② **不要把含中文的路径
当作作业目录**（解压、收据、计划、备份都尽量放 ASCII 路径）；③ 看结果时以 `verify` /
`check-backup` 这类**机器可校验的输出**为准，不要凭终端里的一行中文判断成败。

升级：只替换经过验证的核心，保留私人 profile；先备份旧核心，验证新核心与 data_schema
兼容后切换；失败恢复旧核心。核心显示版本与 schema 独立，v4.x 历史属于旧版本体系，
本版 release_series=modular-1，不能简单按数值认为 v0.9.0 是可覆盖数据的降级。
兼容与降级边界表见 [兼容矩阵](compatibility-matrix.md)。

**开发版 / 预发布候选包的前置说明（U4）**：这类包 `release_ready=false`，因此
① `check` 的 stable 渠道**不会**推荐它（要用默认渠道或 `--include-prerelease`）；
② 安装/升级必须显式加 `--allow-dev`，否则报 `Development release requires explicit allow-dev review`；
③ `--allow-dev` **只是放行这道门禁、不是质量背书**，完整性校验、内容审核与两次人工确认都不因此放松。
④ **v1.0.0 及以后的正式版（`release_ready=true`）不需要 `--allow-dev`**，按普通升级流程处理。
新增文件时另需 `--reviewed-manifest`：可先用
`python -B scripts/release_update.py emit-receipt-template --candidate <候选目录> --target <技能目录> --out <新文件>`
生成收据骨架，只填 `reviewed_by` 与 `reason`（摘要已由脚本算好，不要手改）。

旧版迁移：保留完整旧目录作为本地备份；将私人历史按哈希复制至 legacy；复制偏好事件
原字节；清晰的 S1/S2 内容进入对应记录，混合旧文保持待分类可检索。数据核验后才切换
核心。旧自维护 bridge 应明确停用，不能继续指向换代后的核心目录写入记录。

数据导入：[包协议](pack-format.md)。它不覆盖核心，也不迁移系统权限。
安装时不需要设置任何身份。以后要把另一台设备/客户端的经验并入本机时，把经验包交给
Agent，先 `plan-import --merge-into-current` 预览，确认一次后单事务并入当前档案
（首次确认会记住该来源，后续同来源包不再重复询问归属）。
旧 self_maintain、module_sync、merge-all 的全树分发不再是本版数据维护接口。

不自动联网、下载、生成安装 zip 或发布。发布评估通过并由用户明确要求后，才运行
core_package export 到新的目录；该命令只读取核心清单，无法读取私人绑定/profile，且必须
提供 [内容绑定审核记录](release-check.md)。不能省略审核参数或把审核当成发布授权。


### 托管宿主安装与绑定预检（HM-01）

先运行 `python -B scripts/experience.py doctor`；已有档案且绑定不可用时，用
`python -B scripts/experience.py --profile <已知私人档案绝对路径> doctor` 单独核对。
不要因缺绑定直接 init 新档案，也不要扫描其他会话目录。账号绑定错误不能当成全新用户。

- 核心只读：核心校验通过只证明可读取清单；日常经验写入不需要修改核心。
  升级需要目标核心目录写权限时，使用宿主允许的升级流程，不修改系统权限。
- 私人目录不可访问：保留原件，核对宿主允许范围；已有包的恢复仅按获授权的导入或恢复流程。
- 软链/重解析点：不自动 resolve 绕过保护；核对宿主允许的独立非链接绝对路径，
  已有档案先显式 --profile 诊断，通过后再 bind；不要复制成空档案冒充恢复。
- `write_access` 与 `core_write_access` 的 not-tested 表示没有试写，不能解释成只读或可写；
  `persistence=unknown` 表示未证明跨会话保存。doctor 的 OK 不代表全部数据功能已就绪。
- 真实写入以经授权的正常操作及读回为准；新会话再次读回才提供持久性观察，
  完整支持仍需客户端验收。无实际模板/插件入口时，不推荐猜测的宿主菜单。
