# 私人经验包格式 1

目前提供目录式数据包，不处理 zip 解压、不运行包内脚本、不联网取证。

```text
python -B scripts/experience.py plan-export --components s1 [--scope work] [--module <场景>]
python -B scripts/experience.py export <全新输出目录> --components s1 --plan-id <确认过的计划ID>
python -B scripts/experience.py plan-export --components s1 s2 --scope work
python -B scripts/experience.py plan-import <数据包目录>
python -B scripts/experience.py import <数据包目录> --plan-id <刚检查过的计划ID>
```

只打包所选 component 的 records；S1 同时携带筛选后的偏好事件。依赖自动双向补齐：
向后保留被引用的证据事件与被替代记录，向前保留会改变有效状态的 confirmed/retired
替代标记与 decision/classify 事件，保证导入端评分/状态与源端一致，不复活已被替代或
停用的记录。因此依赖条目可能超出筛选的 module/scope，也可能进入私人作用域。
`plan-export` 会列出原选择、额外范围、原因与实际条目；跨 scope/module 扩展必须确认
plan_id 后才写包（不能以文档说明代替本次范围确认）。若依赖需要未选 component 则拒绝
导出，需要重新选择组件。包的 not_included 明示历史档案、程序、系统权限、外部证据文件
没有随包；引用失效须回查，不能声称已验证全部外部证据。

积分事件仅属于 S1；S2 不携带积分事件，S3 不计分且不进入此包。导入时偏好事件若显式
标记 component=s2/s3 则拒绝；历史省略 component 的偏好事件仍作为 S1，保留原 ID 与分数。

pack.json 含 format/data_schema/core_api、随机 profile_id、components、筛选条件与文件
大小/SHA-256；pack_id 绑定清单内容。SHA-256 不证明作者身份，文件也未加密。
不把私人包公开上传；传输媒介与加密工具按用户需求另选。

并入当前客户端档案（普通用户的默认做法）：

- profile_id 相同：`plan-import` / `import` 直导，原流程不变。
- profile_id 不同：`plan-import <包> --merge-into-current` 预览（显示来源/目标
  profile_id、将新增记录、偏好积分与状态变化、冲突与 S2 环境提示）；确认属于
  本人/授权来源后，`import <包> --plan-id <预览ID> --merge-into-current
  --trust-source "<确认原因>"` 以单一事务并入当前档案。首次确认会把来源
  profile_id 记入可信来源（`trusted-sources` 查看），后续同来源包不再重复问
  “是否本人”，但每次仍先预览变化；`trusted-sources-remove <来源ID>` 可移除信任。
- 安全默认：profile 不同且未显式确认时仍拒绝——不自动覆盖、不隐式合并不同用户；
  你的确认只表示“该包属于你/你授权的来源”，不代表内容真实性或系统授权。

同一用户若希望多端包直导（免确认），可让其他客户端
`--profile <新目录> init --profile-id <你的个人ID>` 建档；这是可选高级做法，
不是安装要求。profile_id 由 init 随机生成、仅属于该用户；核心与文档不含任何
个人 profile_id，其他用户不复制、不使用他人的 id。也可按旧流程在独立空白档案
导入做只读归档；更改默认绑定需审查本机配置，或始终用 --profile。

导入预检校验路径、内容哈希、数量/大小、组件边界、依赖及未知格式；任何冲突先停下，
不会选择“最后写入获胜”。确认 plan-id 后若目标或数据包改变则拒绝。重复导入同一包为
unchanged，不改变 revision，不增加积分。确认文字仅是来源证据，不携带本机执行权限。
导入预览（plan-import）还会输出 rule_changes：将新增/变化的偏好（状态/层级/积分/待确认
原因）、受影响记录的有效状态变化与 staged 条目变化，供导入前判断规则是否被改变。

预览及提交前还检查合并后整个目标档案的容量，而非仅检查输入包。保留文件按磁盘实际
字节计入，新增文件按最终 JSON 序列化字节计入；超过文件数、单文件或总量上限即拒绝。
容量边界及旧版超限档案的处理说明见 [工作流](workflow.md)。
