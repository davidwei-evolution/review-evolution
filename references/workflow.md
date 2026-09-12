# 使用流程

遵循SKILL.md的按任务回查与必要写入；S1/S2模板见record-schema.md。无新增安静结束。
S3先检查s3-status，明确选择并启用才加载模块帮助。不提供开发过程记录或自动修改核心。
完整备份：plan-backup预览、backup确认计划、check-backup校验；恢复仅到新目录，不自动切换绑定。
普通迁移仅S1/S2，plan-import与import需匹配plan-id；不同身份明确核对归属，不以revision决定覆盖。
更新仅自身仓库，使用release_update.py受控流程；不自动联网或下载。
