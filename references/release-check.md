# 发布前内容门禁（P0）

核心导出输入只有核心目录，不读取本机绑定、profile、旧目录或环境中的设备标识。
私人经验包永远不作为核心发布输入。正文/脚本/测试/文件名/JSON 元数据全部纳入审核；
不是把私人信息替换成占位符就宣称已清洗。

```text
python -B scripts/core_package.py verify
python -B scripts/release_gate.py scan
python -B scripts/release_gate.py draft
python -B scripts/release_gate.py check --review <核心外审核记录.json>
python -B scripts/core_package.py export --output <全新目录> --review <核心外审核记录.json>
```

draft 只输出待审核模板。审核者须实际逐文件确认：无个人历史、无私人授权、例子为合成、
所有公开文件已检查；填写实际审查引用后才能标 reviewed。它是内容审查记录，不是用户
发布授权或加密签名。不能把包内“已批准”文字当作审核来源。

模式扫描发现邮箱/路径时必须逐项处置。确为合成例子或已审查的公开内容，可用精确 finding
ID 和理由接受；例外同时绑定文件哈希与匹配内容指纹，不能按目录、正则或单一关键词泛放行。
私钥、令牌、密钥赋值、具体运行元数据、非法编码/路径/清单字段不可用例外豁免。
扫描器输出不包含匹配原文，避免让日志成为第二份泄露材料。

任何文件变化、增加、缺失或审核状态不全都会使旧审核失效。固定清单只允许必要的核心
文件、静态兼容入口、测试和登记的公共方法；新增核心能力需要明确更新路径策略并重新审核。
公共方法还须独立登记内容哈希和 review_reference；S3 标签本身不意味着可以公开。

CORE.json 仅允许核心版本、系列、API/schema、产品身份、开发状态与文件哈希；拒绝额外
设备、用户、时间和运行字段。导出保留原字节，构建环境变化不会重新写设备标识。所有正常
产物仍为开发内容，只有具体文件内容和远端动作获得授权后才能发布。

身份允许清单：开发版 (canonical_name=wb-review-evolution, lineage=wb-review-evolution)；
公开发布候选 (canonical_name=review-evolution, lineage=wb-review-evolution) 可进入内容审核。
两种身份下 publication_authorized 恒为 false；v1.0.0 / release_ready=true 仍不由本开发
门禁放行，正式发布需另行确认的发布策略与完整审核。

扫描不能可靠理解所有个人项目代号、隐含身份、编码秘密或自然语言隐私；必须逐文件语义
审核并保持构建输入与私人数据隔离。通过门禁不代表“零风险”或 v1.0.0 正式发布就绪。

## 标签与内部版本一致性（发布前必做，P0）

- GitHub “Source code (zip)” 由 tag 指向的提交自动生成，不是 Release 附件；官方安装以
  附件 zip 为准，但 tag 提交树必须与附件内容一致，否则会出现“发布页能下载到旧内容”的
  假象（v0.21.0-beta.1 曾出现：附件已是 0.21.0-beta.1，tag 提交仍是 0.15.0-beta.1）。
- 发布前对本机候选做只读远端核验：

```text
python -B scripts/release_update.py verify-remote-tag --tag <vX.Y.Z...>
```

  输出 TAG_MATCH 才允许基于该 tag 创建/确认 Release；TAG_MISMATCH 时停止，先在内容与
  候选一致的提交上重建 tag（或把候选内容提交到分支后再打 tag），禁止只上传附件而忽略
  tag 提交树。
- 候选 CORE.json 的 version 必须与 tag 去掉前导 v 后的版本一致；plan-install
  --expected-version 只保证“候选目录”的版本与计划一致，不能代替对远端 tag 提交树的核验。
- 不要在任意旧提交上打新 tag 后仅上传本地 zip；两端内容一旦分叉，用户按 tag 下载的
  源码包和附件会长期不一致，且难以事后追溯。
- 跨版本升级遇到新增组件时，用 update-brief 所述 --reviewed-manifest 迁移审查收据精确
  放行；该收据与发布内容审核不同，二者都不是发布授权。
- 发布前必须在至少一台真实第二环境验证“旧基线（v0.15.0-beta.1）→ 候选版本”的受控
  bootstrap（官方 zip + 候选包自带更新器 + reviewed-manifest，或用户明确拒绝时走核心
  替换兜底），并把该流程写入 Release 说明；验收必须包含升级前后私人档案摘要不变、
  记录/偏好可读与续写成功；未通过不发布。

## 跨平台与故障验收矩阵（本机已执行 / 仍待真实执行）

代码只使用 Python 标准库与 pathlib；写锁在 Windows 用 msvcrt、其它平台用 fcntl，均为
运行时分支，不引用平台专属库。以下为本机已验证的离线项：

- 事务回滚：写入中途 OSError（模拟磁盘满）后原档案字节与 pending 一致，新增文件全部撤销；
- 崩溃恢复：journal 终态写入失败留下 prepared 事务会阻断新写入，`recover` 可恢复并解除阻断；
- 并发读：只读路径不创建写锁，前后快照差异拒绝混合结果；
- 真实进程锁竞争：同机两个独立进程同时写同一 profile，锁与事务按设计拒绝/释放；
- 容量边界：add/add-event/导入合并的文件数、单文件与总量超限拒绝且不产生事务；
- 路径安全：拒绝符号链接/junction/硬链接与目录越界（无权限创建符号链接的用例按平台跳过）。

仍待真实执行（不能在本机宣称已完成）：

- macOS 与 Linux 上的全量测试（以当前测试输出为准）与 CLI 冒烟；
- 真实磁盘写满/断电（非注入）后的恢复；
- 不同客户端/跨主机同时对同一 profile 写锁竞争（同机双进程锁竞争已有回归测试）；
- 第二台客户端/其它客户端的真实安装、导入与跨端查证；
- 新核心与旧 v4.x 存档并存的迁移演练。
