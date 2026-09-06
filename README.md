# wb-review-evolution · Beta 1（v0.15.0-beta.1）

> 这是一个仍在完善中的 Beta 技能：复盘、经验积累、跨设备经验合并等功能已可用并通过本机
> 回归测试，但尚未覆盖所有客户端与系统，因此适合愿意尝鲜、能接受偶尔需要调整的早期用户。
> 当前支持范围：Windows + Python 3.10+。使用中如遇到问题或有功能建议，欢迎反馈
> （请说明使用环境、操作步骤与实际现象）。你的经验数据默认只保存在本机私人目录，
> 无需上传即可获得使用支持。

核心代码与私人经验分离。S1 是个人经验/偏好，S2 是 AI 防错经验；S3 原始迭代记录保持
私人，通用方法经审查后才进入公共方法库。默认不联网、不自动同步、不发布私人记录。
积分仅用于 S1 的个人经验与偏好证据；S2/S3 不计分、不套用积分门槛。

## 安装（面向非技术用户）

1. 下载本仓库的 Release 附件或 Zip；
2. 解压后把文件夹重命名为 `wb-review-evolution`，放入你的技能目录
   （Codex 为 `%USERPROFILE%\.codex\skills\`）；
3. 新开会话询问“这个技能怎么用 / 自我介绍”，按引导执行私人目录 `init` + `bind`。

安装时不需要设置任何个人身份；之后跨设备经验合并会先预览、确认一次后并入当前档案。

## 能力入口

- 记录：S1/S2 用 `add`，偏好要求用 `add-event`，S3 用 `log-s3`（均支持 `-` stdin）；
- 回查：`query` / `overview` / `consistency-check`（只读）；
- 迁移：`plan-export/export` 与 `plan-import/import`；profile_id 不同时可用
  `--merge-into-current` 并入当前档案；
- 更新：`updates-status` / `updates-check --dry-run`（只提醒，不自动联网）；
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
