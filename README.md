# review-evolution · Beta 1（v0.21.5-beta.1（公开候选，2026-09-09））

> 这是一个仍在完善中的 Beta 技能：复盘、经验积累、跨设备经验合并等功能已可用并通过本机
> 回归测试，但尚未覆盖所有客户端与系统，因此适合愿意尝鲜、能接受偶尔需要调整的早期用户。
> 当前支持范围：Windows + Python 3.10+。使用中如遇到问题或有功能建议，欢迎反馈
> （请说明使用环境、操作步骤与实际现象）。你的经验数据默认只保存在本机私人目录，
> 无需上传即可获得使用支持。

## 它解决什么（设计期望与价值）

- 让 AI 在本地沉淀“可核验经验”：S1 使用者的工作/生活经验与协作偏好、S2 AI 的防错与
  互动改进方法（运行工具/推理核验/任务执行/用户互动表达）、S3 技能自身迭代；
- 在对话开始按场景回查、任务收尾默认复盘，让经验有据可查、按需影响回复；
- 经验本地私密、留痕可审计、跨设备/客户端按需合并，公共发布内容与私人数据严格分离；
- 不承诺自动同步或“一定记住”——候选不等于规则，效果需真实使用样本支持。

## 当前能力与边界（客观口径）

- 已具备：S1/S2/S3 记录与回查、S1 积分、导出/合并、备份/恢复、doctor、首次介绍、
  Python 3.10+ 受控安装引导与最低版本校验；
- 质量基线：本机 156 项回归通过；第二环境核心链路已在 2 台 Windows/QwenWork 1.0.4
  通过；当前为受控 Beta（release_ready=false）；
- 边界：仅声明 Windows + Python 3.10+；真实效果样本、Codex 桌面及其它 OS、正式
  Release 升级/失败恢复仍待真实验收；检索为词面/场景匹配，非语义搜索；
- 公开发布名称为 review-evolution；安装目录名与包内 SKILL name 保持一致即可。

核心代码与私人经验分离。S1 是使用者的工作/生活经验与协作偏好（例：先给结论再展开）；
S2 是 AI 的防错与互动改进方法（运行工具、推理核验、任务执行，以及如何更好与用户对话/
解释/组织回复）；S3 是技能自身迭代记录，默认保持私人，通用方法经审查后才进入公共方法
库。默认不联网、不自动同步、不发布私人记录。
积分仅用于 S1 的个人经验与偏好证据；S2/S3 不计分、不套用积分门槛。

## 安装（面向非技术用户）

1. 下载本仓库 Release 页的附件 zip（优先于页面自动生成的 “Source code” 压缩包，后者
   来自 tag 提交树，可能滞后于附件内容）；
2. 解压后把文件夹放入你的技能目录（Codex 为 `%USERPROFILE%\.codex\skills\`）；
   目录名须与包内 SKILL.md 的 `name` 一致——公开发布名称为 `review-evolution`，
   本地开发版目录名为 `wb-review-evolution`，以你实际使用的包内名称为准；
3. 安装验证后由 Agent 在当前对话主动介绍，并引导私人目录 `init` + `bind`；宿主未加载时可手动新开会话询问“这个技能怎么用”。

安装时不需要设置任何个人身份；之后跨设备经验合并会先预览、确认一次后并入当前档案。

## 能力入口

- 记录：S1/S2 用 `add`，偏好要求用 `add-event`，S3 用 `log-s3`（均支持 `-` stdin）；
- 回查：`recall`（精简）/ `query`（完整核对）/ `overview` / `consistency-check`（只读）；
- 迁移：`plan-export/export` 与 `plan-import/import`；profile_id 不同时可用
  `--merge-into-current` 并入当前档案；
- 更新：`release_update.py check --online`（按请求检查发布，默认包含预发布；
  `--stable-only` 只看正式发布）；`updates-check --dry-run`仅为离线状态，不是联网检查；
- 文档：SKILL.md 为入口，操作细则见 `references/workflow.md` 与
  `references/pack-format.md`。

## 适合这样用 / 搜索关键词

如果你正在找这类能力，本技能可能合适：

- “我想让 AI 记住我习惯先给结论再展开”
- “每次任务收尾帮我复盘并积累经验”
- “让 AI 记录我的偏好、减少重复追问”
- “把我在另一台电脑/客户端积累的经验合并进来”
- “帮我的技能根据使用反馈自我迭代”

搜索标签：经验复盘、收尾复盘、自我迭代、技能进化、理解用户习惯、个性化、长期记忆、
习惯校准、减少重复追问、跨设备经验整合；English: retrospective, reflection,
lessons learned, self-iteration, understand user habits, personalization,
long-term memory, habit calibration, cross-device merge。

## 已知限制（Beta 声明）

- 仅声明支持 Windows + Python 3.10+；macOS/Linux 与其它客户端未经真实验收；
- 技能是提示与离线工具，不能保证每轮自动触发，也不会自动同步或自动升级；
- 大档案查询存在性能上限，接近容量边界时建议分档案；
- 更新与安装仍需人工确认，不自动下载或执行发布内容。

## 许可与反馈

- License: [MIT](LICENSE)（Copyright (c) 2026 davidwei-evolution）。
- 反馈：请在仓库 Issue/Discussion 提交，说明使用环境、操作步骤与实际现象；
  技能本身只读取本机私人数据，不收集、不上传你的经验。
- 测试运行：`python -B -m unittest discover -s tests`。

诊断用 doctor（按需 --deep）；整档案 plan-backup/backup 与 plan-restore/restore 见 workflow，当前恢复要求相同核心摘要。
