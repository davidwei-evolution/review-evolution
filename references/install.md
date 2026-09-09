# 安装、核心升级与私人数据

常规发布更新采用 [更新协议](update-brief.md) 的自然语言引导与 release_update.py
内容绑定计划/事务替换。检查、下载、更新分别处理授权；用户无需 Git 或命令行知识。
没有用户安装的 Python 时先检测宿主内置运行时；均没有时提供官方图形界面安装引导
（Windows 的具体探测与降级路径见下文两节）。

当前是开发版，release_ready=false 表示尚未通过正式发布验收。Agent 应在安装前明确告知；
用户已明确要求开发安装时可继续，完整性校验失败则停止。手工复制不构成发布授权。
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

部分客户端（如 Codex 桌面）默认只允许写入当前工作区；本技能私人档案位于用户数据目录，
首次写入（init/bind/add/log-s3/导出等）可能弹出文件授权窗口。

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

升级：只替换经过验证的核心，保留私人 profile；先备份旧核心，验证新核心与 data_schema
兼容后切换；失败恢复旧核心。核心显示版本与 schema 独立，v4.x 历史属于旧版本体系，
本版 release_series=modular-1，不能简单按数值认为 v0.9.0 是可覆盖数据的降级。
兼容与降级边界表见 [兼容矩阵](compatibility-matrix.md)。

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
