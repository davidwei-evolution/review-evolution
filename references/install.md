# 安装、核心升级与私人数据

常规发布更新采用 [更新协议](update-brief.md) 的自然语言引导与 release_update.py
内容绑定计划/事务替换。检查、下载、更新分别处理授权；用户无需 Git 或命令行知识。
没有用户安装的 Python 时先检测宿主内置运行时；均没有时提供官方图形界面安装引导。

当前是开发版，release_ready=false 表示尚未通过正式发布验收。Agent 应在安装前明确告知；
用户已明确要求开发安装时可继续，完整性校验失败则停止。手工复制不构成发布授权。
v0.11.0 新增 promote 事件与 S1 outcome schema 2；这些数据应由 v0.11.0 或更新兼容核心读取。
旧原件不迁移、不覆盖；旧版可能拒绝新格式，不保证仅回退核心即可继续读取新增数据。

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

新装：检查目标是否存在，独立验证核心；按上面命令创建私人 profile 并绑定；核对
core_package verify 和 experience status；新会话确认技能可见。安装后说明可以查询
“本次新增经验”和“已经记住的经验”。安装验证通过后，按 SKILL.md“首次安装介绍（主动执行）”
协议**主动**生成简短介绍（优先当前安装对话；若该对话先于安装开始导致新技能未加载，
直接读取当前核心并运行 `experience.py intro`，仍在本对话完成介绍；新对话仅为可选路径）。
介绍必须基于当前能力、给自然语言指令和建议，不照抄固定模板。不要把程序可读说成已在当前会话重新加载。

Windows 注意：程序输出与 JSON 输入均为 UTF-8；旧 GBK 命令提示符下若显示乱码，改用
PowerShell/Windows Terminal 或 `chcp 65001`，数据本身不受影响。

升级：只替换经过验证的核心，保留私人 profile；先备份旧核心，验证新核心与 data_schema
兼容后切换；失败恢复旧核心。核心显示版本与 schema 独立，v4.x 历史属于旧版本体系，
本版 release_series=modular-1，不能简单按数值认为 v0.9.0 是可覆盖数据的降级。

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
